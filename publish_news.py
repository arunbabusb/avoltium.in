#!/usr/bin/env python3
"""Publish a small number of sourced news analyses per day.

The difference from generate_article.py is where the facts come from. That
script writes from a topic name, which is why none of the 49 existing posts
could cite anything. This one starts from a real item pulled by
news_sources.py and keeps the link, publisher and timestamp all the way
through to a Sources block on the published page.

Deliberately low volume. Ten AI-written articles a day is the shape Google's
scaled content abuse policy describes, and the goal here is a publication that
survives review, so the default is three.

What the model is allowed to do
-------------------------------
It writes engineering analysis *around* a story it is given — why the number
matters, what it implies for plant design, what to watch next. It is told, in
the prompt, not to invent figures the source does not contain, because a
fabricated number in something labelled news is the worst failure this site
can have. Anything it produces still passes qc_check before publishing, and
anything that trips a blocker is held as a draft.

Usage:
    python3 publish_news.py                     # dry run, shows what it picked
    python3 publish_news.py --execute
    python3 publish_news.py --count 3 --execute
    python3 publish_news.py --india 2 --global 1 --execute
"""
from __future__ import annotations

import argparse
import datetime
import html
import logging
import os
import re
import sys

import requests

import news_sources
import qc_check
import resilient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("news")

WP_URL = (os.environ.get("WP_URL") or "https://www.avoltium.in").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OMNIROUTE_BASE_URL = os.environ.get("OMNIROUTE_BASE_URL", "").strip()
OMNIROUTE_API_KEY = os.environ.get("OMNIROUTE_API_KEY", "").strip()

AUTH = (WP_USERNAME, WP_APP_PASSWORD)
POSTS = f"{WP_URL}/?rest_route=/wp/v2/posts"
POSTS_READ = f"{WP_URL}/wp-json/wp/v2/posts"

NEWS_CATEGORY = int(os.environ.get("NEWS_CATEGORY_ID", "13"))   # Industry News

PROMPT = """You are an engineer writing for Avoltium, a green-hydrogen
engineering publication. Write a short analysis of the news item below for a
technical audience of plant engineers and project developers.

SOURCE ITEM
Headline: {title}
Publisher: {publisher}
Published: {published}
Summary from the source: {summary}
Link: {link}

HARD RULES
1. Do not invent any figure, date, company name, capacity, or quotation that
   is not in the source material above. If a number would help and you do not
   have it, write around it or say plainly that the figure has not been
   disclosed. A fabricated number in a news piece is the single worst thing
   you can produce here.
2. Do not quote anyone. You have no interview.
3. Attribute the facts to the publisher in the opening paragraph, e.g.
   "according to {publisher}".
4. The value you add is engineering context, not restated headlines: what the
   development implies for electrolyser sizing, water treatment duty, power
   conditioning, offtake, or cost per kilogram. Only draw on well-established
   engineering fundamentals for that context.
5. If the item is too thin to support genuine analysis, reply with exactly
   NOT_ENOUGH and nothing else.

FORMAT
- 450 to 700 words of clean HTML: <p>, <h2>, <ul>, <strong> only.
- Start with a <div style="background-color: #f8f9fa; border-left: 4px solid
  #0056b3; padding: 15px; margin-bottom: 20px;"><strong>In brief:</strong>
  one or two sentences</div>
- Then the analysis under two or three <h2> headings.
- No <style>, no scripts, no markdown fences, no LaTeX.
- Do not write a headline; that is supplied separately.
"""


# Featured images for news. qc_check treats a missing image as a BLOCKER, so
# every item needs one — but a news headline is exactly the input that made
# automatic image search produce a monitor lizard for "Water Quality
# Monitoring". So there is no search here. Each entry is a photograph that was
# pulled up and looked at during the image audit, paired with the subject it
# actually depicts. Reusing one across several stories in a section is normal
# editorial practice; publishing a wrong picture is not.
NEWS_IMAGES = [
    (re.compile(r"\b(train|rail|locomotive|metro|tram)\b", re.I),
     "hydrogen train", "Coradia iLint 554 009"),
    (re.compile(r"\b(solar|photovolta|pv)\b", re.I),
     "solar power", "Solnova Solar Power Station"),
    (re.compile(r"\b(wind|offshore)\b", re.I),
     "offshore wind", "Middelgrunden offshore wind farm 03"),
    (re.compile(r"\b(batter|storage|bess)\b", re.I),
     "lithium ion battery pack", "Lithium-Ion Battery for BMW i3"),
    (re.compile(r"\b(port|export|shipping|terminal|jetty)\b", re.I),
     "container port", "Container-Terminal Bremerhaven 01"),
    (re.compile(r"\b(desalinat|water|ultrapure|osmosis)\b", re.I),
     "reverse osmosis plant", "Malta - Pembroke"),
    (re.compile(r"\b(refiner|oil|gas|methanol|ammonia)\b", re.I),
     "oil refinery", "Anacortes Refinery"),
    (re.compile(r"\b(grid|transmission|substation|power)\b", re.I),
     "solar power plant india", "Bhadla Solar Power Plant - 53699816551"),
]
DEFAULT_IMAGE = ("electrolyser", "Science Museum")


def pick_image(item) -> tuple | None:
    """A verified photograph matching the story's subject, or None."""
    import image_sourcing
    text = f"{item.title} {item.summary}"
    query, frag = DEFAULT_IMAGE
    for pat, q, f in NEWS_IMAGES:
        if pat.search(text):
            query, frag = q, f
            break
    try:
        pool = (image_sourcing.search_wikimedia(query)
                + image_sourcing.search_openverse(query))
    except Exception as exc:
        logger.warning("    image search failed (%s)", exc)
        return None
    hit = next((c for c in pool if frag.lower() in c.title.lower()), None)
    if hit is None:
        logger.warning("    no image matched %r ~ %r", query, frag)
        return None
    return hit


def attach_image(item) -> dict | None:
    """Upload the chosen photograph; return the attachment as WordPress has it."""
    hit = pick_image(item)
    if hit is None:
        return None
    from backfill_images import compress, session as _session, slugify, upload
    s = _session()
    try:
        data = requests.get(hit.url, timeout=90,
                            headers={"User-Agent": news_sources.USER_AGENT}).content
    except Exception as exc:
        logger.warning("    image fetch failed (%s)", exc)
        return None
    is_png = hit.url.lower().endswith(".png")
    mime = "image/png" if is_png else "image/jpeg"
    fname = f"{slugify(item.title)}.{'png' if is_png else 'jpg'}"
    alt = re.sub(r"\.(jpe?g|png|webp)$", "", hit.title, flags=re.I).strip() or item.title
    caption = (f"Image: {alt} by {hit.creator or 'Unknown'}, licensed under {hit.licence}."
               if hit.needs_credit else "")
    data, mime, fname = compress(data, fname)
    mid = upload(s, data, fname, mime, alt, caption)
    if not mid:
        return None
    logger.info("    image: %s [%s]", hit.title[:48], hit.licence)
    # qc_check reads alt_text and media_details off the real object, so hand it
    # the attachment as WordPress stored it rather than a hand-built stub.
    try:
        m = requests.get(f"{WP_URL}/wp-json/wp/v2/media/{mid}", auth=AUTH, timeout=45)
        return m.json() if m.status_code == 200 else {"id": mid, "alt_text": alt}
    except Exception:
        return {"id": mid, "alt_text": alt}


def existing_titles(limit: int = 200) -> set[str]:
    out, page = set(), 1
    while len(out) < limit:
        r = requests.get(POSTS_READ, params={"per_page": 100, "page": page,
                                             "_fields": "title", "status": "publish,draft"},
                         auth=AUTH, timeout=60)
        if r.status_code != 200:
            break
        batch = r.json()
        if not batch:
            break
        out |= {re.sub(r"[^a-z0-9]+", "", re.sub("<[^>]+>", "", p["title"]["rendered"]).lower())[:60]
                for p in batch}
        if len(batch) < 100:
            break
        page += 1
    return out


def sources_block(item: news_sources.NewsItem) -> str:
    """The whole point: the story this was written from, named and linked."""
    return (
        '<h2>Source</h2>'
        '<p class="av-sources">This analysis was written from reporting by '
        f'<strong>{html.escape(item.publisher)}</strong>: '
        f'<a href="{html.escape(item.link)}" rel="nofollow noopener" target="_blank">'
        f'{html.escape(item.title)}</a>, published '
        f'{item.published.strftime("%d %B %Y")}. '
        'Figures and events above are as reported there; the engineering '
        'commentary is ours.</p>'
    )


def write_article(item: news_sources.NewsItem) -> str | None:
    body, model = resilient.generate_text(
        GEMINI_API_KEY,
        PROMPT.format(title=item.title, publisher=item.publisher,
                      published=item.published.strftime("%d %B %Y"),
                      summary=item.summary or "(no summary supplied by the feed)",
                      link=item.link),
        timeout=90,
        omniroute_base_url=OMNIROUTE_BASE_URL or None,
        omniroute_api_key=OMNIROUTE_API_KEY or None,
    )
    if not body:
        logger.error("    generation failed")
        return None
    if "NOT_ENOUGH" in body[:200]:
        logger.info("    model judged the item too thin — skipping")
        return None
    body = body.replace("```html", "").replace("```", "")
    body = re.sub(r"<style\b.*?</style>", "", body, flags=re.S | re.I)
    logger.info("    drafted with %s (%d chars)", model, len(body))
    return body.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3, help="total articles (default 3)")
    ap.add_argument("--india", type=int)
    ap.add_argument("--global", dest="glob", type=int)
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    if args.execute and not all([WP_USERNAME, WP_APP_PASSWORD, GEMINI_API_KEY]):
        logger.error("WP_USERNAME, WP_APP_PASSWORD and GEMINI_API_KEY are required")
        return 1

    n_india = args.india if args.india is not None else (args.count + 1) // 2
    n_glob = args.glob if args.glob is not None else args.count // 2

    india, world, feeds_ok = news_sources.collect()
    logger.info("%d feeds answered — %d India, %d global candidates",
                feeds_ok, len(india), len(world))
    if feeds_ok == 0:
        logger.error("no feed answered; not publishing")
        return 1

    seen = existing_titles()
    def fresh(items):
        return [i for i in items
                if re.sub(r"[^a-z0-9]+", "", i.title.lower())[:60] not in seen]

    picked = fresh(india)[:n_india] + fresh(world)[:n_glob]
    logger.info("selected %d item(s) (%d India / %d global)", len(picked), n_india, n_glob)

    published = held = 0
    for item in picked:
        logger.info("[%s] %s", item.region, item.title[:66])
        logger.info("    %s — %s", item.publisher, item.link[:70])
        if not args.execute:
            continue

        body = write_article(item)
        if not body:
            continue
        body += "\n" + sources_block(item)

        try:
            import editorial_provenance
            body += "\n" + editorial_provenance.build_block(
                item.title, editorial_provenance.DEFAULT_REVIEWER,
                editorial_provenance.DEFAULT_ROLE,
                datetime.date.today().strftime("%d %B %Y"))
        except Exception as exc:
            logger.warning("    provenance block skipped (%s)", exc)

        media = attach_image(item)
        media_id = (media or {}).get("id")

        # Same gate as the technical pipeline: a blocker means draft, not live.
        status = "publish"
        try:
            # check_post returns [(severity, message)]; blockers() reduces it.
            issues = qc_check.check_post(item.title, body, media)
            hard = qc_check.blockers(issues)
            for sev, msg in issues:
                logger.info("    QC %s: %s", sev, msg[:90])
            if hard:
                status = "draft"
                held += 1
                logger.warning("    %d blocker(s) — holding as draft", len(hard))
        except Exception as exc:
            logger.warning("    QC could not run (%s) — holding as draft", exc)
            status = "draft"
            held += 1

        r = requests.post(POSTS, auth=AUTH, timeout=90, json={
            "title": item.title,
            "content": body,
            "status": status,
            "categories": [NEWS_CATEGORY],
            "excerpt": (item.summary or item.title)[:180],
            **({"featured_media": media_id} if media_id else {}),
        })
        if r.status_code in (200, 201):
            logger.info("    %s -> %s", status, r.json().get("link"))
            if status == "publish":
                published += 1
        else:
            logger.error("    publish failed: HTTP %s — %s", r.status_code, r.text[:160])

    logger.info("done — %d published, %d held as draft%s",
                published, held, "" if args.execute else " (dry run)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
