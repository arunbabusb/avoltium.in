#!/usr/bin/env python3
"""Set the diagram from diagrams.py as the featured image on named posts.

For an article whose subject is a comparison, a cost structure or a shift in
emphasis, there is no honest photograph to find. Searching for one produces
either something merely adjacent or something actively wrong — "green hydrogen
plant" on Wikimedia Commons returns chlorophyll molecule renders, and
"industrial pump impeller" returns a portrait of a man in a shirt. A drawn
figure that states what the article states is the better answer.

backfill_images.py already prefers a diagram when one matches, but it walks
every post and would also overwrite photographs that are working. This takes
an explicit list instead.

Usage:
    python3 apply_diagrams.py 405 1115 269            # dry run
    python3 apply_diagrams.py --execute 405 1115 269
    python3 apply_diagrams.py --all                   # every matching post
"""
from __future__ import annotations

import argparse
import io
import logging
import re
import sys

import diagrams
from backfill_images import compress, session, slugify, upload, POSTS_READ, POSTS_WRITE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("diagrams")


def fetch_posts(s):
    """Every published post, as id and title only, following pagination."""
    out, page = [], 1
    while True:
        r = s.get(POSTS_READ, params={"per_page": 100, "page": page,
                                      "_fields": "id,title"}, timeout=60)
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


def main() -> int:
    """Render the matching figure for each named post and set it as featured.

    Dry run by default: prints what it would draw and for which post, so the
    pairing can be read before anything on the live site changes.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", type=int)
    ap.add_argument("--all", action="store_true",
                    help="every post whose title matches a diagram")
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    if not args.ids and not args.all:
        ap.error("give post ids, or --all")

    s = session()
    posts = fetch_posts(s)
    wanted = set(args.ids)
    plan = []
    for p in posts:
        title = re.sub(r"<[^>]+>", "", p["title"]["rendered"])
        if not args.all and p["id"] not in wanted:
            continue
        # A cross-section wins where both match: if an article is about what a
        # cell is made of, the cutaway answers that and the process strip does
        # not.
        fig = diagrams.cross_section_for(title) or diagrams.diagram_for(title)
        if fig is None:
            logger.warning("[%s] no figure matches %r — skipping", p["id"], title[:56])
            continue
        plan.append((p["id"], title, fig))

    missing = wanted - {pid for pid, _, _ in plan}
    for pid in sorted(missing):
        logger.warning("post %s not found or has no diagram", pid)

    logger.info("%d post(s) to update", len(plan))
    changed = failed = 0
    for pid, title, dg in plan:
        is_xs = isinstance(dg, diagrams.CrossSection)
        logger.info("[%s] %s", pid, title[:62])
        logger.info("      -> %s%s", dg.title, "  [cross-section]" if is_xs else "")
        if not args.execute:
            continue

        buf = io.BytesIO()
        draw = diagrams.render_cross_section if is_xs else diagrams.render
        draw(dg).save(buf, "PNG", optimize=True)
        data, mime, filename = compress(buf.getvalue(), f"{slugify(dg.title)}.png")

        # The diagram is our own work, so there is no licence credit to carry;
        # the caption is the figure's own caption.
        media_id = upload(s, data, filename, mime, dg.title, dg.caption)
        if not media_id:
            failed += 1
            continue
        r = s.post(f"{POSTS_WRITE}/{pid}", json={"featured_media": media_id}, timeout=60)
        if r.status_code == 200:
            logger.info("      set media %s", media_id)
            changed += 1
        else:
            logger.error("      reassign failed: HTTP %s", r.status_code)
            failed += 1

    logger.info("done — %d changed, %d failed%s", changed, failed,
                "" if args.execute else " (dry run)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
