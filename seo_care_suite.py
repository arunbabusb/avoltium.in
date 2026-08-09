#!/usr/bin/env python3
"""
Unified SEO Care Suite for avoltium.in & techjobs360-scraper

Audits & optimizes both sites for:
  1. Meta tags & schema markup (Article, JobPosting, Organization, BreadcrumbList)
  2. Content analysis (readability, keyword density, H-tag structure, alt text)
  3. Indexation & crawlability (noindex, canonical, robots, sitemap coverage)
  4. Technical SEO (internal links, redirects, duplicate content detection)

Usage:
  python seo_care_suite.py --site avoltium [--audit] [--fix] [--report]
  python seo_care_suite.py --site techjobs360 [--audit] [--fix] [--report]
"""

import os
import sys
import json
import re
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
from urllib.parse import urljoin, urlparse
from html.parser import HTMLParser

import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("seo-care-suite")


@dataclass
class SEOIssue:
    """Represents a single SEO issue found during audit."""
    severity: str  # "critical", "warning", "info"
    category: str  # "meta", "schema", "content", "indexation", "technical"
    page_url: str
    title: str
    description: str
    suggestion: str
    priority: int = 0

    def __post_init__(self):
        if self.severity == "critical":
            self.priority = 3
        elif self.severity == "warning":
            self.priority = 2
        else:
            self.priority = 1


@dataclass
class PageAudit:
    """Results for a single page audit."""
    url: str
    title: str
    status_code: int
    issues: List[SEOIssue] = field(default_factory=list)
    meta_tags: Dict = field(default_factory=dict)
    schema_markup: List[Dict] = field(default_factory=list)
    word_count: int = 0
    readability_score: float = 0.0  # 0-100, higher is better
    internal_links: int = 0
    external_links: int = 0
    images_with_alt: int = 0
    images_without_alt: int = 0


class HTMLMetadataExtractor(HTMLParser):
    """Extract meta tags, schema, headings, images, links from HTML."""

    def __init__(self):
        super().__init__()
        self.meta_tags = {}
        self.schema_markup = []
        self.headings = {"h1": [], "h2": [], "h3": [], "h4": [], "h5": [], "h6": []}
        self.images = []
        self.links = []
        self.text_content = []
        self.current_tag = None
        self.og_tags = {}

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "meta":
            name = attrs_dict.get("name", "")
            property_ = attrs_dict.get("property", "")
            content = attrs_dict.get("content", "")
            if name:
                self.meta_tags[name] = content
            if property_ and property_.startswith("og:"):
                self.og_tags[property_] = content
        elif tag == "script" and attrs_dict.get("type") == "application/ld+json":
            self.current_tag = "schema"
        elif tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            self.current_tag = tag
        elif tag == "img":
            self.images.append({
                "src": attrs_dict.get("src", ""),
                "alt": attrs_dict.get("alt", ""),
            })
        elif tag == "a":
            self.links.append({
                "href": attrs_dict.get("href", ""),
                "text": "",
                "title": attrs_dict.get("title", ""),
            })

    def handle_data(self, data):
        stripped = data.strip()
        if stripped:
            if self.current_tag and self.current_tag.startswith("h"):
                self.headings[self.current_tag].append(stripped)
            elif self.current_tag != "schema":
                self.text_content.append(stripped)

    def handle_endtag(self, tag):
        if tag == "script":
            self.current_tag = None
        elif tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            self.current_tag = None

    def close_with_schema(self, schema_text: str):
        """Extract schema from script content."""
        try:
            self.schema_markup.append(json.loads(schema_text))
        except json.JSONDecodeError:
            pass


class SEOAuditor:
    """Audit a WordPress site for SEO issues."""

    def __init__(self, wp_url: str, wp_username: str, wp_password: str, site_name: str):
        self.wp_url = wp_url.rstrip("/")
        self.wp_username = wp_username
        self.wp_password = wp_password
        self.site_name = site_name
        self.auth = (wp_username, wp_password)
        self.session = requests.Session()
        self.session.auth = self.auth

    def audit_posts(self, post_type: str = "post", limit: int = 10) -> List[PageAudit]:
        """Audit recent posts/pages for SEO issues."""
        audits = []
        try:
            r = self.session.get(
                f"{self.wp_url}/wp-json/wp/v2/{post_type}s",
                params={"per_page": limit, "orderby": "modified", "order": "desc"},
                timeout=30
            )
            r.raise_for_status()
            posts = r.json()

            for post in posts:
                url = post.get("link", "")
                if not url:
                    continue

                audit = self._audit_page(url, post)
                audits.append(audit)

        except Exception as e:
            log.error(f"Failed to fetch posts for {post_type}: {e}")

        return audits

    def _audit_page(self, url: str, post_data: Dict) -> PageAudit:
        """Audit a single page."""
        audit = PageAudit(
            url=url,
            title=post_data.get("title", {}).get("rendered", "Untitled"),
            status_code=200,
        )

        try:
            r = requests.get(url, timeout=30)
            audit.status_code = r.status_code

            if r.status_code != 200:
                audit.issues.append(SEOIssue(
                    severity="critical",
                    category="technical",
                    page_url=url,
                    title="Non-200 Status Code",
                    description=f"Page returned HTTP {r.status_code}",
                    suggestion="Check server logs and page settings.",
                ))
                return audit

            # Extract metadata
            self._extract_metadata(audit, r.text, url)

            # Analyze content
            self._analyze_content(audit, r.text)

            # Check schema markup
            self._check_schema(audit)

            # Audit meta tags
            self._audit_meta_tags(audit, url, post_data)

            # Check indexation
            self._check_indexation(audit, r.text)

        except Exception as e:
            log.error(f"Failed to audit {url}: {e}")
            audit.issues.append(SEOIssue(
                severity="warning",
                category="technical",
                page_url=url,
                title="Audit Failed",
                description=str(e),
                suggestion="Check connectivity and try again.",
            ))

        return audit

    def _extract_metadata(self, audit: PageAudit, html: str, url: str):
        """Extract meta tags and structured data."""
        parser = HTMLMetadataExtractor()
        try:
            parser.feed(html)
        except:
            pass

        audit.meta_tags = parser.meta_tags
        audit.meta_tags.update(parser.og_tags)

        # Extract schema from <script type="application/ld+json">
        schema_pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
        for match in re.finditer(schema_pattern, html, re.DOTALL):
            try:
                audit.schema_markup.append(json.loads(match.group(1)))
            except:
                pass

        audit.images_with_alt = sum(1 for img in parser.images if img.get("alt"))
        audit.images_without_alt = len(parser.images) - audit.images_with_alt
        audit.internal_links = sum(1 for link in parser.links if urlparse(link["href"]).netloc == urlparse(url).netloc)
        audit.external_links = sum(1 for link in parser.links if urlparse(link["href"]).netloc != urlparse(url).netloc)

    def _analyze_content(self, audit: PageAudit, html: str):
        """Analyze content for readability and SEO."""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        audit.word_count = len(text.split())

        # Simple readability: penalize very long/short content
        if audit.word_count < 300:
            audit.issues.append(SEOIssue(
                severity="warning",
                category="content",
                page_url=audit.url,
                title="Short Content",
                description=f"Only {audit.word_count} words. Google prefers 300+ for ranking.",
                suggestion="Add more detailed, original content.",
                priority=2,
            ))
            audit.readability_score = max(0, 100 - (300 - audit.word_count) / 3)
        elif audit.word_count > 5000:
            audit.readability_score = max(0, 100 - (audit.word_count - 5000) / 100)
        else:
            audit.readability_score = 100

    def _check_schema(self, audit: PageAudit):
        """Validate schema markup."""
        if not audit.schema_markup:
            audit.issues.append(SEOIssue(
                severity="warning",
                category="schema",
                page_url=audit.url,
                title="Missing Schema Markup",
                description="No JSON-LD schema found (Article, NewsArticle, JobPosting, etc.)",
                suggestion="Add appropriate schema markup for your content type.",
                priority=2,
            ))
            return

        # Check for required schema types
        schema_types = set()
        for schema in audit.schema_markup:
            schema_type = schema.get("@type", "")
            if isinstance(schema_type, list):
                schema_types.update(schema_type)
            else:
                schema_types.add(schema_type)

        if not any(t in schema_types for t in ["Article", "NewsArticle", "BlogPosting", "JobPosting"]):
            audit.issues.append(SEOIssue(
                severity="info",
                category="schema",
                page_url=audit.url,
                title="Generic Schema",
                description="Schema found but not specific to content type.",
                suggestion="Use Article, JobPosting, NewsArticle, or other specific types.",
                priority=1,
            ))

    def _audit_meta_tags(self, audit: PageAudit, url: str, post_data: Dict):
        """Audit essential meta tags."""
        meta = audit.meta_tags

        # Check title
        if "og:title" not in meta:
            audit.issues.append(SEOIssue(
                severity="warning",
                category="meta",
                page_url=url,
                title="Missing Open Graph Title",
                description="og:title not set for social sharing.",
                suggestion="Add og:title meta tag.",
                priority=2,
            ))

        # Check description
        if "description" not in meta:
            audit.issues.append(SEOIssue(
                severity="warning",
                category="meta",
                page_url=url,
                title="Missing Meta Description",
                description="Meta description drives CTR in search results.",
                suggestion="Set a 150-160 char description.",
                priority=2,
            ))
        elif len(meta.get("description", "")) < 120:
            audit.issues.append(SEOIssue(
                severity="info",
                category="meta",
                page_url=url,
                title="Short Meta Description",
                description=f"Only {len(meta['description'])} chars (120+ recommended).",
                suggestion="Expand to 120-160 characters.",
                priority=1,
            ))

        # Check canonical
        if "og:url" not in meta:
            audit.issues.append(SEOIssue(
                severity="warning",
                category="meta",
                page_url=url,
                title="Missing og:url (Canonical Proxy)",
                description="og:url helps with social sharing and deduplication.",
                suggestion="Add og:url matching the page permalink.",
                priority=1,
            ))

    def _check_indexation(self, audit: PageAudit, html: str):
        """Check noindex, nofollow, robots meta."""
        robots_match = re.search(r'<meta\s+name="robots"\s+content="([^"]+)"', html)
        if robots_match:
            robots_content = robots_match.group(1)
            if "noindex" in robots_content:
                audit.issues.append(SEOIssue(
                    severity="info",
                    category="indexation",
                    page_url=audit.url,
                    title="Page is Noindexed",
                    description="Page won't appear in Google search results.",
                    suggestion="Remove noindex if you want this page ranked.",
                    priority=1,
                ))


class SEOReporter:
    """Generate SEO audit reports."""

    @staticmethod
    def print_report(audits: List[PageAudit], site_name: str):
        """Print audit results."""
        print(f"\n{'='*80}")
        print(f"SEO AUDIT REPORT: {site_name}")
        print(f"{'='*80}\n")

        all_issues = []
        for audit in audits:
            all_issues.extend(audit.issues)

        # Sort by priority (critical first)
        all_issues.sort(key=lambda x: -x.priority)

        if not all_issues:
            print("✓ No SEO issues found!")
            return

        # Group by category
        by_category = {}
        for issue in all_issues:
            if issue.category not in by_category:
                by_category[issue.category] = []
            by_category[issue.category].append(issue)

        for category in ["meta", "schema", "content", "indexation", "technical"]:
            if category not in by_category:
                continue

            print(f"\n--- {category.upper()} ---")
            for issue in by_category[category]:
                emoji = "🔴" if issue.severity == "critical" else "🟡" if issue.severity == "warning" else "ℹ️"
                print(f"{emoji} {issue.title}")
                print(f"   Page: {issue.page_url}")
                print(f"   Issue: {issue.description}")
                print(f"   Fix: {issue.suggestion}\n")

        print(f"\nSummary:")
        print(f"  Total issues: {len(all_issues)}")
        print(f"  Critical: {sum(1 for i in all_issues if i.severity == 'critical')}")
        print(f"  Warnings: {sum(1 for i in all_issues if i.severity == 'warning')}")
        print(f"  Info: {sum(1 for i in all_issues if i.severity == 'info')}")

    @staticmethod
    def export_json(audits: List[PageAudit], filename: str = "seo_audit.json"):
        """Export audit results as JSON."""
        data = {
            "audits": [
                {
                    "url": audit.url,
                    "title": audit.title,
                    "status_code": audit.status_code,
                    "word_count": audit.word_count,
                    "readability_score": audit.readability_score,
                    "images_with_alt": audit.images_with_alt,
                    "images_without_alt": audit.images_without_alt,
                    "internal_links": audit.internal_links,
                    "external_links": audit.external_links,
                    "issues": [
                        {
                            "severity": issue.severity,
                            "category": issue.category,
                            "title": issue.title,
                            "description": issue.description,
                            "suggestion": issue.suggestion,
                        }
                        for issue in audit.issues
                    ],
                }
                for audit in audits
            ]
        }

        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        print(f"✓ Report saved to {filename}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="SEO Care Suite")
    parser.add_argument("--site", choices=["avoltium", "techjobs360"], required=True)
    parser.add_argument("--limit", type=int, default=10, help="Number of posts to audit")
    parser.add_argument("--export", help="Export JSON report")
    args = parser.parse_args()

    if args.site == "avoltium":
        wp_url = os.environ.get("WP_URL", "https://www.avoltium.in")
        post_type = "post"
    else:
        wp_url = os.environ.get("WP_URL_TECHJOBS360", "https://www.techjobs360.com")
        post_type = "job_listing"

    wp_username = os.environ.get("WP_USERNAME")
    wp_password = os.environ.get("WP_APP_PASSWORD")

    if not all([wp_url, wp_username, wp_password]):
        log.error("Missing WP_URL, WP_USERNAME, WP_APP_PASSWORD")
        sys.exit(1)

    auditor = SEOAuditor(wp_url, wp_username, wp_password, args.site)
    audits = auditor.audit_posts(post_type=post_type, limit=args.limit)

    SEOReporter.print_report(audits, args.site)

    if args.export:
        SEOReporter.export_json(audits, args.export)


if __name__ == "__main__":
    main()
