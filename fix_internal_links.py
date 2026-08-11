#!/usr/bin/env python3
"""Repair internal links that point at pages this site does not have.

Every article the generators produced carries two "helpful" internal links,
injected by a regex over the finished copy. One of them was wrong from the
first run: it pointed at /water-consumption-calculator/, and the page is
published at /water-consumption-treatment-calculator/. Forty-six live posts
link to that 404 — a reader clicking "water treatment" in almost any article
on the site lands on an error page.

A second, separate fault produced five more: article URLs that lost their
hyphens somewhere upstream, so /2026/07/22/batteries-and-hydrogen.../ went out
as /2026/07/22/batteriesandhydrogen.../. fix_articles.py patched two known
spellings of this by literal string replacement and could not see the rest.

Rather than extend that table again, this resolves broken links against what
the site actually publishes: it reads every post and page slug, and matches a
dead link to a real one by comparing the two with their hyphens removed. That
is exactly the damage being repaired, so the comparison is a tight fit, and a
link with no confident match is reported rather than guessed at.

Dry run by default. Nothing is written without --execute.

Usage:
    python3 fix_internal_links.py             # report what would change
    python3 fix_internal_links.py --execute
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from urllib.parse import urlsplit

from backfill_images import session, POSTS_READ, POSTS_WRITE
from publish_image_credits import fetch_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("fix-links")

PAGES_READ = POSTS_READ.replace("/posts", "/pages")
LINK = re.compile(r'href="(?P<url>https?://(?:www\.)?avoltium\.in/[^"]*)"', re.I)


def path_of(url: str) -> str:
    """The path part of an internal URL, normalised to a single trailing slash."""
    path = urlsplit(url).path
    return "/" + path.strip("/") + "/" if path.strip("/") else "/"


def squash(path: str) -> str:
    """A path with every hyphen removed — the shape a de-hyphenated link took."""
    return path.replace("-", "")


def build_index(s) -> dict[str, str]:
    """Map every real path on the site, and its de-hyphenated form, to itself.

    Keyed both ways so a lookup can be tried verbatim first and only fall back
    to the lossy comparison when the exact path is unknown.
    """
    live: dict[str, str] = {}
    for endpoint in (POSTS_READ, PAGES_READ):
        for item in fetch_all(s, endpoint, _fields="link,status"):
            if item.get("status") not in (None, "publish"):
                continue
            live[path_of(item["link"])] = path_of(item["link"])
    return live


def resolve(path: str, live: dict[str, str]) -> str | None:
    """The real path this broken link was meant to be, or None if unclear.

    Ambiguity is treated as failure. Two real slugs that differ only by their
    hyphens would both answer to one squashed key, and picking either one on a
    coin flip is how a link ends up quietly pointing at the wrong article.
    """
    if path in live:
        return None                      # already fine, nothing to do

    squashed = squash(path)
    matches = {real for real in live if squash(real) == squashed}
    if len(matches) == 1:
        return matches.pop()
    if matches:
        return None

    # WordPress appends -2, -3 and so on when a slug is already taken, and it
    # did that here: the link was written from the intended slug while the
    # post was published under the suffixed one. Allow a trailing digit run on
    # the live side only — never on the link's side, or /project-2/ would
    # happily resolve to /project/, which is a different article.
    suffixed = {real for real in live
                if re.fullmatch(re.escape(squashed.rstrip("/")) + r"\d+/", squash(real))}
    if len(suffixed) == 1:
        return suffixed.pop()
    return None


# The calculator link is the one case a squashed comparison cannot solve: the
# published slug carries a word ("treatment") that the broken link never had,
# so no amount of hyphen removal makes the two match. It is the single most
# common broken link on the site, so it is resolved by name.
KNOWN = {
    "/water-consumption-calculator/": "/water-consumption-treatment-calculator/",
    "/waterconsumptioncalculator/": "/water-consumption-treatment-calculator/",
}


def repair_body(body: str, live: dict[str, str]) -> tuple[str, list[tuple[str, str]]]:
    """Rewrite every resolvable broken link in one post body."""
    fixes: list[tuple[str, str]] = []

    def sub(m: re.Match) -> str:
        """Replace one href, leaving it untouched if it cannot be resolved."""
        url = m.group("url")
        path = path_of(url)
        target = KNOWN.get(path) or resolve(path, live)
        if not target or target == path:
            return m.group(0)
        fixes.append((path, target))
        return m.group(0).replace(url, url.replace(path, target, 1))

    return LINK.sub(sub, body), fixes


def main() -> int:
    """Repair broken internal links across every published post."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true",
                    help="write the repairs back (default is a dry run)")
    args = ap.parse_args()

    s = session()
    live = build_index(s)
    logger.info("indexed %d live paths", len(live))

    posts = fetch_all(s, POSTS_READ, _fields="id,title,content,link", context="edit")
    changed = failed = 0
    unresolved: set[str] = set()

    for p in posts:
        body = p["content"].get("raw") or p["content"]["rendered"]
        new, fixes = repair_body(body, live)

        for path in {path_of(u) for u in LINK.findall(body)}:
            if path not in live and path not in KNOWN and not resolve(path, live):
                unresolved.add(path)

        if not fixes:
            continue
        changed += 1
        logger.info("[%s] %s", p["id"], p["title"]["rendered"][:58])
        for was, now in dict(fixes).items():
            logger.info("      %s -> %s", was, now)
        if not args.execute:
            continue
        r = s.post(f"{POSTS_WRITE}/{p['id']}", json={"content": new}, timeout=60)
        if r.status_code != 200:
            logger.error("      update failed: HTTP %s", r.status_code)
            changed -= 1
            failed += 1

    if unresolved:
        logger.warning("could not resolve %d link target(s) — fix by hand:",
                       len(unresolved))
        for path in sorted(unresolved):
            logger.warning("      %s", path)

    logger.info("done — %d post(s) %s, %d failed",
                changed, "updated" if args.execute else "would be updated", failed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
