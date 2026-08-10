#!/usr/bin/env python3
"""Publish the transparency pages Google News expects.

Publisher Center looks for a reader being able to find out who is behind a
publication, how it is funded, and how to get something corrected. The site
had about-us and contact-us but nothing on ownership, funding or corrections.

Two things are deliberately left as visible placeholders rather than filled
in: the registered legal entity and the operating location. Inventing either
would be the same class of error as an invented citation, and on a page whose
entire purpose is transparency it would be self-defeating. They are marked
NEEDS CONFIRMATION so they are obvious to whoever reviews the page — and the
script refuses to publish while they remain, unless --allow-placeholders is
passed.

Usage:
    python3 publish_policy_pages.py                       # dry run
    python3 publish_policy_pages.py --execute
    python3 publish_policy_pages.py --entity "Avoltium (sole proprietorship)" \
                                    --location "Kerala, India" --execute
"""
from __future__ import annotations

import argparse
import logging
import sys

from backfill_images import session, POSTS_READ

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("policy-pages")

PAGES = POSTS_READ.replace("/posts", "/pages")
PAGES_WRITE = PAGES.replace("/wp-json/wp/v2/pages", "/?rest_route=/wp/v2/pages")
PLACEHOLDER = "NEEDS CONFIRMATION"

CORRECTIONS = """
<p>Avoltium publishes engineering analysis and sector news. Where we get
something wrong we would rather hear about it and fix it than leave it
standing.</p>

<h2>What we correct</h2>
<ul>
<li><strong>Factual errors</strong> — a wrong figure, a misattributed project,
an incorrect date or specification.</li>
<li><strong>Misleading framing</strong> — where a statement is technically
accurate but leaves a reader with the wrong conclusion.</li>
<li><strong>Broken or wrong links</strong> — including a link offered as
further reading that does not support what it appears to.</li>
<li><strong>Images</strong> — a picture that does not depict what the article
is about, or one whose licence credit is missing or wrong.</li>
</ul>

<h2>How to raise one</h2>
<p>Write to us through the <a href="/contact-us/">contact page</a> with the
article title and the specific passage. If you can point to a primary source
that contradicts it, include that — it makes the check much faster.</p>

<h2>What happens next</h2>
<ul>
<li>We aim to acknowledge within two working days.</li>
<li>A confirmed factual error is corrected in the article, and the correction
is noted at the foot of the piece with the date.</li>
<li>Where an error changed the substance of an article, the note says what the
article previously said.</li>
<li>Silent edits are not made to fix facts. Typography, formatting and broken
links are fixed without a note.</li>
</ul>

<h2>Our use of AI</h2>
<p>Articles on this site are drafted with AI assistance and checked against our
<a href="/editorial-standards/">editorial standards</a> before publication.
That is stated on every article. It is also why this page exists: an
AI-assisted draft can be confidently wrong, and a correction route is how a
reader holds the publication to account for that.</p>
"""

OWNERSHIP = """
<h2>Who publishes this site</h2>
<p>Avoltium is an independent publication covering green hydrogen production
and the engineering around it — electrolysers, water treatment, balance of
plant, and the projects and policy that shape them.</p>
<p>It is written and operated by Arun, who works as an engineer in the sector.
The <a href="/author/admin/">author page</a> has more detail. There is no
newsroom and no reporting staff; the site does not claim otherwise.</p>

<h2>Legal entity and location</h2>
<p>Operating entity: <strong>{entity}</strong><br>
Location: <strong>{location}</strong></p>

<h2>How the site is funded</h2>
<ul>
<li><strong>Advertising.</strong> Pages carry Google AdSense. Advertisers have
no involvement in what is written and no sight of articles before they
publish.</li>
<li><strong>Tools.</strong> The site hosts free engineering calculators. Where
any paid product is offered it is identified as ours on the page itself.</li>
</ul>
<p>We do not publish sponsored articles, paid placements or advertorial dressed
as editorial. If that ever changes, such content will be labelled as sponsored
at the top of the article, not in a footnote.</p>

<h2>Editorial independence</h2>
<p>No company, vendor or trade body pays for coverage or reviews articles
before publication. Where an article discusses a company we have any
relationship with, that relationship is disclosed in the article.</p>

<h2>Sources and accuracy</h2>
<p>Our rules for images, sourcing and AI disclosure are published in full at
<a href="/editorial-standards/">editorial standards</a>, and errors can be
reported through <a href="/corrections/">corrections</a>.</p>
"""


def upsert(s, slug: str, title: str, body: str, execute: bool) -> bool:
    """Create or update one page by slug. True when the write succeeded."""
    found = s.get(PAGES, params={"slug": slug, "status": "publish,draft"}, timeout=60).json()
    payload = {"title": title, "slug": slug, "content": body.strip(), "status": "publish"}
    if not execute:
        logger.info("[DRY-RUN] would %s /%s/", "update" if found else "create", slug)
        return True
    url = f"{PAGES_WRITE}/{found[0]['id']}" if found else PAGES_WRITE
    r = s.post(url, json=payload, timeout=90)
    if r.status_code not in (200, 201):
        logger.error("/%s/ failed: HTTP %s — %s", slug, r.status_code, r.text[:160])
        return False
    logger.info("%s %s", "updated" if found else "created", r.json().get("link"))
    return True


def main() -> int:
    """Publish the transparency pages Google Publisher Center expects.

    Refuses to publish an ownership page that still contains the placeholder
    text unless told to explicitly.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--entity", default=f"{PLACEHOLDER} — registered name of the operating entity")
    ap.add_argument("--location", default=f"{PLACEHOLDER} — city and country of operation")
    ap.add_argument("--allow-placeholders", action="store_true")
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    ownership = OWNERSHIP.format(entity=args.entity, location=args.location)
    if PLACEHOLDER in ownership and args.execute and not args.allow_placeholders:
        logger.error("Ownership page still contains %r.", PLACEHOLDER)
        logger.error("Pass --entity and --location, or --allow-placeholders to publish anyway.")
        return 1

    s = session()
    ok = upsert(s, "corrections", "Corrections and complaints", CORRECTIONS, args.execute)
    ok &= upsert(s, "ownership-and-funding", "Ownership and funding", ownership, args.execute)
    logger.info("done%s", "" if args.execute else " (dry run)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
