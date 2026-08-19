#!/usr/bin/env python3
"""Verify a tagDiv demo/layout import did not undo work already done here.

Importing a Newspaper demo replaces the tagDiv Cloud Templates — Single,
Category, Author, Search, Date and Tag. That is what a "layout only" import
*is*, so choosing to skip the demo posts does not protect the templates. Three
things this repository has already fixed live in exactly what gets replaced,
and all three fail silently: nobody gets an error, the site just quietly goes
back to how it was.

    1. The demo ad banner. A "now available from your pocket" panel with App
       Store and Google Play badges for an app that does not exist, linking to
       href="#". It is a [td_block_ad_box] element inside the templates, not a
       Theme Panel ad spot — which is why it took three wrong guesses to find
       the first time, and why it comes back with an import.

    2. The typeface. The demo carries its own Theme Panel typography and can
       repoint --td_default_google_font_1. The readability stylesheet names
       'Open Sans' on the reading column, so a demo that switches family
       leaves the stylesheet arguing with the theme instead of supporting it.

    3. The readability stylesheet itself, and whether its selectors still
       reach the new markup. It ships through Code Snippets rather than the
       theme, so an import cannot delete it — but new templates emit new
       .tdi_NN block classes, and the body-copy rules had to win a specificity
       fight against the old ones.

Read-only. It changes nothing, so it is safe to run before an import to
capture a baseline and again afterwards to compare.

Usage:
    python3 post_import_check.py                 # check the live site
    python3 post_import_check.py --article URL   # check a specific article
"""
from __future__ import annotations

import argparse
import re
import sys

import requests

from backfill_images import session, WP_URL

H = {"Cache-Control": "no-cache", "User-Agent": "Mozilla/5.0 (avoltium-check)"}
AD_BOX = re.compile(r"\[td_block_ad_box\b[^\]]*\]")

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"


def report(state: str, name: str, detail: str) -> str:
    """Print one result and return its state.

    Returns the state rather than a bool on purpose. The first version of this
    returned `state != FAIL`, which made WARN indistinguishable from PASS — so
    a run with no credentials skipped the ad-banner check, the most important
    one here, and still printed "All checks passed". A check that did not run
    is not a check that passed, and saying otherwise is worse than not
    checking at all.
    """
    print(f"{state:4}  {name}\n      {detail}", flush=True)
    return state


def check_ad_banner(auth) -> bool:
    """No [td_block_ad_box] in any Cloud Template."""
    r = requests.get(f"{WP_URL}/wp-json/av/v1/templates", auth=auth, timeout=120,
                     headers=H, params={"per_page": 100})
    if r.status_code != 200:
        why = ("no credentials — set WP_USERNAME and WP_APP_PASSWORD"
               if r.status_code in (401, 403)
               else f"HTTP {r.status_code}; the av/v1/templates route is not "
                    f"installed. It is installed as a side effect of "
                    f"remove_demo_adspots.py --execute, which is a write, so "
                    f"this read-only check will not do it")
        return report(WARN, "demo ad banner", f"NOT CHECKED: {why}")

    hits = {tid: AD_BOX.findall(t.get("content", ""))
            for tid, t in r.json().items()}
    hits = {k: v for k, v in hits.items() if v}
    if hits:
        where = ", ".join(f"template {k} ({len(v)}x)" for k, v in hits.items())
        return report(FAIL, "demo ad banner",
                      f"the banner is back in {where} — "
                      f"run: python3 remove_demo_adspots.py --backup && "
                      f"python3 remove_demo_adspots.py --execute")
    return report(PASS, "demo ad banner",
                  f"no [td_block_ad_box] in any of {len(r.json())} templates")


def check_stylesheet_live(page: str) -> bool:
    """The readability snippet still reaches the reader."""
    if 'id="av-readability"' not in page:
        return report(FAIL, "readability stylesheet",
                      "not in the page head — redeploy with the "
                      "'Deploy readability CSS' workflow (execute: true)")

    css = re.search(r'<style id="av-readability">(.*?)</style>', page, re.S).group(1)
    active = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    problems = []
    if "color-scheme: only light" not in active:
        problems.append("color-scheme: only light is missing")
    if "prefers-color-scheme" in active:
        problems.append("a dark-mode block is back — it painted body copy "
                        "near-white on the theme's white background")
    if active.count("@font-face") < 4:
        problems.append(f"{active.count('@font-face')} @font-face blocks, expected 4")

    if problems:
        return report(FAIL, "readability stylesheet", "; ".join(problems))
    return report(PASS, "readability stylesheet",
                  f"live, {len(css)} bytes, 4 font faces, no dark-mode block")


def check_typeface(page: str) -> bool:
    """The theme still asks for Open Sans, which is what the stylesheet serves."""
    families = set(re.findall(r"--td_default_google_font_1:\s*([^;}]+)", page))
    if not families:
        # The variable lives in the theme's compiled stylesheet, not inline.
        for href in re.findall(r'href=[\'"]([^\'"]*litespeed/css/[^\'"]+)', page):
            css = requests.get(href, timeout=60, headers=H).text
            families |= set(re.findall(r"--td_default_google_font_1:\s*([^;}]+)", css))

    if not families:
        return report(WARN, "typeface", "could not find --td_default_google_font_1")
    if not any("Open Sans" in f for f in families):
        return report(FAIL, "typeface",
                      f"the theme now asks for {families} — the stylesheet "
                      f"declares faces for 'Open Sans', so either repoint the "
                      f"Theme Panel back or update AVOLTIUM_READABILITY.css")
    return report(PASS, "typeface", f"--td_default_google_font_1 = {families.pop().strip()}")


def check_body_copy_rules(page: str) -> bool:
    """The body-copy selectors still match the markup the theme emits."""
    if "td-post-content" not in page:
        return report(WARN, "body copy selectors",
                      "no .td-post-content on this page — pass --article with "
                      "an article URL to check the reading column")
    blocks = set(re.findall(r"\btdi_(\d+)\b", page))
    return report(PASS, "body copy selectors",
                  f".td-post-content present; {len(blocks)} tdi_NN blocks. "
                  f"The rules key off .td-post-content and .tdb-block-inner, "
                  f"not the numbers, so they survive renumbering — but confirm "
                  f"body text still measures 18px in devtools.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--article", help="an article URL to check instead of the home page")
    args = ap.parse_args()

    auth = session().auth
    url = args.article or WP_URL
    print(f"Checking {url}\n")

    page = requests.get(url, timeout=60, headers=H).text

    results = [
        check_ad_banner(auth),
        check_stylesheet_live(page),
        check_typeface(page),
        check_body_copy_rules(page),
    ]

    print()
    failed = [r for r in results if r == FAIL]
    skipped = [r for r in results if r == WARN]

    if failed:
        print(f"{len(failed)} check(s) FAILED. Each one above names its fix.")
        return 1
    if skipped:
        print(f"{len(results) - len(skipped)} passed, {len(skipped)} could not run. "
              f"Not a clean bill of health — resolve the WARNs and re-run.")
        return 2
    print("All checks passed — the import did not undo anything.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
