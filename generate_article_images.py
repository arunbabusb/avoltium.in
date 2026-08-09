#!/usr/bin/env python3
"""
Generate high-quality professional images for all avoltium articles.

Finds real industrial/engineering photographs for each article topic
from Wikimedia Commons, Pexels, Unsplash, and Pixabay.

Usage:
  python generate_article_images.py --export images_report.json
  python generate_article_images.py --topic "PEM Electrolyzer" --show-urls
"""

import os
import sys
import json
import logging
from professional_image_sourcing import ProfessionalImageFinder

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger()

# Article topics from generate_article.py
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


def generate_images_for_all_topics(export_file: str = None, show_details: bool = True):
    """Find best images for all article topics."""

    results = {
        "timestamp": "2026-08-09",
        "total_topics": len(ARTICLE_TOPICS),
        "articles": []
    }

    print("\n" + "=" * 90)
    print("🖼️  GENERATING HIGH-QUALITY IMAGES FOR ALL AVOLTIUM ARTICLES")
    print("=" * 90 + "\n")

    for i, (topic, categories) in enumerate(ARTICLE_TOPICS.items(), 1):
        print(f"[{i}/{len(ARTICLE_TOPICS)}] 🔍 Searching: {topic[:60]}...")

        try:
            # Search for images
            images = ProfessionalImageFinder.find_image(topic, limit=3)

            article_data = {
                "rank": i,
                "title": topic,
                "categories": categories,
                "images_found": len(images),
                "best_image": None,
                "all_images": []
            }

            if images:
                best_img = images[0]
                article_data["best_image"] = {
                    "url": best_img.url,
                    "source": best_img.source,
                    "title": best_img.title,
                    "creator": best_img.creator,
                    "dimensions": f"{best_img.width}x{best_img.height}",
                    "aspect_ratio": f"{best_img.aspect_ratio:.2f}",
                    "relevance": f"{best_img.relevance_score:.0%}",
                    "license": best_img.license,
                    "attribution_url": best_img.attribution_url,
                }

                # Store all candidates
                for img in images:
                    article_data["all_images"].append({
                        "title": img.title,
                        "source": img.source,
                        "url": img.url,
                        "dimensions": f"{img.width}x{img.height}",
                        "relevance": f"{img.relevance_score:.0%}",
                    })

                # Print summary
                print(f"   ✅ Found: {best_img.title}")
                print(f"      Source: {best_img.source} | Size: {best_img.width}x{best_img.height} | Relevance: {best_img.relevance_score:.0%}")
                if show_details:
                    print(f"      URL: {best_img.url[:70]}...")

            else:
                print(f"   ⚠️  No images found (use diagram/generated fallback)")

            results["articles"].append(article_data)

        except Exception as e:
            print(f"   ❌ Error: {e}")
            results["articles"].append({
                "rank": i,
                "title": topic,
                "categories": categories,
                "error": str(e)
            })

    # Export results
    if export_file:
        with open(export_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n✅ Results exported to: {export_file}")

    # Print summary
    print("\n" + "=" * 90)
    print("📊 SUMMARY")
    print("=" * 90)

    images_found = sum(1 for a in results["articles"] if a.get("best_image"))
    success_rate = (images_found / len(ARTICLE_TOPICS)) * 100

    print(f"Total articles: {len(ARTICLE_TOPICS)}")
    print(f"Images found: {images_found}")
    print(f"Success rate: {success_rate:.0f}%")
    print(f"\n✅ Ready to publish with professional real images!")
    print("=" * 90 + "\n")

    return results


def show_topic_images(topic_query: str):
    """Show images for a specific topic."""
    print(f"\n🔍 Searching for images: {topic_query}\n")

    images = ProfessionalImageFinder.find_image(topic_query, limit=5)

    if not images:
        print("❌ No images found")
        return

    for i, img in enumerate(images, 1):
        print(f"{i}. {img.title}")
        print(f"   Source: {img.source}")
        print(f"   Relevance: {img.relevance_score:.0%}")
        print(f"   Size: {img.width}x{img.height} (ratio: {img.aspect_ratio:.2f})")
        print(f"   License: {img.license}")
        print(f"   Creator: {img.creator}")
        print(f"   URL: {img.url}")
        print()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate images for avoltium articles")
    parser.add_argument("--export", help="Export results to JSON file")
    parser.add_argument("--topic", help="Show images for specific topic")
    parser.add_argument("--show-urls", action="store_true", help="Show full URLs")

    args = parser.parse_args()

    if args.topic:
        show_topic_images(args.topic)
    else:
        generate_images_for_all_topics(
            export_file=args.export,
            show_details=args.show_urls
        )


if __name__ == "__main__":
    main()
