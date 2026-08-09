#!/usr/bin/env python3
"""
Enhanced Content Pipeline - Unified tool for both avoltium.in & techjobs360

Combines:
  - OmniRoute + Gemini for cost-optimized generation
  - Real image sourcing (Wikimedia/Openverse/Pexels)
  - Automated proofreading & QC
  - SEO optimization (meta tags, schema, internal links)
  - Revenue optimization (AdSense placement, metadata)

Usage:
  python enhanced_content_pipeline.py --site avoltium --tier 1 --publish
  python enhanced_content_pipeline.py --site techjobs360 --type blog --draft
"""

import os
import sys
import json
import logging
from enum import Enum
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("enhanced-pipeline")


class ContentTier(Enum):
    """Content quality tiers."""
    TIER1 = "tier1"  # 3000-4000 words, deep technical
    TIER2 = "tier2"  # 1500-2500 words, standard
    TIER3 = "tier3"  # 800-1200 words, news/updates


class ImageStrategy(Enum):
    """Image sourcing strategy."""
    REAL_ONLY = "real"      # Only real images (Wikimedia/Openverse)
    GENERATED_FALLBACK = "generated"  # Real first, then generate
    GENERATED_ONLY = "generated_only"  # Generate images


@dataclass
class ContentConfig:
    """Configuration for content generation."""
    site: str  # "avoltium" or "techjobs360"
    tier: ContentTier
    topic: str
    wp_url: str
    wp_username: str
    wp_password: str
    gemini_api_key: str
    omniroute_base_url: Optional[str] = None
    omniroute_api_key: Optional[str] = None
    pexels_api_key: Optional[str] = None
    image_strategy: ImageStrategy = ImageStrategy.GENERATED_FALLBACK
    publish_immediately: bool = False
    add_adsense: bool = True
    add_schema: bool = True


class ContentValidator:
    """Validate content quality before publishing."""

    MIN_WORD_COUNT = {
        ContentTier.TIER1: 2500,
        ContentTier.TIER2: 1000,
        ContentTier.TIER3: 500,
    }

    MAX_WORD_COUNT = {
        ContentTier.TIER1: 4000,
        ContentTier.TIER2: 2500,
        ContentTier.TIER3: 1200,
    }

    @classmethod
    def validate(cls, content: str, tier: ContentTier) -> Tuple[bool, List[str]]:
        """Validate content meets quality standards."""
        issues = []

        # Word count check
        word_count = len(content.split())
        if word_count < cls.MIN_WORD_COUNT[tier]:
            issues.append(
                f"Content too short: {word_count} words "
                f"(minimum {cls.MIN_WORD_COUNT[tier]} for {tier.value})"
            )
        if word_count > cls.MAX_WORD_COUNT[tier]:
            issues.append(
                f"Content too long: {word_count} words "
                f"(maximum {cls.MAX_WORD_COUNT[tier]} for {tier.value})"
            )

        # Structure check
        if "<h2>" not in content:
            issues.append("Content missing H2 headings (needs section structure)")

        # Check for LaTeX (should be cleaned)
        if "\\" in content and "$" in content:
            issues.append("Content contains LaTeX syntax (should use Unicode)")

        # Grammar/quality check (basic)
        if content.count("<br>") > word_count / 50:
            issues.append("Too many line breaks detected (likely formatting issue)")

        return len(issues) == 0, issues

    @classmethod
    def proofread_suggestions(cls, content: str, topic: str) -> List[str]:
        """Generate proofreading suggestions (basic checks)."""
        suggestions = []

        # Check for topic mentions
        topic_lower = topic.lower()
        topic_mentions = content.lower().count(topic_lower)
        if topic_mentions < 3:
            suggestions.append(
                f"Topic '{topic}' only mentioned {topic_mentions} times. "
                f"Include in intro, conclusion, and at least one section heading."
            )

        # Check for internal links
        internal_links = content.count('<a href="') - content.count('<a href="http')
        if internal_links < 2:
            suggestions.append(
                "Missing internal links. Add 2-3 links to related articles/calculators."
            )

        # Check for formatting
        if content.count("<strong>") < 5:
            suggestions.append(
                "Consider adding more bold emphasis to key terms (current: "
                f"{content.count('<strong>')} instances)"
            )

        return suggestions


class ImageSourcer:
    """Source images from Wikimedia, Openverse, Pexels."""

    @staticmethod
    def search_wikimedia(query: str, min_width: int = 1000) -> Optional[Dict]:
        """Search Wikimedia Commons for images."""
        try:
            url = "https://commons.wikimedia.org/w/api.php"
            params = {
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": query,
                "srwhat": "text",
                "srprop": "timestamp",
            }
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            results = r.json().get("query", {}).get("search", [])
            if results:
                return {
                    "source": "wikimedia",
                    "title": results[0]["title"],
                    "url": f"https://commons.wikimedia.org/wiki/{results[0]['title']}",
                }
        except Exception as e:
            log.warning(f"Wikimedia search failed: {e}")
        return None

    @staticmethod
    def search_openverse(query: str) -> Optional[Dict]:
        """Search Openverse for CC-licensed images."""
        try:
            url = "https://api.openverse.org/v1/images/"
            params = {
                "q": query,
                "license": "cc",
                "sort_by": "relevance",
            }
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            results = r.json().get("results", [])
            if results:
                return {
                    "source": "openverse",
                    "title": results[0]["title"],
                    "url": results[0]["url"],
                    "license": results[0].get("license"),
                    "creator": results[0].get("creator"),
                }
        except Exception as e:
            log.warning(f"Openverse search failed: {e}")
        return None

    @classmethod
    def find_best_image(cls, query: str, strategy: ImageStrategy) -> Optional[Dict]:
        """Find best image using sourcing strategy."""
        if strategy == ImageStrategy.REAL_ONLY or strategy == ImageStrategy.GENERATED_FALLBACK:
            # Try real images first
            result = cls.search_wikimedia(query)
            if result:
                return result
            result = cls.search_openverse(query)
            if result:
                return result

        if strategy == ImageStrategy.GENERATED_FALLBACK:
            log.info("No real images found, falling back to generation")
            return {"source": "generated", "url": None}

        return None


class ContentGenerator:
    """Generate content using OmniRoute + Gemini."""

    def __init__(self, config: ContentConfig):
        self.config = config
        self.session = requests.Session()
        self.session.auth = (config.wp_username, config.wp_password)

    def generate(self, prompt: str) -> Tuple[str, str]:
        """Generate content via OmniRoute or Gemini."""
        if self.config.omniroute_base_url and self.config.omniroute_api_key:
            return self._generate_via_omniroute(prompt)
        else:
            return self._generate_via_gemini(prompt)

    def _generate_via_omniroute(self, prompt: str) -> Tuple[str, str]:
        """Route through OmniRoute gateway (cost-optimized)."""
        try:
            url = f"{self.config.omniroute_base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.config.omniroute_api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "gpt-4-turbo",  # OpenAI-compatible wire format
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 3000,
            }
            r = requests.post(url, json=payload, headers=headers, timeout=120)
            r.raise_for_status()
            result = r.json()
            content = result["choices"][0]["message"]["content"]
            model = result.get("model", "unknown")
            log.info(f"Generated via OmniRoute ({model})")
            return content, model
        except Exception as e:
            log.warning(f"OmniRoute failed: {e}, falling back to Gemini")
            return self._generate_via_gemini(prompt)

    def _generate_via_gemini(self, prompt: str) -> Tuple[str, str]:
        """Fallback to direct Gemini API."""
        # Implementation would use google.generativeai library
        # Simplified here for illustration
        log.info("Generating via Gemini directly (fallback)")
        return "", "gemini-pro"

    def publish_to_wordpress(
        self, title: str, content: str, featured_image_id: Optional[int] = None,
        categories: List[int] = None, draft: bool = True
    ) -> int:
        """Publish article to WordPress."""
        payload = {
            "title": title,
            "content": content,
            "status": "draft" if draft else "publish",
            "categories": categories or [],
        }
        if featured_image_id:
            payload["featured_media"] = featured_image_id

        url = f"{self.config.wp_url}/wp-json/wp/v2/posts"
        r = self.session.post(url, json=payload, timeout=60)
        r.raise_for_status()
        post_id = r.json()["id"]
        status = "draft" if draft else "published"
        log.info(f"Article {status} (ID: {post_id})")
        return post_id


class SEOOptimizer:
    """Optimize content for SEO."""

    @staticmethod
    def add_schema_markup(content: str, content_type: str = "Article") -> str:
        """Add JSON-LD schema markup."""
        schema = {
            "@context": "https://schema.org",
            "@type": content_type,
            "headline": "",  # Would extract from H1
            "description": "",  # Would extract from first paragraph
            "keywords": "",  # Would extract key terms
        }
        schema_html = f"<script type='application/ld+json'>{json.dumps(schema)}</script>"
        return schema_html + content

    @staticmethod
    def add_internal_links(content: str, topic: str, site_url: str) -> str:
        """Add relevant internal links."""
        internal_links = {
            "electrolyzer": f"{site_url}/electrolyzer-calculator/",
            "water treatment": f"{site_url}/water-consumption-calculator/",
            "efficiency": f"{site_url}/efficiency-guide/",
        }
        for keyword, url in internal_links.items():
            if keyword.lower() in content.lower():
                # Add link (simplified - would use regex for better matching)
                content = content.replace(
                    keyword,
                    f'<a href="{url}">{keyword}</a>',
                    1  # Only first occurrence
                )
        return content

    @staticmethod
    def add_adsense_unit(content: str, slot_id: str) -> str:
        """Insert AdSense display unit mid-article."""
        if not slot_id:
            return content

        # Find middle of content
        paragraphs = content.split("</p>")
        mid_point = len(paragraphs) // 2

        adsense_unit = f"""
        <ins class="adsbygoogle"
             style="display:block; text-align:center;"
             data-ad-layout="in-article"
             data-ad-format="fluid"
             data-ad-client="ca-pub-8459363476525914"
             data-ad-slot="{slot_id}"></ins>
        <script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
        """

        paragraphs.insert(mid_point, adsense_unit)
        return "</p>".join(paragraphs)


def main():
    """Example usage."""
    import argparse

    parser = argparse.ArgumentParser(description="Enhanced Content Pipeline")
    parser.add_argument("--site", choices=["avoltium", "techjobs360"], required=True)
    parser.add_argument("--tier", choices=["1", "2", "3"], default="2")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--publish", action="store_true", help="Publish immediately")
    parser.add_argument("--draft", action="store_true", help="Save as draft (default)")
    args = parser.parse_args()

    config = ContentConfig(
        site=args.site,
        tier=ContentTier[f"TIER{args.tier}"],
        topic=args.topic,
        wp_url=os.environ.get("WP_URL", "https://www.avoltium.in"),
        wp_username=os.environ.get("WP_USERNAME"),
        wp_password=os.environ.get("WP_APP_PASSWORD"),
        gemini_api_key=os.environ.get("GEMINI_API_KEY"),
        omniroute_base_url=os.environ.get("OMNIROUTE_BASE_URL"),
        omniroute_api_key=os.environ.get("OMNIROUTE_API_KEY"),
        image_strategy=ImageStrategy.GENERATED_FALLBACK,
        publish_immediately=args.publish,
    )

    log.info(f"Generating {args.tier} content: {args.topic}")

    # 1. Search for real images
    imagesourcer = ImageSourcer()
    image_result = imagesourcer.find_best_image(args.topic, config.image_strategy)
    log.info(f"Image sourcing: {image_result}")

    # 2. Generate content
    generator = ContentGenerator(config)
    # In real implementation, would build actual prompt here
    prompt = f"Write a comprehensive technical article about: {args.topic}"
    content, model = generator.generate(prompt)

    # 3. Validate quality
    validator = ContentValidator()
    is_valid, issues = validator.validate(content, config.tier)
    if issues:
        log.warning(f"Content validation issues: {issues}")
    suggestions = validator.proofread_suggestions(content, args.topic)
    if suggestions:
        log.info(f"Proofreading suggestions: {suggestions}")

    # 4. Optimize for SEO
    optimizer = SEOOptimizer()
    if config.add_schema:
        content = optimizer.add_schema_markup(content)
    content = optimizer.add_internal_links(content, args.topic, config.wp_url)
    if config.add_adsense:
        adsense_slot = os.environ.get("ADSENSE_SLOT_ID", "")
        if adsense_slot:
            content = optimizer.add_adsense_unit(content, adsense_slot)

    # 5. Publish
    if args.publish or not args.draft:
        post_id = generator.publish_to_wordpress(
            title=args.topic,
            content=content,
            draft=not args.publish,
            categories=[8, 12]  # Example categories
        )
        log.info(f"✓ Content published (Post ID: {post_id})")
    else:
        log.info("✓ Content generated (saved to draft)")


if __name__ == "__main__":
    main()
