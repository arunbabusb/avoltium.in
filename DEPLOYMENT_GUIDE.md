# Avoltium.in - Phase 1 Deployment Guide

## 🚀 Pre-Deployment Checklist

- [ ] All code committed and pushed
- [ ] SEO files generated (sitemap.xml, robots.txt)
- [ ] Token cache database initialized
- [ ] Google Search Console domain verified
- [ ] Cloudflare caching rules configured
- [ ] Performance baseline captured (PageSpeed)

---

## Step 1: Deploy Token Caching (5 minutes)

### 1.1 Initialize Cache Database

```bash
cd /home/user/avoltium.in
python token_cache.py
```

**Output:** `token_cache.db` created with schema

### 1.2 Verify Cache Database

```bash
# Check database exists
ls -lh token_cache.db

# View schema
sqlite3 token_cache.db ".schema"

# Check initial state
sqlite3 token_cache.db "SELECT COUNT(*) FROM content_cache;"
```

### 1.3 Add to Production Environment

**Option A: Local Server**
```bash
# Copy to production server
scp token_cache.db user@avoltium.in:/var/www/avoltium.in/
```

**Option B: Git (if not sensitive)**
```bash
# Initialize as empty
python -c "from token_cache import get_cache; get_cache()" 
git add token_cache.db
git commit -m "Initialize empty token cache"
git push
```

---

## Step 2: Deploy SEO Infrastructure (10 minutes)

### 2.1 Generate Sitemaps & robots.txt

```bash
python seo_infrastructure.py
```

**Creates:**
- `sitemap.xml` - URL listing (will add all posts)
- `robots.txt` - Crawler instructions

### 2.2 Upload to Web Root

```bash
# Local server
cp sitemap.xml /var/www/avoltium.in/
cp robots.txt /var/www/avoltium.in/

# Or via SFTP/SCP to remote
scp sitemap.xml robots.txt user@avoltium.in:/var/www/avoltium.in/
```

### 2.3 Verify Accessibility

```bash
# Check robots.txt is accessible
curl https://avoltium.in/robots.txt

# Check sitemap is accessible
curl https://avoltium.in/sitemap.xml | head -20

# Verify format
xmllint --noout sitemap.xml  # Should return silently if valid
```

---

## Step 3: Google Search Console Setup (20 minutes)

### 3.1 Verify Domain Ownership

1. Go to: https://search.google.com/search-console
2. Click **"Add Property"**
3. Enter: `https://avoltium.in`

**Verification Method 1: DNS TXT Record** (Recommended for production)
```
TXT Record:
Name: avoltium.in
Value: google-site-verification=XXXXXXXXXXXX
```

**Verification Method 2: HTML File Upload**
1. Download HTML file from GSC
2. Upload to root: `https://avoltium.in/google-verification.html`

**Verification Method 3: HTML meta tag** (WordPress theme)
Add to `<head>` of homepage:
```html
<meta name="google-site-verification" content="XXXXXXXXXXXX" />
```

### 3.2 Submit Sitemap

1. In GSC, go to **Sitemaps** section
2. Enter: `https://avoltium.in/sitemap.xml`
3. Click **Submit**
4. Check status after 5 minutes

### 3.3 Configure Crawl Settings

**In GSC Settings:**
1. Set **Preferred Domain**: `www.avoltium.in` or `avoltium.in`
2. Set **Geographic Targeting**: India (if applicable)
3. Enable **Security Issues** reporting

---

## Step 4: Deploy Performance Optimizations (15 minutes)

### 4.1 Setup Cloudflare Caching

**In Cloudflare Dashboard:**

1. **Cache Rules** (Speed → Caching → Rules)
   ```
   Path = /static/* → Cache everything (30 days)
   Path = /api/* → Cache 30 min
   Path = / → Cache 5 min
   Path = /*.html → Cache 1 hour
   ```

2. **Page Rules** (Speed → Optimization)
   - Cache level: Cache everything
   - Browser cache TTL: 1 month

3. **Image Optimization**
   - Enable **Polish** (WebP conversion)
   - Enable **Mirage** (lazy loading)
   - Enable **Rocket Loader** (JS optimization)

### 4.2 Inline Critical CSS

Add to WordPress theme `<head>`:
```html
<style>
/* Critical CSS from shared_performance.py */
/* Inline critical.css here */
</style>
```

### 4.3 Defer Non-Critical CSS/JS

In WordPress theme footer:
```html
<!-- Defer non-critical CSS -->
<link rel="preload" href="/css/full.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="/css/full.css"></noscript>

<!-- Async load scripts -->
<script async src="/js/analytics.js"></script>
<script defer src="/js/components.js"></script>
```

---

## Step 5: Setup Monitoring (10 minutes)

### 5.1 Create Cost Tracking Script

Create `monitor_costs.py`:
```python
from token_cache import get_cache
import json
from datetime import datetime

cache = get_cache()
analysis = cache.get_cost_analysis(days=30)

report = {
    "timestamp": datetime.utcnow().isoformat(),
    "period_days": 30,
    **analysis
}

print(json.dumps(report, indent=2))

# Save report
with open("cost_reports/week_1.json", "w") as f:
    json.dump(report, f, indent=2)
```

### 5.2 Schedule Weekly Reports

**Cron job** (every Sunday at 2 AM):
```bash
0 2 * * 0 cd /var/www/avoltium.in && python monitor_costs.py >> cost_monitoring.log 2>&1
```

### 5.3 Setup Performance Monitoring

**Google PageSpeed** (manual check):
```bash
# Create monitoring script
python shared_performance.py
```

**Setup alert** (if LCP > 3s):
```bash
# Create alert script - send email if thresholds exceeded
# Run weekly via cron
```

---

## Step 6: Verify Deployment (15 minutes)

### 6.1 Test Cache Integration

```python
from token_cache import get_cache

# Test cache operations
cache = get_cache()

# Should be empty initially
print(cache.get_cost_analysis(days=30))

# Simulate API call
cache.log_api_call("test_api", tokens_used=1000, cost_usd=0.02)

# Check it's logged
analysis = cache.get_cost_analysis(days=30)
print(f"Total calls: {analysis['summary']['total_api_calls']}")
```

### 6.2 Test SEO Infrastructure

```bash
# Validate sitemaps
xmllint --noout sitemap.xml
xmllint --noout sitemap_index.xml

# Check robots.txt syntax
cat robots.txt

# Verify GSC sees sitemap
# Check in GSC dashboard: Sitemaps section
```

### 6.3 Test Performance

```bash
# Run PageSpeed test
# https://pagespeed.web.dev/?url=https://avoltium.in

# Check Core Web Vitals
# https://search.google.com/search-console/core-web-vitals?resource_id=https://avoltium.in

# Verify Cloudflare is active
curl -I https://avoltium.in | grep "Server:"
# Should show: Server: cloudflare
```

---

## Step 7: Post-Deployment Validation (Daily for 1 week)

### Daily Checklist

- [ ] Check GSC for any crawl errors
- [ ] Monitor Core Web Vitals (should improve)
- [ ] Verify cache is being used (check logs)
- [ ] Monitor cost analytics
- [ ] Check for any user-facing issues

### Week 1 Metrics to Track

| Metric | Target | Status |
|--------|--------|--------|
| LCP | <2.5s | ⏳ |
| FID | <100ms | ⏳ |
| CLS | <0.1 | ⏳ |
| Sitemap indexed | 100+ | ⏳ |
| Cache hit rate | >30% | ⏳ |
| Token costs | -40% | ⏳ |

---

## Rollback Plan (If Issues)

### If Cache Causes Problems

```bash
# Disable cache (stop generating new cache entries)
# Keep existing database

# OR reset entirely
rm token_cache.db
python token_cache.py  # Recreate empty

# Revert code
git revert <commit_hash>
git push
```

### If SEO Changes Break Index

```bash
# Restore old robots.txt
git checkout HEAD~1 robots.txt

# Resubmit sitemap in GSC
# Check coverage → should recover in 1-2 days
```

### If Performance Degrades

```bash
# Disable Cloudflare caching temporarily
# Check if issue is real or caching-related

# Clear Cloudflare cache
# In dashboard: Purge cache → Purge everything

# Check for JS errors
# Open browser DevTools → Console tab
```

---

## Success Criteria (After 1 Week)

✅ **All below must be met:**

- [ ] Sitemaps submitted and indexed (check GSC Sitemaps section)
- [ ] No crawl errors in GSC
- [ ] Cache database has >100 entries
- [ ] Token costs logged and visible
- [ ] LCP improved to <2.5s
- [ ] robots.txt accessible and valid
- [ ] No user-facing errors
- [ ] Core Web Vitals monitoring active

---

## Maintenance Going Forward

### Weekly Tasks
- Review cost analysis
- Monitor GSC coverage
- Check Core Web Vitals

### Monthly Tasks
- Analyze backlog of cached content
- Clear expired cache entries
- Review and optimize cache TTLs

### Quarterly Tasks
- Full SEO audit
- Performance benchmark
- Cache efficiency review

---

## Support & Troubleshooting

**Cache Issues:**
- Check `token_cache.db` permissions
- Verify disk space available
- Check database corruption: `sqlite3 token_cache.db "PRAGMA integrity_check;"`

**SEO Issues:**
- Verify sitemaps are valid XML
- Check robots.txt syntax
- Confirm domain verified in GSC
- Allow 48 hours for full indexing

**Performance Issues:**
- Check Cloudflare is enabled
- Verify critical CSS is inlined
- Test with browser cache disabled
- Check PageSpeed recommendations

---

## Next Steps (After Deployment)

Once Week 1 validation passes:
1. Proceed to **Step 3: Testing**
2. Run integration tests
3. Move to Phase 2: Revenue Setup

---

**Deployment completed:** [DATE]
**Deployed by:** [NAME]
**Status:** ✅ Live

---

*Refer to PHASE_1_IMPLEMENTATION.md for week-by-week roadmap*
