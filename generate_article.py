# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests",
#     "python-dotenv",
#     "beautifulsoup4"
# ]
# ///
import os
import requests
import random
import re
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

WP_URL = os.environ.get("WP_URL", "https://www.avoltium.in").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not all([WP_URL, WP_USERNAME, WP_APP_PASSWORD, GEMINI_API_KEY]):
    print("ERROR: Missing required environment variables (WP_URL, WP_USERNAME, WP_APP_PASSWORD, GEMINI_API_KEY).", flush=True)
    exit(1)

auth = (WP_USERNAME, WP_APP_PASSWORD)
headers = {"Content-Type": "application/json"}

# Each topic is paired with a highly specific image prompt so the featured
# image shows the actual equipment/system being discussed — not a generic
# "green energy facility" render.
TOPICS = {
    "Next-Generation PEM Electrolyzer Architectures and Efficiency Gains": (
        "PEM proton exchange membrane electrolyzer stack cutaway cross-section, "
        "showing iridium oxide anode catalyst layer, Nafion membrane, platinum cathode, "
        "titanium porous transport layer PTL, bipolar flow field plates, "
        "professional industrial product photography, photorealistic, white studio background, "
        "ultra high detail, engineering precision"
    ),
    "Alkaline vs PEM Electrolysis: Scaling for Gigawatt Green Hydrogen Projects": (
        "large scale industrial alkaline electrolyzer plant interior, "
        "tall cylindrical bipolar electrolytic cells KOH solution, "
        "stainless steel piping manifolds diaphragm separators, "
        "side-by-side with compact PEM electrolyzer stack, "
        "professional engineering photography, photorealistic industrial facility"
    ),
    "Ultrapure Water Demand and Reverse Osmosis (RO) Optimization in Hydrogen Hubs": (
        "industrial reverse osmosis water treatment skid for green hydrogen plant, "
        "rows of white cylindrical RO pressure vessels with blue end caps, "
        "high-pressure centrifugal pumps, electrodeionization EDI polishing unit, "
        "ultrapure water conductivity analyzers, stainless steel piping, "
        "professional industrial photography, photorealistic"
    ),
    "Balance of Plant (BOP) Strategies for Large-Scale Green Hydrogen Facilities": (
        "green hydrogen facility balance of plant BOP equipment skid, "
        "industrial centrifugal pumps heat exchangers pressure vessels piping manifolds "
        "control valves instrumentation transmitters, P&ID diagram visible, "
        "complex industrial piping and equipment, professional engineering photography, photorealistic"
    ),
    "Cooling Systems and Thermal Management in Industrial Electrolyzers": (
        "industrial plate heat exchanger and cooling tower system for electrolyzer thermal management, "
        "large stainless steel gasketed plate heat exchangers, cooling water pumps, "
        "expansion vessels, temperature and flow instrumentation, "
        "industrial facility background, professional engineering photography, photorealistic"
    ),
    "Grid Integration and Renewable Energy Coupling for Intermittent Electrolysis": (
        "solar photovoltaic farm and offshore wind turbines connected to green hydrogen "
        "electrolysis plant, high-voltage transmission lines, power electronics rectifiers inverters, "
        "step-down transformers, aerial drone view of hybrid energy facility, "
        "professional industrial photography, photorealistic"
    ),
    "Compressor Technologies for High-Pressure Green Hydrogen Storage": (
        "industrial diaphragm compressor for high-pressure hydrogen gas compression, "
        "metal diaphragm compressor head with stainless steel housing, crankcase assembly, "
        "high-pressure hydrogen piping fittings pressure gauges safety relief valves, "
        "350 bar 700 bar storage system, professional industrial product photography, photorealistic"
    ),
    "Materials Engineering for Electrolyzer Degradation Mitigation": (
        "scanning electron microscope SEM micrograph of PEM electrolyzer membrane electrode assembly MEA, "
        "iridium catalyst nanoparticles on carbon support Nafion ionomer, "
        "platinum cathode degradation cracks, high-magnification scientific materials research image, "
        "realistic laboratory electron microscopy photography"
    ),
}

# CSS property names that Gemini sometimes outputs without hyphens
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
    "letterspaceing": "letter-spacing",
    "wordspacing": "word-spacing",
    "whitespace": "white-space",
    "zindex": "z-index",
    "pointerevents": "pointer-events",
    "overflowx": "overflow-x",
    "overflowy": "overflow-y",
    "gridcolumn": "grid-column",
    "gridrow": "grid-row",
    "spacebetween": "space-between",
    "spacearound": "space-around",
    "flexwrap": "flex-wrap",
    "alignself": "align-self",
}


def sanitize_content(html: str) -> str:
    """Remove LLM artifacts and fix broken CSS in generated HTML content."""

    # 1. Strip any injected <style> blocks (Gemini sometimes wraps CSS in style tags)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # 2. Fix broken CSS property names (missing hyphens) inside inline style attributes
    def _fix_inline_style(m):
        style_val = m.group(1)
        for broken, fixed in _CSS_FIXES.items():
            style_val = re.sub(r"\b" + re.escape(broken) + r"\b", fixed, style_val, flags=re.IGNORECASE)
        return f'style="{style_val}"'

    html = re.sub(r'style="([^"]*)"', _fix_inline_style, html)

    # 3. Remove Markdown code fences the LLM may have slipped in
    html = html.replace("```html", "").replace("```", "")

    # 4. Remove stray LaTeX math expressions ($...$, $$...$$, \command)
    html = re.sub(r"\$\$.*?\$\$", "", html, flags=re.DOTALL)
    html = re.sub(r"\$[^$\n]{1,100}\$", "", html)
    html = re.sub(r"\\(?:Delta|eta|mu|Omega|alpha|beta|gamma|theta|lambda|sigma|phi|tau|pi)\b", "", html)

    # 5. Trim leading/trailing empty paragraph tags
    html = re.sub(r"^(\s*<p>\s*</p>\s*)+", "", html)
    html = re.sub(r"(\s*<p>\s*</p>\s*)+$", "", html)

    return html.strip()


def fetch_contextual_image(topic: str) -> bytes | None:
    """Generate a topic-specific, photorealistic image via Pollinations FLUX."""
    image_prompt = TOPICS.get(topic) or (
        f"professional industrial photograph, {topic}, green hydrogen technology facility, "
        "photorealistic, high detail engineering"
    )

    print(f"Generating contextual image for: {topic}", flush=True)
    encoded_prompt = urllib.parse.quote(image_prompt)
    # FLUX model produces significantly more photorealistic results than the default
    img_url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?width=1200&height=675&nologo=true&model=flux"
    )

    try:
        res = requests.get(img_url, timeout=90)
        if res.status_code == 200:
            return res.content
        print(f"Pollinations returned HTTP {res.status_code}", flush=True)
    except Exception as e:
        print(f"Image generation error: {e}", flush=True)

    return None


def upload_image_to_wp(image_bytes: bytes, topic: str) -> int | None:
    """Upload image bytes to WordPress Media Library, return media ID or None."""
    filename = f"featured_{random.randint(1000, 9999)}.jpg"
    media_headers = {
        "Content-Type": "image/jpeg",
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    try:
        res = requests.post(
            f"{WP_URL}/wp-json/wp/v2/media",
            headers=media_headers,
            auth=auth,
            data=image_bytes,
            timeout=60,
        )
        if res.status_code == 201:
            media_id = res.json()["id"]
            print(f"Image uploaded — Media ID: {media_id}", flush=True)
            return media_id
        print(f"Image upload failed: HTTP {res.status_code} — {res.text[:200]}", flush=True)
    except Exception as e:
        print(f"Image upload error: {e}", flush=True)
    return None


def build_gemini_prompt(topic: str) -> str:
    return f"""You are Arun, the Chief Engineer at Avoltium.
Write a highly technical, professional 1,200-word engineering article on: "{topic}".

=== FORMATTING RULES (STRICTLY FOLLOW ALL) ===

1. Output raw HTML only. Do NOT wrap the response in ```html or ``` code fences.

2. Start immediately with a styled Engineering Insight box using this EXACT HTML:
   <div style="background-color: #f8f9fa; border-left: 4px solid #0056b3; padding: 15px; margin-bottom: 20px;"><strong>Engineering Insight:</strong> [Key takeaway]</div>

3. Use <h2> and <h3> for all subheadings.

4. Include at least two blockquotes using this EXACT style:
   <blockquote style="font-size: 1.2em; font-style: italic; color: #555; border-left: 3px solid #ccc; padding-left: 15px; margin: 20px 0;">"[Quote]"</blockquote>

5. INLINE CSS RULES — CRITICAL:
   - ALWAYS use full hyphenated CSS property names in style attributes:
     ✓ background-color  ✗ backgroundcolor or backgroundColor
     ✓ border-left       ✗ borderleft
     ✓ margin-bottom     ✗ marginbottom
     ✓ font-size         ✗ fontsize
     ✓ font-weight       ✗ fontweight
     ✓ border-radius     ✗ borderradius
     ✓ justify-content   ✗ justifycontent
     ✓ space-between     ✗ spacebetween
   - NEVER output <style> tags, CSS blocks, or @media rules. Inline styles only.

6. SCIENTIFIC NOTATION RULES — CRITICAL:
   - NEVER use LaTeX syntax: no backslashes (\\), no dollar signs ($), no \\Delta, \\eta, etc.
   - Use Unicode symbols directly: η (efficiency), Δ (delta), Ω (ohm), α, β, μ, °C
   - Chemical formulas: use HTML sub/sup tags → H<sub>2</sub>O, O<sub>2</sub>, CO<sub>2</sub>, H<sub>2</sub>SO<sub>4</sub>
   - Superscripts: m<sup>2</sup>, cm<sup>3</sup>, kWh/Nm<sup>3</sup>
   - Write equations in plain readable form:
     ✓ V<sub>cell</sub> = E<sub>rev</sub> + η<sub>anode</sub> + η<sub>cathode</sub> + i·R<sub>ohmic</sub>
     ✓ Efficiency = (ΔG / P<sub>input</sub>) × 100%
     ✓ Current density: i = I / A (A/cm<sup>2</sup>)
   - Use % for efficiency, bar/MPa/PSI for pressure, A/cm² for current density

7. Write in a highly technical tone for industry professionals.
   Naturally use the words "Electrolyzer" and "Water Treatment" a few times.
"""


# ─── Main ────────────────────────────────────────────────────────────────────

topic = random.choice(list(TOPICS.keys()))
print(f"Selected topic: {topic}", flush=True)

# 1. Generate contextual featured image
featured_media_id = None
image_bytes = fetch_contextual_image(topic)
if image_bytes:
    featured_media_id = upload_image_to_wp(image_bytes, topic)
else:
    print("Skipping featured image — will publish without one.", flush=True)

# 2. Generate article via Gemini REST API
MODELS = ["gemini-2.0-flash", "gemini-flash-latest", "gemini-2.0-flash-lite"]
html_content = None

print("Generating article via Gemini...", flush=True)
for model in MODELS:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":generateContent?key={GEMINI_API_KEY}"
    )
    payload = {"contents": [{"parts": [{"text": build_gemini_prompt(topic)}]}]}
    res = requests.post(url, json=payload, timeout=90)

    if res.status_code == 200:
        html_content = res.json()["candidates"][0]["content"]["parts"][0]["text"]
        print(f"Article generated with model {model}.", flush=True)
        break
    elif res.status_code == 429:
        print(f"Rate-limited on {model}, trying next...", flush=True)
    else:
        print(f"Model {model} → HTTP {res.status_code}", flush=True)

if not html_content:
    print("ERROR: Could not generate content from any Gemini model.", flush=True)
    exit(1)

# 3. Sanitize: remove CSS injection, fix broken property names, strip LaTeX
html_content = sanitize_content(html_content)

# 4. Inject internal SEO links (max 2 per anchor type)
html_content = re.sub(
    r"(?i)\b(electrolyzer[s]?|electrolysis)\b",
    f'<a href="{WP_URL}/electrolyzer-calculator/" style="color:#0056b3; font-weight:bold;">\\1</a>',
    html_content,
    count=2,
)
html_content = re.sub(
    r"(?i)\b(water treatment|ultrapure water|water consumption)\b",
    f'<a href="{WP_URL}/water-consumption-calculator/" style="color:#0056b3; font-weight:bold;">\\1</a>',
    html_content,
    count=2,
)

# 5. Publish to WordPress (Category 12 = Technical Articles)
print("Publishing to WordPress...", flush=True)
payload = {
    "title": topic,
    "content": html_content,
    "status": "publish",
    "categories": [12],
}
if featured_media_id:
    payload["featured_media"] = featured_media_id

wp_res = requests.post(
    f"{WP_URL}/wp-json/wp/v2/posts",
    headers=headers,
    auth=auth,
    json=payload,
    timeout=60,
)
if wp_res.status_code == 201:
    post_id = wp_res.json()["id"]
    print(
        f"SUCCESS: '{topic}' published (Post ID: {post_id}, Media ID: {featured_media_id}).",
        flush=True,
    )
else:
    print(f"ERROR: Publish failed — HTTP {wp_res.status_code}", flush=True)
    print(wp_res.text[:500], flush=True)
    exit(1)
