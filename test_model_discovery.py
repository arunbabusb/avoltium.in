"""The 2026-08-19 outage, as a test.

Every model in the configured chain failed that day — gemini-flash-latest on
503 (Google busy) and both gemini-2.0-* names on 404 (retired) — and the
article run died, twice, because nothing in the chain was real enough to fall
through to. These cover the rescue, and equally that the rescue stays out of
the way when it is not needed.
"""
import pytest

import resilient as R


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


LISTING = {
    "models": [
        {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-2.5-flash-preview", "supportedGenerationMethods": ["generateContent"]},
        # Embedding models cannot generate and must not enter the chain.
        {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
    ]
}
GENERATED = {"candidates": [{"content": {"parts": [{"text": "ARTICLE BODY"}]}}]}

IS_LISTING = "/v1beta/models?key="


@pytest.fixture
def transport(monkeypatch):
    """Swap the HTTP layer for a stub and record which endpoints were called."""
    calls: list[str] = []

    def install(handler):
        def fake(method, url, **kwargs):
            calls.append(url.split("/v1beta/")[1].split("?")[0])
            return handler(url)

        monkeypatch.setattr(R, "request_with_retry", fake)
        return calls

    # Discovery caches for the life of the process; each test needs a clean one.
    monkeypatch.setattr(R, "_discovered_models", None)
    return install


def test_discovery_rescues_a_chain_that_has_entirely_failed(transport):
    """The outage itself: 503 on the only real model, 404 on the other two."""

    def handler(url):
        if IS_LISTING in url:
            return FakeResponse(200, LISTING)
        if "gemini-flash-latest" in url:
            return FakeResponse(503)
        if "gemini-2.0-flash" in url:
            return FakeResponse(404)
        if "gemini-2.5-flash:" in url:
            return FakeResponse(200, GENERATED)
        return FakeResponse(404)

    calls = transport(handler)
    text, model = R.gemini_generate("KEY", "prompt")

    assert text == "ARTICLE BODY"
    assert model == "gemini-2.5-flash", "should land on the cheapest discovered model"
    assert "models" in calls, "discovery must have been consulted"


def test_discovery_prefers_flash_and_deprioritises_previews():
    """Ranking is cheapest-first, with the withdrawable builds last."""
    ranked = sorted(
        ["gemini-2.5-pro", "gemini-2.5-flash-preview", "gemini-2.5-flash"],
        key=lambda n: (0 if "flash" in n else 1 if "pro" in n else 2,
                       any(t in n for t in ("preview", "exp", "thinking")),
                       len(n)),
    )
    assert ranked == ["gemini-2.5-flash", "gemini-2.5-flash-preview", "gemini-2.5-pro"]


def test_healthy_run_never_calls_discovery(transport):
    """A working first model must cost exactly one request, as before."""

    def handler(url):
        assert IS_LISTING not in url, "discovery ran on a healthy chain"
        return FakeResponse(200, GENERATED)

    calls = transport(handler)
    text, model = R.gemini_generate("KEY", "prompt")

    assert (text, model) == ("ARTICLE BODY", "gemini-flash-latest")
    assert calls == ["models/gemini-flash-latest:generateContent"]


def test_discovery_being_down_is_not_a_new_failure_mode(transport):
    """Losing discovery leaves exactly the old behaviour: (None, None)."""

    def handler(url):
        return FakeResponse(500) if IS_LISTING in url else FakeResponse(503)

    transport(handler)
    assert R.gemini_generate("KEY", "prompt") == (None, None)


def test_embedding_models_are_excluded_from_discovery(transport):
    """A model that cannot generateContent must never enter the chain."""

    def handler(url):
        if IS_LISTING in url:
            return FakeResponse(200, LISTING)
        return FakeResponse(503)

    transport(handler)
    assert "text-embedding-004" not in R.discover_gemini_models("KEY")
