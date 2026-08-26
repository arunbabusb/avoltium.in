"""
Audit and Fix All TechJobs360.com Posts
=======================================
1. Identifies missing featured media / company logos.
2. Sideloads high-res logos to WordPress Media Library.
3. Sets `featured_media` on all posts.
4. Cleans up any corrupted HTML tags / broken quote artifacts.
5. Reusable logo cache to prevent duplicate media uploads.
"""

import os
import re
import json
import time
import base64
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

WP_URL = os.getenv("WP_URL", "https://www.techjobs360.com")
WP_USERNAME = os.getenv("WP_USERNAME", "admin")
WP_APP_PASS = os.getenv("WP_APP_PASSWORD", os.getenv("WP_APP_PASS", "vgPl O24r nMOq dRF7 GhBN i9l4"))

COMPANY_DOMAINS = {
    "google": "google.com",
    "microsoft": "microsoft.com",
    "amazon": "amazon.com",
    "meta": "meta.com",
    "apple": "apple.com",
    "netflix": "netflix.com",
    "nvidia": "nvidia.com",
    "tcs": "tcs.com",
    "tata consultancy": "tcs.com",
    "infosys": "infosys.com",
    "wipro": "wipro.com",
    "hcl": "hcltech.com",
    "hcltech": "hcltech.com",
    "hclsoftware": "hcltech.com",
    "cognizant": "cognizant.com",
    "tech mahindra": "techmahindra.com",
    "accenture": "accenture.com",
    "ibm": "ibm.com",
    "capgemini": "capgemini.com",
    "deloitte": "deloitte.com",
    "kpmg": "kpmg.com",
    "pwc": "pwc.com",
    "ey": "ey.com",
    "ernst": "ey.com",
    "oracle": "oracle.com",
    "sap": "sap.com",
    "salesforce": "salesforce.com",
    "servicenow": "servicenow.com",
    "adobe": "adobe.com",
    "cisco": "cisco.com",
    "intel": "intel.com",
    "qualcomm": "qualcomm.com",
    "amd": "amd.com",
    "samsung": "samsung.com",
    "siemens": "siemens.com",
    "bosch": "bosch.com",
    "ericsson": "ericsson.com",
    "nokia": "nokia.com",
    "jp morgan": "jpmorgan.com",
    "goldman sachs": "goldmansachs.com",
    "morgan stanley": "morganstanley.com",
    "citi": "citigroup.com",
    "hsbc": "hsbc.com",
    "barclays": "barclays.com",
    "visa": "visa.com",
    "mastercard": "mastercard.com",
    "flipkart": "flipkart.com",
    "walmart": "walmart.com",
    "swiggy": "swiggy.com",
    "zomato": "zomato.com",
    "paytm": "paytm.com",
    "phonepe": "phonepe.com",
    "razorpay": "razorpay.com",
    "freshworks": "freshworks.com",
    "zoho": "zoho.com",
    "wise": "wise.com",
    "stripe": "stripe.com",
    "paypal": "paypal.com",
    "atlassian": "atlassian.com",
    "dell": "dell.com",
    "hp": "hp.com",
    "lenovo": "lenovo.com",
    "fedex": "fedex.com",
    "vashi": "vashiisl.com",
    "mci": "mci.com",
    "harris": "harris.com",
}

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def wp_headers():
    creds = base64.b64encode(f"{WP_USERNAME}:{WP_APP_PASS}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}

def http_get_json(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8", errors="ignore"))

def http_post_json(url, data, headers=None, timeout=30):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers or {}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8", errors="ignore"))

# Cache of uploaded company logos: company_slug -> media_id
MEDIA_CACHE = {}

def populate_existing_media():
    log("Scanning WordPress Media Library for company logos...")
    try:
        # Fetch latest 100 media items
        media_items = http_get_json(f"{WP_URL}/wp-json/wp/v2/media?per_page=100", wp_headers())
        for m in media_items:
            title = (m.get("title", {}).get("rendered", "") or "").lower()
            slug = (m.get("slug", "") or "").lower()
            source_url = m.get("source_url", "")
            media_id = m.get("id")
            for comp_key in COMPANY_DOMAINS.keys():
                if comp_key in title or comp_key in slug or comp_key in source_url.lower():
                    if comp_key not in MEDIA_CACHE:
                        MEDIA_CACHE[comp_key] = {
                            "id": media_id,
                            "url": source_url
                        }
        log(f"Cached {len(MEDIA_CACHE)} existing company logos from media library: {list(MEDIA_CACHE.keys())}")
    except Exception as e:
        log(f"Failed to scan media library: {e}")

def get_company_domain(company):
    c = (company or "").lower()
    for k, d in COMPANY_DOMAINS.items():
        if k in c:
            return d
    clean = re.sub(r'[^a-z0-9]', '', c.split()[0] if c else "company")
    return f"{clean}.com"

def fetch_logo_bytes(company):
    domain = get_company_domain(company)
    filename = f"{re.sub(r'[^a-z0-9]+', '-', company.lower()).strip('-')}-logo.png"

    sources = [
        f"https://icon.horse/icon/{domain}",
        f"https://icons.duckduckgo.com/ip3/{domain}.ico",
        f"https://www.google.com/s2/favicons?domain={domain}&sz=128",
        f"https://cdn.brandfetch.io/{domain}/w/200/h/200?c=1idT29XbSHRcFf6",
    ]

    import ssl
    ctx = ssl._create_unverified_context()

    for url in sources:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "image/png,image/*,*/*"
            })
            with urllib.request.urlopen(req, context=ctx, timeout=10) as res:
                data = res.read()
                content_type = res.headers.get("Content-Type", "")
                if len(data) > 100 and ("image" in content_type or data[:4] in (b'\x89PNG', b'\xff\xd8\xff', b'GIF8', b'RIFF', b'\x00\x00\x01\x00')):
                    return data, filename
        except Exception:
            continue
    return None, None

def get_or_upload_logo(company):
    c_lower = (company or "").lower().strip()
    # Check cache first
    for k, v in MEDIA_CACHE.items():
        if k in c_lower:
            return v["id"], v["url"]

    # Not cached, fetch and upload
    log(f"  Downloading & uploading new logo for '{company}'...")
    img_data, filename = fetch_logo_bytes(company)
    if not img_data:
        log(f"  [WARN] Could not download logo for {company}")
        return None, None

    try:
        creds = base64.b64encode(f"{WP_USERNAME}:{WP_APP_PASS}".encode()).decode()
        headers = {
            "Authorization": f"Basic {creds}",
            "Content-Type": "image/png",
            "Content-Disposition": f'attachment; filename="{filename}"',
        }
        req = urllib.request.Request(
            f"{WP_URL}/wp-json/wp/v2/media",
            data=img_data,
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as res:
            media = json.loads(res.read().decode("utf-8", errors="ignore"))
            media_id = media.get("id")
            source_url = media.get("source_url", "")
            if media_id:
                # Add to cache
                for k in COMPANY_DOMAINS.keys():
                    if k in c_lower:
                        MEDIA_CACHE[k] = {"id": media_id, "url": source_url}
                        break
                MEDIA_CACHE[c_lower] = {"id": media_id, "url": source_url}
                log(f"  [SUCCESS] Uploaded {filename} -> Media ID {media_id}")
                return media_id, source_url
    except Exception as e:
        log(f"  [ERR] Media upload failed for {company}: {e}")
    return None, None

def extract_company_from_title(title):
    # e.g. "Software Engineer at Google" or "Java Developer - Wipro"
    if " at " in title:
        parts = title.split(" at ")
        return parts[-1].strip()
    if " - " in title:
        parts = title.split(" - ")
        return parts[-1].strip()
    if " | " in title:
        parts = title.split(" | ")
        return parts[-1].strip()
    return ""

def clean_post_content(content, company, logo_url):
    """
    Cleans up any corrupted HTML tags like `<p>&#8216;;&#8221; style=...`
    and ensures clean logo display.
    """
    if not content:
        return content

    # Fix corrupted quote / style artifacts
    cleaned = re.sub(r'<p>\s*&#8216;;&#8221;\s*style=&#8221;[^"]*&#8221;\s*/>\s*</p>', '', content, flags=re.IGNORECASE)
    cleaned = re.sub(r'&#8216;;&#8221;\s*style=&#8221;[^"]*&#8221;\s*/>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'<p>\s*\'\s*;\s*"\s*style="[^"]*"\s*/>\s*</p>', '', cleaned, flags=re.IGNORECASE)

    # Fix corrupted checkmark symbol (replacement character)
    cleaned = cleaned.replace('title="Verified Top Tech Employer"><', 'title="Verified Top Tech Employer">✓<')
    cleaned = cleaned.replace('><', '>✓<')

    # Update logo src if we have a proper local logo URL
    if logo_url:
        # Replace existing logo img src in header
        cleaned = re.sub(
            r'(<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;padding:6px;[^>]*>.*?<img[^>]*src=")[^"]+(")',
            rf'\g<1>{logo_url}\g<2>',
            cleaned,
            flags=re.DOTALL
        )

    return cleaned

def audit_and_fix_all():
    populate_existing_media()
    
    log("\nFetching all published posts from TechJobs360...")
    all_posts = []
    page = 1
    while True:
        try:
            url = f"{WP_URL}/wp-json/wp/v2/posts?per_page=50&page={page}&status=publish"
            posts = http_get_json(url, wp_headers())
            if not posts:
                break
            all_posts.extend(posts)
            if len(posts) < 50:
                break
            page += 1
        except urllib.error.HTTPError as e:
            if e.code == 400: # Beyond max pages
                break
            log(f"Error fetching page {page}: {e}")
            break
        except Exception as e:
            log(f"Error fetching page {page}: {e}")
            break

    log(f"Found {len(all_posts)} published posts to audit.")

    fixed_featured = 0
    fixed_content = 0

    for idx, post in enumerate(all_posts, 1):
        post_id = post["id"]
        raw_title = post.get("title", {}).get("rendered", "")
        # Decode HTML entities in title for analysis
        title = raw_title.replace("&#8211;", "–").replace("&#038;", "&").replace("&amp;", "&")
        company = extract_company_from_title(title)
        featured_id = post.get("featured_media", 0)
        content = post.get("content", {}).get("rendered", "")

        needs_update = False
        update_payload = {}

        log(f"\n[{idx}/{len(all_posts)}] Post #{post_id}: '{title}'")
        log(f"  Detected Company: '{company}' | Current Featured Media: {featured_id}")

        # 1. Check / Fix Featured Media & Logo
        logo_url = None
        if company:
            media_id, logo_url = get_or_upload_logo(company)
            if media_id and featured_id != media_id:
                log(f"  -> Setting Featured Media to ID {media_id} ({logo_url})")
                update_payload["featured_media"] = media_id
                needs_update = True
                fixed_featured += 1

        # 2. Check / Clean Content
        new_content = clean_post_content(content, company, logo_url)
        if new_content != content:
            log(f"  -> Cleaned corrupted HTML artifacts & updated logo in content")
            update_payload["content"] = new_content
            needs_update = True
            fixed_content += 1

        # 3. Apply update if needed
        if needs_update:
            try:
                res = http_post_json(f"{WP_URL}/wp-json/wp/v2/posts/{post_id}", update_payload, wp_headers())
                log(f"  [SUCCESS] Post #{post_id} updated successfully!")
            except Exception as e:
                log(f"  [ERROR] Failed to update post #{post_id}: {e}")
        else:
            log(f"  [OK] Post #{post_id} is already in perfect condition.")

        time.sleep(0.5)

    log("\n" + "=" * 60)
    log(f"Audit Complete!")
    log(f"Total Posts Audited: {len(all_posts)}")
    log(f"Featured Media Fixed: {fixed_featured}")
    log(f"Content Cleaned: {fixed_content}")
    log("=" * 60)

if __name__ == "__main__":
    audit_and_fix_all()
