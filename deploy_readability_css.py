#!/usr/bin/env python3
"""Push AVOLTIUM_READABILITY.css to the site as a Code Snippet.

The CSS had no deployment path in this repository. It went out by hand from a
session that happened to hold WordPress credentials, which is why a defect in
it — a table header painted near-white under white text, unreadable on every
article carrying a table — could not be corrected without repeating that by
hand. This script makes the stylesheet in git the thing that is deployed.

WordPress exposes no REST route for Additional CSS: custom_css is not a field
on /wp/v2/settings and a POST there is silently discarded with a 200. So the
stylesheet ships as a Code Snippet that echoes it into wp_head, matching the
snippet already installed on the site.

Usage:
    python3 deploy_readability_css.py             # dry run, prints the diff
    python3 deploy_readability_css.py --execute
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import pathlib
import time

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("css")

WP_URL = (os.environ.get("WP_URL") or "https://www.avoltium.in").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD")

CS = f"{WP_URL}/wp-json/code-snippets/v1/snippets"
H = {"User-Agent": "avoltium-deploy/1.0"}

# Must match the snippet already installed, or this creates a second one and
# the site loads both copies.
SNIPPET_NAME = "Avoltium Readability & Contrast"
CSS_FILE = pathlib.Path(__file__).with_name("AVOLTIUM_READABILITY.css")


def php_wrapper(css: str) -> str:
    """The snippet body: the stylesheet echoed into wp_head.

    The CSS is embedded with a heredoc rather than a quoted string so that the
    braces, quotes and backslashes in a stylesheet cannot terminate it early.
    The id is what makes the deployed copy findable in the page source.
    """
    return (
        "add_action('wp_head', function () {\n"
        "    echo <<<'AVCSS'\n"
        # The stylesheet's @font-face rules pull two woff2 files from
        # fonts.gstatic.com. Without a preconnect the browser only discovers
        # that origin after it has parsed this <style>, and then pays DNS, TCP
        # and TLS before the first byte of the font. crossorigin is required:
        # fonts are fetched in CORS mode, and a preconnect opened without it
        # is a separate connection the font request cannot reuse.
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<style id="av-readability">\n'
        f"{css}\n"
        "</style>\n"
        "AVCSS;\n"
        "}, 99);\n"
    )


def snippets(auth):
    """The installed snippets, retrying while the API returns an error object.

    Code Snippets answers with a dict rather than a list while the plugin is
    still warming up; treating that as the snippet list would install a
    duplicate of one that already exists.
    """
    for _ in range(8):
        r = requests.get(CS, auth=auth, timeout=60, headers=H,
                         params={"_ts": time.time()})
        try:
            d = r.json()
        except json.JSONDecodeError:
            d = None
        if isinstance(d, list):
            return d
        time.sleep(4)
    raise SystemExit("Code Snippets API did not return a list")


def main() -> int:
    """Install or update the readability snippet. Dry run by default."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    if not CSS_FILE.exists():
        logger.error("%s is missing", CSS_FILE.name)
        return 1
    css = CSS_FILE.read_text(encoding="utf-8")

    # A stylesheet that cannot close its own heredoc is the one failure mode
    # that would take down wp_head for every visitor, so it is checked before
    # anything is sent rather than discovered on the live site.
    if "AVCSS" in css:
        logger.error("the stylesheet contains the heredoc terminator 'AVCSS'")
        return 1
    if "</style" in css.lower():
        logger.error("the stylesheet contains a closing style tag")
        return 1

    body = php_wrapper(css)
    logger.info("%s: %d chars of CSS, %d chars of snippet",
                CSS_FILE.name, len(css), len(body))

    if not (WP_USERNAME and WP_APP_PASSWORD):
        logger.error("WP_USERNAME and WP_APP_PASSWORD must be set")
        return 1
    auth = (WP_USERNAME, WP_APP_PASSWORD)

    existing = next((x for x in snippets(auth) if x.get("name") == SNIPPET_NAME), None)
    if existing:
        logger.info("found snippet %s (%s)", existing.get("id"),
                    "active" if existing.get("active") else "inactive")
    else:
        logger.info("no snippet named %r yet; it will be created", SNIPPET_NAME)

    if not args.execute:
        logger.info("[DRY-RUN] nothing sent. Re-run with --execute to deploy.")
        return 0

    payload = {"name": SNIPPET_NAME,
               "desc": "Reading typography, contrast, and the provenance block.",
               "code": body, "scope": "front-end", "priority": 99, "active": True}
    r = (requests.put(f"{CS}/{existing['id']}", auth=auth, json=payload,
                      timeout=120, headers=H)
         if existing
         else requests.post(CS, auth=auth, json=payload, timeout=120, headers=H))
    if r.status_code not in (200, 201):
        logger.error("deploy failed: HTTP %s — %s", r.status_code, r.text[:300])
        return 1
    logger.info("snippet %s deployed", r.json().get("id"))

    # LiteSpeed served the previous stylesheet through two verification rounds
    # once already, and made a working fix look broken.
    try:
        requests.post(f"{WP_URL}/wp-json/av/v1/purge", auth=auth, timeout=90, headers=H)
        logger.info("cache purged")
    except requests.RequestException as e:
        logger.warning("cache purge failed (%s); the CSS is deployed but may "
                       "be served stale for a while", e)

    # Read the page back. A 200 from the REST API only says the snippet was
    # stored, not that it reaches a reader.
    time.sleep(3)
    try:
        page = requests.get(WP_URL, timeout=60, headers=H).text
        logger.info('av-readability present in page head: %s',
                    'yes' if 'id="av-readability"' in page else 'NO — check the snippet')
    except requests.RequestException as e:
        logger.warning("could not verify the live page (%s)", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
