#!/usr/bin/env python3
"""Replace wrong featured images on already-published posts.

The generated images are live. The Electrodeionization article carries a
photograph of a bed, because FLUX read "mixed-bed ion exchange ... room" as a
bedroom. Fixing the pipeline stops new ones; it does nothing for the 46 posts
already published.

Order of preference per post, matching how the pipeline now works:
  1. A generated diagram, when diagrams.py defines one for the title. For a
     process article a correct schematic beats any photograph.
  2. A real licensed photograph via image_sourcing, which refuses anything it
     cannot tie back to the article and returns None rather than guessing.
  3. Nothing. The existing image stays. A post is left alone rather than given
     a second wrong picture.

Dry run by default. --execute uploads and reassigns.

Env: WP_URL, WP_USERNAME, WP_APP_PASSWORD
"""

from __future__ import annotations

import argparse
import html
import io
import logging
import os
import re
import sys

import requests

import diagrams
import image_sourcing

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill")

WP_URL = (os.environ.get("WP_URL") or "https://www.avoltium.in").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME") or ""
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD") or ""

POSTS_READ = f"{WP_URL}/wp-json/wp/v2/posts"
POSTS_WRITE = f"{WP_URL}/?rest_route=/wp/v2/posts"
MEDIA_WRITE = f"{WP_URL}/?rest_route=/wp/v2/media"


def session() -> requests.Session:
    s = requests.Session()
    s.auth = (WP_USERNAME, WP_APP_PASSWORD)
    s.headers.update({"User-Agent": "avoltium-backfill/1.0"})
    return s


def slugify(text: str, limit: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:limit].rstrip("-")) or "figure"


def fetch_posts(s: requests.Session, per_page: int = 100):
    out, page = [], 1
    while True:
        r = s.get(POSTS_READ, params={"per_page": per_page, "page": page,
                                      "_fields": "id,title,link,featured_media"},
                  timeout=45)
        if r.status_code != 200:
            break
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
    return out


def upload(s: requests.Session, data: bytes, filename: str, mime: str,
           alt: str, caption: str = "") -> int | None:
    r = s.post(MEDIA_WRITE, data=data, timeout=120, headers={
        "Content-Type": mime,
        "Content-Disposition": f'attachment; filename="{filename}"',
    })
    if r.status_code not in (200, 201):
        logger.error("  upload failed: HTTP %s — %s", r.status_code, r.text[:160])
        return None
    media_id = r.json().get("id")
    # Alt text is set in a second call: the upload endpoint takes the binary as
    # the body, so there is nowhere to put metadata in the same request.
    s.post(f"{MEDIA_WRITE}/{media_id}", json={"alt_text": alt, "caption": caption},
           timeout=45)
    return media_id


def plain_title(post) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", post["title"]["rendered"])).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="0 = all matching posts")
    ap.add_argument("--only", default="", help="substring filter on the title")
    args = ap.parse_args()

    if not (WP_USERNAME and WP_APP_PASSWORD):
        logger.error("Missing WP credentials in env")
        return 2

    s = session()
    posts = fetch_posts(s)
    logger.info("Fetched %d posts", len(posts))

    planned = []
    for p in posts:
        title = plain_title(p)
        if args.only and args.only.lower() not in title.lower():
            continue
        if diagrams.diagram_for(title) is not None:
            planned.append((p, title, "diagram", None))
            continue
        hit = image_sourcing.find_image(title)
        if hit is not None:
            planned.append((p, title, "photo", hit))
        # else: left alone deliberately.

    logger.info("%d post(s) have a better image available", len(planned))
    if args.limit:
        planned = planned[:args.limit]

    changed = failed = 0
    for post, title, kind, hit in planned:
        logger.info("[%s] %s", kind, title[:66])

        if kind == "diagram":
            dg = diagrams.diagram_for(title)
            buf = io.BytesIO()
            diagrams.render(dg).save(buf, "PNG", optimize=True)
            data, mime = buf.getvalue(), "image/png"
            filename = f"{slugify(dg.title)}.png"
            alt = dg.title
            caption = dg.caption
        else:
            try:
                data = requests.get(hit.url, timeout=90,
                                    headers={"User-Agent": image_sourcing.USER_AGENT}).content
            except Exception as exc:
                logger.error("  fetch failed: %s", exc)
                failed += 1
                continue
            mime = "image/png" if hit.url.lower().endswith(".png") else "image/jpeg"
            filename = f"{slugify(title)}.{'png' if mime.endswith('png') else 'jpg'}"
            alt = hit.title or title
            # Attribution rides with the image so the credit cannot be lost if
            # the post body is later rewritten.
            caption = re.sub(r"<[^>]+>", "", hit.attribution_html()) if hit.needs_credit else ""

        if not args.execute:
            logger.info("  [DRY-RUN] would upload %s (%d KB) and reassign", filename, len(data) // 1024)
            continue

        media_id = upload(s, data, filename, mime, alt, caption)
        if not media_id:
            failed += 1
            continue
        r = s.post(f"{POSTS_WRITE}/{post['id']}", json={"featured_media": media_id}, timeout=60)
        if r.status_code == 200:
            logger.info("  set media %s on post %s", media_id, post["id"])
            changed += 1
        else:
            logger.error("  reassign failed: HTTP %s", r.status_code)
            failed += 1

    logger.info("DONE — mode=%s changed=%d failed=%d candidates=%d",
                "EXECUTE" if args.execute else "DRY-RUN", changed, failed, len(planned))
    if not args.execute:
        logger.info("Nothing written. Re-run with --execute.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
