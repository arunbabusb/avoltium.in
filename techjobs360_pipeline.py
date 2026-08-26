"""
TechJobs360.com — MNC Jobs Pipeline (LinkedIn Public API, No Apify)
====================================================================
Uses LinkedIn's public guest API to fetch FULL job descriptions
for reputed MNC companies in India. No API key, no cost.

Usage:
    python techjobs360_pipeline.py

Schedule daily with Windows Task Scheduler.
"""

import os
import re
import json
import time
import base64
import random
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from html.parser import HTMLParser

# ─── CONFIG ────────────────────────────────────────────────────────────────────
# Automatically load from local .env if present
if os.path.exists(".env"):
    try:
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
    except Exception:
        pass

WP_URL      = os.getenv("TECHJOBS_WP_URL",      os.getenv("WP_URL", "https://www.techjobs360.com"))
WP_USERNAME = os.getenv("TECHJOBS_WP_USERNAME", os.getenv("WP_USERNAME", "admin"))
WP_APP_PASS = os.getenv("TECHJOBS_WP_APP_PASSWORD", os.getenv("WP_APP_PASSWORD", os.getenv("WP_APP_PASS", "vgPl O24r nMOq dRF7 GhBN i9l4")))

MAX_JOBS_PER_QUERY = 10   # jobs to fetch per search query
MAX_PUBLISH        = 30   # max to publish per run

# MNC-targeted search queries for India
JOB_QUERIES = [
    "software engineer Google India",
    "software engineer Microsoft India",
    "software engineer Amazon India",
    "software engineer Accenture India",
    "software engineer TCS India",
    "software engineer Infosys India",
    "software engineer Wipro India",
    "software engineer Cognizant India",
    "software engineer IBM India",
    "software engineer Capgemini India",
    "software engineer Oracle India",
    "software engineer SAP India",
    "software engineer Deloitte India",
    "software engineer Goldman Sachs India",
    "software engineer JP Morgan India",
    "software engineer Cisco India",
    "software engineer Intel India",
    "software engineer Qualcomm India",
    "software engineer Samsung India",
    "data scientist Flipkart India",
    "software engineer Walmart India",
    "software engineer Adobe India",
    "software engineer Salesforce India",
    "software engineer HCL India",
]

# ─── MNC WHITELIST ─────────────────────────────────────────────────────────────
MNC_COMPANIES = {
    "google","alphabet","microsoft","amazon","meta","apple","netflix","nvidia","tesla","spacex",
    "tcs","tata","infosys","wipro","hcl","hcltech","cognizant","tech mahindra","mphasis",
    "hexaware","coforge","ltimindtree","persistent","mindtree","birlasoft","zensar","cyient","kpit",
    "accenture","ibm","capgemini","atos","dxc","ntt data","fujitsu","thoughtworks","publicis",
    "deloitte","kpmg","pwc","ey","ernst","mckinsey","bcg","bain","kearney","gartner",
    "oracle","sap","salesforce","servicenow","workday","adobe","autodesk","vmware",
    "cisco","intel","qualcomm","amd","broadcom","samsung","siemens","bosch","ericsson","nokia",
    "jp morgan","goldman sachs","morgan stanley","citi","hsbc","barclays","hdfc","icici",
    "axis bank","kotak","visa","mastercard","american express","blackrock",
    "flipkart","walmart","swiggy","zomato","paytm","phonepe","razorpay","freshworks","zoho",
    "charles schwab","wise","stripe","paypal","atlassian","slack","zoom","hubspot","zendesk",
    "dell","hp","lenovo","sony","lg","panasonic","motorola","zebra",
    "pfizer","novartis","johnson","abbott","ge healthcare","philips","airtel","jio",
    "ola","uber","delhivery","fedex","dhl","tata motors","maruti","hyundai",
    "honeywell","schneider","abb","3m","emerson","caterpillar","cummins",
    "naukri","info edge","quess","teamlease","adecco","manpower",
    "byju","unacademy","upgrad","vedantu","scaler","great learning","coursera",
    "meesho","nykaa","myntra","snapdeal",
}

INDIA_KEYWORDS = [
    "india","bengaluru","bangalore","mumbai","delhi","hyderabad","pune",
    "chennai","kolkata","noida","gurgaon","gurugram","ahmedabad","kochi",
    "coimbatore","chandigarh","jaipur","indore","bhopal","nagpur",
]

SKIP_TITLES = {
    "general apply","apply now","job opening","careers","general opportunity",
    "general consideration","employment opportunities","interdisciplinary",
    "maintenance","cashier","labor","build your own role","general interest",
    "resume inbox","growth","full-time and part-time",
}

# ─── HELPERS ───────────────────────────────────────────────────────────────────

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def wp_headers():
    creds = base64.b64encode(f"{WP_USERNAME}:{WP_APP_PASS}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}

def is_mnc(company):
    name = (company or "").lower()
    return any(m in name for m in MNC_COMPANIES)

def is_india(location):
    if not location:
        return True
    loc = location.lower()
    return any(k in loc for k in INDIA_KEYWORDS)

def http_get(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read().decode("utf-8", errors="ignore")

def http_get_json(url, headers=None, timeout=20):
    return json.loads(http_get(url, headers, timeout))

def http_post_json(url, data, headers=None, timeout=20):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers or {}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read())

# ─── LINKEDIN PUBLIC GUEST API ─────────────────────────────────────────────────

# Browser-like headers to avoid blocks
LI_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/127.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.linkedin.com/jobs/search/",
}

import html

def strip_html(html_text):
    """Remove HTML tags, decode all entities, normalize whitespace."""
    if not html_text:
        return ""
    # Remove script/style blocks
    clean = re.sub(r'<(script|style)[^>]*>.*?</(script|style)>', '', html_text, flags=re.DOTALL)
    # Remove all HTML tags
    clean = re.sub(r'<[^>]+>', ' ', clean)
    # Fully unescape HTML entities (both named and numeric)
    clean = html.unescape(clean)
    # Normalize special unicode spaces and dashes
    clean = clean.replace('\xa0', ' ').replace('\u2013', '–').replace('\u2014', '—')
    # Clean whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

def clean_role_title(raw_title, company):
    """Clean and standardize the job role title before appending company."""
    title = strip_html(raw_title)
    # Remove redundant company suffixes if already in title (e.g. 'Software Engineer - Google')
    comp_esc = re.escape(company.strip())
    title = re.sub(rf'\s*[-|–—]\s*{comp_esc}.*$', '', title, flags=re.IGNORECASE).strip()
    title = re.sub(rf'\s+at\s+{comp_esc}.*$', '', title, flags=re.IGNORECASE).strip()
    # Remove leading special characters or bullet points
    title = re.sub(r'^[^a-zA-Z0-9(]+', '', title).strip()
    return title or raw_title.strip()

def search_linkedin_jobs(query, location="India", count=10):
    """Search LinkedIn public job listings — no login required."""
    encoded_query = urllib.parse.quote(query)
    encoded_loc   = urllib.parse.quote(location)
    # LinkedIn guest search API
    url = (
        f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?"
        f"keywords={encoded_query}&location={encoded_loc}"
        f"&geoId=102713980&f_TPR=r604800&start=0&count={count}"
    )
    try:
        html = http_get(url, LI_HEADERS)
        # Extract job IDs from the HTML
        job_ids = re.findall(r'data-entity-urn="urn:li:jobPosting:(\d+)"', html)
        if not job_ids:
            # Try alternate pattern
            job_ids = re.findall(r'"jobPostingId":"(\d+)"', html)
        if not job_ids:
            job_ids = re.findall(r'/jobs/view/(\d+)/', html)
        log(f"   Found {len(job_ids)} job IDs")
        return list(set(job_ids))[:count]
    except Exception as e:
        log(f"   LinkedIn search error: {e}")
        return []

def get_linkedin_job_detail(job_id):
    """Fetch full job details from LinkedIn public job posting page."""
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    try:
        html = http_get(url, LI_HEADERS)

        # Extract title
        title_m = re.search(r'<h2[^>]*class="[^"]*top-card-layout__title[^"]*"[^>]*>(.*?)</h2>', html, re.DOTALL)
        title = strip_html(title_m.group(1)) if title_m else ""

        # Extract company
        company_m = re.search(r'<a[^>]*class="[^"]*topcard__org-name-link[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL)
        if not company_m:
            company_m = re.search(r'<span[^>]*class="[^"]*topcard__flavor[^"]*"[^>]*>(.*?)</span>', html, re.DOTALL)
        company = strip_html(company_m.group(1)) if company_m else ""

        # Extract location
        loc_m = re.search(r'<span[^>]*class="[^"]*topcard__flavor--bullet[^"]*"[^>]*>(.*?)</span>', html, re.DOTALL)
        location = strip_html(loc_m.group(1)) if loc_m else ""

        # Extract description (full)
        desc_m = re.search(r'<div[^>]*class="[^"]*description__text[^"]*"[^>]*>(.*?)</div\s*>', html, re.DOTALL)
        if not desc_m:
            desc_m = re.search(r'<section[^>]*class="[^"]*description[^"]*"[^>]*>(.*?)</section>', html, re.DOTALL)
        description = strip_html(desc_m.group(1)) if desc_m else ""

        # Extract criteria (job type, seniority, etc.)
        criteria = {}
        crit_items = re.findall(
            r'<li[^>]*class="[^"]*description__job-criteria-item[^"]*"[^>]*>.*?'
            r'<h3[^>]*>(.*?)</h3>.*?<span[^>]*>(.*?)</span>.*?</li>',
            html, re.DOTALL
        )
        for label, value in crit_items:
            criteria[strip_html(label).lower()] = strip_html(value)

        job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"

        return {
            "id": job_id,
            "title": title,
            "company": company,
            "location": location,
            "description": description,
            "url": job_url,
            "job_type": criteria.get("employment type", criteria.get("job type", "")),
            "seniority": criteria.get("seniority level", ""),
            "industry": criteria.get("industries", ""),
            "functions": criteria.get("job function", ""),
        }
    except Exception as e:
        log(f"   Job detail error for {job_id}: {e}")
        return None

# ─── WORDPRESS ─────────────────────────────────────────────────────────────────

def job_exists_on_wp(title):
    enc = urllib.parse.quote(title[:50])
    try:
        posts = http_get_json(
            f"{WP_URL}/wp-json/wp/v2/posts?search={enc}&per_page=5",
            wp_headers()
        )
        for p in posts:
            if title.lower()[:35] in p["title"]["rendered"].lower():
                return True
    except:
        pass
    return False

# ─── COMPANY LOGOS (Clearbit API — free, no key needed) ───────────────────────

# Maps company name keywords → their official domain for logo lookup
COMPANY_DOMAINS = {
    "google": "google.com",       "alphabet": "abc.xyz",
    "microsoft": "microsoft.com", "amazon": "amazon.com",
    "meta": "meta.com",           "apple": "apple.com",
    "netflix": "netflix.com",     "nvidia": "nvidia.com",
    "ibm": "ibm.com",             "accenture": "accenture.com",
    "tcs": "tcs.com",             "infosys": "infosys.com",
    "wipro": "wipro.com",         "hcl": "hcltech.com",
    "cognizant": "cognizant.com", "tech mahindra": "techmahindra.com",
    "capgemini": "capgemini.com", "oracle": "oracle.com",
    "sap": "sap.com",             "cisco": "cisco.com",
    "intel": "intel.com",         "qualcomm": "qualcomm.com",
    "samsung": "samsung.com",     "sony": "sony.com",
    "deloitte": "deloitte.com",   "kpmg": "kpmg.com",           "pwc": "pwc.com",
    "ey": "ey.com",               "mckinsey": "mckinsey.com",   "bcg": "bcg.com",
    "goldman sachs": "goldmansachs.com", "jp morgan": "jpmorgan.com",
    "morgan stanley": "morganstanley.com", "wells fargo": "wellsfargo.com",
    "barclays": "barclays.com",   "hsbc": "hsbc.com",           "citi": "citi.com",
    "visa": "visa.com",           "mastercard": "mastercard.com","american express": "americanexpress.com",
    "adobe": "adobe.com",         "salesforce": "salesforce.com","servicenow": "servicenow.com",
    "atlassian": "atlassian.com", "vmware": "vmware.com",       "broadcom": "broadcom.com",
    "amd": "amd.com",             "flipkart": "flipkart.com",   "walmart": "walmart.com",
    "swiggy": "swiggy.com",       "zomato": "zomato.com",       "meesho": "meesho.com",
    "zerodha": "zerodha.com",     "cred": "cred.club",          "freshworks": "freshworks.com",
    "zoho": "zoho.com",           "razorpay": "razorpay.com",   "phonepe": "phonepe.com",
    "paytm": "paytm.com",         "wise": "wise.com",           "stripe": "stripe.com",
    "paypal": "paypal.com",       "charles schwab": "schwab.com",
    "airtel": "airtel.in",        "jio": "jio.com",
    "uber": "uber.com",           "ola": "olacabs.com",
    "honeywell": "honeywell.com", "siemens": "siemens.com",
    "bosch": "bosch.com",         "dell": "dell.com",
    "hp": "hp.com",               "lenovo": "lenovo.com",
}

def get_company_domain(company):
    """Map company name to domain for logo lookup."""
    name = company.lower()
    for keyword, domain in COMPANY_DOMAINS.items():
        if keyword in name:
            return domain
    # Fallback: guess domain from company name
    clean = re.sub(r'[^a-z0-9]', '', name.split()[0])
    return f"{clean}.com"

# Cache of uploaded company logos: company_slug -> {"id": media_id, "url": source_url}
MEDIA_CACHE = {}

def populate_existing_media():
    """Scan WP Media library to reuse already-uploaded company logos."""
    log("Scanning WordPress Media Library for existing company logos...")
    try:
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
        log(f"Cached {len(MEDIA_CACHE)} existing company logos from media library.")
    except Exception as e:
        log(f"Note: could not preload media cache: {e}")

def fetch_logo_bytes(company):
    """
    Fetch company logo. Tries multiple reliable sources:
    1. icon.horse (Clean high-res PNG for any domain)
    2. DuckDuckGo icon cache
    3. Google Favicons (128px)
    4. Brandfetch CDN
    Returns (bytes, filename) or (None, None).
    """
    domain = get_company_domain(company)
    filename = f"{re.sub(r'[^a-z0-9]+', '-', company.lower()).strip('-')}-logo.png"

    sources = [
        f"https://icon.horse/icon/{domain}",
        f"https://icons.duckduckgo.com/ip3/{domain}.ico",
        f"https://www.google.com/s2/favicons?domain={domain}&sz=128",
        f"https://cdn.brandfetch.io/{domain}/w/200/h/200?c=1idT29XbSHRcFf6",
        f"https://ui-avatars.com/api/?name={urllib.parse.quote(company)}&size=200&background=2563eb&color=fff&bold=true&format=png",
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
    """Get existing media ID/URL or upload new company logo to WP. Returns (media_id, url)."""
    c_lower = (company or "").lower().strip()
    # Check cache first
    for k, v in MEDIA_CACHE.items():
        if k in c_lower:
            return v["id"], v["url"]

    # Not cached, fetch and upload
    log(f"   [LOGO] Downloading & uploading new logo for '{company}'...")
    img_data, filename = fetch_logo_bytes(company)
    if not img_data:
        log(f"   [WARN] Could not download logo for {company}")
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
                for k in COMPANY_DOMAINS.keys():
                    if k in c_lower:
                        MEDIA_CACHE[k] = {"id": media_id, "url": source_url}
                        break
                MEDIA_CACHE[c_lower] = {"id": media_id, "url": source_url}
                log(f"   [LOGO] Uploaded {filename} -> Media ID {media_id}")
                return media_id, source_url
    except Exception as e:
        log(f"   [ERR] Media upload failed for {company}: {e}")
    return None, None


# ─── CATEGORY & SCHEMA HELPERS ──────────────────────────────────────────────────

CATEGORY_CACHE = {}

def get_or_create_category(company):
    """Find or create WordPress category for the company (e.g., 'IBM Jobs')."""
    if not company:
        return None
    comp_clean = company.strip()
    cat_name = f"{comp_clean} Jobs"
    if cat_name in CATEGORY_CACHE:
        return CATEGORY_CACHE[cat_name]

    try:
        # Check existing categories
        cats = http_get_json(f"{WP_URL}/wp-json/wp/v2/categories?search={urllib.parse.quote(comp_clean)}&per_page=10", wp_headers())
        for c in cats:
            if c["name"].lower() == cat_name.lower() or c["name"].lower() == comp_clean.lower():
                CATEGORY_CACHE[cat_name] = c["id"]
                return c["id"]

        # Create new category
        slug = re.sub(r'[^a-z0-9]+', '-', cat_name.lower()).strip('-')
        new_cat = http_post_json(
            f"{WP_URL}/wp-json/wp/v2/categories",
            {
                "name": cat_name,
                "slug": slug,
                "description": f"Latest {comp_clean} job openings in India."
            },
            wp_headers()
        )
        cat_id = new_cat.get("id")
        if cat_id:
            CATEGORY_CACHE[cat_name] = cat_id
            log(f"   [CAT] Created category '{cat_name}' (ID: {cat_id})")
            return cat_id
    except Exception as e:
        log(f"   [CAT] Error resolving category for {company}: {e}")
    return None

def build_job_posting_schema(job, logo_url=""):
    """Generate Schema.org JobPosting JSON-LD for Google Jobs rich results."""
    domain = get_company_domain(job["company"])
    desc = job.get("description") or f"Job opening for {job['title']} at {job['company']} in {job['location']}."
    desc_clean = re.sub(r'<[^>]+>', ' ', desc).strip()
    
    schema = {
        "@context": "https://schema.org/",
        "@type": "JobPosting",
        "title": job["title"],
        "description": desc_clean,
        "datePosted": datetime.utcnow().strftime("%Y-%m-%d"),
        "employmentType": "FULL_TIME",
        "hiringOrganization": {
            "@type": "Organization",
            "name": job["company"],
            "sameAs": f"https://www.{domain}",
        },
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": job["location"] or "India",
                "addressCountry": "IN"
            }
        },
        "directApply": True
    }
    if logo_url:
        schema["hiringOrganization"]["logo"] = logo_url
    return f'\n\n<script type="application/ld+json">\n{json.dumps(schema, indent=2)}\n</script>'

def build_post_content(job, logo_url=""):
    apply_btn = (
        f'<a href="{job["url"]}" target="_blank" rel="noopener nofollow" '
        f'style="display:inline-block;background:#2563eb;color:#ffffff;'
        f'padding:14px 32px;border-radius:8px;text-decoration:none;'
        f'font-weight:700;font-size:16px;box-shadow:0 4px 12px rgba(37,99,235,0.3);">'
        f'Apply on Company Website &rarr;</a>'
    ) if job.get("url") else ""

    comp_clean = job["company"].strip()
    
    logo_img = f'<img src="{logo_url}" alt="{comp_clean} logo" class="no-lazy skip-lazy" data-no-lazy="1" loading="eager" decoding="async" style="max-height:52px;max-width:52px;width:auto;height:auto;object-fit:contain;display:block;"/>' if logo_url else ''
    
    logo_element = (
        f'<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;padding:6px;'
        f'display:flex;align-items:center;justify-content:center;width:68px;height:68px;'
        f'box-shadow:0 2px 8px rgba(0,0,0,0.06);flex-shrink:0;">'
        f'{logo_img}'
        f'</div>'
    ) if logo_url else ""

    comp_slug = re.sub(r'[^a-z0-9]+', '-', job["company"].lower()).strip('-')
    company_hub_url = f"{WP_URL}/category/{comp_slug}-jobs/"

    # Metadata Pills
    pills = [
        f'<span style="background:#f1f5f9;color:#334155;padding:6px 14px;border-radius:20px;font-size:13.5px;font-weight:600;display:inline-flex;align-items:center;gap:6px;">📍 {job["location"]}</span>',
        f'<span style="background:#eff6ff;color:#1d4ed8;padding:6px 14px;border-radius:20px;font-size:13.5px;font-weight:600;display:inline-flex;align-items:center;gap:6px;">💼 {job.get("job_type") or "Full-time"}</span>',
    ]
    if job.get("seniority"):
        pills.append(f'<span style="background:#faf5ff;color:#7e22ce;padding:6px 14px;border-radius:20px;font-size:13.5px;font-weight:600;display:inline-flex;align-items:center;gap:6px;">📈 {job["seniority"]}</span>')
    if job.get("industry"):
        pills.append(f'<span style="background:#f0fdf4;color:#15803d;padding:6px 14px;border-radius:20px;font-size:13.5px;font-weight:600;display:inline-flex;align-items:center;gap:6px;">🏢 {job["industry"]}</span>')
    pills_html = " ".join(pills)

    description = job.get("description") or "View full job description by clicking Apply Now."
    desc_html = "".join(
        f"<p style='margin:0 0 16px;line-height:1.8;color:#334155;font-size:16px;'>{p.strip()}</p>"
        for p in description.split(". ")
        if len(p.strip()) > 15
    ) if len(description) < 500 else f"<div style='line-height:1.8;color:#334155;font-size:16px;'>{description}</div>"

    schema_json = build_job_posting_schema(job, logo_url)

    return f"""<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:920px;margin:0 auto;line-height:1.7;">

<!-- Hero Employer Header -->
<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;padding:24px 28px;margin-bottom:24px;box-shadow:0 2px 10px rgba(0,0,0,0.03);">
  <div style="display:flex;align-items:center;gap:18px;margin-bottom:16px;flex-wrap:wrap;">
    {logo_element}
    <div>
      <h2 style="margin:0 0 4px;font-size:22px;color:#0f172a;font-weight:700;">
        <a href="{company_hub_url}" style="color:#0f172a;text-decoration:none;">{job["company"]}</a>
        <span style="color:#2563eb;font-size:16px;margin-left:4px;" title="Verified Top Tech Employer">✓</span>
      </h2>
      <p style="margin:0;color:#64748b;font-size:14.5px;font-weight:500;">Direct Tech Hiring &bull; Verified Opening</p>
    </div>
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px;">
    {pills_html}
  </div>
  <div>
    {apply_btn}
  </div>
</div>

<!-- Job Alerts Community Bar -->
<div style="margin:0 0 24px;padding:16px 20px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
  <div>
    <strong style="color:#15803d;font-size:15px;">🔔 Instant Tech Job Alerts</strong>
    <span style="color:#166534;font-size:13.5px;display:block;margin-top:2px;">Join 25,000+ job seekers for daily verified MNC & off-campus drives.</span>
  </div>
  <div style="display:flex;gap:10px;flex-wrap:wrap;">
    <a href="https://t.me/techjobs360" target="_blank" rel="noopener" style="background:#0284c7;color:#ffffff;padding:7px 16px;border-radius:6px;text-decoration:none;font-weight:700;font-size:13px;display:inline-flex;align-items:center;gap:6px;">✈️ Telegram</a>
    <a href="https://whatsapp.com/channel/0029Va4T360" target="_blank" rel="noopener" style="background:#25D366;color:#ffffff;padding:7px 16px;border-radius:6px;text-decoration:none;font-weight:700;font-size:13px;display:inline-flex;align-items:center;gap:6px;">💬 WhatsApp</a>
  </div>
</div>

<!-- Job Description Section -->
<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;padding:28px 32px;margin-bottom:24px;box-shadow:0 2px 10px rgba(0,0,0,0.03);">
  <h3 style="color:#0f172a;border-bottom:2px solid #2563eb;padding-bottom:10px;font-size:20px;margin-top:0;font-weight:700;">About This Role & Detailed Responsibilities</h3>
  <div style="line-height:1.8;color:#334155;font-size:16.5px;margin-top:16px;">
    {desc_html}
  </div>
</div>

<!-- Action Box -->
<div style="margin-top:32px;padding:28px;background:#f0f9ff;border-radius:14px;border:1px solid #bae6fd;text-align:center;">
  <p style="margin:0 0 16px;font-weight:700;color:#0369a1;font-size:18px;">Ready to Take the Next Step in Your Career?</p>
  {apply_btn}
  <div style="margin-top:16px;display:flex;justify-content:center;gap:12px;flex-wrap:wrap;">
    <a href="https://api.whatsapp.com/send?text=🔥+Hiring+at+{urllib.parse.quote(job['company'])}+-+{urllib.parse.quote(job['title'])}+in+{urllib.parse.quote(job['location'])}!+Apply+here:+{WP_URL}/" target="_blank" rel="noopener" style="background:#25D366;color:#ffffff;padding:9px 18px;border-radius:6px;text-decoration:none;font-weight:600;font-size:13.5px;">💬 Share with Friends on WhatsApp</a>
  </div>
</div>

<!-- Related Openings -->
<div style="margin-top:28px;padding:20px 24px;background:#f8fafc;border-radius:12px;border:1px solid #e2e8f0;">
  <h4 style="margin:0 0 10px;color:#0f172a;font-size:16px;font-weight:700;">🔍 Explore Related Job Openings:</h4>
  <ul style="margin:0;padding-left:20px;line-height:2.1;color:#2563eb;font-size:15px;">
    <li><a href="{company_hub_url}" style="color:#2563eb;text-decoration:none;font-weight:600;">More {job["company"]} Jobs & Careers in India &rarr;</a></li>
    <li><a href="{WP_URL}/" style="color:#2563eb;text-decoration:none;">Browse All Fresh Off-Campus & MNC Tech Drives &rarr;</a></li>
  </ul>
</div>

{schema_json}
</div>"""

def publish_job(job):
    if not job.get("title") or not job.get("company"):
        return False

    # Quality gate 1: skip generic titles
    if job["title"].lower().strip() in SKIP_TITLES:
        log(f"   [SKIP] Generic title: {job['title']}")
        return False

    # Quality gate 2: MNC/reputed company only
    if not is_mnc(job["company"]):
        log(f"   [FILTER] Not MNC: {job['company']}")
        return False

    # Quality gate 3: India location only
    if not is_india(job["location"]):
        log(f"   [FILTER] Not India: {job['location']}")
        return False

    # Quality gate 4: must have substantive description
    if len(job.get("description", "").strip()) < 80:
        log(f"   [SKIP] Description too short for: {job['title']} at {job['company']}")
        return False

    # Standardize title format
    role = clean_role_title(job["title"], job["company"])
    full_title = f"{role} at {job['company']}"

# ─── TELEGRAM & INSTANT INDEXING HOOKS ──────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "@techjobs360")
INDEXNOW_KEY       = os.getenv("INDEXNOW_KEY", "d8f5c3a4e9b2478190c1f5e8a7b3c2d1")
GOOGLE_SERVICE_KEY = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "service_account.json")

def broadcast_to_telegram(job, post_url, logo_url=""):
    """Broadcast newly published job to Telegram channel with rich photo card."""
    if not TELEGRAM_BOT_TOKEN:
        return
    
    role = clean_role_title(job.get("title", ""), job.get("company", ""))
    company = job.get("company", "")
    location = job.get("location") or "India"
    job_type = job.get("job_type") or "Full-time"
    
    caption = (
        f"🔥 <b>{role} at {company}</b>\n\n"
        f"🏢 <b>Company:</b> {company} ✓\n"
        f"📍 <b>Location:</b> {location}\n"
        f"💼 <b>Job Type:</b> {job_type}\n\n"
        f"🚀 <b>Direct Application & Details:</b>\n"
        f"👉 <a href=\"{post_url}\">Click Here to Apply on TechJobs360</a>\n\n"
        f"🔔 <i>Join @techjobs360 for daily verified MNC & off-campus tech drives!</i>\n"
        f"#TechJobs #{company.replace(' ', '')} #Hiring #IndiaTechJobs"
    )

    inline_keyboard = {
        "inline_keyboard": [
            [{"text": "🚀 Apply on TechJobs360", "url": post_url}],
            [{"text": "✈️ Join Telegram Channel", "url": "https://t.me/techjobs360"}]
        ]
    }

    try:
        if logo_url and logo_url.startswith("http"):
            # Send photo with formatted caption
            tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "photo": logo_url,
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": inline_keyboard
            }
        else:
            # Fallback to text message
            tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": caption,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
                "reply_markup": inline_keyboard
            }

        req = urllib.request.Request(
            tg_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as res:
            log(f"   [TELEGRAM] Broadcast sent to {TELEGRAM_CHAT_ID} (HTTP {res.status})")
    except Exception as e:
        log(f"   [TELEGRAM] Broadcast notice: {e}")

def instant_index_url(post_url):
    """Instant index post across Bing, Yahoo, Yandex, and Google."""
    if not post_url:
        return

    # 1. IndexNow Submission (Bing, Yahoo, Yandex, Naver, Seznam)
    try:
        indexnow_url = "https://api.indexnow.org/indexnow"
        host = urllib.parse.urlparse(WP_URL).netloc
        payload = {
            "host": host,
            "key": INDEXNOW_KEY,
            "keyLocation": f"{WP_URL}/{INDEXNOW_KEY}.txt",
            "urlList": [post_url]
        }
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        }
        req = urllib.request.Request(
            indexnow_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            log(f"   [INDEXNOW] Instant indexing submitted for {post_url} (HTTP {res.status})")
    except Exception as e:
        log(f"   [INDEXNOW] Submission note: {e}")

    # 2. Google Indexing API (If Service Account JSON is present)
    service_file = GOOGLE_SERVICE_KEY if os.path.exists(GOOGLE_SERVICE_KEY) else None
    if service_file:
        try:
            from google.oauth2 import service_account
            import google.auth.transport.requests
            
            SCOPES = ["https://www.googleapis.com/auth/indexing"]
            credentials = service_account.Credentials.from_service_account_file(service_file, scopes=SCOPES)
            authed_session = google.auth.transport.requests.AuthorizedSession(credentials)
            
            endpoint = "https://indexing.googleapis.com/v3/urlNotifications:publish"
            body = {"url": post_url, "type": "URL_UPDATED"}
            response = authed_session.post(endpoint, json=body, timeout=15)
            log(f"   [GOOGLE INDEXING] Submitted to Google Jobs Indexing API: {post_url} (HTTP {response.status_code})")
        except Exception as e:
            log(f"   [GOOGLE INDEXING] Note: {e}")

    # 3. Google & Bing Sitemap Ping
    try:
        sitemap_url = f"{WP_URL}/sitemap_index.xml"
        urllib.request.urlopen(f"https://www.google.com/ping?sitemap={urllib.parse.quote(sitemap_url)}", timeout=5)
        urllib.request.urlopen(f"https://www.bing.com/ping?sitemap={urllib.parse.quote(sitemap_url)}", timeout=5)
    except Exception:
        pass


def publish_job(job):
    if not job.get("title") or not job.get("company"):
        return False

    # Quality gate 1: skip generic titles
    if job["title"].lower().strip() in SKIP_TITLES:
        log(f"   [SKIP] Generic title: {job['title']}")
        return False

    # Quality gate 2: MNC/reputed company only
    if not is_mnc(job["company"]):
        log(f"   [FILTER] Not MNC: {job['company']}")
        return False

    # Quality gate 3: India location only
    if not is_india(job["location"]):
        log(f"   [FILTER] Not India: {job['location']}")
        return False

    # Quality gate 4: must have substantive description
    if len(job.get("description", "").strip()) < 80:
        log(f"   [SKIP] Description too short for: {job['title']} at {job['company']}")
        return False

    # Standardize title format
    role = clean_role_title(job["title"], job["company"])
    full_title = f"{role} at {job['company']}"

    if job_exists_on_wp(full_title):
        log(f"   [DUP] {full_title}")
        return False

    # Fetch + upload company logo (for featured image + post body)
    log(f"   [LOGO] Resolving logo for {job['company']}...")
    media_id, logo_url = get_or_upload_logo(job["company"])
    if media_id:
        log(f"   [LOGO] Media attached (ID: {media_id}) -> {logo_url}")

    # Resolve company category
    cat_id = get_or_create_category(job["company"])

    excerpt = f"Apply for {role} at {job['company']} in {job['location'] or 'India'}. Full job description, eligibility, and apply link inside."
    post_data = {
        "title":          full_title,
        "content":        build_post_content(job, logo_url=logo_url or ""),
        "excerpt":        excerpt,
        "status":         "publish",
        "meta": {
            "fsp_employer": job["company"],
            "fsp_location": job["location"] or "India",
            "fsp_summary":  f"Latest {job['company']} opportunity in {job['location'] or 'India'}"
        }
    }
    if media_id:
        post_data["featured_media"] = media_id   # Sets WordPress post thumbnail / featured image
    if cat_id:
        post_data["categories"] = [cat_id]       # Assigns post to company category

    try:
        result = http_post_json(f"{WP_URL}/wp-json/wp/v2/posts", post_data, wp_headers())
        post_url = result.get("link", "")
        log(f"   [OK] Published: {full_title}")
        log(f"        {post_url}")

        # Instant Indexing submission
        instant_index_url(post_url)

        # Telegram Channel Broadcast
        broadcast_to_telegram(job, post_url, logo_url=logo_url or "")

        return True
    except urllib.error.HTTPError as e:
        log(f"   [ERR] WP {e.code}: {e.read().decode()[:100]}")
        return False
    except Exception as e:
        log(f"   [ERR] {e}")
        return False

# ─── MAIN PIPELINE ─────────────────────────────────────────────────────────────

def run_pipeline():
    log("=" * 60)
    log("TechJobs360 MNC Pipeline — LinkedIn Public API")
    log("=" * 60)

    # Preload media cache to reuse logos
    populate_existing_media()

    # Pick 3 random queries per run for variety
    queries = random.sample(JOB_QUERIES, min(3, len(JOB_QUERIES)))

    all_job_ids = []
    for query in queries:
        log(f"\n[SEARCH] {query}")
        ids = search_linkedin_jobs(query, location="India", count=MAX_JOBS_PER_QUERY)
        all_job_ids.extend(ids)
        time.sleep(2)

    # Deduplicate
    all_job_ids = list(set(all_job_ids))
    log(f"\n[INFO] Total unique job IDs: {len(all_job_ids)}")

    if not all_job_ids:
        log("[WARN] No job IDs found. LinkedIn may be rate limiting.")
        return

    published = 0
    skipped   = 0

    log("\n[PUBLISH] Fetching details and publishing...")
    for job_id in all_job_ids:
        if published >= MAX_PUBLISH:
            log(f"[DONE] Reached max publish limit ({MAX_PUBLISH})")
            break

        log(f"  Fetching job {job_id}...")
        job = get_linkedin_job_detail(job_id)
        if not job:
            skipped += 1
            continue

        success = publish_job(job)
        if success:
            published += 1
        else:
            skipped += 1

        time.sleep(1.5)  # Polite rate limit

    log("\n" + "=" * 60)
    log(f"DONE! Published: {published} | Skipped/Filtered: {skipped}")
    log("=" * 60)

if __name__ == "__main__":
    run_pipeline()
