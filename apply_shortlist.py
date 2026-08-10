#!/usr/bin/env python3
"""Apply approved images from a context-matched shortlist to live posts.

Pairs with build_shortlist.py, which proposes candidates but writes nothing.
This script is the second half: it uploads and reassigns only the entries a
human has approved, and refuses to guess.

Why the split. Automatic subject extraction was measured against the real
corpus three ways — whole title, tf-idf phrases from the body, and title
phrases vetoed by the body — and the best of them still chose a wrong subject
for roughly a third of posts (a cooling-tower photo for a reverse-osmosis
article, an aircraft cylinder for balance-of-plant instrumentation). On a
technical site a wrong photograph costs more than a plain one, so the
selection stays advisory and a person approves it.

Approvals come from the contact sheet: click the pictures you want, copy the
box at the bottom into approvals.json. It is a post-id to candidate-index map,

    {"1234": 0, "1240": 2}

meaning "post 1234 gets its first candidate, post 1240 its third". Any post
not listed keeps the image it already has. Alternatively set "approved" on
entries directly in shortlist.json.

Usage:
    python3 apply_shortlist.py --approvals approvals.json             # dry run
    python3 apply_shortlist.py --approvals approvals.json --execute   # apply
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys

import requests

from backfill_images import compress, session, slugify, upload, POSTS_WRITE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("apply-shortlist")

USER_AGENT = os.environ.get(
    "IMAGE_USER_AGENT",
    "avoltium-image-backfill/1.0 (https://www.avoltium.in; hello@avoltium.in)",
)


def load(path: str) -> list[dict]:
    """Read a shortlist JSON file, failing loudly if it is not a list."""
    with open(path) as fh:
        rows = json.load(fh)
    if not isinstance(rows, list):
        sys.exit(f"{path}: expected a list of entries")
    return rows


def chosen(row: dict) -> dict | None:
    """The approved candidate for a row, or None when it was not approved."""
    idx = row.get("approved")
    if idx is None or idx is False:
        return None
    cands = row.get("candidates") or []
    if not isinstance(idx, int) or not 0 <= idx < len(cands):
        logger.warning("post %s: approved=%r is out of range (%d candidates) — skipping",
                       row.get("id"), idx, len(cands))
        return None
    return cands[idx]


def main() -> int:
    """Upload and assign the approved candidate for each shortlist entry.

    Entries without an approval are left alone — an unapproved post keeps the
    image it already has, which is the correct outcome when no candidate was
    right.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--shortlist", default="shortlist.json")
    ap.add_argument("--approvals",
                    help="JSON map of post id -> candidate index, as copied "
                         "from the contact sheet")
    ap.add_argument("--execute", action="store_true",
                    help="actually upload and reassign; omit for a dry run")
    args = ap.parse_args()

    rows = load(args.shortlist)

    if args.approvals:
        with open(args.approvals) as fh:
            picks = json.load(fh)
        if not isinstance(picks, dict):
            sys.exit(f"{args.approvals}: expected an object of post-id -> index")
        known = {str(r["id"]) for r in rows}
        for pid in set(picks) - known:
            logger.warning("approval for post %s is not in %s — ignoring",
                           pid, args.shortlist)
        for r in rows:
            if str(r["id"]) in picks:
                r["approved"] = picks[str(r["id"])]

    plan = [(r, c) for r in rows if (c := chosen(r)) is not None]
    logger.info("%d of %d entries approved", len(plan), len(rows))
    if not plan:
        logger.info("Nothing approved. Set \"approved\": <candidate index> on the "
                    "entries you want applied.")
        return 0

    s = session()
    changed = failed = 0
    for row, cand in plan:
        title = row.get("title", "")
        logger.info("[%s] %s", row.get("id"), title[:66])
        logger.info("    -> %s (%s, %s)", cand["title"][:60], cand["licence"], cand["source"])

        if not args.execute:
            logger.info("    [DRY-RUN] would upload and set as featured image")
            continue

        try:
            res = requests.get(cand["url"], timeout=120,
                               headers={"User-Agent": USER_AGENT})
        except Exception as exc:
            logger.error("    fetch failed: %s", exc)
            failed += 1
            continue
        # Commons and Openverse answer 403/404 with an HTML or JSON body.
        # Unchecked, that body sails through compress() and gets attached to
        # a live post as the featured image.
        if res.status_code != 200 or len(res.content) < 10_000:
            logger.error("    fetch rejected: HTTP %s, %d bytes",
                         res.status_code, len(res.content))
            failed += 1
            continue
        data = res.content

        is_png = cand["url"].lower().endswith(".png")
        mime = "image/png" if is_png else "image/jpeg"
        filename = f"{slugify(title)}.{'png' if is_png else 'jpg'}"
        # Commons titles are filenames; strip the extension before using as alt.
        alt = re.sub(r"\.(jpe?g|png|webp)$", "", cand["title"], flags=re.I).strip() or title
        # CC BY and BY-SA require visible credit. It rides on the attachment so
        # a later rewrite of the post body cannot silently drop it.
        caption = ""
        if cand.get("credit"):
            caption = (f"Image: {alt} by {cand.get('creator') or 'Unknown'}, "
                       f"licensed under {cand['licence']}.")

        before = len(data)
        data, mime, filename = compress(data, filename)
        if len(data) != before:
            logger.info("    compressed %d KB -> %d KB", before // 1024, len(data) // 1024)

        media_id = upload(s, data, filename, mime, alt, caption)
        if not media_id:
            failed += 1
            continue

        r = s.post(f"{POSTS_WRITE}/{row['id']}", json={"featured_media": media_id}, timeout=60)
        if r.status_code == 200:
            logger.info("    set media %s on post %s", media_id, row["id"])
            changed += 1
        else:
            logger.error("    reassign failed: HTTP %s", r.status_code)
            failed += 1

    logger.info("done — %d changed, %d failed%s",
                changed, failed, "" if args.execute else " (dry run)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
