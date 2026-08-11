#!/usr/bin/env python3
"""Add a provenance block — byline, review date, AI disclosure, further reading.

Why this is not a citations feature
-----------------------------------
There is no record of where any existing claim came from. Checked before
writing this: no post carries a source URL in meta, and not one of the 49
published articles links to anything outside the site. The articles were
generated from topic prompts, not from source documents.

So a "Sources" list added now could only be links chosen after the fact
because they look like they might support the text. That is a fabricated
citation. It is worse than no citation, because a reader who follows one and
finds it does not say what the sentence says stops believing the rest of the
site — and this is the same failure we spent a day removing from the images,
where a file named "IISc hydrogen plant" turned out to be a street with a
scooter on it.

What this adds instead is true on its face:

  * a named human and the date the article was last reviewed,
  * a plain statement that AI assisted the drafting,
  * "Further reading" — authoritative pages on the article's subject, offered
    as background rather than as evidence for any particular sentence.

Every link is checked to return 200 and is rejected if it redirects somewhere
off-topic. The US DOE "Hydrogen Shot" page 404s and two energy.gov links
silently redirect to unrelated offices; all three were dropped for that reason
rather than being pasted in on the strength of the URL looking plausible.

Per-claim citation is a generation-time problem, and generate_article.py is
where it has to be solved: an article has to be written from sources that are
recorded as it is written.

Usage:
    python3 editorial_provenance.py                    # dry run
    python3 editorial_provenance.py --execute
    python3 editorial_provenance.py --reviewer "Name"  # override byline
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import logging
import os
import re
import sys

from backfill_images import session, POSTS_READ, POSTS_WRITE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("provenance")

START = "<!-- avoltium:provenance -->"
END = "<!-- /avoltium:provenance -->"
BLOCK = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)

DEFAULT_REVIEWER = "Arun"
DEFAULT_ROLE = "Chief Engineer, Avoltium"

# Only pages that were fetched and returned 200 on their final URL, and whose
# final URL is still about the thing it was chosen for. A 200 after a redirect
# proves the server answered, not that the destination is relevant.
LIBRARY = {
    "india": [
        ("National Green Hydrogen Mission — Ministry of New and Renewable Energy",
         "https://mnre.gov.in/en/national-green-hydrogen-mission/"),
        ("Press Information Bureau — Government of India releases",
         "https://www.pib.gov.in/"),
        ("NITI Aayog", "https://www.niti.gov.in/"),
    ],
    "hydrogen": [
        ("US DOE Hydrogen Program", "https://www.hydrogen.energy.gov/"),
        ("Hydrogen Council", "https://hydrogencouncil.com/en/"),
        ("Clean Hydrogen Partnership (European Union)",
         "https://www.clean-hydrogen.europa.eu/index_en"),
    ],
    "rail": [
        ("Alstom Coradia iLint — the first hydrogen passenger train",
         "https://www.alstom.com/solutions/rolling-stock/"
         "alstom-coradia-ilint-worlds-1st-hydrogen-powered-train"),
    ],
}

INDIA = re.compile(r"\b(india|indian|modi|centre|haryana|gujarat|paradip|iit|"
                   r"parliament|crore|jind|sonipat)\b", re.I)
RAIL = re.compile(r"\b(train|rail|railway|locomotive|traction)\b", re.I)


# Verified per-post sources, keyed by slug. See citations.json for what
# "verified" means and what was checked; the short version is that someone
# opened each URL and confirmed it carries the claim the post is built on.
CITATIONS_FILE = os.environ.get("CITATIONS_FILE", "citations.json")


def load_citations(path: str = "") -> dict:
    """The verified citation map, or an empty one if the file is absent.

    Missing or malformed, this degrades to "no post has citations" rather
    than failing the run: the provenance block is still an improvement on no
    block, and a broken JSON file should not take the byline off 51 posts.
    """
    try:
        with open(path or CITATIONS_FILE) as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        logger.warning("no usable citations file (%s) — "
                       "posts will show background links only", exc)
        return {}
    return {k: v for k, v in data.items() if not k.startswith("_")}


def sources_html(slug: str, citations: dict) -> str:
    """The Sources section for one post, or "" if it has no verified sources.

    Publisher and date are rendered alongside the title because that is what
    makes a citation checkable at a glance: a reader can see whether the
    thing being cited is the announcement itself or somebody's write-up of
    it, and how old it is.
    """
    entry = citations.get(slug)
    if not entry or not entry.get("sources"):
        return ""
    items = "".join(
        f'<li><a href="{html.escape(s["url"])}" rel="nofollow noopener" '
        f'target="_blank">{html.escape(s["title"])}</a> — '
        f'{html.escape(s["publisher"])}, {html.escape(s["date"])}</li>'
        for s in entry["sources"])
    # Where the reporting is materially older than the post, say so here
    # rather than leaving a reader to work it out from the datelines.
    note = (f'<p class="av-src-note">{html.escape(entry["note"])}</p>'
            if entry.get("note") else "")
    return (f'<h3>Sources</h3>'
            f'<p class="av-src-note">The reporting this article is built on. '
            f'Figures above are drawn from these.</p>'
            f'<ul class="av-sources">{items}</ul>{note}')


def further_reading(title: str) -> list[tuple[str, str]]:
    """Background links for this article's subject, most specific first."""
    out: list[tuple[str, str]] = []
    if RAIL.search(title):
        out += LIBRARY["rail"]
    if INDIA.search(title):
        out += LIBRARY["india"]
    out += LIBRARY["hydrogen"]
    seen, uniq = set(), []
    for label, url in out:
        if url not in seen:
            seen.add(url)
            uniq.append((label, url))
    return uniq[:4]


def build_block(title: str, reviewer: str, role: str, reviewed: str,
                slug: str = "", citations: dict | None = None) -> str:
    """Build the provenance aside, wrapped in the sentinel comments.

    The sentinels are what make this idempotent: a later run substitutes the
    block in place instead of appending a second copy.
    """
    links = "".join(
        f'<li><a href="{html.escape(u)}" rel="nofollow noopener" '
        f'target="_blank">{html.escape(l)}</a></li>'
        for l, u in further_reading(title))
    sources = sources_html(slug, citations or {})
    # The old note said the same thing on every post: that these links are
    # background and cite nothing in particular. On a post that now carries
    # real sources that reads as a disclaimer against its own citations, so
    # the wording splits on whether there is anything above it.
    fr_note = ("Further background, beyond the sources above." if sources else
               "Background on this subject. These are not citations for "
               "individual statements above.")
    return (
        f'{START}'
        f'<aside class="av-provenance">'
        f'<h2>About this article</h2>'
        f'<p class="av-byline"><strong>{html.escape(reviewer)}</strong> — '
        f'{html.escape(role)}<br>'
        f'<span class="av-reviewed">Last updated {html.escape(reviewed)}</span></p>'
        # Wording is deliberately limited to what actually happens. The
        # pipeline drafts with a model and gates on qc_check.py against
        # editorial_standards.md; it does not line-edit. Claiming a human
        # review that did not occur would cost more trust than it buys, which
        # is the opposite of the point of this block.
        f'<p class="av-disclosure">Drafted with AI assistance and checked against '
        f'Avoltium\'s <a href="/editorial-standards/">editorial standards</a> before '
        f'publication. Figures quoted above are the ones this article works from; '
        f'where a number carries a decision, verify it against the primary source '
        f'for your own case.</p>'
        f'{sources}'
        f'<h3>Further reading</h3>'
        f'<p class="av-fr-note">{fr_note}</p>'
        f'<ul class="av-further-reading">{links}</ul>'
        f'</aside>{END}'
    )


def fetch_all(s):
    """Every published post with the fields this script needs, paginated."""
    out, page = [], 1
    while True:
        r = s.get(POSTS_READ, params={"per_page": 100, "page": page,
                                      "_fields": "id,title,content,modified,slug"},
                  timeout=60)
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
    """Add or refresh the provenance block on every post. Dry run by default."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviewer", default=DEFAULT_REVIEWER)
    ap.add_argument("--role", default=DEFAULT_ROLE)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--citations", default="",
                    help=f"verified sources file (default {CITATIONS_FILE})")
    args = ap.parse_args()

    s = session()
    citations = load_citations(args.citations)
    posts = fetch_all(s)
    if args.limit:
        posts = posts[:args.limit]
    logger.info("%d post(s), %d with verified sources", len(posts), len(citations))

    # A slug in the citations file that matches no post means the research was
    # filed against a post that has since been renamed or retired, and the
    # sources are silently going nowhere.
    unmatched = set(citations) - {p.get("slug", "") for p in posts}
    if unmatched:
        logger.warning("citations with no matching post: %s", ", ".join(sorted(unmatched)))

    changed = cited = 0
    for p in posts:
        title = html.unescape(re.sub(r"<[^>]+>", "", p["title"]["rendered"]))
        slug = p.get("slug", "")
        if slug in citations:
            cited += 1
        # This write itself updates WordPress's `modified` timestamp, so
        # reading the pre-update value printed a date that stopped being true
        # the moment the post saved. Use the date of the edit.
        reviewed = dt.date.today().strftime("%d %B %Y")
        block = build_block(title, args.reviewer, args.role, reviewed,
                            slug=slug, citations=citations)
        body = p["content"]["rendered"]
        new = BLOCK.sub(block, body) if BLOCK.search(body) else body.rstrip() + "\n" + block
        if new.strip() == body.strip():
            continue
        logger.info("[%s] %s", p["id"], title[:60])
        changed += 1
        if args.execute:
            r = s.post(f"{POSTS_WRITE}/{p['id']}", json={"content": new}, timeout=60)
            if r.status_code != 200:
                logger.error("      update failed: HTTP %s", r.status_code)

    logger.info("done — %d post(s) %s; %d carry verified sources", changed,
                "updated" if args.execute else "would be updated (dry run)", cited)
    return 0


if __name__ == "__main__":
    sys.exit(main())
