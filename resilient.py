# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
"""Retry helpers for the third-party APIs this site depends on.

Every publish run talks to two services that fail transiently: Pollinations
(image generation) and the Gemini REST API (article text). Both had been
called exactly once per run, so a momentary 429 or 503 took down the whole
scheduled publish. Two consecutive Mon/Wed/Fri runs were lost that way:

  * Pollinations returned HTTP 500 → no image → the QC image rule blocked
    the post and it was parked as a draft nobody was told about.
  * All three Gemini models answered 429/503 within 0.6 s — the fallback
    chain burned through every model faster than any rate-limit window
    could close — and the run exited with no article at all.

The fix in both cases is the same: retry with exponential backoff, and let
the model fallback chain take long enough to outlast a short throttle.
"""
import random
import time

import requests

# Statuses worth a second attempt: throttling and transient upstream faults.
# A 4xx that is not 408/429 means the request itself is wrong — retrying it
# just burns the schedule window.
RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})

# Ordered by what actually answered. gemini-flash-latest is the one that
# produced every article in the 2026-08-11 run; gemini-2.0-flash failed
# instantly and non-retryably on all three, which is the signature of a model
# name the endpoint does not serve rather than a busy one. It stays in the
# chain as a fallback but no longer costs a wasted call in front of the model
# that works.
DEFAULT_GEMINI_MODELS = ["gemini-flash-latest", "gemini-2.0-flash", "gemini-2.0-flash-lite"]


def sleep_backoff(attempt: int, base: float = 2.0, cap: float = 30.0) -> None:
    """Sleep before retry `attempt` (0-indexed): 2s, 4s, 8s … capped, jittered.

    The jitter matters when several workflows retry at once — without it they
    re-collide on exactly the same schedule.
    """
    delay = min(cap, base * (2 ** attempt))
    time.sleep(delay + random.uniform(0, delay * 0.25))


def request_with_retry(
    method: str,
    url: str,
    *,
    attempts: int = 3,
    label: str = "request",
    retry_on: frozenset[int] = RETRYABLE_STATUS,
    **kwargs,
) -> requests.Response | None:
    """Issue a request, retrying transient failures with exponential backoff.

    Returns the last response received — including a failed one, so callers
    can inspect the status — or None when every attempt raised before any
    response came back.
    """
    last: requests.Response | None = None

    for attempt in range(attempts):
        try:
            res = requests.request(method, url, **kwargs)
        except requests.RequestException as e:
            print(f"    {label}: request error ({e}) [{attempt + 1}/{attempts}]", flush=True)
        else:
            if res.status_code not in retry_on:
                return res
            last = res
            print(
                f"    {label}: HTTP {res.status_code} [{attempt + 1}/{attempts}]",
                flush=True,
            )

        if attempt < attempts - 1:
            sleep_backoff(attempt)

    return last


def gemini_generate(
    api_key: str,
    prompt: str,
    *,
    models: list[str] | None = None,
    attempts_per_model: int = 3,
    timeout: int = 120,
) -> tuple[str | None, str | None]:
    """Generate text, trying each model in turn with retries inside each.

    Returns (text, model_used), or (None, None) when the whole chain fails.
    Retrying *within* a model before falling through is what makes the chain
    span tens of seconds instead of milliseconds — long enough for a
    short-lived quota window to reopen.
    """
    for model in models or DEFAULT_GEMINI_MODELS:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
            f":generateContent?key={api_key}"
        )
        res = request_with_retry(
            "POST",
            url,
            attempts=attempts_per_model,
            label=f"gemini/{model}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=timeout,
        )

        if res is None or res.status_code != 200:
            # The status matters and used to be dropped. A 503 is Google being
            # busy and the retries were worth it; a 404 is a model that does
            # not exist, where every call is wasted and the name needs
            # changing. Both printed the same line, so a dead model in the
            # chain was indistinguishable from a bad afternoon.
            why = "no response" if res is None else f"HTTP {res.status_code}"
            print(f"  {model} exhausted ({why}) — falling through to next model.", flush=True)
            continue

        try:
            return res.json()["candidates"][0]["content"]["parts"][0]["text"], model
        except (KeyError, IndexError, ValueError):
            # A 200 can still carry a safety block or an empty candidate list.
            print(f"  {model}: unusable response shape — trying next model.", flush=True)

    return None, None


class GatewayUnreachable(Exception):
    """The OmniRoute gateway never answered — no response, not a refusal.

    Distinct from an exhausted chain, which means the gateway answered and
    every model failed. That is worth retrying on the next article; a gateway
    that is not listening is not.
    """


def omniroute_generate(
    api_key: str,
    prompt: str,
    *,
    base_url: str,
    models: list[str] | None = None,
    attempts_per_model: int = 3,
    timeout: int = 120,
) -> tuple[str | None, str | None]:
    """Generate text through an OmniRoute (or any OpenAI-compatible) gateway.

    Same retry/model-fallback shape as gemini_generate, but speaks the
    OpenAI chat-completions wire format OmniRoute exposes at
    `{base_url}/chat/completions`, rather than Google's REST API directly.
    """
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}

    for model in models or DEFAULT_GEMINI_MODELS:
        res = request_with_retry(
            "POST",
            url,
            attempts=attempts_per_model,
            label=f"omniroute/{model}",
            headers=headers,
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            timeout=timeout,
        )

        if res is None or res.status_code != 200:
            why = "no response" if res is None else f"HTTP {res.status_code}"
            print(f"  {model} exhausted ({why}) — falling through to next model.", flush=True)
            # A gateway that never answered will not answer for the next model
            # either. Nine connection refusals per article, one for every
            # model-and-retry, is forty seconds of nothing.
            if res is None:
                raise GatewayUnreachable(url)
            continue

        try:
            return res.json()["choices"][0]["message"]["content"], model
        except (KeyError, IndexError, ValueError):
            # A 200 can still carry an empty/unexpected choices list.
            print(f"  {model}: unusable response shape — trying next model.", flush=True)

    return None, None


# Set once a run has established that the gateway is not answering at all.
# OMNIROUTE_BASE_URL was pointing at localhost:20128, which exists on a
# developer's machine and never on a GitHub runner, so every article paid nine
# connection refusals before falling back to Gemini and succeeding. The
# fallback made it invisible in the output and merely slow.
_omniroute_down = False


def generate_text(
    api_key: str,
    prompt: str,
    *,
    models: list[str] | None = None,
    attempts_per_model: int = 3,
    timeout: int = 120,
    omniroute_base_url: str | None = None,
    omniroute_api_key: str | None = None,
) -> tuple[str | None, str | None]:
    """Generate text, preferring OmniRoute when configured, else Gemini direct.

    OMNIROUTE_BASE_URL / OMNIROUTE_API_KEY are optional. Neither being set
    reproduces the old gemini_generate-only behavior exactly, so an
    unconfigured run is unaffected. When both are set, OmniRoute is tried
    first (for its cost/token-compression routing) and a failed chain falls
    back to calling Gemini directly rather than failing the whole run.

    A gateway that proves unreachable is not tried again for the rest of the
    run. Retrying is right for a busy gateway and pointless for an absent one,
    and the difference is visible after the first article.
    """
    global _omniroute_down

    if _omniroute_down:
        return gemini_generate(api_key, prompt, models=models,
                               attempts_per_model=attempts_per_model, timeout=timeout)

    if omniroute_base_url and omniroute_api_key:
        try:
            text, model = omniroute_generate(
                omniroute_api_key,
                prompt,
                base_url=omniroute_base_url,
                models=models,
                attempts_per_model=attempts_per_model,
                timeout=timeout,
            )
        except GatewayUnreachable as exc:
            _omniroute_down = True
            print(f"  OmniRoute is unreachable at {exc}; using Gemini directly for "
                  f"the rest of this run.", flush=True)
        else:
            if text:
                return text, model
            print("  OmniRoute chain exhausted — falling back to direct Gemini API.",
                  flush=True)

    return gemini_generate(
        api_key, prompt, models=models, attempts_per_model=attempts_per_model, timeout=timeout
    )
