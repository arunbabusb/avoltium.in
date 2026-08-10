"""
Phase 1 Integration Tests - Avoltium.in
Tests token caching, SEO infrastructure, and performance optimizations
"""

import unittest
import json
import os
import tempfile
import sqlite3
from pathlib import Path

# Test imports
try:
    from token_cache import TokenCache, get_cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False

try:
    from seo_infrastructure import (
        JSONLDGenerator, SitemapGenerator, RobotsGenerator,
        MetaTagOptimizer, GSCSetup
    )
    SEO_AVAILABLE = True
except ImportError:
    SEO_AVAILABLE = False

try:
    from shared_performance import (
        ImageOptimizer, CachingStrategy, CoreWebVitalsMonitor,
        PerformanceBudget
    )
    PERF_AVAILABLE = True
except ImportError:
    PERF_AVAILABLE = False


class TestTokenCache(unittest.TestCase):
    """Test token caching system"""

    def setUp(self):
        """Point the cache at a throwaway SQLite file for this test."""
        if not CACHE_AVAILABLE:
            self.skipTest("token_cache module not available")
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.cache = TokenCache(self.temp_db.name)

    def tearDown(self):
        """Delete the throwaway SQLite file."""
        if os.path.exists(self.temp_db.name):
            os.remove(self.temp_db.name)

    def test_cache_initialization(self):
        """Test cache database is created with correct schema"""
        self.assertTrue(os.path.exists(self.temp_db.name))
        self.assertGreater(os.path.getsize(self.temp_db.name), 0)

    def test_cache_content_storage(self):
        """Test caching and retrieving content"""
        topic = "test_article"
        content = "Test article content"
        params = {"style": "technical"}

        # Cache content
        self.cache.cache_content(topic, content, params, tokens_saved=800)

        # Retrieve from cache
        cached = self.cache.get_cached_content(topic, params)
        self.assertEqual(cached, content)

    def test_cache_expiration(self):
        """Test cache entries expire correctly"""
        topic = "expiring_content"
        content = "This should expire"
        params = {}

        # Cache with 0-day TTL (immediate expiration)
        self.cache.cache_content(topic, content, params, ttl_days=0)

        # Should not be in cache
        cached = self.cache.get_cached_content(topic, params)
        self.assertIsNone(cached)

    def test_cache_expiry_honours_legacy_iso_timestamps(self):
        """Rows written before the format fix must still expire.

        Expiry used to be stored as an ISO timestamp and compared as a bare
        string against SQLite's datetime('now'), which uses a space where ISO
        puts a "T". "T" sorts after a space, so every such row read as
        unexpired forever. Any cache file predating the fix still holds them.
        """
        import datetime as _dt
        stale = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=5)).isoformat()
        digest = self.cache.get_content_hash("legacy", {})
        with sqlite3.connect(self.temp_db.name) as conn:
            conn.execute(
                "INSERT INTO content_cache (hash, topic, content, tokens_saved, expires_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (digest, "legacy", "five days stale", 0, stale))

        self.assertIsNone(self.cache.get_cached_content("legacy", {}))
        self.assertEqual(self.cache.clear_expired(), 1)

    def test_cost_analysis_tolerates_null_metrics(self):
        """tokens_used and cost_usd are nullable; SUM over all-NULL is NULL.

        Summing that in Python raised TypeError and took down the whole
        report, not just the one endpoint with missing numbers.
        """
        with sqlite3.connect(self.temp_db.name) as conn:
            conn.execute(
                "INSERT INTO api_calls (endpoint, tokens_used, cost_usd, cached)"
                " VALUES ('legacy', NULL, NULL, 0)")

        summary = self.cache.get_cost_analysis(days=30)['summary']
        self.assertEqual(summary['total_api_calls'], 1)
        self.assertEqual(summary['total_tokens'], 0)
        self.assertEqual(summary['total_cost_usd'], 0.0)

    def test_api_call_logging(self):
        """Test API call metrics logging"""
        self.cache.log_api_call("gemini", tokens_used=1250, cost_usd=0.025)
        self.cache.log_api_call("gemini", tokens_used=800, cost_usd=0.016, cached=True)

        # Check analysis
        analysis = self.cache.get_cost_analysis(days=30)
        self.assertEqual(analysis['summary']['total_api_calls'], 2)
        self.assertEqual(analysis['summary']['total_tokens'], 2050)
        self.assertEqual(analysis['summary']['cached_hits'], 1)

    def test_batch_processing(self):
        """Test batch creation and tracking"""
        batch_id = self.cache.create_batch("test_batch", "technology", 10)
        self.assertIsNotNone(batch_id)

        # Update batch
        self.cache.update_batch("test_batch", tokens=5000, cost=0.10, status="in_progress")

        # Check status
        status = self.cache.batch_status("test_batch")
        self.assertEqual(status['total_tokens'], 5000)
        self.assertEqual(status['status'], 'in_progress')

    def test_cost_analysis(self):
        """Test cost analysis reporting"""
        # Log multiple API calls
        for i in range(5):
            self.cache.log_api_call("gemini", tokens_used=1000 + i*100, cost_usd=0.02 + i*0.002)

        analysis = self.cache.get_cost_analysis(days=30)
        self.assertEqual(analysis['summary']['total_api_calls'], 5)
        self.assertGreater(analysis['summary']['total_cost_usd'], 0.1)


class TestSEOInfrastructure(unittest.TestCase):
    """Test SEO infrastructure generation"""

    def setUp(self):
        """Skip the class when the SEO module is not importable."""
        if not SEO_AVAILABLE:
            self.skipTest("seo_infrastructure module not available")

    def test_organization_schema(self):
        """Test organization schema generation"""
        schema = JSONLDGenerator.organization()
        self.assertEqual(schema['@type'], 'Organization')
        self.assertEqual(schema['name'], 'Avoltium')
        self.assertIn('url', schema)

    def test_article_schema(self):
        """Test article schema generation"""
        schema = JSONLDGenerator.article(
            title="Test Article",
            content="Test content",
            author="Test Author"
        )
        self.assertEqual(schema['@type'], 'BlogPosting')
        self.assertEqual(schema['headline'], "Test Article")
        self.assertIn('datePublished', schema)

    def test_breadcrumb_schema(self):
        """Test breadcrumb schema generation"""
        items = [
            {"name": "Home", "url": "https://example.com"},
            {"name": "Blog", "url": "https://example.com/blog"},
            {"name": "Article", "url": "https://example.com/blog/article"}
        ]
        schema = JSONLDGenerator.breadcrumb(items)
        self.assertEqual(schema['@type'], 'BreadcrumbList')
        self.assertEqual(len(schema['itemListElement']), 3)

    def test_faq_schema(self):
        """Test FAQ page schema"""
        questions = [
            {"question": "Q1?", "answer": "A1"},
            {"question": "Q2?", "answer": "A2"}
        ]
        schema = JSONLDGenerator.faq(questions)
        self.assertEqual(schema['@type'], 'FAQPage')
        self.assertEqual(len(schema['mainEntity']), 2)

    def test_sitemap_generation(self):
        """Test sitemap XML generation"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            sitemap_path = f.name

        urls = [
            {
                "loc": "https://example.com/",
                "lastmod": "2026-08-09",
                "changefreq": "daily",
                "priority": "1.0"
            }
        ]

        path = SitemapGenerator.generate(urls, sitemap_path)
        self.assertTrue(os.path.exists(path))

        with open(path) as f:
            content = f.read()
            self.assertIn('<urlset', content)
            self.assertIn('https://example.com/', content)

        os.remove(path)

    def test_robots_txt_generation(self):
        """Test robots.txt generation"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            robots_path = f.name

        path = RobotsGenerator.generate(
            "https://example.com/sitemap.xml",
            robots_path
        )
        self.assertTrue(os.path.exists(path))

        with open(path) as f:
            content = f.read()
            self.assertIn('User-agent', content)
            self.assertIn('Sitemap:', content)

        os.remove(path)

    def test_meta_tags_optimization(self):
        """Test meta tag generation"""
        tags = MetaTagOptimizer.generate_meta_tags(
            title="Test Page",
            description="Test description",
            keywords=["test", "page"]
        )
        self.assertEqual(tags['title'], "Test Page")
        self.assertEqual(tags['description'], "Test description")
        self.assertIn('og:title', tags)
        self.assertIn('twitter:card', tags)

    def test_meta_tags_html_rendering(self):
        """Test HTML rendering of meta tags"""
        tags = MetaTagOptimizer.generate_meta_tags(
            title="Test",
            description="Test description"
        )
        html = MetaTagOptimizer.render_meta_html(tags)
        self.assertIn('<title>', html)
        self.assertIn('<meta', html)
        self.assertIn('name="description"', html)


class TestPerformanceOptimization(unittest.TestCase):
    """Test performance optimization utilities"""

    def setUp(self):
        """Skip the class when the performance module is not importable."""
        if not PERF_AVAILABLE:
            self.skipTest("shared_performance module not available")

    def test_vitals_db_migrates_from_the_fid_schema(self):
        """A database created before the INP rename must not break on insert.

        CREATE TABLE IF NOT EXISTS is a no-op against an existing file, so
        without an explicit migration record_metrics fails with "no column
        named inp" on every deployment that had already recorded anything.
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as fh:
            db_path = fh.name
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("""
                    CREATE TABLE web_vitals (
                        id INTEGER PRIMARY KEY, url TEXT NOT NULL,
                        lcp REAL, fid REAL, cls REAL, ttfb REAL, fcp REAL,
                        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
                """)
                conn.execute("INSERT INTO web_vitals (url, lcp, fid, cls)"
                             " VALUES ('/old', 2000, 80, 0.05)")

            monitor = CoreWebVitalsMonitor(db_path)
            monitor.record_metrics("/new", lcp=2100, inp=150, cls=0.08)
            self.assertEqual(monitor.get_metrics_report()['metrics']['INP']['value'], 150)

            # The old readings were real measurements; the migration keeps them.
            with sqlite3.connect(db_path) as conn:
                self.assertEqual(
                    conn.execute("SELECT fid FROM web_vitals WHERE url='/old'").fetchone()[0], 80)
        finally:
            os.remove(db_path)

    def test_vitals_report_marks_an_empty_metric_no_data(self):
        """AVG() over a column nothing was written to is NULL, not a bad score."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as fh:
            db_path = fh.name
        try:
            monitor = CoreWebVitalsMonitor(db_path)
            monitor.record_metrics("/", lcp=2100, inp=150, cls=0.08)
            metrics = monitor.get_metrics_report()['metrics']
            self.assertEqual(metrics['TTFB']['status'], 'no_data')
            self.assertIsNone(metrics['TTFB']['value'])
            self.assertEqual(metrics['LCP']['status'], 'good')
        finally:
            os.remove(db_path)

    def test_image_optimization_config(self):
        """Test image optimization specifications"""
        hero_config = ImageOptimizer.get_image_config("hero")
        self.assertEqual(hero_config['width'], 1200)
        self.assertEqual(hero_config['height'], 675)

    def test_responsive_image_html(self):
        """Test responsive image HTML generation"""
        html = ImageOptimizer.generate_responsive_html(
            "https://example.com/image.jpg",
            "Test image",
            context="hero",
            lazy_load=True
        )
        self.assertIn('<picture>', html)
        self.assertIn('webp', html)
        self.assertIn('loading="lazy"', html)

    def test_cache_headers(self):
        """Test cache header generation"""
        headers = CachingStrategy.get_cache_headers("image")
        self.assertIn('Cache-Control', headers)
        self.assertIn('max-age', headers['Cache-Control'])

    def test_cloudflare_cache_rules(self):
        """Test Cloudflare cache rules generation"""
        rules = CachingStrategy.get_cloudflare_cache_rules()
        self.assertIn('static_assets', rules)
        self.assertIn('html_pages', rules)
        self.assertEqual(rules['static_assets']['browser_cache_ttl'], 31536000)

    def test_core_web_vitals_monitoring(self):
        """Test Core Web Vitals tracking"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            db_path = f.name

        monitor = CoreWebVitalsMonitor(db_path)

        # Record metrics
        monitor.record_metrics(
            url="https://example.com/",
            lcp=2100,
            inp=150,
            cls=0.08
        )

        # Check report
        report = monitor.get_metrics_report(days=30)
        self.assertEqual(report['metrics']['LCP']['value'], 2100)
        self.assertEqual(report['metrics']['INP']['value'], 150)
        self.assertEqual(report['metrics']['CLS']['value'], 0.08)

        os.remove(db_path)

    def test_performance_budget(self):
        """Test performance budget tracking"""
        budget = PerformanceBudget.get_budget()
        self.assertIn('bundle_js', budget)
        self.assertEqual(budget['lcp']['value'], 2500)

    def test_performance_budget_violation(self):
        """Test performance budget violation detection"""
        actual = {
            "bundle_js": 200,  # Over budget (150kb)
            "lcp": 3000,  # Over budget (2500ms)
        }
        violations = PerformanceBudget.check_budget(actual)
        self.assertEqual(len(violations), 2)


class TestIntegration(unittest.TestCase):
    """Integration tests across modules"""

    def test_all_modules_importable(self):
        """Test all Phase 1 modules can be imported"""
        modules = []
        if CACHE_AVAILABLE:
            modules.append("token_cache")
        if SEO_AVAILABLE:
            modules.append("seo_infrastructure")
        if PERF_AVAILABLE:
            modules.append("shared_performance")

        self.assertGreater(len(modules), 0, "At least one module should be available")

    def test_cache_with_seo_workflow(self):
        """Test caching with SEO infrastructure"""
        if not (CACHE_AVAILABLE and SEO_AVAILABLE):
            self.skipTest("Required modules not available")

        # Create cache
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_db.close()
        cache = TokenCache(temp_db.name)

        # Generate schema
        schema = JSONLDGenerator.article(
            title="Test",
            content="Content"
        )

        # Cache schema
        cache.cache_content(
            topic="test_article",
            content=json.dumps(schema),
            params={},
            tokens_saved=100
        )

        # Verify it's cached
        cached = cache.get_cached_content("test_article", {})
        self.assertIsNotNone(cached)

        os.remove(temp_db.name)


def run_tests():
    """Run all tests with verbose output"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestTokenCache))
    suite.addTests(loader.loadTestsFromTestCase(TestSEOInfrastructure))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceOptimization))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*70)
    print("PHASE 1 INTEGRATION TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*70)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
