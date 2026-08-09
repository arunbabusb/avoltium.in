# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "python-dotenv"]
# ///
"""
One-time content remediation for avoltium.in.

Two problems this fixes:

  1. EMPTY / STUB POSTS — published posts whose body is blank or only an image
     credit. These are pure thin content and an AdSense liability.

  2. SYNDICATED NEWS POSTS — short posts whose body reads as copied newswire
     text. Duplicate content is the single biggest AdSense rejection reason.

Both are replaced with original engineering commentary written from the
Avoltium chief-engineer perspective: the news event becomes the hook, and the
body is original technical analysis that no other site has.

SAFETY
  - Every original body is written to content_backup.json BEFORE any update,
    and that file is uploaded as a workflow artifact so changes are reversible.
  - Existing "Featured Image Credit" blocks are preserved verbatim and
    re-appended, because those carry CC-BY attribution we are legally obliged
    to keep.
  - A post is only updated if Gemini returns usable content; on any failure the
    original is left untouched.
"""
import json
import os
import re
import time

import requests
from dotenv import load_dotenv

import resilient

load_dotenv()

WP_URL = os.environ.get("WP_URL", "https://www.avoltium.in").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Optional: route rewrites through an OmniRoute (or other OpenAI-compatible)
# gateway for cost/token-compression routing. Leaving either unset falls
# back to calling the Gemini API directly, unchanged.
OMNIROUTE_BASE_URL = os.environ.get("OMNIROUTE_BASE_URL", "").strip()
OMNIROUTE_API_KEY = os.environ.get("OMNIROUTE_API_KEY", "").strip()

if not all([WP_URL, WP_USERNAME, WP_APP_PASSWORD, GEMINI_API_KEY]):
    print("ERROR: Missing WP_URL / WP_USERNAME / WP_APP_PASSWORD / GEMINI_API_KEY.", flush=True)
    raise SystemExit(1)

auth = (WP_USERNAME, WP_APP_PASSWORD)

# Posts with an empty or near-empty body — need a full original article.
STUB_POSTS = [415, 405, 401, 306, 305, 302, 315, 269]

# Short posts that read as syndicated newswire copy — need original commentary.
SYNDICATED_POSTS = [
    303, 301, 300, 298, 297, 296, 295, 283, 282, 281, 279,
    172, 170, 168, 166, 164,
]

# Drafts surfaced by recover_drafts.py on 7 Aug 2026. These were already held
# by the QC gate for editorial faults a rewrite fixes, so they belong in the
# same remediation. Kept in their own lists so it stays clear which batch a
# post came from and what the QC gate actually complained about.
HELD_DRAFT_STUBS = [
    413,  # "27 Hydrogen trade" — body is completely empty (0 chars)
    268,  # 168 chars
    267,  # 211 chars
]
HELD_DRAFT_SYNDICATED = [
    174,  # 1,878 chars — under the 2,500 minimum
    273,  # LaTeX in body ($…$); news roundup
    317,  # LaTeX in body (\text{}); "As told to Parliament" newswire copy
]

MODELS = ["gemini-2.0-flash", "gemini-flash-latest", "gemini-2.0-flash-lite"]

_CSS_FIXES = {
    "backgroundcolor": "background-color", "borderradius": "border-radius",
    "borderleft": "border-left", "bordertop": "border-top",
    "borderbottom": "border-bottom", "borderright": "border-right",
    "marginbottom": "margin-bottom", "margintop": "margin-top",
    "marginleft": "margin-left", "marginright": "margin-right",
    "paddingbottom": "padding-bottom", "paddingtop": "padding-top",
    "paddingleft": "padding-left", "paddingright": "padding-right",
    "fontsize": "font-size", "fontweight": "font-weight",
    "fontstyle": "font-style", "fontfamily": "font-family",
    "lineheight": "line-height", "textalign": "text-align",
    "textdecoration": "text-decoration", "objectfit": "object-fit",
    "maxwidth": "max-width", "maxheight": "max-height",
    "boxshadow": "box-shadow", "justifycontent": "justify-content",
    "alignitems": "align-items", "spacebetween": "space-between",
}


def sanitize(html: str) -> str:
    """Strip LLM artifacts and repair broken CSS in generated HTML."""
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = html.replace("```html", "").replace("```", "")

    def _fix_style(m):
        val = m.group(1)
        for broken, good in _CSS_FIXES.items():
            val = re.sub(r"\b" + broken + r"\b", good, val, flags=re.IGNORECASE)
        return f'style="{val}"'

    html = re.sub(r'style="([^"]*)"', _fix_style, html)

    # Strip LaTeX — the site standard is Unicode + HTML sub/sup
    html = re.sub(r"\$\$.*?\$\$", "", html, flags=re.DOTALL)
    html = re.sub(r"\$[^$\n]{1,100}\$", "", html)
    html = re.sub(r"\\text\{([^}]*)\}", r"\1", html)
    html = re.sub(r"\\(?:Delta|eta|mu|Omega|alpha|beta|gamma|frac|times)\b", "", html)

    html = re.sub(r"^(\s*<p>\s*</p>\s*)+", "", html)
    return html.strip()


def extract_image_credit(html: str) -> str:
    """Return the Featured Image Credit block verbatim — CC-BY attribution."""
    m = re.search(
        r'<div[^>]*>\s*<strong>\s*Featured Image Credit:.*?</div>',
        html, flags=re.DOTALL | re.IGNORECASE,
    )
    return m.group(0) if m else ""


def plain_text(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def build_prompt(title: str, existing: str, mode: str) -> str:
    shared_rules = """
FORMATTING RULES (follow every one):

1. Output raw HTML only. No ```html fences, no <style> tags, no <html>/<body>.
2. Open with exactly this box:
   <div style="background-color: #f8f9fa; border-left: 4px solid #0056b3; padding: 15px; margin-bottom: 20px;"><strong>Engineering Insight:</strong> [one-sentence engineering takeaway]</div>
3. Use <h2> and <h3> for subheadings, <p> for body text.
4. Include at least one blockquote styled exactly:
   <blockquote style="font-size: 1.2em; font-style: italic; color: #555; border-left: 3px solid #ccc; padding-left: 15px; margin: 20px 0;">"[quote]"</blockquote>
5. CSS property names must be fully hyphenated: background-color, font-size,
   margin-bottom, border-left. Never backgroundcolor or fontSize.
6. NO LaTeX. No backslash commands, no dollar-sign math. Use Unicode (η, Δ, Ω,
   °C, ±) and HTML tags for formulas: H<sub>2</sub>O, A/cm<sup>2</sup>,
   kWh/kg H<sub>2</sub>.
7. Write as Arun, Chief Engineer at Avoltium — technical, specific, and
   confident. Include real engineering numbers (efficiencies, pressures,
   current densities, costs) wherever they support the argument.
8. Naturally mention "electrolyzer" and "water treatment" where relevant.
9. Do NOT invent quotes from named real people, and do NOT claim Avoltium was
   involved in projects it was not. Attribute any factual claim generically
   ("reported capacity of...", "the announced scope covers...").
"""

    if mode == "stub":
        return f"""You are Arun, Chief Engineer at Avoltium, an engineering consultancy
specialising in green hydrogen, electrolyzers and industrial water treatment.

Write a completely original 900-word technical article for the headline:
"{title}"

This page is currently empty. Write the definitive engineering explainer on this
subject — what the technology or policy actually involves, the engineering
constraints that decide whether it succeeds, and what practitioners should watch.
Do not pretend to report breaking news; write evergreen technical analysis.
{shared_rules}"""

    return f"""You are Arun, Chief Engineer at Avoltium, an engineering consultancy
specialising in green hydrogen, electrolyzers and industrial water treatment.

The text below is a syndicated news item republished on our site. Republished
newswire copy is duplicate content and must be replaced.

Rewrite it as a 900-word ORIGINAL engineering commentary. Use the underlying
event only as a hook in the opening paragraph, then pivot to analysis that
exists nowhere else: the engineering fundamentals, the balance-of-plant and
water-treatment implications, realistic cost and efficiency figures, and what
the development means for practitioners. Do not paraphrase the source
sentence-by-sentence — replace it with your own technical argument.

HEADLINE: {title}

SOURCE ITEM (for factual context only — do not copy its wording):
{plain_text(existing)[:1800]}
{shared_rules}"""


def call_gemini(prompt: str) -> str | None:
    text, _model = resilient.generate_text(
        GEMINI_API_KEY,
        prompt,
        models=MODELS,
        timeout=120,
        omniroute_base_url=OMNIROUTE_BASE_URL or None,
        omniroute_api_key=OMNIROUTE_API_KEY or None,
    )
    return text


def make_excerpt(html: str) -> str:
    m = re.search(r"Engineering Insight:</strong>\s*(.*?)</div>", html, re.DOTALL)
    text = plain_text(m.group(1) if m else html)
    return text[:152] + "..." if len(text) > 155 else text


def process(post_id: int, mode: str, backup: dict) -> bool:
    res = resilient.request_with_retry(
        "GET",
        f"{WP_URL}/wp-json/wp/v2/posts/{post_id}",
        attempts=3,
        label=f"wp/fetch/{post_id}",
        params={"context": "edit"}, auth=auth, timeout=30,
    )
    if res is None or res.status_code != 200:
        status = res.status_code if res is not None else "no response"
        print(f"  fetch failed: {status}", flush=True)
        return False

    data = res.json()
    title = data["title"]["raw"]
    original = data["content"]["raw"]
    print(f"  [{mode}] {title[:65]}", flush=True)

    backup[str(post_id)] = {"title": title, "content": original}

    generated = call_gemini(build_prompt(title, original, mode))
    if not generated:
        print("  SKIPPED — Gemini returned nothing", flush=True)
        return False

    body = sanitize(generated)
    if len(plain_text(body)) < 500:
        print(f"  SKIPPED — output too short ({len(plain_text(body))} chars)", flush=True)
        return False

    credit = extract_image_credit(original)
    if credit:
        body = f"{body}\n\n{credit}"

    # Internal links to our calculators, capped so they stay natural
    body = re.sub(
        r"(?i)\b(electrolyzer[s]?)\b",
        f'<a href="{WP_URL}/electrolyzer-calculator/" style="color:#0056b3; font-weight:bold;">\\1</a>',
        body, count=1,
    )
    body = re.sub(
        r"(?i)\b(water treatment|ultrapure water)\b",
        f'<a href="{WP_URL}/water-consumption-calculator/" style="color:#0056b3; font-weight:bold;">\\1</a>',
        body, count=1,
    )

    upd = resilient.request_with_retry(
        "POST",
        f"{WP_URL}/wp-json/wp/v2/posts/{post_id}",
        attempts=3,
        label=f"wp/update/{post_id}",
        auth=auth,
        json={"content": body, "excerpt": make_excerpt(body)},
        timeout=60,
    )
    if upd is not None and upd.status_code == 200:
        print(f"  OK — {len(plain_text(body))} chars of original content", flush=True)
        return True

    status = upd.status_code if upd is not None else "no response"
    print(f"  UPDATE FAILED: {status}", flush=True)
    return False


def main() -> None:
    backup: dict = {}
    done = 0
    targets = [(pid, "stub") for pid in STUB_POSTS + HELD_DRAFT_STUBS] + \
              [(pid, "syndicated") for pid in SYNDICATED_POSTS + HELD_DRAFT_SYNDICATED]

    # RETRY_POST_IDS lets a follow-up run re-process only the posts that failed
    # (usually Gemini rate limits) without touching posts already rewritten.
    # This matters because a full re-run would overwrite content_backup.json
    # with already-rewritten bodies, destroying the only copy of the originals.
    retry_raw = os.environ.get("RETRY_POST_IDS", "").strip()
    if retry_raw:
        wanted = {int(x) for x in re.findall(r"\d+", retry_raw)}
        targets = [(pid, mode) for pid, mode in targets if pid in wanted]
        unknown = wanted - {pid for pid, _ in targets}
        if unknown:
            print(f"WARNING: ignoring IDs not in target lists: {sorted(unknown)}", flush=True)
        print(f"RETRY MODE — only posts {sorted(p for p, _ in targets)}", flush=True)

    if not targets:
        print("Nothing to do.", flush=True)
        return

    print(f"Processing {len(targets)} posts\n", flush=True)
    for pid, mode in targets:
        print(f"--- post {pid} ---", flush=True)
        try:
            if process(pid, mode, backup):
                done += 1
        except Exception as e:
            print(f"  ERROR: {e}", flush=True)
        # Stay well inside Gemini free-tier rate limits
        time.sleep(5)

    # Distinct filename per retry run so a retry never clobbers the backup
    # holding the true pre-rewrite originals.
    backup_name = f"content_backup_retry_{'_'.join(str(p) for p, _ in targets)}.json" \
        if retry_raw else "content_backup.json"
    with open(backup_name, "w", encoding="utf-8") as fh:
        json.dump(backup, fh, indent=2, ensure_ascii=False)

    print(f"\nRewrote {done}/{len(targets)} posts.", flush=True)
    print(f"Originals backed up for {len(backup)} posts in {backup_name}", flush=True)


if __name__ == "__main__":
    main()
