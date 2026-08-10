#!/usr/bin/env python3
"""Render image credit lines into post bodies where the licence requires them.

apply_shortlist.py stores the credit on the media attachment. That satisfies
record-keeping and nothing else: this site runs the tagDiv Newspaper theme,
which never renders a featured image's caption, so the credit is invisible on
the published page. CC BY and CC BY-SA both require the attribution to be
visible to the reader, so an invisible credit is a licence breach, not a
cosmetic gap. Verified on a live post before writing this — the string
"licensed under" appeared zero times in the served HTML.

This appends one credit paragraph to the post body for every post whose
featured image carries a credit-requiring licence, marked with a stable
sentinel so re-runs update in place instead of stacking duplicates.

Usage:
    python3 publish_image_credits.py            # dry run
    python3 publish_image_credits.py --execute
"""
from __future__ import annotations

import argparse
import html
import logging
import re
import sys

from backfill_images import session, POSTS_READ, POSTS_WRITE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("credits")

# Everything between the markers is ours to rewrite; anything outside is the
# author's copy and is never touched.
START = "<!-- avoltium:image-credit -->"
END = "<!-- /avoltium:image-credit -->"
BLOCK = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)

# Licences that oblige us to name the author next to the work. CC0 and public
# domain do not, and adding a credit there is noise.
NEEDS_CREDIT = re.compile(r"\bCC\s*BY\b", re.I)


def fetch_all(s, endpoint, **params):
    """Every item from a paginated REST endpoint."""
    out, page = [], 1
    while True:
        r = s.get(endpoint, params={"per_page": 100, "page": page, **params}, timeout=60)
        if r.status_code != 200:
            break
        batch = r.json()
        if not batch:
            break
        out += batch
        if len(batch) < 100:
            break
        page += 1
    return out


def credit_html(caption_text: str, source_page: str) -> str:
    """The credit paragraph, wrapped in sentinels so a re-run replaces it."""
    text = html.escape(caption_text.strip().rstrip("."))
    if source_page:
        link = html.escape(source_page)
        text += f' — <a href="{link}" rel="nofollow noopener" target="_blank">source</a>'
    return (f'{START}<p class="image-credit"><small>{text}.</small></p>{END}')


def main() -> int:
    """Write the image credit into the body of every post that needs one.

    The caption stored on the attachment is not enough: the theme never
    renders it, so a CC BY image was live with its credit visible nowhere.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    s = session()
    posts = fetch_all(s, POSTS_READ, _fields="id,title,content,featured_media",
                      context="edit")
    with_media = [p for p in posts if p.get("featured_media")]
    media = fetch_all(s, POSTS_READ.replace("/posts", "/media"),
                      include=",".join(str(p["featured_media"]) for p in with_media),
                      _fields="id,caption,source_url")
    caps = {m["id"]: re.sub(r"<[^>]+>", "", (m.get("caption") or {}).get("rendered", "")).strip()
            for m in media}

    changed = skipped = 0
    for p in with_media:
        cap = caps.get(p["featured_media"], "")
        # content.raw, not rendered: writing filtered output back would
        # flatten Gutenberg block comments and shortcodes into plain HTML.
        # These posts happen to be classic HTML today, but one block post
        # would be destroyed silently.
        body = p["content"].get("raw") or p["content"]["rendered"]
        if not cap or not NEEDS_CREDIT.search(cap):
            # No obligation. If we previously added one, take it back out.
            if BLOCK.search(body):
                new = BLOCK.sub("", body).strip()
                logger.info("[%s] removing stale credit — %s", p["id"], p["title"]["rendered"][:48])
                if args.execute:
                    s.post(f"{POSTS_WRITE}/{p['id']}", json={"content": new}, timeout=60)
                changed += 1
            continue

        block = credit_html(html.unescape(cap), "")
        new = BLOCK.sub(block, body) if BLOCK.search(body) else body.rstrip() + "\n" + block
        if new.strip() == body.strip():
            skipped += 1
            continue

        logger.info("[%s] %s", p["id"], p["title"]["rendered"][:56])
        logger.info("      %s", cap[:88])
        if not args.execute:
            changed += 1
            continue
        r = s.post(f"{POSTS_WRITE}/{p['id']}", json={"content": new}, timeout=60)
        if r.status_code == 200:
            changed += 1
        else:
            logger.error("      update failed: HTTP %s", r.status_code)

    logger.info("done — %d post(s) %s, %d already correct",
                changed, "updated" if args.execute else "would be updated", skipped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
