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
import logging
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


def build_block(title: str, reviewer: str, role: str, reviewed: str) -> str:
    links = "".join(
        f'<li><a href="{html.escape(u)}" rel="nofollow noopener" '
        f'target="_blank">{html.escape(l)}</a></li>'
        for l, u in further_reading(title))
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
        f'<h3>Further reading</h3>'
        f'<p class="av-fr-note">Background on this subject. These are not citations '
        f'for individual statements above.</p>'
        f'<ul class="av-further-reading">{links}</ul>'
        f'</aside>{END}'
    )


def fetch_all(s):
    out, page = [], 1
    while True:
        r = s.get(POSTS_READ, params={"per_page": 100, "page": page,
                                      "_fields": "id,title,content,modified"}, timeout=60)
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviewer", default=DEFAULT_REVIEWER)
    ap.add_argument("--role", default=DEFAULT_ROLE)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    s = session()
    posts = fetch_all(s)
    if args.limit:
        posts = posts[:args.limit]
    logger.info("%d post(s)", len(posts))

    changed = 0
    for p in posts:
        title = html.unescape(re.sub(r"<[^>]+>", "", p["title"]["rendered"]))
        # The article's own last-modified date, not today's — claiming a review
        # happened today on a post nobody opened today would be untrue.
        reviewed = dt.datetime.fromisoformat(
            p["modified"]).strftime("%d %B %Y")
        block = build_block(title, args.reviewer, args.role, reviewed)
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

    logger.info("done — %d post(s) %s", changed,
                "updated" if args.execute else "would be updated (dry run)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
