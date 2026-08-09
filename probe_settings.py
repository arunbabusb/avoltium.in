#!/usr/bin/env python3
"""Report which options the REST settings endpoint actually exposes.

Asked to change LiteSpeed Cache settings from here. The plugin's own REST
namespace only carries cloud-service callbacks (ping, cdn_status, notify_img
and friends) — nothing that reads or writes configuration. The remaining
possibility is that it registers options with show_in_rest, which would put
them on /wp/v2/settings. This checks rather than assumes.
"""
import os, sys, requests

WP = (os.environ.get("WP_URL") or "https://www.avoltium.in").rstrip("/")
s = requests.Session()
s.auth = (os.environ.get("WP_USERNAME",""), os.environ.get("WP_APP_PASSWORD",""))
r = s.get(f"{WP}/wp-json/wp/v2/settings", timeout=45)
print("HTTP", r.status_code)
if r.status_code != 200:
    print(r.text[:300]); sys.exit(1)
keys = sorted(r.json().keys())
print(f"{len(keys)} settings exposed:")
for k in keys:
    print("   ", k)
hits = [k for k in keys if any(t in k.lower() for t in ("lite","lscache","cache","optim","css","js_","minify"))]
print("\ncache/optimisation-related keys:", hits or "NONE")
