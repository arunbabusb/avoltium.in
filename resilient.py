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

DEFAULT_GEMINI_MODELS = ["gemini-2.0-flash", "gemini-flash-latest", "gemini-2.0-flash-lite"]


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
            print(f"  {model} exhausted — falling through to next model.", flush=True)
            continue

        try:
            return res.json()["candidates"][0]["content"]["parts"][0]["text"], model
        except (KeyError, IndexError, ValueError):
            # A 200 can still carry a safety block or an empty candidate list.
            print(f"  {model}: unusable response shape — trying next model.", flush=True)

    return None, None
