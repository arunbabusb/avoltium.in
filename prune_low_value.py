#!/usr/bin/env python3
"""Retire the pages that make this site look like a content farm.

AdSense rejected the site for low value content. Two things on the live
archive account for most of that judgement, and neither is about writing
quality:

1. Thirteen separate posts covering one event. India's first hydrogen train
   ran on 17 July 2026; between the 15th and the 22nd the site published a
   preview, a launch piece, three separate "how does it work" explainers, a
   "why it is special", two PM Modi pieces, and more. Individually they are
   fine. As an archive they read as one press cycle spun out thirteen ways,
   which is the shape a reviewer is looking for.

2. Three tagDiv theme demo pages — tds-checkout, tds-my-account and
   tds-login-register — indexed and in the sitemap. They contain no content
   at all, only the theme's generated CSS, and they advertise a shop and a
   member login that this site does not have.

news_sources.py already stops the first problem happening again; its duplicate
rules were written after this pile-up and would have caught it. What nothing
did was clean up what was already published, and the published archive is what
a reviewer reads.

Why a manifest and not a similarity threshold
---------------------------------------------
Clustering these by text similarity was tried and abandoned. These posts are
not copies of one another — they were written separately about one event, so
they share a subject and not their sentences. Every threshold that grouped the
thirteen also grouped things that must not be touched: "Gasket and Sealing
Technology" with "Compressor Technologies", and the Rs 22 crore startup award
with the Rs 797 crore jetty approval — different stories that happen to share
vocabulary. Unpublishing a good article to satisfy a threshold is a worse
outcome than leaving a duplicate up, so the retire list below is explicit,
reviewed, and the only thing this script will act on.

--audit reports candidate clusters it did not act on, so the list can grow by
someone reading it rather than by a number moving.

Nothing is deleted. Posts are moved to draft, which takes them out of the
sitemap and out of the index while leaving every word recoverable — from the
WordPress admin, or with --restore and the journal this writes.

Usage:
    python3 prune_low_value.py                      # dry run: what would change
    python3 prune_low_value.py --audit              # + duplicate candidates
    python3 prune_low_value.py --execute
    python3 prune_low_value.py --restore pruned-20260811-142530.json
"""
from __future__ import annotations

import argparse
import collections
import datetime
import json
import logging
import re
import sys

from backfill_images import session, POSTS_READ, POSTS_WRITE
from publish_image_credits import fetch_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("prune")

PAGES_READ = POSTS_READ.replace("/posts", "/pages")
PAGES_WRITE = POSTS_WRITE.replace("/wp/v2/posts", "/wp/v2/pages")

# The two kept from the hydrogen-train cluster, and why each earns its place:
# one evergreen explainer of how the technology works, which is the kind of
# piece the rest of the site is built on, and one record of the event itself.
# That is what a publication covering this story would have had.
TRAIN_KEEP = (
    "hydrogen-train",                                             # 1,745w explainer
    "pm-modi-inaugurates-indias-first-hydrogen-train-on-jind-sonipat-route",
)

# The eleven that go. Each is the same launch told again: a preview of it, a
# second and third explanation of the same fuel-cell traction, a second Modi
# piece, a restatement three days later.
TRAIN_RETIRE = (
    "india-set-to-launch-its-first-hydrogen-train-under-hydrogen-for-heritage-project-2",
    "indias-hydrogen-train-working-advantages-challenges-national-green-hydrogen-mission-2",
    "indias-first-hydrogen-train-signals-a-new-era-of-green-rail-mobility",
    "indias-first-hydrogen-train-set-for-july-17-launch-route-features-inside-look-and-faqs",
    "pm-modi-to-flag-off-indias-first-hydrogen-powered-train-marking-a-new-era-in-green-rail-mobility",
    "why-indias-first-hydrogen-train-is-special",
    "how-does-indias-first-hydrogen-train-work-the-science-behind-the-green-engine",
    "how-indias-first-hydrogen-powered-train-works-explained",
    "india-launches-first-hydrogen-powered-train-built-in-the-country-to-expand-clean-energy-on-railways",
    "indias-first-hydrogen-powered-train-advancing-green-rail-mobility-3",
    "hydrogen-rail-signals-clean-energy-leap",
)

# Theme demo pages. Not thin content — no content, and they describe a shop
# and a login that do not exist.
DEMO_PAGES = ("tds-checkout", "tds-my-account", "tds-login-register")

RETIRE_REASON = {
    **{s: "duplicate coverage of the July 2026 hydrogen train launch" for s in TRAIN_RETIRE},
    **{s: "tagDiv theme demo page — no content, describes features the site lacks"
       for s in DEMO_PAGES},
}


def slug_of(url: str) -> str:
    """The final path segment of a permalink."""
    return url.rstrip("/").rsplit("/", 1)[-1]


def plan(posts: list[dict], pages: list[dict]) -> tuple[list[dict], list[str]]:
    """What to retire, and which manifest entries matched nothing.

    An entry that matches nothing is reported rather than ignored: it means a
    slug changed or a post was already dealt with, and silently doing eleven
    things when the list asks for twelve is how a cleanup half-happens.
    """
    targets, missing = [], []
    for items, kind, endpoint in ((posts, "post", POSTS_WRITE), (pages, "page", PAGES_WRITE)):
        wanted = TRAIN_RETIRE if kind == "post" else DEMO_PAGES
        by_slug = {slug_of(i["link"]): i for i in items}
        for want in wanted:
            item = by_slug.get(want)
            if not item:
                missing.append(want)
                continue
            if item.get("status") != "publish":
                continue                      # already retired; nothing to do
            targets.append({
                "id": item["id"], "kind": kind, "endpoint": endpoint,
                "slug": want, "status": item["status"],
                "title": re.sub(r"<[^>]+>", "", item["title"]["rendered"]),
                "reason": RETIRE_REASON[want],
            })
    return targets, missing


def audit(posts: list[dict]) -> None:
    """Report clusters of posts sharing a subject, for a human to judge.

    Deliberately advisory. This groups on distinctive title words within a
    three-week window, which is loose enough to surface things worth a look
    and far too loose to act on by itself.
    """
    common = {"hydrogen", "green", "india", "indias", "energy", "the", "and", "for",
              "with", "from", "how", "why", "what", "new", "its", "national"}
    published = [p for p in posts if p.get("status") == "publish"]
    groups: dict[frozenset, list[dict]] = collections.defaultdict(list)
    for p in published:
        title = re.sub(r"<[^>]+>", "", p["title"]["rendered"]).lower()
        words = {w for w in re.findall(r"[a-z]{4,}", title) if w not in common}
        for pair in ((a, b) for a in words for b in words if a < b):
            groups[frozenset(pair)].append(p)

    retiring = set(TRAIN_RETIRE)
    seen: set[tuple] = set()
    logger.info("")
    logger.info("audit — subject clusters not covered by the retire list:")
    found = False
    for key, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        live = [m for m in members if slug_of(m["link"]) not in retiring]
        if len(live) < 3:
            continue
        dates = sorted(m["date"][:10] for m in live)
        span = (datetime.date.fromisoformat(dates[-1])
                - datetime.date.fromisoformat(dates[0])).days
        if span > 21:
            continue
        ident = tuple(sorted(m["id"] for m in live))
        if ident in seen:
            continue
        seen.add(ident)
        found = True
        logger.info("  %s — %d posts over %d days",
                    " + ".join(sorted(key)), len(live), span)
        for m in sorted(live, key=lambda x: x["date"]):
            logger.info("      %s  %s", m["date"][:10],
                        re.sub(r"<[^>]+>", "", m["title"]["rendered"])[:66])
    if not found:
        logger.info("  none")


def main() -> int:
    """Retire the manifest, or restore a previous run."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true",
                    help="apply the changes (default is a dry run)")
    ap.add_argument("--audit", action="store_true",
                    help="also report duplicate candidates outside the manifest")
    ap.add_argument("--restore", metavar="JOURNAL",
                    help="put everything in a previous run's journal back to publish")
    args = ap.parse_args()

    s = session()

    if args.restore:
        with open(args.restore) as fh:
            journal = json.load(fh)
        for entry in journal["retired"]:
            logger.info("restoring [%s] %s", entry["id"], entry["title"][:60])
            if not args.execute:
                continue
            r = s.post(f"{entry['endpoint']}/{entry['id']}",
                       json={"status": entry["status"]}, timeout=60)
            if r.status_code != 200:
                logger.error("      restore failed: HTTP %s", r.status_code)
        logger.info("done — %d item(s) %s", len(journal["retired"]),
                    "restored" if args.execute else "would be restored")
        return 0

    fields = "id,title,link,status,date"
    posts = fetch_all(s, POSTS_READ, _fields=fields, context="edit", status="publish,draft")
    pages = fetch_all(s, PAGES_READ, _fields=fields, context="edit", status="publish,draft")
    logger.info("read %d posts, %d pages", len(posts), len(pages))

    targets, missing = plan(posts, pages)
    for t in targets:
        logger.info("[%s] %s %s", t["id"], t["kind"], t["title"][:58])
        logger.info("      %s", t["reason"])
    if missing:
        logger.warning("manifest entries that matched nothing live: %s", ", ".join(missing))

    published = sum(1 for p in posts if p.get("status") == "publish")
    logger.info("posts published: %d -> %d after this runs",
                published, published - sum(1 for t in targets if t["kind"] == "post"))

    if args.audit:
        audit(posts)

    if not args.execute:
        logger.info("dry run — %d item(s) would be retired; re-run with --execute",
                    len(targets))
        return 0

    done = []
    for t in targets:
        r = s.post(f"{t['endpoint']}/{t['id']}", json={"status": "draft"}, timeout=60)
        if r.status_code == 200:
            done.append(t)
        else:
            logger.error("[%s] retire failed: HTTP %s", t["id"], r.status_code)

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = f"pruned-{stamp}.json"
    with open(path, "w") as fh:
        json.dump({"when": stamp, "retired": done}, fh, indent=2)

    logger.info("done — %d item(s) retired to draft", len(done))
    logger.info("journal written to %s — restore with --restore %s --execute", path, path)
    logger.info("next: submit the retired URLs for removal in Search Console, "
                "then re-run fix_internal_links.py so nothing still links to them")
    return 0 if len(done) == len(targets) else 1


if __name__ == "__main__":
    sys.exit(main())
