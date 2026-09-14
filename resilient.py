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

# Preference order, not a guarantee: these names are tried first and any that
# the endpoint no longer serves is skipped after one 404. gemini-2.0-flash and
# gemini-2.0-flash-lite are kept here only because they cost one call each to
# rule out, and discovery (below) is what actually supplies the fallback.
#
# They were previously described as "a fallback". They were not. Both answer
# 404 — the endpoint does not serve those names — which left gemini-flash-latest
# as the only working model in a three-model chain. On 2026-08-19 that model
# returned 503 (Google busy, nothing to do with us) and the whole article run
# died behind it, twice, because there was nothing real behind it to fall to.
DEFAULT_GEMINI_MODELS = ["gemini-flash-latest", "gemini-2.0-flash", "gemini-2.0-flash-lite"]

# Resolved once per run by discover_gemini_models().
_discovered_models: list[str] | None = None


def discover_gemini_models(api_key: str, timeout: int = 30) -> list[str]:
    """Model names the endpoint actually serves, best first.

    A hardcoded model list rots: names are retired, and the failure it
    produces is a 404 on every call with no hint at what to use instead. This
    asks the API what exists rather than guessing, so a retired name costs one
    run at most instead of every run until someone reads the logs.

    Ranked cheapest-and-fastest first — flash ahead of pro — with previews and
    experimental builds last, since they are the ones most likely to be
    withdrawn. Returns [] when discovery itself fails, which leaves the
    configured chain as the only behaviour and is exactly what happened before
    this existed.
    """
    global _discovered_models
    if _discovered_models is not None:
        return _discovered_models

    res = request_with_retry(
        "GET",
        f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
        attempts=2,
        label="gemini/ListModels",
        timeout=timeout,
    )
    if res is None or res.status_code != 200:
        why = "no response" if res is None else f"HTTP {res.status_code}"
        print(f"  model discovery unavailable ({why}); using the configured chain only.",
              flush=True)
        _discovered_models = []
        return _discovered_models

    try:
        served = res.json().get("models", [])
    except ValueError:
        _discovered_models = []
        return _discovered_models

    names = [
        m["name"].split("/", 1)[-1]
        for m in served
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]

    def rank(name: str) -> tuple:
        family = 0 if "flash" in name else 1 if "pro" in name else 2
        unstable = any(t in name for t in ("preview", "exp", "thinking"))
        return (family, unstable, len(name))

    names.sort(key=rank)
    _discovered_models = names
    print(f"  discovered {len(names)} usable model(s); first: {names[:3]}", flush=True)
    return names


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
    chain = list(models or DEFAULT_GEMINI_MODELS)
    tried: set[str] = set()
    discovered_appended = False

    while True:
        if not chain:
            # The configured chain is spent. Before giving up, ask the endpoint
            # what it serves — a chain that has rotted into all-404s is exactly
            # the case worth surviving, and it is invisible from here otherwise.
            if discovered_appended:
                break
            discovered_appended = True
            chain = [m for m in discover_gemini_models(api_key, timeout=timeout)
                     if m not in tried]
            if not chain:
                break
            print("  configured models exhausted; trying discovered models.", flush=True)

        model = chain.pop(0)
        tried.add(model)
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
