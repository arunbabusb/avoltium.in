# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests",
#     "python-dotenv"
# ]
# ///
import os
import requests
import random
import re
import urllib.parse
from dotenv import load_dotenv

import qc_check

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

# Each topic maps to:
#   - image_prompt : highly specific photorealistic Pollinations prompt
#   - categories   : WordPress category IDs (from site's category list)
#
# WP category IDs:
#   8  = Electrolyzer Technology
#   9  = Balance of Plant (BOP)
#   10 = Green Hydrogen
#   12 = Technical Articles
#   15 = Water Treatment Systems
#   29 = Pumps & Valves
TOPICS = {
    "Next-Generation PEM Electrolyzer Architectures and Efficiency Gains": {
        "image_prompt": (
            "PEM proton exchange membrane electrolyzer stack cutaway cross-section, "
            "showing iridium oxide anode catalyst layer, Nafion membrane, platinum cathode, "
            "titanium porous transport layer PTL, bipolar flow field plates, "
            "professional industrial product photography, photorealistic, white studio background, "
            "ultra high detail, engineering precision"
        ),
        "categories": [8, 12],
    },
    "Alkaline vs PEM Electrolysis: Scaling for Gigawatt Green Hydrogen Projects": {
        "image_prompt": (
            "large scale industrial alkaline electrolyzer plant interior, "
            "tall cylindrical bipolar electrolytic cells KOH solution, "
            "stainless steel piping manifolds diaphragm separators, "
            "side-by-side with compact PEM electrolyzer stack, "
            "professional engineering photography, photorealistic industrial facility"
        ),
        "categories": [8, 10, 12],
    },
    "Ultrapure Water Demand and Reverse Osmosis (RO) Optimization in Hydrogen Hubs": {
        "image_prompt": (
            "industrial reverse osmosis water treatment skid for green hydrogen plant, "
            "rows of white cylindrical RO pressure vessels with blue end caps, "
            "high-pressure centrifugal pumps, electrodeionization EDI polishing unit, "
            "ultrapure water conductivity analyzers, stainless steel piping, "
            "professional industrial photography, photorealistic"
        ),
        "categories": [15, 12],
    },
    "Balance of Plant (BOP) Strategies for Large-Scale Green Hydrogen Facilities": {
        "image_prompt": (
            "green hydrogen facility balance of plant BOP equipment skid, "
            "industrial centrifugal pumps heat exchangers pressure vessels piping manifolds "
            "control valves instrumentation transmitters, P&ID diagram visible, "
            "complex industrial piping and equipment, professional engineering photography, photorealistic"
        ),
        "categories": [9, 12],
    },
    "Cooling Systems and Thermal Management in Industrial Electrolyzers": {
        "image_prompt": (
            "industrial plate heat exchanger and cooling tower system for electrolyzer thermal management, "
            "large stainless steel gasketed plate heat exchangers, cooling water pumps, "
            "expansion vessels, temperature and flow instrumentation, "
            "industrial facility background, professional engineering photography, photorealistic"
        ),
        "categories": [8, 12],
    },
    "Grid Integration and Renewable Energy Coupling for Intermittent Electrolysis": {
        "image_prompt": (
            "solar photovoltaic farm and offshore wind turbines connected to green hydrogen "
            "electrolysis plant, high-voltage transmission lines, power electronics rectifiers inverters, "
            "step-down transformers, aerial drone view of hybrid energy facility, "
            "professional industrial photography, photorealistic"
        ),
        "categories": [10, 12],
    },
    "Compressor Technologies for High-Pressure Green Hydrogen Storage": {
        "image_prompt": (
            "industrial diaphragm compressor for high-pressure hydrogen gas compression, "
            "metal diaphragm compressor head with stainless steel housing, crankcase assembly, "
            "high-pressure hydrogen piping fittings pressure gauges safety relief valves, "
            "350 bar 700 bar storage system, professional industrial product photography, photorealistic"
        ),
        "categories": [12],
    },
    "Materials Engineering for Electrolyzer Degradation Mitigation": {
        "image_prompt": (
            "scanning electron microscope SEM micrograph of PEM electrolyzer membrane electrode assembly MEA, "
            "iridium catalyst nanoparticles on carbon support Nafion ionomer, "
            "platinum cathode degradation cracks, high-magnification scientific materials research image, "
            "realistic laboratory electron microscopy photography"
        ),
        "categories": [8, 12],
    },
    "Centrifugal vs Diaphragm Pumps for Electrolyte Circulation in Alkaline Electrolyzers": {
        "image_prompt": (
            "industrial centrifugal pump and diaphragm metering pump side by side on skid, "
            "stainless steel casings, KOH electrolyte circulation piping, pressure gauges, "
            "mechanical seals, professional industrial product photography, photorealistic"
        ),
        "categories": [29, 8, 12],
    },
    "Control Valve Selection and Sizing for High-Purity Hydrogen Service": {
        "image_prompt": (
            "precision control valves for hydrogen gas service, stainless steel globe valve "
            "with pneumatic actuator and positioner, high-purity gas piping installation, "
            "instrumentation, professional industrial product photography, photorealistic"
        ),
        "categories": [29, 12],
    },
    "Electrodeionization (EDI) vs Mixed-Bed Polishing for Electrolyzer Feedwater": {
        "image_prompt": (
            "electrodeionization EDI modules and mixed-bed ion exchange polishing vessels in "
            "ultrapure water treatment room, resistivity meters, stainless piping, "
            "clean industrial water plant, professional photography, photorealistic"
        ),
        "categories": [15, 12],
    },
    "Hydrogen Gas Drying Technologies: PSA, TSA and Membrane Dehumidification": {
        "image_prompt": (
            "twin tower pressure swing adsorption PSA hydrogen gas dryer skid with desiccant "
            "vessels, switching valves, dew point analyzers, industrial gas processing plant, "
            "professional engineering photography, photorealistic"
        ),
        "categories": [10, 12],
    },
    "Stack Lifetime Extension: Voltage Cycling Protocols and Degradation Diagnostics": {
        "image_prompt": (
            "electrolyzer stack test bench with electrical measurement instrumentation, "
            "voltage monitoring cables on cell terminals, data acquisition system screens showing "
            "polarization curves, laboratory test facility, professional photography, photorealistic"
        ),
        "categories": [8, 12],
    },
    "Oxygen Side Management and Safety Systems in Large Electrolyzer Plants": {
        "image_prompt": (
            "industrial oxygen gas handling system at electrolyzer plant, gas-liquid separator "
            "vessels, flame arrestors, oxygen analyzers, safety relief valves, vent stacks, "
            "professional industrial photography, photorealistic"
        ),
        "categories": [8, 9, 12],
    },
    "Seawater Desalination Integration for Coastal Green Hydrogen Projects": {
        "image_prompt": (
            "coastal seawater desalination plant feeding green hydrogen facility, reverse osmosis "
            "trains, seawater intake structures, ocean in background with wind turbines, "
            "aerial industrial photography, photorealistic"
        ),
        "categories": [15, 10, 12],
    },
    "AEM Electrolyzers: Bridging the Cost Gap Between Alkaline and PEM": {
        "image_prompt": (
            "compact anion exchange membrane AEM electrolyzer module, modern laboratory prototype "
            "stack with polymer membrane cells, nickel-based electrodes, clean tech workshop, "
            "professional product photography, photorealistic"
        ),
        "categories": [8, 12],
    },
    "Hydrogen Leak Detection and Ventilation Design for Indoor Electrolyzer Rooms": {
        "image_prompt": (
            "hydrogen safety instrumentation in industrial electrolyzer room, gas detector heads "
            "mounted near ceiling, ventilation ducting, emergency shutoff panels, ATEX rated "
            "equipment, professional industrial photography, photorealistic"
        ),
        "categories": [9, 12],
    },
    "Power Electronics for Electrolysis: Rectifier Topologies and Harmonic Mitigation": {
        "image_prompt": (
            "high-current thyristor rectifier cabinets for electrolysis plant power supply, "
            "busbars, transformer connections, power electronics hall, electrical engineering "
            "installation, professional industrial photography, photorealistic"
        ),
        "categories": [9, 12],
    },
    "Waste Heat Recovery from Electrolyzers for District Heating and Process Use": {
        "image_prompt": (
            "industrial waste heat recovery system with plate heat exchangers and insulated hot "
            "water piping connecting electrolyzer plant to district heating network, pumps and "
            "control valves, professional engineering photography, photorealistic"
        ),
        "categories": [9, 10, 12],
    },
    "Green Ammonia Synthesis: Coupling Haber-Bosch with Intermittent Electrolysis": {
        "image_prompt": (
            "green ammonia synthesis plant with Haber-Bosch reactor columns, high-pressure "
            "synthesis loop piping, ammonia storage spheres, adjacent electrolyzer building and "
            "renewable energy, aerial industrial photography, photorealistic"
        ),
        "categories": [10, 12],
    },
    "Water Quality Monitoring Instrumentation for Ultrapure Electrolyzer Feed": {
        "image_prompt": (
            "online water quality analyzer panel with conductivity resistivity TOC and silica "
            "analyzers, sample lines, digital displays, ultrapure water plant instrumentation, "
            "professional industrial photography, photorealistic"
        ),
        "categories": [15, 12],
    },
    "Bipolar Plate Materials and Coatings: Titanium, Stainless and Beyond": {
        "image_prompt": (
            "precision machined titanium bipolar plates for electrolyzer stack with flow field "
            "channels, gold and platinum coated samples, metallurgical laboratory setting, "
            "macro product photography, photorealistic, high detail"
        ),
        "categories": [8, 12],
    },
    "Hydrogen Storage Options Compared: Compressed Gas, Liquid and Metal Hydrides": {
        "image_prompt": (
            "hydrogen storage comparison scene, high-pressure composite cylinders, cryogenic "
            "liquid hydrogen tank, metal hydride storage modules, industrial gas facility, "
            "professional industrial photography, photorealistic"
        ),
        "categories": [10, 12],
    },
    "Electrolyzer Plant Commissioning: FAT, SAT and Performance Test Protocols": {
        "image_prompt": (
            "engineers commissioning electrolyzer plant, checking instrumentation and control "
            "panels, test documentation, industrial control room and plant floor, "
            "professional engineering photography, photorealistic"
        ),
        "categories": [9, 12],
    },
    "LCOH Deep Dive: Sensitivity of Hydrogen Cost to Electricity Price and Capacity Factor": {
        "image_prompt": (
            "green hydrogen plant at sunset with solar farm and transmission lines, "
            "large industrial electrolyzer buildings, economic energy infrastructure scene, "
            "aerial photography, photorealistic"
        ),
        "categories": [10, 12],
    },
    "Membrane Technologies in Water Treatment: UF, RO and EDI Train Design for Hydrogen Plants": {
        "image_prompt": (
            "complete membrane water treatment train, ultrafiltration modules, reverse osmosis "
            "pressure vessels, EDI stacks in series, stainless steel piping and instrumentation, "
            "modern water treatment hall, professional photography, photorealistic"
        ),
        "categories": [15, 12],
    },
    "Gasket and Sealing Technology for High-Pressure Alkaline Stacks": {
        "image_prompt": (
            "industrial gaskets and sealing components for electrolyzer cell stack assembly, "
            "PTFE and elastomer gaskets, flange faces, torque tools, assembly workshop bench, "
            "macro product photography, photorealistic"
        ),
        "categories": [8, 29, 12],
    },
    "Piping Material Selection for Hydrogen Service: Embrittlement and Code Compliance": {
        "image_prompt": (
            "stainless steel hydrogen piping installation with orbital welded joints, pipe "
            "supports, material test certificates, ASME code stamped spools, industrial "
            "construction site, professional photography, photorealistic"
        ),
        "categories": [9, 29, 12],
    },
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
    image_prompt = (TOPICS.get(topic) or {}).get("image_prompt") or (
        f"professional industrial photograph, {topic}, green hydrogen technology facility, "
        "photorealistic, high detail engineering"
    )

    print(f"Generating contextual image for: {topic}", flush=True)
    encoded_prompt = urllib.parse.quote(image_prompt)
    # FLUX model produces significantly more photorealistic results than the default.
    # Random seed prevents Pollinations from serving the same cached image every
    # time a topic repeats — without it, identical prompts return identical images.
    seed = random.randint(1, 999_999)
    img_url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?width=1200&height=675&nologo=true&model=flux&seed={seed}"
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
    """Upload image bytes to WordPress Media Library with alt text, return media ID."""
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
            # Alt text for SEO and accessibility
            requests.post(
                f"{WP_URL}/wp-json/wp/v2/media/{media_id}",
                auth=auth,
                json={"alt_text": topic, "title": topic},
                timeout=30,
            )
            print(f"Image uploaded — Media ID: {media_id}", flush=True)
            return media_id
        print(f"Image upload failed: HTTP {res.status_code} — {res.text[:200]}", flush=True)
    except Exception as e:
        print(f"Image upload error: {e}", flush=True)
    return None


def _normalize_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", t.lower())


def fetch_existing_titles() -> set[str]:
    """Fetch all existing post titles (any status) to avoid duplicate topics."""
    titles, page = set(), 1
    while True:
        try:
            res = requests.get(
                f"{WP_URL}/wp-json/wp/v2/posts",
                params={"per_page": 100, "page": page, "status": "publish,draft,pending,future",
                        "_fields": "title"},
                auth=auth,
                timeout=30,
            )
            if res.status_code != 200:
                break
            batch = res.json()
            if not batch:
                break
            for p in batch:
                titles.add(_normalize_title(p["title"]["rendered"]))
            if len(batch) < 100:
                break
            page += 1
        except Exception as e:
            print(f"Title fetch error: {e}", flush=True)
            break
    return titles


def pick_topic() -> tuple[str, str]:
    """Pick a topic not yet covered on the site.

    Returns (topic_key, post_title). If every topic already has an article,
    reuse a random topic with a dated 'Engineering Review' title so the post
    title is still unique.
    """
    existing = fetch_existing_titles()
    unused = [t for t in TOPICS if _normalize_title(t) not in existing]
    if unused:
        topic = random.choice(unused)
        return topic, topic
    import datetime
    topic = random.choice(list(TOPICS.keys()))
    stamp = datetime.date.today().strftime("%B %Y")
    return topic, f"{topic}: {stamp} Engineering Review"


def make_excerpt(html: str) -> str:
    """Meta-description-length excerpt from the Engineering Insight box."""
    m = re.search(r"Engineering Insight:</strong>\s*(.*?)</div>", html, re.S)
    text = m.group(1) if m else html
    text = re.sub(r"<[^>]+>", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:152] + "..." if len(text) > 155 else text


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

topic, post_title = pick_topic()
print(f"Selected topic: {topic}", flush=True)
if post_title != topic:
    print(f"All topics covered — publishing dated review: {post_title}", flush=True)

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

# 5. Quality gate — a defective article is held as a draft rather than
#    published, so readers and Googlebot never see it. Every rule in
#    qc_check exists because that defect once shipped live.
qc_media = None
if featured_media_id:
    qc_media = {
        "alt_text": topic,
        "media_details": {"width": 1200, "height": 675},
    }

issues = qc_check.check_post(post_title, html_content, qc_media)
fatal = qc_check.blockers(issues)
for severity, message in issues:
    print(f"  QC {severity}: {message}", flush=True)

publish_status = "publish"
if fatal:
    publish_status = "draft"
    print(
        f"QC FAILED ({len(fatal)} blockers) — saving as DRAFT for human review "
        "instead of publishing.",
        flush=True,
    )
else:
    print("QC passed.", flush=True)

# 6. Publish to WordPress with topic-specific categories and SEO excerpt
categories = (TOPICS.get(topic) or {}).get("categories", [12])
print(f"Sending to WordPress as '{publish_status}' (categories: {categories})...", flush=True)
payload = {
    "title": post_title,
    "content": html_content,
    "status": publish_status,
    "categories": categories,
    "excerpt": make_excerpt(html_content),
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
        f"SUCCESS: '{post_title}' saved as {publish_status} "
        f"(Post ID: {post_id}, Media ID: {featured_media_id}).",
        flush=True,
    )
    # Non-zero exit makes the workflow run go red so a held draft is visible
    # in the Actions tab instead of passing silently.
    if publish_status == "draft":
        print("Review the draft in WordPress before publishing.", flush=True)
        exit(1)
else:
    print(f"ERROR: Publish failed — HTTP {wp_res.status_code}", flush=True)
    print(wp_res.text[:500], flush=True)
    exit(1)
