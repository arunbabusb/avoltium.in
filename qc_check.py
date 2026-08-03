# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "python-dotenv"]
# ///
"""
Quality control engine for avoltium.in.

Used two ways:

  1. As a GATE inside generate_article.py — an article that fails a BLOCKER
     check is published as a draft instead of going live, so a defective post
     never reaches readers or Googlebot.

  2. As a standalone SITE AUDIT — `python qc_check.py` walks every published
     post and reports violations, exit code 1 if any blocker is found.

Every rule here exists because the problem it catches actually shipped to
production at least once. See editorial_standards.md for the reasoning.
"""
from __future__ import annotations

import os
import re
import sys
import time

import requests

# ── Rule tables ──────────────────────────────────────────────────────────────

# CSS properties Gemini has historically emitted with the hyphen stripped.
# These render as garbage text or silently dead styling.
BROKEN_CSS = [
    "backgroundcolor", "borderleft", "bordertop", "borderbottom", "borderright",
    "borderradius", "marginbottom", "margintop", "marginleft", "marginright",
    "paddingtop", "paddingbottom", "paddingleft", "paddingright",
    "fontsize", "fontweight", "fontstyle", "fontfamily", "lineheight",
    "textalign", "textdecoration", "objectfit", "maxwidth", "maxheight",
    "boxshadow", "justifycontent", "alignitems", "spacebetween", "zindex",
]

# LaTeX must never reach the page — the house style is Unicode + <sub>/<sup>.
LATEX_PATTERNS = [
    r"\\Delta", r"\\eta\b", r"\\frac", r"\\text\{", r"\\mathrm",
    r"\\times", r"\\Omega", r"\$\$", r"\$[^$\n]{1,80}\$",
]

# Compound words that lose their hyphen in generated copy.
DEHYPHENATED = [
    "hydrogenpowered", "nextgeneration", "largescale", "highpressure",
    "multimilliondollar", "highcurrent", "threepillar", "stateoftheart",
    "lowtemperature", "zeroincident",
    "realtime", "closedloop", "defectrich",
]

# Words whose everyday meaning differs from the meaning in an energy headline.
# An image prompt built naively from a headline containing these produces the
# wrong picture — this is the "BriHyNergy *Ships* 15MW system" failure, where
# a verb was illustrated as an ocean vessel.
AMBIGUOUS_HEADLINE_TERMS = {
    "ships": "verb meaning 'delivers' — do NOT illustrate a marine vessel",
    "shipping": "usually logistics/delivery, not maritime",
    "bop": "Balance of Plant (hydrogen) vs Blowout Preventer (oil & gas) — disambiguate",
    "plant": "industrial facility, not vegetation",
    "train": "check it is rail transport and not machine-learning 'train'",
    "current": "electrical current vs 'present-day'",
    "cell": "electrochemical cell, not biology or phone",
    "stack": "electrolyzer stack, not a pile or software stack",
}

MIN_BODY_CHARS = 2500       # below this a post reads as thin content
MIN_IMAGE_WIDTH = 900       # featured images must survive retina/hero crops
MAX_ASPECT_RATIO = 2.4      # ultrawide banners crop badly in card layouts


def plain_text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


# ── Individual checks ────────────────────────────────────────────────────────
# Each returns a list of (severity, message). severity: "BLOCKER" | "WARN".

def check_content(html: str) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    body = plain_text(html)

    if len(body) < MIN_BODY_CHARS:
        issues.append(("BLOCKER", f"thin content: {len(body)} chars (min {MIN_BODY_CHARS})"))

    hit_css = sorted({p for p in BROKEN_CSS if re.search(rf"\b{p}\s*:", html, re.I)})
    if hit_css:
        issues.append(("BLOCKER", f"de-hyphenated CSS: {', '.join(hit_css[:6])}"))

    hit_latex = sorted({p for p in LATEX_PATTERNS if re.search(p, html)})
    if hit_latex:
        issues.append(("BLOCKER", f"LaTeX in body: {', '.join(hit_latex[:5])}"))

    if re.search(r"<style", html, re.I):
        issues.append(("BLOCKER", "raw <style> block in post body"))

    if "```" in html:
        issues.append(("BLOCKER", "markdown code fence leaked into HTML"))

    if "Engineering Insight" not in html:
        issues.append(("WARN", "missing Engineering Insight box"))

    if not re.search(r"<h2", html, re.I):
        issues.append(("WARN", "no <h2> subheadings"))

    # Ignore matches inside href/src — permalink slugs legitimately run words
    # together, and rewriting a live URL would break inbound links.
    without_urls = re.sub(r'(?:href|src)="[^"]*"', "", html, flags=re.I)
    hit_words = sorted({
        w for w in DEHYPHENATED
        if re.search(rf"(?<![\w-]){w}(?![\w-])", without_urls, re.I)
    })
    if hit_words:
        issues.append(("WARN", f"de-hyphenated words: {', '.join(hit_words[:5])}"))

    if re.search(r"/electrolyzercalculator/|/waterconsumptioncalculator/", html):
        issues.append(("BLOCKER", "internal link missing hyphens (404)"))

    return issues


def check_title(title: str) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    if len(title) < 15:
        issues.append(("BLOCKER", f"title too short: {title!r}"))
    # CamelCase collision such as "NextGeneration" / "LargeScale"
    if re.search(r"[a-z][A-Z]", re.sub(r"\b[A-Z]{2,}\b", "", title)):
        issues.append(("WARN", "title looks de-hyphenated (camel-case run-on)"))
    return issues


def check_image(media: dict | None, title: str) -> list[tuple[str, str]]:
    """Validate the featured image's presence, alt text, and dimensions."""
    issues: list[tuple[str, str]] = []
    if not media:
        issues.append(("BLOCKER", "no featured image"))
        return issues

    if not (media.get("alt_text") or "").strip():
        issues.append(("BLOCKER", "featured image has no alt text"))

    d = media.get("media_details") or {}
    w, h = d.get("width"), d.get("height")
    if w and w < MIN_IMAGE_WIDTH:
        issues.append(("WARN", f"featured image only {w}px wide (min {MIN_IMAGE_WIDTH})"))
    if w and h and h and (w / h) > MAX_ASPECT_RATIO:
        issues.append(("WARN", f"featured image ultrawide ({w}x{h}) — crops badly"))

    return issues


def check_headline_image_trap(title: str) -> list[tuple[str, str]]:
    """Flag headlines whose wording misleads naive image generation.

    This does not mean the image IS wrong — it means a human must confirm the
    picture reflects the article's meaning rather than a literal reading of
    the headline.
    """
    issues = []
    words = set(re.findall(r"[a-z]+", title.lower()))
    for term, why in AMBIGUOUS_HEADLINE_TERMS.items():
        if term in words:
            issues.append(("WARN", f"headline contains ambiguous '{term}': {why}"))
    return issues


def check_post(title: str, html: str, media: dict | None) -> list[tuple[str, str]]:
    """Run every rule against one post."""
    return (
        check_title(title)
        + check_content(html)
        + check_image(media, title)
        + check_headline_image_trap(title)
    )


def blockers(issues: list[tuple[str, str]]) -> list[str]:
    return [m for sev, m in issues if sev == "BLOCKER"]


# ── Standalone site audit ────────────────────────────────────────────────────

def audit() -> int:
    wp = os.environ.get("WP_URL", "https://www.avoltium.in").rstrip("/")
    user = os.environ.get("WP_USERNAME")
    pw = os.environ.get("WP_APP_PASSWORD")
    if not (user and pw):
        print("ERROR: WP_USERNAME and WP_APP_PASSWORD required for audit.")
        return 2
    auth = (user, pw)

    def get(url, **kw):
        """GET with retries — shared hosting intermittently times out on
        large edit-context pages, which must not fail the whole audit."""
        last = None
        for attempt in range(4):
            try:
                return requests.get(url, auth=auth, timeout=90, **kw)
            except requests.RequestException as e:
                last = e
                print(f"  (retry {attempt + 1} after {type(e).__name__})")
                time.sleep(5 * (attempt + 1))
        raise last

    # Page size kept small deliberately: edit-context bodies are large and the
    # host times out on 100-post pages.
    posts, page = [], 1
    while True:
        r = get(f"{wp}/wp-json/wp/v2/posts",
                params={"per_page": 25, "page": page, "status": "publish", "context": "edit"})
        if r.status_code != 200:
            print(f"ERROR: post fetch failed HTTP {r.status_code}")
            return 2
        batch = r.json()
        if not batch:
            break
        posts += batch
        if len(batch) < 25:
            break
        page += 1

    media_cache: dict[int, dict] = {}

    def media_for(mid):
        if not mid:
            return None
        if mid not in media_cache:
            try:
                m = get(f"{wp}/wp-json/wp/v2/media/{mid}")
                media_cache[mid] = m.json() if m.status_code == 200 else {}
            except requests.RequestException:
                # Unknown beats a false "no image" blocker.
                media_cache[mid] = {"alt_text": "?", "media_details": {}}
        return media_cache[mid]

    total_block = total_warn = 0
    seen_titles: dict[str, int] = {}

    print(f"Auditing {len(posts)} published posts against editorial standards\n")
    for p in sorted(posts, key=lambda x: x["id"]):
        title = p["title"]["raw"]
        issues = check_post(title, p["content"]["raw"], media_for(p.get("featured_media")))

        key = re.sub(r"[^a-z0-9]+", "", title.lower())
        if key in seen_titles:
            issues.append(("BLOCKER", f"duplicate title of post {seen_titles[key]}"))
        else:
            seen_titles[key] = p["id"]

        if p.get("comment_status") == "open":
            issues.append(("WARN", "comments open (spam vector)"))

        if issues:
            print(f"[{p['id']}] {title[:66]}")
            for sev, msg in issues:
                print(f"    {sev}: {msg}")
                if sev == "BLOCKER":
                    total_block += 1
                else:
                    total_warn += 1

    print(f"\n{'='*60}")
    print(f"RESULT: {total_block} blockers, {total_warn} warnings across {len(posts)} posts")
    return 1 if total_block else 0


if __name__ == "__main__":
    sys.exit(audit())
