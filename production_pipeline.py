#!/usr/bin/env python3
"""
Production Pipeline - Integrated implementation of modular architecture

Orchestrates:
1. Article topic selection
2. OmniRoute content generation (cost-optimized)
3. Professional image sourcing (4-source fallback)
4. SEO optimization (schema, meta tags)
5. Monetization (AdSense placement)
6. Quality validation (5-point gate)
7. WordPress REST API publishing
8. Revenue tracking
"""

import os
import sys
import json
import logging
from typing import Dict, Optional, List
from dotenv import load_dotenv
import requests

# Import modular components
from omniroute_content_generator import OmniRouteGateway
from professional_image_sourcing import ProfessionalImageFinder
from monetization_engine import AdSenseOptimizer, RevenueTracker
from seo_optimizer import SchemaMarkupGenerator, MetaTagOptimizer
from quality_gate import ContentQualityGate
from modular_pipeline import ModularPipeline

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger("production-pipeline")


class ProductionPipeline:
    """Production-ready implementation of modular architecture."""

    # Article topics with WordPress category mappings
    ARTICLE_TOPICS = {
        "Next-Generation PEM Electrolyzer Architectures and Efficiency Gains": [8, 12],
        "Alkaline vs PEM Electrolysis: Scaling for Gigawatt Green Hydrogen Projects": [8, 10, 12],
        "Ultrapure Water Demand and Reverse Osmosis (RO) Optimization in Hydrogen Hubs": [15, 12],
        "Balance of Plant (BOP) Strategies for Large-Scale Green Hydrogen Facilities": [9, 12],
        "Cooling Systems and Thermal Management in Industrial Electrolyzers": [8, 12],
        "Grid Integration and Renewable Energy Coupling for Intermittent Electrolysis": [10, 12],
        "Compressor Technologies for High-Pressure Green Hydrogen Storage": [12],
        "Materials Engineering for Electrolyzer Degradation Mitigation": [8, 12],
        "Centrifugal vs Diaphragm Pumps for Electrolyte Circulation in Alkaline Electrolyzers": [29, 8, 12],
        "Control Valve Selection and Sizing for High-Purity Hydrogen Service": [29, 12],
        "Electrodeionization (EDI) vs Mixed-Bed Polishing for Electrolyzer Feedwater": [15, 12],
        "Hydrogen Gas Drying Technologies: PSA, TSA and Membrane Dehumidification": [10, 12],
        "Stack Lifetime Extension: Voltage Cycling Protocols and Degradation Diagnostics": [8, 12],
        "Oxygen Side Management and Safety Systems in Large Electrolyzer Plants": [8, 9, 12],
        "Seawater Desalination Integration for Coastal Green Hydrogen Projects": [15, 10, 12],
        "AEM Electrolyzers: Bridging the Cost Gap Between Alkaline and PEM": [8, 12],
        "Hydrogen Leak Detection and Ventilation Design for Indoor Electrolyzer Rooms": [9, 12],
        "Power Electronics for Electrolysis: Rectifier Topologies and Harmonic Mitigation": [9, 12],
        "Waste Heat Recovery from Electrolyzers for District Heating and Process Use": [9, 10, 12],
        "Green Ammonia Synthesis: Coupling Haber-Bosch with Intermittent Electrolysis": [10, 12],
        "Water Quality Monitoring Instrumentation for Ultrapure Electrolyzer Feed": [15, 12],
        "Bipolar Plate Materials and Coatings: Titanium, Stainless and Beyond": [8, 12],
        "Hydrogen Storage Options Compared: Compressed Gas, Liquid and Metal Hydrides": [10, 12],
    }

    def __init__(self):
        """Initialize production pipeline."""
        # Configuration from environment
        self.wp_url = os.environ.get("WP_URL", "https://www.avoltium.in").rstrip("/")
        self.wp_username = os.environ.get("WP_USERNAME")
        self.wp_app_password = os.environ.get("WP_APP_PASSWORD")
        self.adsense_client = os.environ.get("ADSENSE_CLIENT", "ca-pub-8459363476525914")

        # Initialize components
        self.modular_pipeline = ModularPipeline()
        self.revenue_tracker = RevenueTracker()

        # Statistics
        self.stats = {
            "articles_processed": 0,
            "articles_published": 0,
            "articles_failed": 0,
            "total_revenue_estimated": 0,
            "total_time_seconds": 0
        }

        # Validate configuration
        if not all([self.wp_url, self.wp_username, self.wp_app_password]):
            log.error("Missing WordPress configuration (WP_URL, WP_USERNAME, WP_APP_PASSWORD)")
            raise RuntimeError("WordPress configuration incomplete")

    def generate_and_publish_article(
        self,
        topic: str,
        categories: List[int],
        tier: str = "tier1",
        dry_run: bool = False
    ) -> Dict:
        """
        Generate article using modular pipeline and publish to WordPress.

        Args:
            topic: Article topic
            categories: WordPress category IDs
            tier: Content tier (tier1, tier2, tier3)
            dry_run: If True, don't actually publish to WordPress

        Returns:
            Complete result with article data and WordPress post ID
        """
        log.info(f"🚀 Starting production pipeline for: {topic}")

        try:
            # Generate complete article using modular pipeline
            result = self.modular_pipeline.generate_article(
                topic=topic,
                tier=tier,
                include_monetization=True,
                publish_to_wordpress=False  # We'll handle publishing ourselves
            )

            if result["status"] != "success":
                log.error(f"Modular pipeline failed: {result.get('error', 'unknown')}")
                self.stats["articles_failed"] += 1
                return {
                    "status": "failed",
                    "error": result.get("error", "Pipeline failed"),
                    "topic": topic
                }

            # Extract article data
            article_data = result["content"]

            # Prepare WordPress post
            wp_post = self._prepare_wordpress_post(
                article_data=article_data,
                categories=categories,
                tier=tier
            )

            if dry_run:
                log.info("📋 DRY RUN MODE - Not publishing to WordPress")
                result["wordpress"] = {"status": "dry_run", "post": wp_post}
                self.stats["articles_processed"] += 1
                return result

            # Publish to WordPress
            post_id = self._publish_to_wordpress(wp_post)

            if not post_id:
                log.error("Failed to publish to WordPress")
                self.stats["articles_failed"] += 1
                return {
                    "status": "failed",
                    "error": "WordPress publishing failed",
                    "topic": topic
                }

            # Log revenue
            ad_placements = len(AdSenseOptimizer.get_placements_for_tier(tier))
            estimated_revenue = 5.50 * ad_placements / 1000 * 1000  # 5.50 RPM per placement, 1K views estimate
            self.revenue_tracker.log_revenue(
                "adsense",
                estimated_revenue,
                {
                    "topic": topic,
                    "post_id": post_id,
                    "ad_placements": ad_placements,
                    "tier": tier
                }
            )
            self.stats["total_revenue_estimated"] += estimated_revenue

            # Success!
            log.info(f"✅ Published to WordPress: Post ID {post_id}")
            self.stats["articles_published"] += 1
            self.stats["articles_processed"] += 1

            result["wordpress"] = {
                "status": "published",
                "post_id": post_id,
                "post_url": f"{self.wp_url}/?p={post_id}",
                "categories": categories
            }

            return result

        except Exception as e:
            log.error(f"Pipeline error: {e}", exc_info=True)
            self.stats["articles_failed"] += 1
            return {
                "status": "error",
                "error": str(e),
                "topic": topic
            }

    def _prepare_wordpress_post(
        self,
        article_data: Dict,
        categories: List[int],
        tier: str
    ) -> Dict:
        """Prepare WordPress post from article data."""
        return {
            "title": article_data["title"],
            "content": article_data["body"],
            "excerpt": article_data["description"],
            "categories": categories,
            "featured_media": None,  # Will be set after image upload
            "meta": {
                "_yoast_wpseo_metadesc": article_data["description"],
                "_yoast_wpseo_focuskw": ",".join(article_data["keywords"][:3]),
                "schema_markup": article_data["schema_markup"],
                "tier": tier,
                "image_attribution": article_data.get("featured_image_attribution", ""),
            },
            "status": "draft"  # Publish as draft for review
        }

    def _publish_to_wordpress(self, wp_post: Dict) -> Optional[int]:
        """
        Publish post to WordPress via REST API.

        Returns:
            Post ID if successful, None otherwise
        """
        try:
            # Upload featured image if available
            # (This would require additional logic to handle image upload)

            # Create post
            response = requests.post(
                f"{self.wp_url}/wp-json/wp/v2/posts",
                json=wp_post,
                auth=(self.wp_username, self.wp_app_password),
                timeout=30
            )

            if response.status_code not in [200, 201]:
                log.error(f"WordPress API error: {response.status_code} - {response.text[:200]}")
                return None

            post_data = response.json()
            return post_data.get("id")

        except Exception as e:
            log.error(f"Failed to publish to WordPress: {e}")
            return None

    def generate_batch(
        self,
        topics: Optional[List[str]] = None,
        dry_run: bool = False,
        limit: Optional[int] = None
    ) -> Dict:
        """
        Generate multiple articles in batch.

        Args:
            topics: Specific topics to generate (defaults to all)
            dry_run: If True, don't publish to WordPress
            limit: Max articles to generate

        Returns:
            Batch summary with all results
        """
        topics_to_process = topics if topics else list(self.ARTICLE_TOPICS.keys())

        if limit:
            topics_to_process = topics_to_process[:limit]

        results = {
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "total_topics": len(topics_to_process),
            "dry_run": dry_run,
            "articles": [],
            "summary": {
                "processed": 0,
                "published": 0,
                "failed": 0,
                "total_revenue": 0
            }
        }

        log.info(f"📚 Starting batch generation: {len(topics_to_process)} articles")
        log.info(f"   Dry run: {dry_run}")
        log.info("=" * 80)

        for i, topic in enumerate(topics_to_process, 1):
            print(f"\n[{i}/{len(topics_to_process)}] {topic[:60]}...")

            categories = self.ARTICLE_TOPICS[topic]
            result = self.generate_and_publish_article(
                topic=topic,
                categories=categories,
                tier="tier1",
                dry_run=dry_run
            )

            results["articles"].append(result)

            if result["status"] == "success":
                results["summary"]["published"] += 1
            elif result["status"] == "failed" or result["status"] == "error":
                results["summary"]["failed"] += 1

            results["summary"]["processed"] += 1
            results["summary"]["total_revenue"] = self.stats["total_revenue_estimated"]

        # Print summary
        self._print_summary(results)

        return results

    def _print_summary(self, results: Dict):
        """Print batch processing summary."""
        print("\n" + "=" * 80)
        print("📊 BATCH PROCESSING SUMMARY")
        print("=" * 80)
        print(f"Total articles: {results['total_topics']}")
        print(f"Processed: {results['summary']['processed']}")
        print(f"Published: {results['summary']['published']}")
        print(f"Failed: {results['summary']['failed']}")
        print(f"Estimated revenue: ${results['summary']['total_revenue']:.2f}")
        print("=" * 80 + "\n")

    def print_stats(self):
        """Print pipeline statistics."""
        print("\n" + "=" * 80)
        print("📈 PIPELINE STATISTICS")
        print("=" * 80)
        print(f"Articles processed: {self.stats['articles_processed']}")
        print(f"Articles published: {self.stats['articles_published']}")
        print(f"Articles failed: {self.stats['articles_failed']}")
        print(f"Estimated revenue: ${self.stats['total_revenue_estimated']:.2f}")
        print("=" * 80 + "\n")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Production pipeline for modular article generation"
    )
    parser.add_argument(
        "--topic",
        help="Generate single article by topic"
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Generate all articles"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit batch to N articles"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't publish to WordPress, just generate"
    )

    args = parser.parse_args()

    try:
        pipeline = ProductionPipeline()

        if args.topic:
            # Single article
            categories = pipeline.ARTICLE_TOPICS.get(args.topic, [12])
            result = pipeline.generate_and_publish_article(
                topic=args.topic,
                categories=categories,
                dry_run=args.dry_run
            )
            print(json.dumps(result, indent=2))

        elif args.batch:
            # Batch processing
            results = pipeline.generate_batch(
                dry_run=args.dry_run,
                limit=args.limit
            )
            with open("batch_results.json", "w") as f:
                json.dump(results, f, indent=2)
            print("✅ Results saved to batch_results.json")

        else:
            # Default: generate first 3 articles
            results = pipeline.generate_batch(
                dry_run=args.dry_run,
                limit=3
            )

        pipeline.print_stats()

    except Exception as e:
        log.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
