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

import article_source
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
Text of the source article (your only fact base):
{summary}
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
    # Checked first: "natural hydrogen" stories also mention production and
    # would otherwise fall through to the electrolyser photo.
    (re.compile(r"\b(natural|geologic\w*|white|gold)\s+hydrogen\b|\bexploration\b|\bdrill\w*", re.I),
     "drilling rig", "Drill rig-invergordon"),
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
    (re.compile(r"\b(electroly[sz]er|pem|alkaline\s+stack|catalyst"
                r"|hydrogen\s+(production|plant|supply))\b", re.I),
     "PEM electrolyzer", "PEM electrolyzer"),
    (re.compile(r"\b(saudi|riyadh|gulf|uae|abu\s*dhabi|middle\s*east)\b", re.I),
     "Riyadh Saudi Arabia skyline", "Riyadh Skyline"),
]
DEFAULT_IMAGE = ("electrolyser", "Science Museum")


def _relevant(candidate, query: str) -> bool:
    """A search hit whose title shares a real word with the query.

    The guard that keeps a fallback pick on subject: without it, the first
    result for "water quality monitoring" was a monitor lizard.
    """
    words = {w for w in re.findall(r"[a-z]{4,}", query.lower())}
    title = candidate.title.lower()
    return any(w in title for w in words)


def _search(query: str) -> list:
    import image_sourcing
    try:
        return (image_sourcing.search_wikimedia(query)
                + image_sourcing.search_openverse(query))
    except Exception as exc:
        logger.warning("    image search failed for %r (%s)", query, exc)
        return []


# Words in a headline that say what the story is physically about, mapped to
# an image search. These make the search specific to the article, so two
# stories under the same broad subject do not draw the same photograph.
SUBJECT_TERMS = [
    (r"\bport\b|\bterminal\b|\bjetty\b", "port terminal"),
    (r"\bship\w*|\bvessel|\bbunker\w*", "cargo ship"),
    (r"\bsteel\b|\bDRI\b|\biron\b", "steel plant"),
    (r"\bammonia\b|\bfertili[sz]er", "ammonia plant"),
    (r"\brefiner(y|ies)\b", "oil refinery"),
    (r"\bpipeline", "gas pipeline"),
    (r"\btruck|\bbus(es)?\b|\bvehicle", "hydrogen truck"),
    (r"\bfuel[- ]cell", "fuel cell"),
    (r"\btrain|\brail", "hydrogen train"),
    (r"\bsolar\b", "solar farm"),
    (r"\bwind\b", "wind farm"),
    (r"\bdesalinat|\bwater\b", "water treatment plant"),
    (r"\bstorage\b|\btank", "gas storage tanks"),
    (r"\bmethanol\b", "chemical plant"),
    (r"\belectroly[sz]", "electrolysis"),
    (r"\bfactory\b|\bmanufactur", "factory production line"),
]


def used_image_names(pages: int = 3) -> set[str]:
    """Normalised names of images already in the media library.

    attach_image stores the photograph's title as alt text, so a hit whose
    title matches one of these has already been used on the site.
    """
    names = set()
    for page in range(1, pages + 1):
        try:
            r = requests.get(f"{WP_URL}/wp-json/wp/v2/media", auth=AUTH, timeout=45,
                             params={"per_page": 100, "page": page,
                                     "_fields": "alt_text,title"})
        except Exception:
            break
        if r.status_code != 200 or not r.json():
            break
        for m in r.json():
            for v in (m.get("alt_text") or "", (m.get("title") or {}).get("rendered", "")):
                if v:
                    names.add(_image_key(v))
        if len(r.json()) < 100:
            break
    names.discard("")
    return names


def _image_key(name: str) -> str:
    """A comparable key for an image name: no extension, punctuation or case."""
    name = re.sub(r"\.(jpe?g|png|webp|tiff?)$", "", html.unescape(name), flags=re.I)
    return re.sub(r"[^a-z0-9]+", "", name.lower())[:50]


def _queries(item) -> list[tuple[str, str | None]]:
    """Image searches for this story, most specific first.

    Each entry is (query, preferred_title_fragment). Article-specific subjects
    come before the broad audited ones so that photos vary from post to post.
    """
    text = f"{item.title} {item.summary}"
    out = []
    for pat, q in SUBJECT_TERMS:
        if re.search(pat, item.title, re.I):
            out.append((q, None))
    for pat, q, f in NEWS_IMAGES:
        if pat.search(text):
            out.append((q, f))
    for pat, q in SUBJECT_TERMS:
        if re.search(pat, text, re.I) and (q, None) not in out:
            out.append((q, None))
    out.append(DEFAULT_IMAGE)
    seen, uniq = set(), []
    for q, f in out:
        if q not in seen:
            seen.add(q)
            uniq.append((q, f))
    return uniq[:5]


def pick_image(item, search=_search, used=None) -> tuple | None:
    """A fitting photograph that the site has not used before.

    For each search, most specific first: the audited photo if it is unused,
    else the widest unused, on-subject, landscape hit. Only if every search
    comes back with used photos does it fall back to reusing one, because a
    repeated photo is better than a post held as a draft.
    """
    used = used if used is not None else set()
    fallback = None
    for query, frag in _queries(item):
        pool = search(query)
        fits = [c for c in pool
                if c.width >= c.height and (_relevant(c, query)
                                            or (frag and frag.lower() in c.title.lower()))]
        fresh = [c for c in fits if _image_key(c.title) not in used]
        if frag:
            exact = next((c for c in fresh if frag.lower() in c.title.lower()), None)
            if exact:
                return exact
        if fresh:
            pick = max(fresh, key=lambda c: c.width)
            logger.info("    image for %r: %s", query, pick.title[:50])
            return pick
        if fits and fallback is None:
            fallback = fits[0]
    if fallback is not None:
        logger.warning("    every fitting photo already used; reusing %s", fallback.title[:50])
    return fallback


# Filled once per run in main(); updated as each post takes a photo, so the
# three posts of one run cannot share a picture either.
USED_IMAGES: set[str] = set()


def attach_image(item) -> dict | None:
    """Upload the chosen photograph; return the attachment as WordPress has it."""
    hit = pick_image(item, used=USED_IMAGES)
    if hit is None:
        return None
    USED_IMAGES.add(_image_key(hit.title))
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


def existing_titles(limit: int = 200) -> list[str]:
    """Titles already on the site, for skipping stories we have run.

    Returns the titles themselves rather than normalised keys, because the
    caller now compares them the same way news_sources compares two feed items.
    An exact key is not enough: "Centre awards 30 KTPA green hydrogen capacity
    to four oil refineries" was published at 12:47 and "India Awards
    30,000-Tonne Green Hydrogen Supply Contracts to Decarbonise State
    Refineries" at 16:58, one award and two articles, because the strings
    differ.
    """
    out, page = [], 1
    while len(out) < limit:
        r = requests.get(POSTS_READ, params={"per_page": 100, "page": page,
                                             "_fields": "title", "status": "publish,draft"},
                         auth=AUTH, timeout=60)
        if r.status_code != 200:
            break
        batch = r.json()
        if not batch:
            break
        out += [html.unescape(re.sub("<[^>]+>", "", p["title"]["rendered"])) for p in batch]
        if len(batch) < 100:
            break
        page += 1
    return out


# Subscripts and superscripts, to the digits they stand for. WordPress keeps
# them verbatim in a slug, so "Cu₃Pt" became the URL
# .../strain-engineered-cu%e2%82%83pt-catalyst-... — unreadable, ugly when
# pasted into a chat or a citation, and awkward for anything that has to
# re-encode it. On a hydrogen site this is not an edge case: H₂, H₂O, CO₂ and
# NH₃ all carry one and all turn up in headlines.
_DIGIT_LOOKALIKES = str.maketrans({
    "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
    "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
    "–": "-", "—": "-", "’": "", "‘": "", "“": "", "”": "",
})


def url_slug(title: str) -> str:
    """An ASCII slug for a headline, with formulae kept readable.

    The title itself is left alone — "Cu₃Pt" is correct in a headline and
    should stay. Only the URL is flattened.
    """
    s = title.translate(_DIGIT_LOOKALIKES).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    # WordPress truncates around 200; keep it well short and end on a word.
    if len(s) > 90:
        s = s[:90].rsplit("-", 1)[0]
    return s


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


def make_excerpt(body: str, limit: int = 155) -> str:
    """The post excerpt, taken from the article's own "In brief" box.

    The feed summary used to go here, and for Google News items that is just
    "Headline Publisher". The In brief line is written for exactly this job.
    """
    m = re.search(r"In brief:\s*</strong>(.*?)</div>", body, re.S | re.I)
    text = m.group(1) if m else body
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit - 1].rsplit(" ", 1)[0].rstrip(",;:-")
    return cut + "\u2026"


# Tag name -> pattern matched against the headline and body. Ordered by
# specificity; the first five that match are used.
TAG_RULES = [
    # Countries first: where a story happens is the tag readers browse by most,
    # and listing them last let generic matches crowd them out of the five.
    ("India", r"\b(India|Indian|Gujarat|Odisha|Tamil Nadu|Rajasthan|NTPC|SECI|MNRE)\b"),
    ("China", r"\b(China|Chinese)\b"),
    ("Saudi Arabia", r"\b(Saudi|NEOM)\b"),
    ("PEM electrolyzer", r"\bPEM\b|proton exchange membrane"),
    ("alkaline electrolyzer", r"\balkaline\s+(electroly\w+|stack|system)"),
    ("green ammonia", r"\bammonia\b"),
    ("refineries", r"\brefiner(y|ies)\b"),
    ("fuel cells", r"\bfuel[- ]cells?\b"),
    # Phrases, not bare words: "train" alone matched process trains and
    # "on track" copy, and tagged an offtake story as rail.
    ("hydrogen rail", r"\b(hydrogen|fuel[- ]cell)[- ](train|rail|locomotive)s?\b|\bhydrail\b"),
    ("hydrogen storage", r"\b(salt cavern|liquefaction|storage tanks?|hydrogen storage)\b"),
    ("hydrogen transport", r"\b(pipeline|bunkering|refuell?ing station)s?\b"),
    ("electrolyser manufacturing", r"\b(gigafactory|electroly[sz]er manufactur\w+)\b"),
    ("water treatment", r"\b(desalination|reverse osmosis|demineral\w+)\b"),
    ("policy", r"\b(policy|mission|tender|subsid\w+|SIGHT)\b"),
    ("green hydrogen", r"\bgreen hydrogen\b"),
]
MAX_TAGS = 5


def tag_names(title: str, body: str) -> list[str]:
    """Up to MAX_TAGS tag names that fit this article."""
    text = f"{title} {re.sub('<[^>]+>', ' ', body)}"
    out = []
    for name, pat in TAG_RULES:
        if re.search(pat, text, re.I) and name not in out:
            out.append(name)
        if len(out) == MAX_TAGS:
            break
    return out


def tag_ids(title: str, body: str, session=requests) -> list[int]:
    """WordPress tag IDs for the article, creating any tag that is missing."""
    ids = []
    for name in tag_names(title, body):
        try:
            r = session.get(f"{WP_URL}/wp-json/wp/v2/tags", auth=AUTH, timeout=30,
                            params={"search": name, "per_page": 20, "_fields": "id,name"})
            hit = next((t["id"] for t in (r.json() if r.status_code == 200 else [])
                        if html.unescape(t["name"]).lower() == name.lower()), None)
            if hit is None:
                c = session.post(f"{WP_URL}/?rest_route=/wp/v2/tags", auth=AUTH,
                                 timeout=30, json={"name": name})
                if c.status_code in (200, 201):
                    hit = c.json()["id"]
                elif c.status_code == 400 and "term_exists" in c.text:
                    hit = c.json().get("data", {}).get("term_id")
            if hit:
                ids.append(int(hit))
        except Exception as exc:
            logger.warning("    tag %r skipped (%s)", name, exc)
    return ids


def prepare_source(item) -> bool:
    """Swap in the publisher URL and the publisher's article text.

    Returns False when the item must be skipped: a Google link that will not
    resolve, or an article too short to write from honestly.
    """
    if article_source.is_google_news(item.link):
        url = article_source.resolve_google_news(item.link)
        if not url:
            logger.warning("    unresolved Google News link — skipping")
            return False
        logger.info("    resolved -> %s", url[:90])
        item.link = url
    text = article_source.fetch_article_text(item.link)
    if len(text) >= article_source.MIN_ARTICLE_CHARS:
        item.summary = text
        return True
    if not article_source.is_headline_echo(item.title, item.summary, item.publisher) \
            and len(item.summary) >= news_sources.WRITABLE_SUMMARY:
        logger.info("    article text unavailable; feed summary is substantive")
        return True
    logger.warning("    too little source text (%d chars) — skipping", len(text))
    return False


def write_article(item: news_sources.NewsItem) -> str | None:
    """Draft the article body for one news item, or None if it cannot be written.

    The prompt is allowed to answer NOT_ENOUGH when the feed summary does not
    support an article; that reply is honoured rather than published.
    """
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
    """Publish the day's news articles, split between Indian and global feeds."""
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

    # De-duplication inside collect() only sees one run. The site is the other
    # half of the memory: without this, a story picked up again the next
    # morning under a reworded headline is published a second time, which is
    # how the site ended up with eleven versions of one hydrogen-train story.
    seen = news_sources.SeenStories(existing_titles())
    if args.execute:
        USED_IMAGES.update(used_image_names())
        logger.info("%d images already on the site will not be reused", len(USED_IMAGES))

    def fresh(items):
        """Items that do not retell something already on the site."""
        out = []
        for i in items:
            if seen.covers(i.title):
                logger.info("    already covered, skipping: %s", i.title[:64])
                continue
            # Recorded as we go, so the India and global slices of one run
            # cannot pick the same story either.
            seen.add(i.title)
            out.append(i)
        return out

    # Candidates beyond the quota are kept as reserves: an item whose link
    # will not resolve or whose article cannot be fetched is skipped, and the
    # next one in rank order takes its place. The quota itself — the daily
    # cadence — does not change.
    queues = [(fresh(india), n_india), (fresh(world), n_glob)]
    logger.info("target %d item(s) (%d India / %d global)", n_india + n_glob, n_india, n_glob)

    picked = []
    for queue, quota in queues:
        taken = 0
        for item in queue:
            if taken >= quota:
                break
            logger.info("[%s] %s", item.region, item.title[:66])
            logger.info("    %s — %s", item.publisher, item.link[:70])
            if prepare_source(item):
                picked.append(item)
                taken += 1
    logger.info("selected %d item(s) with publisher links and source text", len(picked))

    published = held = 0
    for item in picked:
        logger.info("[%s] writing: %s", item.region, item.title[:60])
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
            "slug": url_slug(item.title),
            "content": body,
            "status": status,
            "categories": [NEWS_CATEGORY],
            "excerpt": make_excerpt(body),
            "tags": tag_ids(item.title, body),
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
