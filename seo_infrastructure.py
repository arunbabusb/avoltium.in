"""
SEO Infrastructure Setup for Avoltium.in
- JSON-LD schema generation
- Sitemap generation
- Meta tag optimization
- Structured data for search engines
"""

import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seo_infrastructure")


class JSONLDGenerator:
    """Generate JSON-LD structured data for content."""

    @staticmethod
    def organization() -> Dict[str, Any]:
        """Organization schema for Avoltium.in."""
        return {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "Avoltium",
            "url": "https://www.avoltium.in",
            "logo": "https://www.avoltium.in/logo.png",
            "description": "AI-powered content generation platform for creators and marketers",
            "sameAs": [
                "https://twitter.com/avoltium",
                "https://linkedin.com/company/avoltium"
            ],
            "contactPoint": {
                "@type": "ContactPoint",
                "contactType": "Customer Support",
                "email": "support@avoltium.in"
            }
        }

    @staticmethod
    def article(
        title: str,
        content: str,
        author: str = "Avoltium",
        publish_date: Optional[str] = None,
        image_url: Optional[str] = None,
        article_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Article schema for blog posts/content."""
        if not publish_date:
            publish_date = datetime.utcnow().isoformat() + "Z"

        schema = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": title,
            "articleBody": content,
            "author": {
                "@type": "Person",
                "name": author
            },
            "datePublished": publish_date,
            "dateModified": datetime.utcnow().isoformat() + "Z",
        }

        if image_url:
            schema["image"] = image_url

        if article_url:
            schema["url"] = article_url

        return schema

    @staticmethod
    def breadcrumb(items: List[Dict[str, str]]) -> Dict[str, Any]:
        """Breadcrumb navigation schema."""
        breadcrumb_list = []
        for idx, item in enumerate(items, 1):
            breadcrumb_list.append({
                "@type": "ListItem",
                "position": idx,
                "name": item.get("name"),
                "item": item.get("url")
            })

        return {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": breadcrumb_list
        }

    @staticmethod
    def faq(questions: List[Dict[str, str]]) -> Dict[str, Any]:
        """FAQ page schema."""
        faq_items = []
        for q in questions:
            faq_items.append({
                "@type": "Question",
                "name": q.get("question"),
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": q.get("answer")
                }
            })

        return {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": faq_items
        }


class SitemapGenerator:
    """Generate XML sitemaps for search engines."""

    @staticmethod
    def generate(
        urls: List[Dict[str, Any]],
        output_path: str = "sitemap.xml"
    ) -> str:
        """
        Generate sitemap.xml file.

        Args:
            urls: List of dicts with 'loc', 'lastmod', 'changefreq', 'priority'
            output_path: Where to write the sitemap

        Returns:
            Path to generated sitemap
        """
        urlset = ET.Element("urlset")
        urlset.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")

        for url_data in urls:
            url_elem = ET.SubElement(urlset, "url")

            loc = ET.SubElement(url_elem, "loc")
            loc.text = url_data.get("loc")

            if url_data.get("lastmod"):
                lastmod = ET.SubElement(url_elem, "lastmod")
                lastmod.text = url_data.get("lastmod")

            if url_data.get("changefreq"):
                changefreq = ET.SubElement(url_elem, "changefreq")
                changefreq.text = url_data.get("changefreq")

            if url_data.get("priority"):
                priority = ET.SubElement(url_elem, "priority")
                priority.text = str(url_data.get("priority"))

        # Pretty print
        xml_str = minidom.parseString(ET.tostring(urlset)).toprettyxml(indent="  ")
        # Remove extra blank lines
        xml_str = "\n".join([line for line in xml_str.split("\n") if line.strip()])

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_str)

        logger.info(f"✓ Generated sitemap with {len(urls)} URLs: {output_path}")
        return output_path

    @staticmethod
    def generate_sitemap_index(
        sitemaps: List[Dict[str, str]],
        output_path: str = "sitemap_index.xml"
    ) -> str:
        """
        Generate sitemap index for large sites.

        Args:
            sitemaps: List of dicts with 'loc', 'lastmod'
            output_path: Where to write the index

        Returns:
            Path to generated index
        """
        sitemapindex = ET.Element("sitemapindex")
        sitemapindex.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")

        for sitemap in sitemaps:
            sitemap_elem = ET.SubElement(sitemapindex, "sitemap")

            loc = ET.SubElement(sitemap_elem, "loc")
            loc.text = sitemap.get("loc")

            if sitemap.get("lastmod"):
                lastmod = ET.SubElement(sitemap_elem, "lastmod")
                lastmod.text = sitemap.get("lastmod")

        xml_str = minidom.parseString(ET.tostring(sitemapindex)).toprettyxml(indent="  ")
        xml_str = "\n".join([line for line in xml_str.split("\n") if line.strip()])

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_str)

        logger.info(f"✓ Generated sitemap index with {len(sitemaps)} sitemaps: {output_path}")
        return output_path


class RobotsGenerator:
    """Generate robots.txt for search engine crawlers."""

    @staticmethod
    def generate(
        sitemap_url: str,
        disallow_paths: List[str] = None,
        output_path: str = "robots.txt"
    ) -> str:
        """Generate robots.txt file."""
        if disallow_paths is None:
            disallow_paths = [
                "/admin",
                "/wp-admin",
                "/wp-includes",
                "/*?",
                "/search",
                "/cart"
            ]

        content = "# Avoltium.in robots.txt\n"
        content += "User-agent: *\n"
        content += "Allow: /\n"

        for path in disallow_paths:
            content += f"Disallow: {path}\n"

        content += f"\nSitemap: {sitemap_url}\n"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"✓ Generated robots.txt: {output_path}")
        return output_path


class MetaTagOptimizer:
    """Generate optimized meta tags for content."""

    @staticmethod
    def generate_meta_tags(
        title: str,
        description: str,
        image_url: str = None,
        url: str = None,
        keywords: List[str] = None,
        author: str = "Avoltium"
    ) -> Dict[str, str]:
        """Generate meta tags for a page."""
        # Ensure title is 50-60 chars
        title = title[:60] if len(title) > 60 else title

        # Ensure description is 150-160 chars
        description = description[:160] if len(description) > 160 else description

        tags = {
            "title": title,
            "description": description,
            "author": author,
            "og:title": title,
            "og:description": description,
            "og:type": "article",
            "twitter:card": "summary_large_image",
            "twitter:title": title,
            "twitter:description": description,
        }

        if image_url:
            tags["og:image"] = image_url
            tags["twitter:image"] = image_url

        if url:
            tags["og:url"] = url
            tags["canonical"] = url

        if keywords:
            tags["keywords"] = ", ".join(keywords[:5])  # Max 5 keywords

        return tags

    @staticmethod
    def render_meta_html(meta_tags: Dict[str, str]) -> str:
        """Render meta tags as HTML."""
        html = []
        for key, value in meta_tags.items():
            if key == "title":
                html.append(f"<title>{value}</title>")
            elif key == "canonical":
                html.append(f'<link rel="canonical" href="{value}" />')
            elif key.startswith("og:"):
                html.append(f'<meta property="{key}" content="{value}" />')
            elif key.startswith("twitter:"):
                html.append(f'<meta name="{key}" content="{value}" />')
            else:
                html.append(f'<meta name="{key}" content="{value}" />')

        return "\n".join(html)


class GSCSetup:
    """Google Search Console setup instructions and validation."""

    @staticmethod
    def get_setup_checklist() -> List[Dict[str, str]]:
        """Get GSC setup checklist."""
        return [
            {
                "step": 1,
                "title": "Verify Ownership",
                "details": "Add DNS TXT record or HTML file to verify domain ownership",
                "action": "Add verification method in Google Search Console"
            },
            {
                "step": 2,
                "title": "Submit Sitemap",
                "details": "Submit sitemap.xml to GSC for indexing",
                "action": "Go to Sitemaps section and submit https://avoltium.in/sitemap.xml"
            },
            {
                "step": 3,
                "title": "Set Preferred Domain",
                "details": "Specify www vs non-www version",
                "action": "Settings → Site Settings → Preferred domain"
            },
            {
                "step": 4,
                "title": "Set Target Audience",
                "details": "Set geographic targeting",
                "action": "Settings → Audience"
            },
            {
                "step": 5,
                "title": "Monitor Coverage",
                "details": "Check index coverage and fix errors",
                "action": "Index Coverage report → Fix exclusions"
            },
            {
                "step": 6,
                "title": "Submit URL Inspection",
                "details": "Test specific URLs for indexing",
                "action": "URL Inspection tool → Request indexing"
            }
        ]


if __name__ == "__main__":
    # Example usage
    logger.info("=== SEO Infrastructure Setup ===\n")

    # 1. Generate Organization schema
    org_schema = JSONLDGenerator.organization()
    print("Organization Schema:")
    print(json.dumps(org_schema, indent=2))
    print()

    # 2. Generate Article schema
    article_schema = JSONLDGenerator.article(
        title="How to Use AI for Content Generation",
        content="This is an example article...",
        image_url="https://avoltium.in/images/ai-content.jpg",
        article_url="https://avoltium.in/blog/ai-content-generation/"
    )
    print("Article Schema:")
    print(json.dumps(article_schema, indent=2))
    print()

    # 3. Generate Sitemap
    urls = [
        {
            "loc": "https://avoltium.in/",
            "lastmod": datetime.utcnow().isoformat(),
            "changefreq": "daily",
            "priority": "1.0"
        },
        {
            "loc": "https://avoltium.in/features/",
            "lastmod": datetime.utcnow().isoformat(),
            "changefreq": "weekly",
            "priority": "0.8"
        },
        {
            "loc": "https://avoltium.in/pricing/",
            "lastmod": datetime.utcnow().isoformat(),
            "changefreq": "monthly",
            "priority": "0.7"
        }
    ]
    SitemapGenerator.generate(urls)

    # 4. Generate robots.txt
    RobotsGenerator.generate("https://avoltium.in/sitemap.xml")

    # 5. Generate meta tags
    meta_tags = MetaTagOptimizer.generate_meta_tags(
        title="AI Article Generator - Avoltium",
        description="Generate high-quality articles with AI in seconds",
        image_url="https://avoltium.in/images/hero.jpg",
        url="https://avoltium.in/",
        keywords=["AI", "content generation", "automation"]
    )
    print("Meta Tags (HTML):")
    print(MetaTagOptimizer.render_meta_html(meta_tags))
    print()

    # 6. GSC Setup
    print("Google Search Console Setup Checklist:")
    for item in GSCSetup.get_setup_checklist():
        print(f"Step {item['step']}: {item['title']}")
        print(f"  Details: {item['details']}")
        print(f"  Action: {item['action']}\n")
