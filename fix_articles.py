# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "python-dotenv"]
# ///
"""
One-time repair script for existing articles with broken CSS.
Fixes:
  - <style> block injections in post content
  - Inline CSS properties missing hyphens (backgroundcolor → background-color, etc.)
  - Stray LaTeX math expressions
Run once via GitHub Actions then disable the workflow.
"""
import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

WP_URL = os.environ.get("WP_URL", "https://www.avoltium.in").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD")

if not all([WP_URL, WP_USERNAME, WP_APP_PASSWORD]):
    print("ERROR: Missing WP_URL, WP_USERNAME, or WP_APP_PASSWORD.", flush=True)
    exit(1)

auth = (WP_USERNAME, WP_APP_PASSWORD)

# Posts confirmed to have broken CSS or style-block injection
POSTS_TO_FIX = [613, 686]

_CSS_FIXES = {
    "backgroundcolor": "background-color",
    "borderradius": "border-radius",
    "borderleft": "border-left",
    "bordertop": "border-top",
    "borderbottom": "border-bottom",
    "borderright": "border-right",
    "marginbottom": "margin-bottom",
    "margintop": "margin-top",
    "marginleft": "margin-left",
    "marginright": "margin-right",
    "paddingbottom": "padding-bottom",
    "paddingtop": "padding-top",
    "paddingleft": "padding-left",
    "paddingright": "padding-right",
    "fontsize": "font-size",
    "fontweight": "font-weight",
    "fontstyle": "font-style",
    "fontfamily": "font-family",
    "lineheight": "line-height",
    "textalign": "text-align",
    "textdecoration": "text-decoration",
    "texttransform": "text-transform",
    "objectfit": "object-fit",
    "maxwidth": "max-width",
    "maxheight": "max-height",
    "minwidth": "min-width",
    "minheight": "min-height",
    "boxshadow": "box-shadow",
    "liststyle": "list-style",
    "flexdirection": "flex-direction",
    "justifycontent": "justify-content",
    "alignitems": "align-items",
    "spacebetween": "space-between",
    "spacearound": "space-around",
    "flexwrap": "flex-wrap",
    "alignself": "align-self",
    "letterspaceing": "letter-spacing",
    "wordspacing": "word-spacing",
    "whitespace": "white-space",
    "zindex": "z-index",
    "pointerevents": "pointer-events",
}


def fix_content(html: str) -> str:
    """Repair the HTML defects the generator is known to emit.

    Strips injected <style> blocks, restores de-hyphenated CSS property names,
    and fixes internal links that lost their hyphens.
    """
    original_len = len(html)

    # 1. Strip injected <style> blocks
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # 2. Fix broken inline CSS property names
    def _fix_style(m):
        """Rewrite one style="..." attribute with hyphenated property names."""
        val = m.group(1)
        for broken, fixed in _CSS_FIXES.items():
            val = re.sub(r"\b" + re.escape(broken) + r"\b", fixed, val, flags=re.IGNORECASE)
        return f'style="{val}"'

    html = re.sub(r'style="([^"]*)"', _fix_style, html)

    # 3. Fix broken internal links that lost hyphens in URLs
    #    e.g. href="https://www.avoltium.in/electrolyzercalculator/"
    #       → href="https://www.avoltium.in/electrolyzer-calculator/"
    #
    #    Pair-by-pair replacement is what let this stay broken: the water
    #    entry pointed at water-consumption-calculator, which is not a page on
    #    this site, so the "repair" turned one dead link into another. Anything
    #    not in this table — five article URLs that lost their hyphens the same
    #    way — went unrepaired entirely. fix_internal_links.py resolves those
    #    against the live slug list; these two are the pair worth fixing
    #    offline because the generators emit them into every article.
    html = html.replace("/electrolyzercalculator/", "/electrolyzer-calculator/")
    html = html.replace("/waterconsumptioncalculator/",
                        "/water-consumption-treatment-calculator/")
    html = html.replace("/water-consumption-calculator/",
                        "/water-consumption-treatment-calculator/")

    # 4. Remove stray LaTeX
    html = re.sub(r"\$\$.*?\$\$", "", html, flags=re.DOTALL)
    html = re.sub(r"\$[^$\n]{1,100}\$", "", html)

    # 5. Clean up leading empty paragraphs added by WordPress rendering
    html = re.sub(r"^(\s*<p>\s*</p>\s*)+", "", html)
    html = html.strip()

    changed = len(html) != original_len or html != html
    return html


def fetch_raw_content(post_id: int) -> tuple[str, str] | None:
    """Fetch post title and raw content using edit context (requires auth)."""
    res = requests.get(
        f"{WP_URL}/wp-json/wp/v2/posts/{post_id}",
        params={"context": "edit"},
        auth=auth,
        timeout=30,
    )
    if res.status_code != 200:
        print(f"  Failed to fetch post {post_id}: HTTP {res.status_code}", flush=True)
        return None

    data = res.json()
    title = data.get("title", {}).get("raw", "")
    # 'raw' is the stored content before WordPress applies wpautop etc.
    content = data.get("content", {}).get("raw") or data.get("content", {}).get("rendered", "")
    return title, content


def patch_post(post_id: int, fixed_content: str) -> bool:
    """Write repaired content back to a post. True when WordPress accepted it."""
    res = requests.post(
        f"{WP_URL}/wp-json/wp/v2/posts/{post_id}",
        auth=auth,
        json={"content": fixed_content},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    return res.status_code in (200, 201)


# ─── Main ────────────────────────────────────────────────────────────────────

fixed_count = 0
for post_id in POSTS_TO_FIX:
    print(f"\n─── Post {post_id} ───", flush=True)
    result = fetch_raw_content(post_id)
    if result is None:
        continue

    title, raw = result
    print(f"  Title: {title}", flush=True)
    print(f"  Raw content length: {len(raw)} chars", flush=True)

    fixed = fix_content(raw)

    # Count how many CSS fixes were applied
    broken_before = sum(
        len(re.findall(r"\b" + re.escape(b) + r"\b", raw, re.IGNORECASE))
        for b in _CSS_FIXES
    )
    style_blocks = len(re.findall(r"<style[^>]*>", raw, re.IGNORECASE))
    print(f"  Broken CSS properties found: {broken_before}", flush=True)
    print(f"  Injected <style> blocks found: {style_blocks}", flush=True)

    if fixed == raw:
        print("  No changes needed.", flush=True)
        continue

    if patch_post(post_id, fixed):
        print(f"  SUCCESS: Post {post_id} updated.", flush=True)
        fixed_count += 1
    else:
        print(f"  ERROR: Failed to update post {post_id}.", flush=True)

print(f"\nDone. Fixed {fixed_count}/{len(POSTS_TO_FIX)} posts.", flush=True)
