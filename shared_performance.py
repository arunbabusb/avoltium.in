"""
Shared Performance Optimization Module
For both Avoltium.in and TechJobs360.com
- Image optimization strategies
- CSS/JS minification
- Caching strategies
- Core Web Vitals monitoring
"""

import hashlib
import time
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("performance")


class ImageOptimizer:
    """Optimize images for web delivery."""

    # Recommended image sizes for different contexts
    IMAGE_SPECS = {
        "hero": {"width": 1200, "height": 675, "quality": 85},
        "featured": {"width": 600, "height": 400, "quality": 80},
        "thumbnail": {"width": 300, "height": 200, "quality": 75},
        "card": {"width": 400, "height": 300, "quality": 80},
        "avatar": {"width": 150, "height": 150, "quality": 85},
    }

    FORMATS = {
        "modern": "webp",  # Modern browsers - best compression
        "fallback": "jpg",  # JPEG fallback for older browsers
        "png": "png"  # PNG for graphics with transparency
    }

    @staticmethod
    def get_image_config(context: str) -> Dict[str, int]:
        """Get recommended image dimensions for context."""
        return ImageOptimizer.IMAGE_SPECS.get(context, ImageOptimizer.IMAGE_SPECS["card"])

    @staticmethod
    def generate_responsive_html(
        image_url: str,
        alt_text: str,
        context: str = "card",
        lazy_load: bool = True
    ) -> str:
        """Generate responsive image HTML with WebP support."""
        config = ImageOptimizer.get_image_config(context)
        width = config["width"]
        height = config["height"]

        loading_attr = 'loading="lazy"' if lazy_load else ""

        html = f"""<picture>
  <source
    srcset="{image_url}?w={width}&h={height}&fm=webp&q={config['quality']} 1x,
            {image_url}?w={width * 2}&h={height * 2}&fm=webp&q={config['quality']} 2x"
    type="image/webp"
  >
  <source
    srcset="{image_url}?w={width}&h={height}&fm=jpg&q={config['quality']} 1x,
            {image_url}?w={width * 2}&h={height * 2}&fm=jpg&q={config['quality']} 2x"
    type="image/jpeg"
  >
  <img
    src="{image_url}?w={width}&h={height}&fm=jpg&q={config['quality']}"
    alt="{alt_text}"
    width="{width}"
    height="{height}"
    {loading_attr}
    decoding="async"
  >
</picture>"""
        return html


class CachingStrategy:
    """Caching strategies for different content types."""

    # Cache TTL in seconds
    CACHE_TTLS = {
        "html_page": 3600,  # 1 hour
        "html_homepage": 300,  # 5 minutes (changes frequently)
        "api_response": 1800,  # 30 minutes
        "image": 86400 * 30,  # 30 days
        "css": 86400 * 365,  # 1 year (versioned)
        "js": 86400 * 365,  # 1 year (versioned)
        "json": 3600,  # 1 hour
    }

    @staticmethod
    def get_cache_headers(content_type: str) -> Dict[str, str]:
        """Get cache headers for content type."""
        ttl = CachingStrategy.CACHE_TTLS.get(content_type, 3600)

        max_age = ttl
        expires = datetime.utcnow() + timedelta(seconds=ttl)

        return {
            "Cache-Control": f"public, max-age={max_age}",
            "Expires": expires.strftime("%a, %d %b %Y %H:%M:%S GMT"),
            "Pragma": "cache" if ttl > 0 else "no-cache",
        }

    @staticmethod
    def get_cloudflare_cache_rules() -> Dict[str, Dict[str, Any]]:
        """Get Cloudflare cache rules configuration."""
        return {
            "static_assets": {
                "path_pattern": "/static/*",
                "browser_cache_ttl": 31536000,  # 1 year
                "edge_cache_ttl": 31536000,
                "cache_on_cookie": None
            },
            "api_responses": {
                "path_pattern": "/api/*",
                "browser_cache_ttl": 0,  # Don't cache in browser
                "edge_cache_ttl": 1800,  # 30 min on edge
                "cache_on_cookie": None
            },
            "html_pages": {
                "path_pattern": "/*.html",
                "browser_cache_ttl": 3600,  # 1 hour
                "edge_cache_ttl": 3600,
                "cache_on_cookie": None
            },
            "homepage": {
                "path_pattern": "/",
                "browser_cache_ttl": 300,  # 5 min
                "edge_cache_ttl": 600,  # 10 min on edge
                "cache_on_cookie": None
            }
        }


class CoreWebVitalsMonitor:
    """Monitor and track Core Web Vitals metrics."""

    def __init__(self, db_path: str = "web_vitals.db"):
        """Open (creating if needed) the SQLite file that stores the metrics."""
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize metrics database."""
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS web_vitals (
                    id INTEGER PRIMARY KEY,
                    url TEXT NOT NULL,
                    lcp REAL,
                    inp REAL,
                    cls REAL,
                    ttfb REAL,
                    fcp REAL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def record_metrics(
        self,
        url: str,
        lcp: Optional[float] = None,
        inp: Optional[float] = None,
        cls: Optional[float] = None,
        ttfb: Optional[float] = None,
        fcp: Optional[float] = None
    ):
        """Record Core Web Vitals metrics."""
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO web_vitals (url, lcp, inp, cls, ttfb, fcp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (url, lcp, inp, cls, ttfb, fcp))
            conn.commit()

    def get_metrics_report(self, days: int = 30) -> Dict[str, Any]:
        """Generate metrics report."""
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    AVG(lcp) as avg_lcp,
                    AVG(inp) as avg_inp,
                    AVG(cls) as avg_cls,
                    AVG(ttfb) as avg_ttfb,
                    AVG(fcp) as avg_fcp,
                    COUNT(*) as samples
                FROM web_vitals
                WHERE recorded_at > datetime('now', '-' || ? || ' days')
            """, (days,))

            result = cursor.fetchone()

        def entry(value, unit, target):
            """One metric, with "no_data" kept distinct from a failing score."""
            # AVG() over a column nothing was recorded into returns NULL.
            # Reporting that as "needs_improvement" invents a bad score out of
            # an empty table, which is how you end up chasing a regression
            # that never happened.
            if value is None:
                status = "no_data"
            else:
                status = "good" if value <= target else "needs_improvement"
            return {"value": value, "unit": unit, "target": target, "status": status}

        return {
            "period_days": days,
            "metrics": {
                "LCP": entry(result[0], "ms", 2500),
                # INP replaced FID as a Core Web Vital in March 2024. The
                # threshold is 200 ms, not FID's 100 ms, and it measures the
                # whole interaction rather than only the delay before handling.
                "INP": entry(result[1], "ms", 200),
                "CLS": entry(result[2], "", 0.1),
                "TTFB": entry(result[3], "ms", 600),
                "FCP": entry(result[4], "ms", 1800),
            },
            "samples": result[5]
        }


class CriticalCSSExtractor:
    """Extract critical CSS for above-the-fold content."""

    @staticmethod
    def generate_inline_css() -> str:
        """Generate critical CSS for inline injection."""
        return """
/* Critical CSS - Inline for fastest paint */
:root {
  --font-system: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --color-text: #1a1a1a;
  --color-bg: #ffffff;
  --color-primary: #0066cc;
  --spacing-unit: 1rem;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html {
  font-size: 16px;
}

body {
  font-family: var(--font-system);
  line-height: 1.5;
  color: var(--color-text);
  background: var(--color-bg);
}

/* Hero / above-the-fold */
.hero {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.hero h1 {
  font-size: clamp(2rem, 5vw, 3.5rem);
  margin-bottom: 1rem;
}

/* Navigation */
header {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--color-bg);
  border-bottom: 1px solid #eee;
}

nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

/* Cards */
.card {
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  padding: 1.5rem;
  margin-bottom: 1rem;
}

/* Grid */
.grid {
  display: grid;
  gap: 1.5rem;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
}

/* Typography */
h2 {
  font-size: clamp(1.5rem, 4vw, 2.5rem);
  margin-bottom: 0.5rem;
}

a {
  color: var(--color-primary);
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

/* Loading state */
.skeleton {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: loading 1.5s infinite;
}

@keyframes loading {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
"""


class PerformanceBudget:
    """Define and monitor performance budgets."""

    BUDGETS = {
        "bundle_js": {
            "value": 150,
            "unit": "kb",
            "metric": "Total JS size"
        },
        "bundle_css": {
            "value": 50,
            "unit": "kb",
            "metric": "Total CSS size"
        },
        "images": {
            "value": 200,
            "unit": "kb",
            "metric": "Above-fold images total"
        },
        "requests": {
            "value": 45,
            "unit": "count",
            "metric": "HTTP requests"
        },
        "lcp": {
            "value": 2500,
            "unit": "ms",
            "metric": "Largest Contentful Paint"
        },
        "inp": {
            "value": 200,
            "unit": "ms",
            "metric": "Interaction to Next Paint"
        },
        "cls": {
            "value": 0.1,
            "unit": "",
            "metric": "Cumulative Layout Shift"
        }
    }

    @staticmethod
    def get_budget() -> Dict[str, Dict[str, Any]]:
        """Get performance budget definition."""
        return PerformanceBudget.BUDGETS

    @staticmethod
    def check_budget(actual: Dict[str, float]) -> List[Dict[str, Any]]:
        """Check if metrics are within budget."""
        violations = []

        for metric, budget in PerformanceBudget.BUDGETS.items():
            if metric in actual:
                if actual[metric] > budget["value"]:
                    violations.append({
                        "metric": metric,
                        "budget": budget["value"],
                        "actual": actual[metric],
                        "unit": budget["unit"],
                        "overflow": actual[metric] - budget["value"]
                    })

        return violations


if __name__ == "__main__":
    logger.info("=== Performance Optimization Module ===\n")

    # 1. Image optimization
    print("Responsive Image HTML:")
    img_html = ImageOptimizer.generate_responsive_html(
        "https://example.com/image.jpg",
        "Product showcase",
        context="hero",
        lazy_load=True
    )
    print(img_html)
    print()

    # 2. Cache headers
    print("Cache Headers for Different Content Types:")
    for content_type in ["html_page", "api_response", "image", "css"]:
        headers = CachingStrategy.get_cache_headers(content_type)
        print(f"  {content_type}:")
        for key, value in headers.items():
            print(f"    {key}: {value}")
    print()

    # 3. Core Web Vitals
    monitor = CoreWebVitalsMonitor()
    monitor.record_metrics("https://example.com/", lcp=2100, inp=150, cls=0.08)
    monitor.record_metrics("https://example.com/products", lcp=2800, inp=260, cls=0.12)

    report = monitor.get_metrics_report()
    print("Core Web Vitals Report:")
    for metric, data in report["metrics"].items():
        value = data["value"]
        # AVG() over a column nothing was recorded into returns NULL, and
        # formatting None with :.0f raises. CLS is a small unitless ratio, so
        # rounding it to whole numbers printed every score as 0.
        if value is None:
            shown = "no samples"
        elif data["unit"]:
            shown = f"{value:.0f}{data['unit']}"
        else:
            shown = f"{value:.3f}"
        print(f"  {metric}: {shown} ({data['status']})")
    print()

    # 4. Performance budget
    print("Performance Budget Check:")
    actual_metrics = {
        "bundle_js": 180,
        "bundle_css": 45,
        "lcp": 2300,
        "inp": 180
    }
    violations = PerformanceBudget.check_budget(actual_metrics)
    if violations:
        print("  ⚠️ Budget violations:")
        for v in violations:
            print(f"    - {v['metric']}: {v['actual']}{v['unit']} (budget: {v['budget']})")
    else:
        print("  ✓ All metrics within budget")
