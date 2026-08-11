#!/usr/bin/env python3
"""Repair image credits that are showing their own markup to readers.

Seven published posts carry a credit line that renders like this:

    Featured Image Credit: <a href="//commons.wikimedia.org/wiki/User:Kyy0602"
    title="User:Kyy0602">Scarlett Kang</a> / CC BY-SA 4.0 via Wikimedia Commons

Not a link — that angle-bracket text is what the reader sees. Wikimedia gives
the author as markup rather than a name, an early version of the credit writer
escaped it wholesale, and the result went live. publish_image_credits.py no
longer does this (see clean_caption there), but fixing the writer does not fix
the pages that were already written, because the damage sits in a legacy block
that predates the current sentinel and so is never rewritten in place.

This finds those blocks and repairs them. Where the post also carries a
correct credit under the modern sentinel, the legacy block is simply removed:
it is a broken duplicate of a line that is already right. Where it does not,
the attribution is recovered as plain text and reissued through the same
sentinel every other credit uses, so a later run of publish_image_credits.py
keeps ownership of it.

Dry run by default. Nothing is written without --execute.

Usage:
    python3 fix_image_credits.py             # report what would change
    python3 fix_image_credits.py --execute
"""
from __future__ import annotations

import argparse
import logging
import re
import sys

from backfill_images import session, POSTS_READ, POSTS_WRITE
from publish_image_credits import START, END, BLOCK, clean_caption, fetch_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("fix-credits")

# The legacy block, in both the spaced and the compact form that were emitted.
# Anchored on the "Featured Image Credit:" label rather than on the style
# attribute, because the styling varies and the label does not. Non-greedy to
# the first closing div: these blocks never nest.
LEGACY = re.compile(
    r"<div\b[^>]*>\s*<strong>\s*Featured Image Credit:\s*</strong>(?P<body>.*?)</div>",
    re.S | re.I)

# What a repaired credit says when the licence is named in the recovered text.
# Kept identical in shape to publish_image_credits.credit_html so the two
# cannot drift into two different-looking credit lines on one site.
def repaired_block(text: str) -> str:
    """A clean credit paragraph carrying the modern sentinel."""
    import html as _html
    return f'{START}<p class="image-credit"><small>{_html.escape(text)}.</small></p>{END}'


def repair(body: str) -> tuple[str, str] | None:
    """Rewrite one post body, or None if it has no broken credit.

    Returns the new body and a short note describing what was done, so the
    caller can log a reason rather than just a count.
    """
    m = LEGACY.search(body)
    if not m:
        return None

    recovered = clean_caption(m.group("body")).strip(" /-—.")
    has_modern = bool(BLOCK.search(body))

    if has_modern:
        # Not a duplicate of the modern credit — an older one. Several of
        # these name a completely different photograph from the one now
        # featured ("Government of India / GODL-India" sitting above an image
        # actually shot by someone else), because the featured image was
        # swapped later and only the new credit was rewritten. A credit naming
        # the wrong author is worse than no credit, and the current image is
        # already correctly attributed under the sentinel, so this goes.
        new = LEGACY.sub("", body, count=1)
        note = "removed stale credit for a since-replaced image"
    elif recovered:
        new = LEGACY.sub(lambda _: repaired_block(recovered), body, count=1)
        note = f"rewrote as text: {recovered[:60]}"
    else:
        # Nothing legible came out of it. Removing beats leaving markup on the
        # page, but say so rather than claiming a repair.
        new = LEGACY.sub("", body, count=1)
        note = "removed — no attribution text could be recovered"

    new = re.sub(r"\n{3,}", "\n\n", new).strip()
    return new, note


def main() -> int:
    """Repair every post whose credit line is showing raw markup."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true",
                    help="write the repairs back (default is a dry run)")
    args = ap.parse_args()

    s = session()
    posts = fetch_all(s, POSTS_READ, _fields="id,title,content,link", context="edit")
    logger.info("scanning %d posts", len(posts))

    changed = failed = 0
    for p in posts:
        # content.raw so Gutenberg block comments survive the round trip.
        body = p["content"].get("raw") or p["content"]["rendered"]
        out = repair(body)
        if not out:
            continue
        new, note = out
        changed += 1
        logger.info("[%s] %s", p["id"], p["title"]["rendered"][:60])
        logger.info("      %s", note)
        if not args.execute:
            continue
        r = s.post(f"{POSTS_WRITE}/{p['id']}", json={"content": new}, timeout=60)
        if r.status_code != 200:
            logger.error("      update failed: HTTP %s", r.status_code)
            changed -= 1
            failed += 1

    logger.info("done — %d post(s) %s, %d failed",
                changed, "repaired" if args.execute else "would be repaired", failed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
