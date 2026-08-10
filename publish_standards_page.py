#!/usr/bin/env python3
"""Publish editorial_standards.md as the /editorial-standards/ page.

The provenance block on every article links here. That link was added before
the page existed, so for a short window all 49 posts pointed at a 404 — the
disclosure that is supposed to build trust was itself broken. This closes it,
and keeps the published page in step with the file in the repo so the two
cannot drift.

Usage:
    python3 publish_standards_page.py            # dry run
    python3 publish_standards_page.py --execute
"""
from __future__ import annotations

import argparse
import html
import logging
import re
import sys

from backfill_images import session, POSTS_READ

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("standards-page")

SLUG = "editorial-standards"
TITLE = "Editorial standards"
PAGES = POSTS_READ.replace("/posts", "/pages")
PAGES_WRITE = PAGES.replace("/wp-json/wp/v2/pages", "/?rest_route=/wp/v2/pages")


def md_to_html(md: str) -> str:
    """Render the subset of Markdown editorial_standards.md actually uses.

    A dependency-free converter rather than a library, because the pipeline
    already runs on a bare `pip install requests` and this is the only file it
    ever has to convert.
    """
    out: list[str] = []
    rows: list[str] = []
    in_code = False
    code: list[str] = []
    bullets: list[str] = []

    def flush_bullets():
        if bullets:
            out.append("<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>")
            bullets.clear()

    def flush_rows():
        if not rows:
            return
        head, body = rows[0], [r for r in rows[1:] if not set(r.replace("|", "").strip()) <= set("-: ")]
        def cells(r, tag):
            return "".join(f"<{tag}>{inline(c.strip())}</{tag}>"
                           for c in r.strip().strip("|").split("|"))
        out.append("<table><thead><tr>" + cells(head, "th") + "</tr></thead><tbody>"
                   + "".join("<tr>" + cells(r, "td") + "</tr>" for r in body)
                   + "</tbody></table>")
        rows.clear()

    def inline(t: str) -> str:
        t = html.escape(t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
        return t

    for line in md.splitlines():
        if line.startswith("```"):
            if in_code:
                out.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
                code.clear()
            in_code = not in_code
            continue
        if in_code:
            code.append(line)
            continue
        if line.startswith("|"):
            flush_bullets()
            rows.append(line)
            continue
        flush_rows()
        if line.startswith("- "):
            bullets.append(inline(line[2:]))
            continue
        flush_bullets()
        if re.match(r"^#{1,4} ", line):
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{min(level + 1, 5)}>{inline(line[level:].strip())}</h{min(level + 1, 5)}>")
        elif line.strip() == "---":
            out.append("<hr>")
        elif line.strip():
            out.append(f"<p>{inline(line.strip())}</p>")
    flush_bullets()
    flush_rows()
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    with open("editorial_standards.md") as fh:
        md = fh.read()
    body = (
        "<p><em>These are the rules every article on this site has to satisfy "
        "before it is published. They are kept in the site's repository and "
        "this page is generated from that file, so what you read here is what "
        "the publishing pipeline actually enforces.</em></p>\n" + md_to_html(md)
    )
    logger.info("rendered %d chars of HTML from editorial_standards.md", len(body))

    s = session()
    res = s.get(PAGES, params={"slug": SLUG, "status": "publish,draft"}, timeout=60)
    if res.status_code != 200:
        logger.error("lookup failed: HTTP %s — %s", res.status_code, res.text[:200])
        return 1
    found = res.json()
    if not isinstance(found, list):
        # An error object here is truthy, so found[0]['id'] would raise — and a
        # permission problem returning [] would silently create a second page
        # on the same slug, with articles linking to whichever WordPress served.
        logger.error("lookup returned %s, expected a list", type(found).__name__)
        return 1
    payload = {"title": TITLE, "slug": SLUG, "content": body, "status": "publish"}

    if not args.execute:
        logger.info("[DRY-RUN] would %s /%s/",
                    "update" if found else "create", SLUG)
        return 0

    if found:
        r = s.post(f"{PAGES_WRITE}/{found[0]['id']}", json=payload, timeout=90)
        action = "updated"
    else:
        r = s.post(PAGES_WRITE, json=payload, timeout=90)
        action = "created"
    if r.status_code not in (200, 201):
        logger.error("%s failed: HTTP %s — %s", action, r.status_code, r.text[:200])
        return 1
    logger.info("%s page %s -> %s", action, r.json().get("id"), r.json().get("link"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
