# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
"""One-off publish for "How Much KOH? Choosing Electrolyte Concentration for
an Alkaline Electrolyzer".

Unlike generate_article.py this does not draft anything — the article body
already exists at article_assets/koh/content.html and the three charts already
exist as PNGs in the same directory. This script only uploads the images,
substitutes their WordPress URLs into the body, and publishes the post. It
reuses the same WP_URL / WP_USERNAME / WP_APP_PASSWORD REST pattern as
generate_article.py and publish_news.py.

Run by .github/workflows/publish_koh_article.yml (workflow_dispatch only —
this is a single article, not a recurring job).
"""
import os
import re
import sys

import requests

import resilient

WP_URL = os.environ.get("WP_URL", "https://www.avoltium.in").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD")

if not all([WP_URL, WP_USERNAME, WP_APP_PASSWORD]):
    print("ERROR: WP_URL, WP_USERNAME and WP_APP_PASSWORD are required.", flush=True)
    sys.exit(1)

AUTH = (WP_USERNAME, WP_APP_PASSWORD)
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "article_assets", "koh")

TITLE = "How Much KOH? Choosing Electrolyte Concentration for an Alkaline Electrolyzer"
SLUG = "koh-concentration-alkaline-electrolyzer"
EXCERPT = (
    "Why alkaline electrolyzers run on 25-30% potassium hydroxide: the "
    "conductivity peak, corrosion limits, freezing point and carbonate "
    "control behind the number."
)
TAGS = ["potassium hydroxide", "alkaline electrolyzer", "electrolyte",
        "water electrolysis", "green hydrogen"]
CATEGORY_NAMES = ["Green Hydrogen", "Electrolyzer Technology", "Technical Articles"]
DEFAULT_CATEGORIES = [10, 8, 12]  # fallback if name lookup fails

IMAGES = [
    ("koh-conductivity-vs-concentration.png",
     "Chart of KOH ionic conductivity versus concentration at 25 C and 80 C "
     "showing the peak near 30 wt%", "__IMG_TRADEOFF__"),
    ("koh-vs-naoh-conductivity.png",
     "Comparison chart showing potassium hydroxide conducts better than "
     "sodium hydroxide across all concentrations at 25 C", "__IMG_NAOH__"),
    ("koh-concentration-tradeoffs.png",
     "Diagram showing which factors push KOH concentration up and which "
     "pull it down, converging on 25 to 30 weight percent", "__IMG_TRADEOFFS_DIAGRAM__"),
]


def upload_image(filename: str, alt: str) -> dict | None:
    path = os.path.join(ASSETS_DIR, filename)
    with open(path, "rb") as f:
        data = f.read()
    headers = {
        "Content-Type": "image/png",
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    res = resilient.request_with_retry(
        "POST", f"{WP_URL}/wp-json/wp/v2/media",
        attempts=3, label=f"wp/media-upload:{filename}",
        headers=headers, auth=AUTH, data=data, timeout=60,
    )
    if res is None or res.status_code != 201:
        print(f"Image upload failed for {filename}: "
              f"{res.status_code if res is not None else 'no response'}", flush=True)
        return None
    media = res.json()
    media_id = media["id"]
    alt_res = resilient.request_with_retry(
        "POST", f"{WP_URL}/wp-json/wp/v2/media/{media_id}",
        attempts=3, label=f"wp/media-alt:{filename}",
        auth=AUTH, json={"alt_text": alt, "title": alt}, timeout=30,
    )
    if alt_res is None or alt_res.status_code != 200:
        print(f"WARNING: alt text not set on media {media_id}", flush=True)
    print(f"Uploaded {filename} -> media {media_id}: {media['source_url']}", flush=True)
    return {"id": media_id, "url": media["source_url"]}


def get_or_create_term(taxonomy: str, name: str) -> int | None:
    res = requests.get(f"{WP_URL}/wp-json/wp/v2/{taxonomy}",
                        params={"search": name, "per_page": 20}, auth=AUTH, timeout=30)
    if res.status_code == 200:
        for term in res.json():
            if term["name"].strip().lower() == name.strip().lower():
                return term["id"]
    res = requests.post(f"{WP_URL}/wp-json/wp/v2/{taxonomy}",
                         auth=AUTH, json={"name": name}, timeout=30)
    if res.status_code == 201:
        return res.json()["id"]
    print(f"WARNING: could not get/create {taxonomy} '{name}': "
          f"{res.status_code} {res.text[:150]}", flush=True)
    return None


def find_category_ids() -> list[int]:
    ids = []
    for name in CATEGORY_NAMES:
        res = requests.get(f"{WP_URL}/wp-json/wp/v2/categories",
                            params={"search": name, "per_page": 20}, auth=AUTH, timeout=30)
        if res.status_code == 200:
            for term in res.json():
                if term["name"].strip().lower() == name.strip().lower():
                    ids.append(term["id"])
                    break
    return ids or DEFAULT_CATEGORIES


def post_exists(slug: str) -> int | None:
    res = requests.get(f"{WP_URL}/wp-json/wp/v2/posts",
                        params={"slug": slug, "status": "publish,draft,pending,future"},
                        auth=AUTH, timeout=30)
    if res.status_code == 200 and res.json():
        return res.json()[0]["id"]
    return None


def build_schema(canonical_url: str, image_url: str, date_str: str) -> str:
    faqs = [
        ("What concentration of KOH is used in alkaline electrolyzers?",
         "Most industrial alkaline electrolyzers run on 25-30 wt% potassium hydroxide in "
         "demineralised water. This band sits close to the peak of the ionic conductivity "
         "curve at typical stack operating temperatures of 70-90 degrees Celsius."),
        ("Why is KOH used instead of NaOH in water electrolysis?",
         "Potassium hydroxide conducts better, is less viscous at equivalent strength, and "
         "forms a more soluble carbonate. Potassium ions carry a lighter hydration shell than "
         "sodium ions, so they move through the solution faster and carry charge more "
         "efficiently."),
        ("Is potassium hydroxide consumed during electrolysis?",
         "No. Water is consumed and split into hydrogen and oxygen. The potassium ion is a "
         "spectator and the hydroxide ion is regenerated at the cathode as fast as it is "
         "consumed at the anode. Only water needs to be replenished."),
        ("Why does electrolyte concentration rise over time?",
         "Because water leaves the system as hydrogen and oxygen while the KOH stays behind, "
         "the remaining solution becomes progressively more concentrated. Demineralised water "
         "is dosed in to hold the setpoint, usually under density or conductivity control."),
        ("What happens if CO2 gets into the electrolyte?",
         "It converts KOH to potassium carbonate, which conducts poorly and can precipitate "
         "inside porous electrodes and diaphragms. Performance degrades gradually. Sealed "
         "circuits, inert gas blanketing and periodic electrolyte analysis are the standard "
         "defences."),
    ]
    import json as _json
    schema = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "TechArticle",
                "headline": TITLE,
                "description": EXCERPT,
                "image": image_url,
                "author": {"@type": "Person", "name": "Arun",
                           "jobTitle": "Mechanical Engineer, Green Hydrogen Systems",
                           "url": "https://avoltium.in/about/"},
                "publisher": {"@type": "Organization", "name": "Avoltium",
                              "url": "https://avoltium.in/"},
                "datePublished": date_str,
                "dateModified": date_str,
                "mainEntityOfPage": canonical_url,
                "proficiencyLevel": "Beginner",
                "about": [
                    {"@type": "Thing", "name": "Potassium hydroxide"},
                    {"@type": "Thing", "name": "Alkaline water electrolysis"},
                    {"@type": "Thing", "name": "Green hydrogen"},
                ],
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {"@type": "Question", "name": q,
                     "acceptedAnswer": {"@type": "Answer", "text": a}}
                    for q, a in faqs
                ],
            },
        ],
    }
    return f'<script type="application/ld+json">\n{_json.dumps(schema, indent=2)}\n</script>'


def main() -> None:
    with open(os.path.join(ASSETS_DIR, "content.html"), encoding="utf-8") as f:
        body = f.read()

    uploads = {}
    for filename, alt, placeholder in IMAGES:
        media = upload_image(filename, alt)
        if media is None:
            print(f"ERROR: could not upload {filename}, aborting.", flush=True)
            sys.exit(1)
        uploads[placeholder] = media

    for placeholder, media in uploads.items():
        body = body.replace(placeholder, media["url"])

    import datetime
    date_str = datetime.date.today().isoformat()
    featured_url = uploads["__IMG_TRADEOFF__"]["url"]
    canonical = f"{WP_URL}/{SLUG}/"
    body += "\n" + build_schema(canonical, featured_url, date_str)

    category_ids = find_category_ids()
    tag_ids = [tid for tid in (get_or_create_term("tags", t) for t in TAGS) if tid]

    payload = {
        "title": TITLE,
        "slug": SLUG,
        "content": body,
        "status": "publish",
        "categories": category_ids,
        "tags": tag_ids,
        "excerpt": EXCERPT,
        "featured_media": uploads["__IMG_TRADEOFF__"]["id"],
    }

    existing_id = post_exists(SLUG)
    if existing_id:
        url = f"{WP_URL}/wp-json/wp/v2/posts/{existing_id}"
        label = "wp/update-post"
    else:
        url = f"{WP_URL}/wp-json/wp/v2/posts"
        label = "wp/create-post"

    res = resilient.request_with_retry(
        "POST", url, attempts=3, label=label, auth=AUTH, json=payload, timeout=60,
    )
    if res is not None and res.status_code in (200, 201):
        link = res.json().get("link")
        print(f"SUCCESS: published at {link}", flush=True)
    else:
        status = res.status_code if res is not None else "no response"
        print(f"ERROR: publish failed — {status}", flush=True)
        if res is not None:
            print(res.text[:500], flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
