# Integrated Content & Revenue Pipeline

## Architecture Overview

This document describes the end-to-end content generation, optimization, and monetization strategy for both avoltium.in and techjobs360-scraper.

### Pipeline Flow

```
Content Generation → Image Sourcing → Proofreading/QC → SEO Optimization → Publishing → Revenue Tracking
```

---

## 1. OmniRoute Configuration (Both Sites)

### avoltium.in
**File:** `.github/workflows/publish_article.yml`
- **Status:** ✓ OmniRoute integrated (optional routing via OMNIROUTE_BASE_URL + OMNIROUTE_API_KEY)
- **Fallback:** Direct Gemini calls if OmniRoute fails or secrets not set
- **Setup:** GitHub Secrets required:
  - `OMNIROUTE_BASE_URL`: Your OmniRoute endpoint (e.g., `http://localhost:20128/v1`)
  - `OMNIROUTE_API_KEY`: API key for OmniRoute

### techjobs360-scraper
**Note:** Currently a job-listing scraper (no article generation).
- If adding blog posts later, reuse the same OmniRoute setup via environment variables.

---

## 2. Content Generation Strategy

### avoltium.in - Technical Articles

**Quality Tiers:**
- **Tier 1 (High-Value):** Deep technical dives (3000-4000 words)
  - Use OmniRoute → Gemini (structured prompt)
  - Real images from Wikimedia/Openverse
  - 2-3 internal links to calculators
  - Schema: NewsArticle + FAQPage
  - AdSense unit placement (mid-body)

- **Tier 2 (Regular):** Standard articles (1500-2500 words)
  - OmniRoute → Gemini
  - Generated image (if real image unavailable)
  - 1-2 internal links
  - Schema: BlogPosting
  - AdSense Auto Ads only

- **Tier 3 (Quick Updates):** News/updates (800-1200 words)
  - OmniRoute → Gemini (lightweight prompt)
  - No featured image (text-only)
  - Schema: NewsArticle (minimal)

### techjobs360-scraper - Job Listings + Blog Content

**Current Role:**
- Scrapes tech job listings from multiple sources
- Maintains job metadata (salary, location, company logos)
- Noindexed to preserve domain authority for main content

**Potential Enhancement (Future):**
- Add weekly "Tech Job Market Trends" blog posts
- Use OmniRoute for trend analysis
- Images from company logos + market charts

---

## 3. Image Strategy

### Real Images (Primary - Higher SEO Value)

**Tier 1: Wikimedia Commons**
- Query: Engineering/industrial equipment
- License: CC BY / CC0 (requires attribution for BY)
- No API key needed
- Best for: electrolyzer stacks, cooling systems, industrial plants

**Tier 2: Openverse**
- Query: Broader tech equipment + industrial
- License: Various CC (check each result)
- No API key needed
- Fallback when Wikimedia unavailable

**Tier 3: Pexels (Optional)**
- Query: Generic stock photos
- License: Free (no attribution needed)
- Requires: `PEXELS_API_KEY`
- Best for: generic tech/business images

### Generated Images (Fallback)

**Current:** Pollinations FLUX (flaky, sometimes wrong results)

**Better Alternative:** Perplexity/Claude image generation (if implementing)
- More accurate for technical subjects
- Can use OmniRoute for cost optimization

**Implementation:** `image_sourcing.py` already supports fallback to generated images via diagrams module.

---

## 4. Proofreading & Quality Control

### Automated QC (`qc_check.py` - avoltium.in)

**Current Checks:**
- [ ] Title non-empty and <160 chars
- [ ] Content has body text (not empty)
- [ ] No LaTeX syntax remaining
- [ ] Featured image exists and >10KB
- [ ] Internal links pointing to valid URLs
- [ ] No duplicate headings
- [ ] Word count within range (300-5000)

### Manual Proofreading (Recommended)

**Before Publishing:**
1. Read through generated content for factual accuracy
2. Verify chemical/engineering terminology correct
3. Check numbers/calculations align with topic
4. Review image appropriateness
5. Test all internal links click-through

**Workflow Step:**
```yaml
- name: Hold for Manual Review
  run: |
    echo "Draft published at: ${{ env.POST_URL }}"
    echo "Review and publish manually via wp-admin"
```

---

## 5. SEO Optimization

### Meta Tags (OG + Rich Snippets)

**WordPress REST API Setup:**
```python
payload = {
    "title": "Next-Generation PEM Electrolyzer Architectures...",
    "content": "...",
    "excerpt": "Technical deep dive into PEM electrolyzer efficiency...",
    "featured_media": 12345,  # Featured image ID
    "meta": {
        "rank_math_title": "PEM Electrolyzer Tech | Efficiency Gains",
        "rank_math_description": "Deep technical analysis of next-gen PEM...",
        "rank_math_canonical_url": "https://avoltium.in/pem-efficiency",
    }
}
```

### Schema Markup

**Article + NewsArticle (for Tier 1 content):**
```json
{
  "@context": "https://schema.org",
  "@type": ["Article", "NewsArticle"],
  "headline": "Next-Generation PEM Electrolyzer Architectures",
  "description": "...",
  "image": "https://avoltium.in/wp-content/uploads/...",
  "author": {
    "@type": "Organization",
    "name": "avoltium"
  },
  "datePublished": "2026-08-09",
  "articleBody": "...",
  "keywords": "electrolyzer, PEM, efficiency, hydrogen"
}
```

**Internal Linking Strategy:**
- Max 2-3 links per article
- Link to: calculators, category pages, related articles
- Anchor text keyword-rich but natural

### Keyword Optimization

**Per-Article Process:**
1. Research 5-10 LSI keywords (Semrush/Ahrefs alternative: Google search "related to")
2. Weave into headings, intro, conclusion naturally
3. Avoid keyword stuffing (target density 1-2%)
4. Use bold/italic for emphasis on key terms

---

## 6. Revenue Generation Strategy

### avoltium.in - Green Hydrogen Authority Site

**Primary: Google AdSense**
- **AdSense Client ID:** `ca-pub-8459363476525914` (configured)
- **Display Units:** Auto Ads (all pages) + Manual mid-article unit (high-traffic articles)
- **Slot ID (Optional):** Set via `ADSENSE_SLOT_ID` env var
- **CPM Target:** $5-15 (technical B2B content)
- **Monthly Revenue Estimate:** 50,000 sessions × 3 pages/session × 2 ads/page × $0.10 RPM = ~$300/month

**Secondary Revenue (Future):**
- Affiliate links to electrolyzer equipment (if sourced from vendors)
- Premium technical guides (gated content)
- Sponsored content from hydrogen equipment manufacturers

**Optimization:**
- Place ads above fold (higher visibility)
- Match ad colors to site theme (higher CTR)
- A/B test ad placements weekly
- Monitor coverage (aim for 100% of sessions showing ads)

### techjobs360-scraper - Job Listing Portal

**Primary: AdSense (Job Listings Noindexed)**
- **Strategy:** Auto Ads on `/jobs/` hub page + category pages
- **CPM Target:** $1-3 (job listing content typically lower)
- **Monthly Revenue Estimate:** 100,000 sessions × $0.50 RPM = ~$50/month

**Secondary Revenue (High Potential):**
- **Sponsored Job Listings** (Featured placements)
  - Charge recruiters $50-200 per featured listing
  - Estimated: 5 featured jobs × $100 = $500/month
- **Recruitment Agency Partnerships**
  - Referral fees for job placements
  - $20-50 per hire (20 hires/month = $400-1000)
- **Resume Database Access** (Future)
  - Charge employers for candidate profiles
  - Estimated: $500-2000/month

**Optimization:**
- Create dedicated "Featured Listings" section
- Email alerts to job seekers (drives repeat traffic)
- Display job stats/trends (builds authority)

---

## 7. Implementation Checklist

### Phase 1: OmniRoute Setup (Week 1)
- [ ] Configure GitHub Secrets for both repos
  - [ ] `OMNIROUTE_BASE_URL`
  - [ ] `OMNIROUTE_API_KEY`
- [ ] Test publish workflow with OmniRoute active
- [ ] Monitor logs for routing vs. fallback

### Phase 2: Image Optimization (Week 2)
- [ ] Enable `image_sourcing.py` as primary for avoltium.in
- [ ] Configure Pexels API key (if using)
- [ ] Audit existing images for sourcing improvements
- [ ] Add image attribution to article footers (CC BY compliance)

### Phase 3: SEO Enhancement (Week 2-3)
- [ ] Run `seo_care_suite.py` audit on all existing content
- [ ] Fix critical SEO issues (meta tags, schema)
- [ ] Set up Rank Math meta configuration
- [ ] Create XML sitemap (if missing)

### Phase 4: Monetization (Week 3)
- [ ] Audit AdSense placement on both sites
- [ ] Set up Google Analytics goals for ad impressions
- [ ] Create "Sponsored Listings" WordPress page template (techjobs360)
- [ ] Document sponsor contact process

### Phase 5: Content Calendar (Ongoing)
- [ ] Schedule regular Tier 1 articles (biweekly)
- [ ] Schedule Tier 2 articles (weekly)
- [ ] Set up editorial review process before publish

---

## 8. Monitoring & Metrics

### avoltium.in - Article Performance

**Dashboard Metrics:**
- Page views per article
- Average read time
- Bounce rate
- AdSense RPM (Revenue Per Mille)
- Internal link CTR
- Conversion to "Related Articles"

**Target KPIs:**
- 5,000+ views per Tier 1 article within 3 months
- 40%+ of sessions viewing 2+ pages
- $10+ RPM on high-traffic articles

### techjobs360-scraper - Job Listing Performance

**Dashboard Metrics:**
- Jobs posted per week
- Unique job views
- Application rate
- Featured listing conversion rate
- AdSense RPM
- Sponsor inquiry rate

**Target KPIs:**
- 20,000+ total job listings
- 100,000+ unique views/month
- 5-10 sponsored listings/month
- $1,000+ total monthly revenue

---

## 9. API Keys & Configuration Required

### Environment Variables

```bash
# Both sites
WP_URL=https://www.avoltium.in
WP_USERNAME=api_user
WP_APP_PASSWORD=xxxx
GEMINI_API_KEY=xxxx

# OmniRoute (both sites)
OMNIROUTE_BASE_URL=http://localhost:20128/v1
OMNIROUTE_API_KEY=sk-xxxx

# Image sourcing (optional)
PEXELS_API_KEY=xxxx

# Analytics (optional)
GOOGLE_ANALYTICS_ID=G-xxxx
ADSENSE_CLIENT_ID=ca-pub-xxxx
ADSENSE_SLOT_ID=xxxx

# techjobs360 (if needed)
WP_URL_TECHJOBS360=https://www.techjobs360.com
```

---

## 10. Troubleshooting

### OmniRoute Not Used
- **Symptom:** Workflow logs show "Falling back to Gemini"
- **Check:** GitHub Secrets are set and match env vars in workflow YAML
- **Fix:** Re-run workflow manually after confirming secrets

### Generated Images Wrong
- **Symptom:** Image doesn't match article (e.g., bedroom for EDI article)
- **Check:** Enable `image_sourcing.py` to search real images first
- **Fix:** Manually upload correct image to WordPress media library

### Low AdSense RPM
- **Symptom:** Revenue under $5/month despite 50K+ sessions
- **Check:** Ad placement (should be above fold)
- **Check:** AdSense policies compliance
- **Fix:** A/B test ad sizes and placements

### SEO Issues Detected
- **Run:** `python seo_care_suite.py --site avoltium --export report.json`
- **Review:** JSON report for critical/warning issues
- **Fix:** Update post meta or add missing schema

---

## Quick Links

- **avoltium.in Repo:** https://github.com/arunbabusb/avoltium.in
- **techjobs360-scraper Repo:** https://github.com/arunbabusb/techjobs360-scraper
- **OmniRoute Docs:** (your OmniRoute endpoint docs)
- **Google AdSense:** https://adsense.google.com/
- **Rank Math:** https://rankmath.com/
