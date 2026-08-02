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

if not all([WP_URL, WP_USERNAME, WP_APP_PASSWORD]):
    print("ERROR: Missing required environment variables.", flush=True)
    exit(1)

auth = (WP_USERNAME, WP_APP_PASSWORD)
headers = {"Content-Type": "application/json"}

# 1. Select a random technical topic
topics = [
    "Next-Generation PEM Electrolyzer Architectures and Efficiency Gains",
    "Alkaline vs PEM Electrolysis: Scaling for Gigawatt Green Hydrogen Projects",
    "Ultrapure Water Demand and Reverse Osmosis (RO) Optimization in Hydrogen Hubs",
    "Balance of Plant (BOP) Strategies for Large-Scale Green Hydrogen Facilities",
    "Cooling Systems and Thermal Management in Industrial Electrolyzers",
    "Grid Integration and Renewable Energy Coupling for Intermittent Electrolysis",
    "Compressor Technologies for High-Pressure Green Hydrogen Storage",
    "Materials Engineering for Electrolyzer Degradation Mitigation"
]
topic = random.choice(topics)
print(f"Selected Topic: {topic}", flush=True)

# 2. Generate Image via Pollinations AI & Upload to WordPress Media
featured_media_id = None
try:
    print("Generating featured image for topic...", flush=True)
    clean_prompt = f"clean energy engineering, {topic}, modern hydrogen technology facility, highly detailed 3d render"
    encoded_prompt = urllib.parse.quote(clean_prompt)
    img_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=800&height=450&nologo=true"
    
    img_res = requests.get(img_url, timeout=30)
    if img_res.status_code == 200:
        print("Uploading image to WordPress Media Library...", flush=True)
        filename = f"featured_{random.randint(1000, 9999)}.jpg"
        media_headers = {
            "Content-Type": "image/jpeg",
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
        media_res = requests.post(f"{WP_URL}/wp-json/wp/v2/media", headers=media_headers, auth=auth, data=img_res.content, timeout=30)
        if media_res.status_code == 201:
            featured_media_id = media_res.json()['id']
            print(f"Successfully created Featured Media ID: {featured_media_id}", flush=True)
        else:
            print(f"Failed to upload image to WP: {media_res.status_code}", flush=True)
except Exception as e:
    print(f"Image generation failed: {e}", flush=True)

# 3. Generate Content via Gemini REST API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
prompt = f"""
You are Arun, the Chief Engineer at Avoltium. 
Write a highly technical, professional 1,200-word engineering article on the topic: "{topic}".

Formatting Rules (CRITICAL FOR ADSENSE APPROVAL):
1. Output raw HTML, not Markdown. Do NOT wrap the response in ```html or ``` blocks.
2. Use <h2> and <h3> tags for all subheadings.
3. Start the article immediately with a <div> styled box extracting the "Engineering Insight" (key takeaway). Use this exact style: 
   <div style="background-color: #f8f9fa; border-left: 4px solid #0056b3; padding: 15px; margin-bottom: 20px;"><strong>Engineering Insight:</strong> [Your takeaway]</div>
4. Include at least two <blockquote> elements styled like this:
   <blockquote style="font-size: 1.2em; font-style: italic; color: #555; border-left: 3px solid #ccc; padding-left: 15px; margin: 20px 0;">"[Important quote]"</blockquote>
5. Write in a highly technical tone suitable for industry professionals. Do NOT use LaTeX math symbols, backslashes, or dollar signs like $\Delta H$ or \eta. Use plain text, standard HTML, and Unicode symbols (e.g., Δ, Ω, ², ³, °C, η) for all formulas and equations.
6. Make sure you naturally use the words "Electrolyzer" and "Water Treatment" a few times.
"""

print("Generating article via Gemini REST API...", flush=True)
models_to_try = ["gemini-2.0-flash", "gemini-flash-latest", "gemini-2.0-flash-lite"]
html_content = None

for m in models_to_try:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    res = requests.post(url, json=payload, timeout=60)
    if res.status_code == 200:
        result_json = res.json()
        html_content = result_json['candidates'][0]['content']['parts'][0]['text']
        print(f"Successfully generated article using model {m}!", flush=True)
        break
    elif res.status_code == 429:
        print(f"Rate limited on {m}, trying next available model...", flush=True)
    else:
        print(f"Model {m} returned status {res.status_code}.", flush=True)

if not html_content:
    print("ERROR: Could not generate content from any Gemini API model.", flush=True)
    exit(1)

# Clean up any potential markdown formatting the LLM might have slipped in
html_content = html_content.replace('```html', '').replace('```', '').strip()

# Inject Internal SEO Links
html_content = re.sub(r'(?i)\b(electrolyzer[s]?|electrolysis)\b', f'<a href="{WP_URL}/electrolyzer-calculator/" style="color:#0056b3; font-weight:bold;">\\1</a>', html_content, count=2)
html_content = re.sub(r'(?i)\b(water treatment|ultrapure water|water consumption)\b', f'<a href="{WP_URL}/water-consumption-calculator/" style="color:#0056b3; font-weight:bold;">\\1</a>', html_content, count=2)

# Publish to WordPress
print("Publishing to WordPress...", flush=True)
# Category 12 = Technical Articles
payload = {
    "title": topic,
    "content": html_content,
    "status": "publish",
    "categories": [12] 
}

if featured_media_id:
    payload["featured_media"] = featured_media_id

wp_res = requests.post(f"{WP_URL}/wp-json/wp/v2/posts", headers=headers, auth=auth, json=payload)
if wp_res.status_code == 201:
    print(f"SUCCESS: Article '{topic}' has been autonomously published with Featured Media ID {featured_media_id}!", flush=True)
else:
    print(f"ERROR: Failed to publish article. Status: {wp_res.status_code}", flush=True)
    print(wp_res.text, flush=True)
