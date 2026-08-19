"""The 2026-08-19 outage, as a test.

Every model in the configured chain failed that day — gemini-flash-latest on
503 (Google busy) and both gemini-2.0-* names on 404 (retired) — and the
article run died, twice, because nothing in the chain was real enough to fall
through to. These cover the rescue, and equally that the rescue stays out of
the way when it is not needed.
"""
import sys, types, json
import resilient as R

class Res:
    def __init__(self, code, payload=None): self.status_code=code; self._p=payload or {}
    def json(self): return self._p

LISTING = {"models":[
    {"name":"models/gemini-2.5-flash","supportedGenerationMethods":["generateContent"]},
    {"name":"models/gemini-2.5-pro","supportedGenerationMethods":["generateContent"]},
    {"name":"models/gemini-2.5-flash-preview","supportedGenerationMethods":["generateContent"]},
    {"name":"models/text-embedding-004","supportedGenerationMethods":["embedContent"]},
]}
OK = {"candidates":[{"content":{"parts":[{"text":"ARTICLE BODY"}]}}]}

def scenario(name, handler, expect_text):
    R._discovered_models = None
    calls=[]
    def fake(method, url, **kw):
        calls.append(url.split('/v1beta/')[1].split('?')[0])
        return handler(url)
    R.request_with_retry = fake
    text, model = R.gemini_generate("KEY", "prompt")
    ok = (text == expect_text)
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    print(f"       -> text={text!r} model={model!r}")
    print(f"       -> calls: {calls}")
    return ok

# 1. The actual outage: flash-latest 503, the two 2.0 names 404, discovery works.
def outage(url):
    if url.endswith("models?key=KEY"): return Res(200, LISTING)
    if "gemini-flash-latest" in url: return Res(503)
    if "gemini-2.0-flash" in url: return Res(404)
    if "gemini-2.5-flash:" in url: return Res(200, OK)
    return Res(404)

# 2. Happy path unchanged: first model answers, discovery never called.
def happy(url):
    if url.endswith("models?key=KEY"): raise AssertionError("discovery must not run")
    return Res(200, OK)

# 3. Discovery itself down -> behaves exactly as before (returns None).
def no_discovery(url):
    if url.endswith("models?key=KEY"): return Res(500)
    return Res(503)

results = [
    scenario("outage: configured chain all-fail, discovery rescues", outage, "ARTICLE BODY"),
    scenario("happy path: first model answers, no discovery call", happy, "ARTICLE BODY"),
    scenario("discovery unavailable: fails cleanly like before", no_discovery, None),
]
print("\nALL PASS" if all(results) else "\nFAILURES PRESENT")
sys.exit(0 if all(results) else 1)
