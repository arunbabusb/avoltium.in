#!/usr/bin/env python3
"""
Integrated Modular Pipeline - Orchestrates all content generation components

Orchestrates:
1. OmniRoute content generation (cost-optimized)
2. Professional image sourcing (4-source fallback)
3. SEO optimization (schema, meta tags, internal links)
4. Monetization engine (AdSense, sponsored listings)
5. Quality gate (validation before publishing)
6. WordPress publishing (via REST API)
"""

import os
import json
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

from omniroute_content_generator import OmniRouteGateway
from professional_image_sourcing import ProfessionalImageFinder
from seo_optimizer import (
    SchemaMarkupGenerator,
    MetaTagOptimizer,
    InternalLinkingStrategy,
    ReadabilityAnalyzer,
    KeywordDensityAnalyzer
)
from monetization_engine import (
    AdSenseOptimizer,
    SponsoredListingManager,
    ReferralLinkManager,
    RevenueTracker
)
from quality_gate import ContentQualityGate

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("modular-pipeline")


class ModularPipeline:
    """Master orchestration for entire content generation pipeline."""

    def __init__(self):
        self.omniroute = OmniRouteGateway()
        self.quality_gate = ContentQualityGate(strict_mode=False)
        self.revenue_tracker = RevenueTracker()
        self.referral_manager = ReferralLinkManager()
        self.monetization_stats = {
            "articles_processed": 0,
            "total_estimated_revenue": 0,
            "failed_validations": 0
        }

    def generate_article(
        self,
        topic: str,
        tier: str = "tier2",
        include_monetization: bool = True,
        publish_to_wordpress: bool = False,
        wordpress_url: str = None,
        wordpress_token: str = None
    ) -> Dict:
        """
        Generate complete article with all optimizations.

        Returns: Complete article data with metadata, ready for WordPress
        """
        start_time = datetime.now()
        pipeline_results = {
            "timestamp": datetime.now().isoformat(),
            "topic": topic,
            "tier": tier,
            "stages": {}
        }

        try:
            # Stage 1: Generate content with OmniRoute
            log.info(f"📝 Stage 1: Content generation for '{topic}'")
            content, content_meta = self.omniroute.generate(topic)
            pipeline_results["stages"]["content_generation"] = {
                "status": "success",
                "api_used": content_meta["api_used"],
                "cost_cents": content_meta["cost_cents"],
                "duration_seconds": content_meta["generation_time_seconds"]
            }

            # Stage 2: Source professional image
            log.info("📸 Stage 2: Professional image sourcing")
            images = ProfessionalImageFinder.find_image(topic, limit=1)
            if images:
                featured_image = images[0]
                pipeline_results["stages"]["image_sourcing"] = {
                    "status": "success",
                    "source": featured_image.source,
                    "url": featured_image.url,
                    "size": f"{featured_image.width}x{featured_image.height}",
                    "relevance": f"{featured_image.relevance_score:.0%}",
                    "attribution": featured_image.attribution_url
                }
            else:
                featured_image = None
                pipeline_results["stages"]["image_sourcing"] = {
                    "status": "no_image_found",
                    "fallback": "Use placeholder or diagram generation"
                }

            # Stage 3: SEO Optimization
            log.info("🔍 Stage 3: SEO optimization")
            title = self._generate_title(topic, tier)
            description = self._generate_description(content[:300])
            keywords = self._extract_keywords(topic)

            schema = SchemaMarkupGenerator.generate_article_schema(
                title=title,
                description=description,
                content_length=len(content.split()),
                image_url=featured_image.url if featured_image else "",
                keywords=keywords
            )

            meta_tags = MetaTagOptimizer.generate_meta_tags(
                title=title,
                description=description,
                keywords=keywords,
                canonical_url=f"https://avoltium.in/{topic.lower().replace(' ', '-')}",
                image_url=featured_image.url if featured_image else ""
            )

            pipeline_results["stages"]["seo_optimization"] = {
                "status": "success",
                "title": title,
                "description": description,
                "keywords": keywords,
                "schema_type": "Article",
                "meta_tags_count": len(meta_tags)
            }

            # Stage 4: Monetization
            log.info("💰 Stage 4: Monetization setup")
            if include_monetization:
                placements = AdSenseOptimizer.get_placements_for_tier(tier)
                monetized_content, money_meta = AdSenseOptimizer.inject_ads(
                    content,
                    placements
                )
                pipeline_results["stages"]["monetization"] = {
                    "status": "success",
                    "ad_placements": money_meta["placements"],
                    "estimated_rpm": f"${money_meta['estimated_rpm']:.2f}",
                    "estimated_monthly": f"${money_meta['estimated_monthly_revenue']:.2f}"
                }
                content = monetized_content
                self.monetization_stats["total_estimated_revenue"] += money_meta["estimated_monthly_revenue"]
            else:
                pipeline_results["stages"]["monetization"] = {"status": "skipped"}

            # Stage 5: Quality Gate Validation
            log.info("✓ Stage 5: Quality validation")
            report = self.quality_gate.validate_all(
                content=content,
                title=title,
                description=description,
                keywords=keywords,
                tier=tier,
                featured_image_size=(
                    featured_image.width, featured_image.height
                ) if featured_image else (0, 0)
            )

            pipeline_results["stages"]["quality_gate"] = {
                "status": "success",
                "overall_score": report["overall_score"],
                "can_publish": report["can_publish"],
                "passed_checks": f"{report['passed_checks']}/{report['total_checks']}"
            }

            if not report["can_publish"]:
                pipeline_results["stages"]["quality_gate"]["status"] = "warnings"
                self.monetization_stats["failed_validations"] += 1

            # Stage 6: Build complete article
            pipeline_results["content"] = {
                "title": title,
                "description": description,
                "body": content,
                "keywords": keywords,
                "featured_image_url": featured_image.url if featured_image else None,
                "featured_image_attribution": featured_image.attribution_url if featured_image else None,
                "schema_markup": schema,
                "meta_tags": meta_tags,
                "content_tier": tier,
                "publication_status": "ready_to_publish" if report["can_publish"] else "review_needed"
            }

            # Stage 7: Optional WordPress publish
            if publish_to_wordpress and wordpress_url and wordpress_token:
                log.info("📤 Stage 7: WordPress publishing")
                wp_result = self._publish_to_wordpress(
                    pipeline_results["content"],
                    wordpress_url,
                    wordpress_token
                )
                pipeline_results["stages"]["wordpress_publishing"] = wp_result

            # Update statistics
            self.monetization_stats["articles_processed"] += 1

            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()
            pipeline_results["total_duration_seconds"] = duration
            pipeline_results["status"] = "success"

            log.info(f"✅ Article complete: '{topic}' ({duration:.1f}s)")
            return pipeline_results

        except Exception as e:
            log.error(f"Pipeline failed: {e}")
            pipeline_results["status"] = "error"
            pipeline_results["error"] = str(e)
            return pipeline_results

    def _generate_title(self, topic: str, tier: str) -> str:
        """Generate SEO-optimized title."""
        title = topic

        # Add qualifier based on tier
        if tier == "tier1":
            title = f"Advanced {topic}: Deep Technical Analysis"
        elif tier == "tier2":
            title = f"{topic}: Complete Guide & Best Practices"
        elif tier == "tier3":
            title = f"{topic}: Latest Updates & Industry News"

        return title[:60]

    def _generate_description(self, content_snippet: str) -> str:
        """Generate meta description from content."""
        desc = content_snippet.replace("\n", " ").strip()[:160]
        return desc

    def _extract_keywords(self, topic: str) -> list:
        """Extract keywords from topic."""
        # Simple keyword extraction from topic
        stopwords = {"and", "or", "for", "the", "a", "an", "in", "to", "of"}
        words = [w for w in topic.lower().split() if w not in stopwords]
        return words + [topic.lower()] + ["industrial", "engineering"]

    def _publish_to_wordpress(
        self,
        article_data: Dict,
        wordpress_url: str,
        wordpress_token: str
    ) -> Dict:
        """Publish to WordPress via REST API."""
        try:
            import requests

            headers = {
                "Authorization": f"Bearer {wordpress_token}",
                "Content-Type": "application/json"
            }

            post_data = {
                "title": article_data["title"],
                "content": article_data["body"],
                "excerpt": article_data["description"],
                "meta": {
                    "schema_markup": article_data["schema_markup"],
                    "keywords": ",".join(article_data["keywords"]),
                    "featured_image_url": article_data["featured_image_url"]
                },
                "status": "draft"
            }

            response = requests.post(
                f"{wordpress_url}/wp-json/wp/v2/posts",
                json=post_data,
                headers=headers,
                timeout=30
            )

            if response.status_code == 201:
                post = response.json()
                return {
                    "status": "success",
                    "post_id": post["id"],
                    "post_url": post["link"],
                    "status_code": 201
                }
            else:
                return {
                    "status": "error",
                    "status_code": response.status_code,
                    "error": response.text[:200]
                }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    def get_pipeline_stats(self) -> Dict:
        """Get pipeline statistics."""
        return {
            "articles_processed": self.monetization_stats["articles_processed"],
            "total_estimated_monthly_revenue": f"${self.monetization_stats['total_estimated_revenue']:.2f}",
            "failed_validations": self.monetization_stats["failed_validations"],
            "omniroute_stats": self.omniroute.get_stats(),
            "revenue_estimates": self.revenue_tracker.estimate_monthly_revenue()
        }

    def print_stats(self):
        """Print pipeline statistics."""
        stats = self.get_pipeline_stats()

        print("\n" + "=" * 80)
        print("📊 MODULAR PIPELINE STATISTICS")
        print("=" * 80)

        print(f"\nArticles Processed: {stats['articles_processed']}")
        print(f"Failed Validations: {stats['failed_validations']}")
        print(f"Total Estimated Monthly Revenue: {stats['total_estimated_monthly_revenue']}")

        print("\n" + "-" * 80)
        print("OmniRoute Routing:")
        for key, value in stats["omniroute_stats"].items():
            if isinstance(value, str) and "%" not in key:
                print(f"  {key}: {value}")


def main():
    """Test integrated modular pipeline."""
    pipeline = ModularPipeline()

    topics = [
        "PEM Electrolyzer Architecture",
        "Water Treatment Systems",
    ]

    print("\n" + "=" * 80)
    print("🚀 INTEGRATED MODULAR PIPELINE")
    print("=" * 80 + "\n")

    for topic in topics:
        print(f"\n{'='*80}")
        print(f"Processing: {topic}")
        print(f"{'='*80}\n")

        result = pipeline.generate_article(
            topic=topic,
            tier="tier1",
            include_monetization=True,
            publish_to_wordpress=False  # Set to True with valid WordPress credentials
        )

        # Print result summary
        print(f"Status: {result['status']}")
        print(f"Duration: {result.get('total_duration_seconds', 0):.1f}s")

        if result["status"] == "success":
            print(f"Title: {result['content']['title']}")
            print(f"Words: {len(result['content']['body'].split())}")
            print(f"Ready to publish: {result['content']['publication_status']}")

    pipeline.print_stats()


if __name__ == "__main__":
    main()
