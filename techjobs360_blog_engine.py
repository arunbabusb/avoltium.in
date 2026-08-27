"""
TechJobs360.com — 100-Year Autonomous Career Blog & SEO Article Engine
=======================================================================
Generates and publishes authoritative, long-form, SEO-optimized tech career guides,
salary benchmark analyses, ATS resume tutorials, and hiring drive roadmaps.
Includes Schema.org Article & FAQPage JSON-LD, internal linking, AdSense integration,
IndexNow search indexing, and Telegram broadcasts.

Usage:
    python techjobs360_blog_engine.py
"""

import os
import json
import base64
import random
import urllib.request
import urllib.parse
from datetime import datetime

WP_URL      = os.getenv("TECHJOBS_WP_URL", "https://www.techjobs360.com")
WP_USERNAME = os.getenv("TECHJOBS_WP_USERNAME", "admin")
WP_APP_PASS = os.getenv("TECHJOBS_WP_APP_PASSWORD", "vgPl O24r nMOq dRF7 GhBN i9l4")
INDEXNOW_KEY = os.getenv("INDEXNOW_KEY", "45d7b3c29f8e4a1b8c2d6e7f0a9b3c4d")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "984894655:AAHMzMqRzZK6nvh02WotbkFortsLwMJ2sM0")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "-1001183899008")

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def wp_headers():
    creds = base64.b64encode(f"{WP_USERNAME}:{WP_APP_PASS}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}

# ─── CURATED LONG-FORM CAREER BLOG TOPICS ──────────────────────────────────────

CAREER_BLOG_POSTS = [
    {
        "title": "The Ultimate 2026 Tech Resume Guide: How to Beat ATS Algorithms and Land Top MNC Interviews",
        "slug": "ultimate-tech-resume-guide-beat-ats-algorithms-2026",
        "summary": "Master the modern single-column ATS resume format used by Google, Microsoft, and top Indian MNCs. Learn keyword placement, quantifiable impact metrics, and common screening traps.",
        "content": """
<p class="lead" style="font-size: 18px; line-height: 1.8; color: #334155; font-weight: 500;">In 2026, over 95% of Fortune 500 tech companies and top Indian IT giants (including Google, Microsoft, Amazon, TCS, Infosys, and Cognizant) use Applicant Tracking Systems (ATS) to filter thousands of job applications. If your resume format is not machine-readable, your profile will be rejected before a human recruiter even sees it.</p>

<!-- Top Ad Unit -->
<div style="margin: 24px auto; text-align: center; max-width: 100%; overflow: hidden;">
    <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;">Advertisement</div>
    <ins class="adsbygoogle" style="display:block" data-ad-client="ca-pub-8459363476525914" data-ad-slot="" data-ad-format="auto" data-full-width-responsive="true"></ins>
    <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
</div>

<h2>What is an ATS (Applicant Tracking System) and How Does It Work?</h2>
<p>An ATS parses resumes by extracting text from structured sections: Contact Information, Work Experience, Technical Skills, and Education. It scores candidate profiles against specific keywords in the job description.</p>

<div style="background: #eff6ff; border-left: 4px solid #2563eb; padding: 18px 22px; border-radius: 0 10px 10px 0; margin: 24px 0;">
    <strong style="color: #1e40af; font-size: 16px;">💡 Pro-Tip for Tech Job Seekers:</strong>
    <p style="margin: 6px 0 0 0; color: #1e3a8a; font-size: 14.5px;">Never use multi-column tables, graphical skill bars, or text inside floating images. ATS parsers read left-to-right, top-to-bottom and will scramble multi-column layouts into unreadable gibberish.</p>
</div>

<h2>The 4 Pillars of a High-Scoring ATS Tech Resume</h2>

<h3>1. Single-Column Chronological Layout</h3>
<p>Modern ATS algorithms favor clean, linear layouts. Organize your resume in this exact sequence:</p>
<ul>
    <li><strong>Header:</strong> Full Name, Target Job Title, Email, Phone Number, City/Country, LinkedIn URL, GitHub / Portfolio.</li>
    <li><strong>Professional Summary:</strong> 3-line elevator pitch highlighting years of experience, core tech stack (e.g. Java, Spring Boot, React, AWS), and top achievements.</li>
    <li><strong>Technical Skills Grid:</strong> Categorized into <em>Languages</em>, <em>Frameworks</em>, <em>Cloud & DevOps</em>, and <em>Databases</em>.</li>
    <li><strong>Work Experience:</strong> Reverse-chronological with quantifiable bullet points.</li>
    <li><strong>Education & Certifications:</strong> Degree, University, Graduation Year, CGPA.</li>
</ul>

<h3>2. Quantifiable Impact with Google's X-Y-Z Formula</h3>
<p>Recruiters at top tech firms look for proven impact rather than generic task lists. Follow Google's famous formula: <em>"Accomplished [X] as measured by [Y], by doing [Z]"</em>.</p>

<table style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14.5px;">
    <thead>
        <tr style="background: #f1f5f9; text-align: left;">
            <th style="padding: 12px; border: 1px solid #cbd5e1; color: #dc2626;">❌ Weak Bullet Point</th>
            <th style="padding: 12px; border: 1px solid #cbd5e1; color: #16a34a;">✅ Strong ATS High-Impact Bullet</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td style="padding: 12px; border: 1px solid #cbd5e1;">Responsible for writing backend APIs in Java.</td>
            <td style="padding: 12px; border: 1px solid #cbd5e1;">Architected 12+ RESTful microservices using Spring Boot & Redis, handling 45,000 daily requests with 99.9% uptime.</td>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #cbd5e1;">Worked on database performance.</td>
            <td style="padding: 12px; border: 1px solid #cbd5e1;">Optimized PostgreSQL query execution plans and database indexes, reducing query latency by 42%.</td>
        </tr>
    </tbody>
</table>

<!-- Mid Content Ad -->
<div style="margin: 28px auto; text-align: center; max-width: 100%; overflow: hidden;">
    <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;">Advertisement</div>
    <ins class="adsbygoogle" style="display:block" data-ad-client="ca-pub-8459363476525914" data-ad-slot="" data-ad-format="auto" data-full-width-responsive="true"></ins>
    <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
</div>

<h2>Free Tool: Build Your Recruiter-Ready ATS Resume in 3 Minutes</h2>
<p>Instead of wrestling with Microsoft Word formatting, you can use our free interactive tool built specifically for tech professionals:</p>

<div style="background: #f8fafc; border: 2px dashed #3b82f6; border-radius: 14px; padding: 24px; text-align: center; margin: 28px 0;">
    <h3 style="margin: 0 0 8px 0; font-size: 20px; font-weight: 700; color: #0f172a;">🛠️ TechJobs360 ATS CV Builder</h3>
    <p style="margin: 0 0 16px 0; color: #64748b; font-size: 15px;">Real-time preview, ATS 98/100 scoring, pre-filled engineering samples, and 1-click A4 PDF export.</p>
    <a href="https://www.techjobs360.com/cv-builder/" style="display: inline-block; background: #2563eb; color: #ffffff; padding: 12px 28px; border-radius: 8px; font-weight: 700; text-decoration: none; box-shadow: 0 4px 12px rgba(37,99,235,0.25);">Launch Free ATS CV Builder &rarr;</a>
</div>

<h2>Frequently Asked Questions (FAQ)</h2>
<div style="margin-top: 16px;">
    <h4 style="margin: 0 0 4px 0; font-size: 16px; color: #0f172a;">Q1: Should I submit my resume in PDF or Word (.docx) format?</h4>
    <p style="margin: 0 0 16px 0; color: #475569;">PDF is the recommended format across 99% of modern ATS systems because it preserves fonts and margins identically across operating systems.</p>

    <h4 style="margin: 0 0 4px 0; font-size: 16px; color: #0f172a;">Q2: How long should my tech resume be?</h4>
    <p style="margin: 0 0 16px 0; color: #475569;">For engineers with 0 to 5 years of experience, stick strictly to <strong>1 page</strong>. For senior engineers or tech leads with 6+ years and extensive architecture projects, 2 pages is acceptable.</p>
</div>
""",
        "categories": [245, 654], # Career Guide, Software Engineer
        "faqs": [
            {"q": "Should I submit my resume in PDF or Word format?", "a": "PDF is recommended across modern ATS systems as it preserves typography and layout without distortion."},
            {"q": "How long should a tech resume be?", "a": "1 page for 0-5 years experience, up to 2 pages for 6+ years experience."}
        ]
    },
    {
        "title": "In-Hand Salary vs CTC in India 2026: Complete Breakdown with FY 2026-27 New Tax Slabs",
        "slug": "in-hand-salary-vs-ctc-breakdown-india-tax-slabs-2026",
        "summary": "Understand how your annual CTC translates into monthly take-home salary in India. Learn about Basic Pay, HRA, EPF (12%), Gratuity, Professional Tax, and the New vs Old Tax Regime differences.",
        "content": """
<p class="lead" style="font-size: 18px; line-height: 1.8; color: #334155; font-weight: 500;">When you receive a job offer letter stating an Annual CTC of ₹12,00,000 (₹12 LPA) or ₹25,00,000 (₹25 LPA), your monthly credited bank deposit will look significantly different. Understanding the difference between <strong>Cost to Company (CTC)</strong>, <strong>Gross Salary</strong>, and <strong>Net In-Hand Salary</strong> is crucial for offer negotiations and financial planning.</p>

<!-- Top Ad Unit -->
<div style="margin: 24px auto; text-align: center; max-width: 100%; overflow: hidden;">
    <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;">Advertisement</div>
    <ins class="adsbygoogle" style="display:block" data-ad-client="ca-pub-8459363476525914" data-ad-slot="" data-ad-format="auto" data-full-width-responsive="true"></ins>
    <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
</div>

<h2>The Anatomy of an Indian CTC Structure</h2>
<p>Cost to Company represents the entire cost an employer incurs to employ you for one year. It is composed of three main layers:</p>

<ul>
    <li><strong>1. Direct Benefits (Monthly Earnings):</strong> Basic Salary (typically 40–50% of CTC), House Rent Allowance (HRA), Special Allowance, and Conveyance.</li>
    <li><strong>2. Indirect Benefits (Employer Retirals):</strong> Employer PF Contribution (12% of Basic), Gratuity (approx 4.81% of Basic), and Group Medical Insurance premium.</li>
    <li><strong>3. Variable / Bonus Components:</strong> Annual performance bonus, joining bonus, or company stock units (RSUs).</li>
</ul>

<h2>Sample ₹12,00,000 (₹12 LPA) CTC Breakdown Table</h2>
<table style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14.5px;">
    <thead>
        <tr style="background: #0f172a; color: #ffffff; text-align: left;">
            <th style="padding: 12px; border: 1px solid #334155;">Salary Component</th>
            <th style="padding: 12px; border: 1px solid #334155;">Annual Amount (₹)</th>
            <th style="padding: 12px; border: 1px solid #334155;">Monthly Amount (₹)</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td style="padding: 10px; border: 1px solid #cbd5e1;">Basic Salary (40%)</td>
            <td style="padding: 10px; border: 1px solid #cbd5e1;">₹4,80,000</td>
            <td style="padding: 10px; border: 1px solid #cbd5e1;">₹40,000</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #cbd5e1;">House Rent Allowance (HRA)</td>
            <td style="padding: 10px; border: 1px solid #cbd5e1;">₹2,40,000</td>
            <td style="padding: 10px; border: 1px solid #cbd5e1;">₹20,000</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #cbd5e1;">Special Allowance</td>
            <td style="padding: 10px; border: 1px solid #cbd5e1;">₹3,56,400</td>
            <td style="padding: 10px; border: 1px solid #cbd5e1;">₹29,700</td>
        </tr>
        <tr style="background: #f8fafc; font-weight: 700;">
            <td style="padding: 10px; border: 1px solid #cbd5e1;">Total Gross Salary</td>
            <td style="padding: 10px; border: 1px solid #cbd5e1;">₹10,76,400</td>
            <td style="padding: 10px; border: 1px solid #cbd5e1;">₹89,700</td>
        </tr>
        <tr style="color: #dc2626;">
            <td style="padding: 10px; border: 1px solid #cbd5e1;">Employee EPF (12% of Basic)</td>
            <td style="padding: 10px; border: 1px solid #cbd5e1;">- ₹57,600</td>
            <td style="padding: 10px; border: 1px solid #cbd5e1;">- ₹4,800</td>
        </tr>
        <tr style="color: #dc2626;">
            <td style="padding: 10px; border: 1px solid #cbd5e1;">Professional Tax (PT)</td>
            <td style="padding: 10px; border: 1px solid #cbd5e1;">- ₹2,400</td>
            <td style="padding: 10px; border: 1px solid #cbd5e1;">- ₹200</td>
        </tr>
        <tr style="color: #dc2626;">
            <td style="padding: 10px; border: 1px solid #cbd5e1;">Income Tax TDS (New Regime)</td>
            <td style="padding: 10px; border: 1px solid #cbd5e1;">- ₹41,600</td>
            <td style="padding: 10px; border: 1px solid #cbd5e1;">- ₹3,467</td>
        </tr>
        <tr style="background: #dcfce7; font-weight: 800; color: #166534; font-size: 16px;">
            <td style="padding: 12px; border: 1px solid #86efac;">Net Monthly In-Hand Salary</td>
            <td style="padding: 12px; border: 1px solid #86efac;">₹9,74,800 / yr</td>
            <td style="padding: 12px; border: 1px solid #86efac;">₹81,233 / mo</td>
        </tr>
    </tbody>
</table>

<!-- Mid Content Ad -->
<div style="margin: 28px auto; text-align: center; max-width: 100%; overflow: hidden;">
    <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;">Advertisement</div>
    <ins class="adsbygoogle" style="display:block" data-ad-client="ca-pub-8459363476525914" data-ad-slot="" data-ad-format="auto" data-full-width-responsive="true"></ins>
    <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
</div>

<h2>Calculate Your Exact In-Hand Salary Instantly</h2>
<p>Use our free calculator to test custom CTC figures, compare New vs Old Tax regimes, and calculate city-specific professional taxes:</p>

<div style="background: #f0fdf4; border: 2px dashed #16a34a; border-radius: 14px; padding: 24px; text-align: center; margin: 28px 0;">
    <h3 style="margin: 0 0 8px 0; font-size: 20px; font-weight: 700; color: #14532d;">💰 Free In-Hand Salary Calculator (FY 2026-27)</h3>
    <p style="margin: 0 0 16px 0; color: #166534; font-size: 15px;">Real-time CTC slider, itemized deductions breakdown, and tax rebate optimization.</p>
    <a href="https://www.techjobs360.com/in-hand-salary-calculator/" style="display: inline-block; background: #16a34a; color: #ffffff; padding: 12px 28px; border-radius: 8px; font-weight: 700; text-decoration: none; box-shadow: 0 4px 12px rgba(22,163,74,0.25);">Open In-Hand Salary Calculator &rarr;</a>
</div>
""",
        "categories": [245, 654],
        "faqs": [
            {"q": "How much in-hand salary for 12 LPA CTC?", "a": "For a 12 LPA CTC under the New Tax Regime, the monthly in-hand take-home salary is approximately ₹81,200 to ₹83,500 after EPF, Professional Tax, and Income Tax deductions."},
            {"q": "Is EPF deducted from Basic or total CTC?", "a": "Employee EPF (12%) is deducted from the Basic Salary component, not the entire CTC."}
        ]
    }
]

def publish_career_blog(blog):
    title = blog["title"]
    log(f"\n[BLOG ENGINE] Preparing: {title}")
    
    # Generate Schema JSON-LD (Article + FAQPage)
    faq_entities = []
    for f in blog.get("faqs", []):
        faq_entities.append({
            "@type": "Question",
            "name": f["q"],
            "acceptedAnswer": {
                "@type": "Answer",
                "text": f["a"]
            }
        })
        
    article_schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": blog["summary"],
        "datePublished": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dateModified": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "author": {
            "@type": "Organization",
            "name": "TechJobs360 Editorial Team",
            "url": "https://www.techjobs360.com"
        },
        "publisher": {
            "@type": "Organization",
            "name": "TechJobs360",
            "logo": {
                "@type": "ImageObject",
                "url": "https://www.techjobs360.com/wp-content/uploads/2026/08/techjobs360-logo.png"
            }
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": f"{WP_URL}/{blog['slug']}/"
        }
    }
    
    faq_schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": faq_entities
    }
    
    schema_html = f"""
<script type="application/ld+json">
{json.dumps(article_schema, indent=2)}
</script>
<script type="application/ld+json">
{json.dumps(faq_schema, indent=2)}
</script>
"""
    
    full_content = blog["content"] + schema_html
    
    post_payload = {
        "title": title,
        "slug": blog["slug"],
        "content": full_content,
        "excerpt": blog["summary"],
        "status": "publish",
        "categories": blog["categories"]
    }
    
    try:
        req = urllib.request.Request(
            f"{WP_URL}/wp-json/wp/v2/posts",
            data=json.dumps(post_payload).encode("utf-8"),
            headers=wp_headers(),
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=20) as res:
            res_data = json.loads(res.read())
            post_url = res_data.get("link", "")
            log(f"  [OK] Published Blog: ID {res_data.get('id')} -> {post_url}")
            
            # Submit to IndexNow
            submit_to_indexnow(post_url)
            
            # Broadcast to Telegram
            broadcast_blog_telegram(title, blog["summary"], post_url)
            return True
    except Exception as e:
        log(f"  [ERR] Blog publish failed: {e}")
        return False

def submit_to_indexnow(url):
    try:
        payload = {
            "host": "www.techjobs360.com",
            "key": INDEXNOW_KEY,
            "keyLocation": f"https://www.techjobs360.com/{INDEXNOW_KEY}.txt",
            "urlList": [url]
        }
        for endpoint in ["https://api.indexnow.org/indexnow", "https://www.bing.com/indexnow"]:
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as res:
                log(f"  [INDEXNOW] Submitted {url} to {endpoint} (HTTP {res.status})")
    except Exception as e:
        log(f"  [INDEXNOW] Note: {e}")

def broadcast_blog_telegram(title, summary, post_url):
    if not TELEGRAM_BOT_TOKEN:
        return
    caption = (
        f"📚 <b>New Tech Career Guide:</b>\n"
        f"<b>{title}</b>\n\n"
        f"📝 {summary}\n\n"
        f"👉 <a href=\"{post_url}\">Read Full Article on TechJobs360</a>\n\n"
        f"🔔 <i>Follow @techjobs360 for career roadmaps & salary benchmarks!</i>\n"
        f"#TechCareers #ResumeTips #SalaryGuide #TechJobs360"
    )
    inline_keyboard = {
        "inline_keyboard": [
            [{"text": "📖 Read Full Guide", "url": post_url}],
            [{"text": "✈️ Join Telegram Community", "url": "https://t.me/techjobs360"}]
        ]
    }
    try:
        tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": caption,
            "parse_mode": "HTML",
            "reply_markup": inline_keyboard
        }
        req = urllib.request.Request(tg_url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as res:
            log(f"  [TELEGRAM] Broadcast blog sent to {TELEGRAM_CHAT_ID} (HTTP {res.status})")
    except Exception as e:
        log(f"  [TELEGRAM] Note: {e}")

def run_blog_engine():
    log("=" * 70)
    log("🚀 Starting TechJobs360 Autonomous Career Blog Engine")
    log("=" * 70)
    
    published_count = 0
    for blog in CAREER_BLOG_POSTS:
        success = publish_career_blog(blog)
        if success:
            published_count += 1
            
    log("\n" + "=" * 70)
    log(f"✅ Blog Engine Completed: {published_count} Authority Articles Published & Indexed.")
    log("=" * 70)

if __name__ == "__main__":
    run_blog_engine()
