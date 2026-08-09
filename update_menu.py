#!/usr/bin/env python3
"""Put the calculators where people can find them.

The problem
-----------
The nav lists ten category archives before it reaches a calculator, and the
LCOH Calculator — the site's flagship tool — is not in the menu at all. A
visitor cannot reach it except by knowing the URL.

That matters more than it sounds. Categories are lists of articles, which
every hydrogen blog has. The calculators are the thing nobody else has, the
reason someone would bookmark the site, and the only pages likely to earn a
link. Burying them behind ten archive links inverts the site's value.

What this does
--------------
Creates a single "Calculators" parent near the front of the menu and nests all
three tools under it:

    Home · Calculators ▾ · Green Hydrogen · ... · About Us
             ├ LCOH Calculator
             ├ Electrolyzer Calculator
             └ Water Consumption & Treatment

Idempotent: existing calculator items are re-parented and re-ordered rather
than duplicated, so re-running changes nothing. Dry run by default.

Env: WP_URL, WP_USERNAME, WP_APP_PASSWORD
"""

from __future__ import annotations

import argparse
import html
import logging
import os
import re
import sys

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("menu")

WP_URL = (os.environ.get("WP_URL") or "https://www.avoltium.in").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME") or ""
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD") or ""

READ = f"{WP_URL}/wp-json/wp/v2"
# Writes go through ?rest_route= for the same reason every other script here
# does: the host WAF 403s writes to /wp-json/wp/v2/*.
WRITE = f"{WP_URL}/?rest_route=/wp/v2"

PARENT_TITLE = "Calculators"

# Slug -> menu label. Order here is the order they appear in the dropdown,
# LCOH first because it is the one people search for by name.
CALCULATORS = [
    ("lcoh-calculator", "LCOH Calculator"),
    ("electrolyzer-calculator", "Electrolyzer Calculator"),
    ("water-consumption-treatment-calculator", "Water Consumption & Treatment"),
]


def session() -> requests.Session:
    s = requests.Session()
    s.auth = (WP_USERNAME, WP_APP_PASSWORD)
    s.headers.update({"User-Agent": "avoltium-menu/1.0"})
    return s


def plain(t) -> str:
    if isinstance(t, dict):
        t = t.get("rendered", "")
    return html.unescape(re.sub(r"<[^>]+>", "", t or "")).strip()


def find_existing(items, page, slug, label):
    """Locate an existing menu entry for this page, however it was added.

    Matching on object_id alone is not enough. The dry run showed "Water
    Consumption Calculator" already in the menu as a custom-URL link, which
    carries object_id=0 and a different label from ours — so an object_id or
    exact-title check both miss it, and the run would have added a second
    entry pointing at the same page. Matching the slug in the URL catches the
    custom-link case, which is how a human adds a menu item in a hurry.
    """
    for i in items:
        if i.get("object_id") and page and i["object_id"] == page["id"]:
            return i
        if slug and slug in (i.get("url") or ""):
            return i
        if plain(i.get("title")).lower() == label.lower():
            return i
    return None


def get_json(s, url, **params):
    r = s.get(url, params=params or None, timeout=45)
    if r.status_code != 200:
        logger.error("GET %s -> HTTP %s %s", url, r.status_code, r.text[:160])
        return None
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--menu-id", type=int, default=0,
                    help="0 = auto-detect the menu with the most items")
    args = ap.parse_args()

    if not (WP_USERNAME and WP_APP_PASSWORD):
        logger.error("Missing WP credentials in env")
        return 2

    s = session()

    menus = get_json(s, f"{READ}/menus", per_page=50)
    if menus is None:
        logger.error("Could not read menus. The REST menu endpoints need an "
                     "account with edit_theme_options.")
        return 1
    if not menus:
        logger.error("No menus found")
        return 1
    for m in menus:
        logger.info("menu id=%s name=%r locations=%s", m["id"], plain(m.get("name")),
                    m.get("locations"))

    menu_id = args.menu_id
    if not menu_id:
        # Pick the menu with the most items — the primary nav, whatever it is
        # called on this theme.
        counts = {}
        for m in menus:
            items = get_json(s, f"{READ}/menu-items", menus=m["id"], per_page=100) or []
            counts[m["id"]] = len(items)
        menu_id = max(counts, key=counts.get)
        logger.info("auto-selected menu id=%s (%d items)", menu_id, counts[menu_id])

    items = get_json(s, f"{READ}/menu-items", menus=menu_id, per_page=100) or []
    by_title = {plain(i.get("title")).lower(): i for i in items}
    logger.info("menu has %d items", len(items))

    # Resolve the calculator pages to real IDs so the menu links to objects
    # rather than raw URLs — object links survive a slug change.
    pages = {}
    for slug, label in CALCULATORS:
        hit = get_json(s, f"{READ}/pages", slug=slug, _fields="id,link,title")
        if hit:
            pages[slug] = hit[0]
        else:
            logger.warning("page not found for slug %r — skipping", slug)

    parent = by_title.get(PARENT_TITLE.lower())
    plan = []
    if parent:
        logger.info("'%s' parent already exists (id=%s)", PARENT_TITLE, parent["id"])
    else:
        plan.append(("create-parent", PARENT_TITLE, None))

    for slug, label in CALCULATORS:
        page = pages.get(slug)
        if not page:
            continue
        existing = find_existing(items, page, slug, label)
        plan.append(("move" if existing else "add", label, existing))

    logger.info("planned changes: %d", len(plan))
    for kind, label, _ in plan:
        logger.info("  %-14s %s", kind, label)

    if not args.execute:
        logger.info("[DRY-RUN] nothing written. Re-run with --execute.")
        return 0

    # The parent is a plain non-linking entry: it exists to group, and a
    # top-level link that goes nowhere useful is worse than a label.
    if not parent:
        r = s.post(f"{WRITE}/menu-items", timeout=45, json={
            "title": PARENT_TITLE, "menus": menu_id, "type": "custom",
            "url": "#", "menu_order": 2, "status": "publish",
        })
        if r.status_code not in (200, 201):
            logger.error("creating parent failed: HTTP %s %s", r.status_code, r.text[:200])
            return 1
        parent = r.json()
        logger.info("created parent id=%s", parent["id"])

    order = 1
    for slug, label in CALCULATORS:
        page = pages.get(slug)
        if not page:
            continue
        existing = find_existing(items, page, slug, label)
        payload = {
            "title": label, "menus": menu_id, "parent": parent["id"],
            "type": "post_type", "object": "page", "object_id": page["id"],
            "menu_order": order, "status": "publish",
        }
        if existing:
            r = s.post(f"{WRITE}/menu-items/{existing['id']}", json=payload, timeout=45)
            verb = "moved"
        else:
            r = s.post(f"{WRITE}/menu-items", json=payload, timeout=45)
            verb = "added"
        if r.status_code in (200, 201):
            logger.info("%s %s", verb, label)
        else:
            logger.error("%s %s failed: HTTP %s %s", verb, label, r.status_code, r.text[:200])
        order += 1

    logger.info("DONE — menu %s updated", menu_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
