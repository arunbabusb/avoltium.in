import os
import requests
import google.generativeai as genai
import random
import re

# Configuration via Environment Variables (Set in GitHub Secrets)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WP_URL = os.environ.get("WP_URL", "https://www.avoltium.in").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD")

if not all([GEMINI_API_KEY, WP_URL, WP_USERNAME, WP_APP_PASSWORD]):
    print("ERROR: Missing required environment variables.")
    exit(1)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-pro')

# Select a random technical topic
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
print(f"Selected Topic: {topic}")

# Generate Article Content
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
5. Write in a highly technical tone suitable for industry professionals. Do not hallucinate statistics, stick to proven engineering physics and thermodynamics.
6. Make sure you naturally use the words "Electrolyzer" and "Water Treatment" a few times.
"""

print("Generating article via Gemini API...")
response = model.generate_content(prompt)
html_content = response.text

# Clean up any potential markdown formatting the LLM might have slipped in
html_content = html_content.replace('```html', '').replace('```', '').strip()

# Inject Internal SEO Links
html_content = re.sub(r'(?i)\\b(electrolyzer[s]?|electrolysis)\\b', f'<a href="{WP_URL}/electrolyzer-calculator/" style="color:#0056b3; font-weight:bold;">\\g<1></a>', html_content, count=2)
html_content = re.sub(r'(?i)\\b(water treatment|ultrapure water|water consumption)\\b', f'<a href="{WP_URL}/water-consumption-calculator/" style="color:#0056b3; font-weight:bold;">\\g<1></a>', html_content, count=2)

# Publish to WordPress
print("Publishing to WordPress...")
headers = {"Content-Type": "application/json"}
auth = (WP_USERNAME, WP_APP_PASSWORD)
# Category 12 = Technical Articles
payload = {
    "title": topic,
    "content": html_content,
    "status": "publish",
    "categories": [12] 
}

wp_res = requests.post(f"{WP_URL}/wp-json/wp/v2/posts", headers=headers, auth=auth, json=payload)
if wp_res.status_code == 201:
    print(f"SUCCESS: Article '{topic}' has been autonomously published!")
else:
    print(f"ERROR: Failed to publish article. Status: {wp_res.status_code}")
    print(wp_res.text)
