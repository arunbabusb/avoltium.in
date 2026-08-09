#!/usr/bin/env python3
"""
SEO Optimizer - Automated Schema Markup & Meta Tag Generation

Handles:
- JSON-LD schema markup (Article, JobPosting, Organization)
- Meta tag optimization
- Internal linking strategy
- Keyword density balancing
- Readability scoring (Flesch-Kincaid)
"""

import json
import logging
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("seo-optimizer")


class SchemaMarkupGenerator:
    """Generate JSON-LD schema markup for Google Search."""

    @staticmethod
    def generate_article_schema(
        title: str,
        description: str,
        content_length: int,
        image_url: str,
        author: str = "Avoltium",
        published_date: str = None,
        keywords: List[str] = None
    ) -> str:
        """Generate Article schema for blog posts."""
        if not published_date:
            published_date = datetime.now().isoformat()

        schema = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": title,
            "description": description,
            "image": image_url,
            "author": {
                "@type": "Organization",
                "name": author,
                "logo": "https://avoltium.in/logo.png"
            },
            "datePublished": published_date,
            "dateModified": published_date,
            "articleBody": f"{content_length} words",
            "wordCount": content_length
        }

        if keywords:
            schema["keywords"] = ", ".join(keywords)

        return json.dumps(schema, indent=2)

    @staticmethod
    def generate_job_posting_schema(
        title: str,
        company: str,
        location: str,
        description: str,
        salary_min: Optional[float] = None,
        salary_max: Optional[float] = None,
        job_type: str = "FULL_TIME"
    ) -> str:
        """Generate JobPosting schema (for TechJobs360)."""
        schema = {
            "@context": "https://schema.org",
            "@type": "JobPosting",
            "title": title,
            "description": description,
            "hiringOrganization": {
                "@type": "Organization",
                "name": company,
                "logo": "https://techjobs360.com/logo.png"
            },
            "jobLocation": {
                "@type": "Place",
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": location,
                    "addressCountry": "US"
                }
            },
            "employmentType": job_type,
            "datePosted": datetime.now().isoformat(),
            "validThrough": "2026-12-31"
        }

        if salary_min and salary_max:
            schema["baseSalary"] = {
                "@type": "PriceSpecification",
                "priceCurrency": "USD",
                "price": {
                    "@type": "PriceSpecification",
                    "minPrice": salary_min,
                    "maxPrice": salary_max,
                    "priceValidUntil": "2026-12-31"
                }
            }

        return json.dumps(schema, indent=2)

    @staticmethod
    def generate_organization_schema(
        org_name: str = "Avoltium",
        website: str = "https://avoltium.in",
        logo_url: str = "https://avoltium.in/logo.png"
    ) -> str:
        """Generate Organization schema (site-wide)."""
        schema = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": org_name,
            "url": website,
            "logo": logo_url,
            "description": "Industrial engineering and green hydrogen technology insights",
            "sameAs": [
                "https://twitter.com/avoltium",
                "https://linkedin.com/company/avoltium",
            ]
        }

        return json.dumps(schema, indent=2)


class MetaTagOptimizer:
    """Optimize meta tags for SEO."""

    @staticmethod
    def generate_meta_tags(
        title: str,
        description: str,
        keywords: List[str],
        canonical_url: str,
        image_url: str = None
    ) -> Dict[str, str]:
        """Generate optimized meta tags."""
        # Optimize title (50-60 chars ideal)
        if len(title) > 60:
            title = title[:57] + "..."

        # Optimize description (150-160 chars ideal)
        if len(description) > 160:
            description = description[:157] + "..."

        meta_tags = {
            "title": title,
            "meta_description": description,
            "meta_keywords": ", ".join(keywords[:5]),  # Top 5 keywords
            "canonical": canonical_url,
            "og_title": title,
            "og_description": description,
            "og_image": image_url or "https://avoltium.in/default-og-image.jpg",
            "twitter_card": "summary_large_image",
            "twitter_title": title,
            "twitter_description": description,
        }

        return meta_tags


class InternalLinkingStrategy:
    """Generate internal linking opportunities."""

    # Topic map for internal linking
    TOPIC_CONNECTIONS = {
        "PEM Electrolyzer": [
            "Water Treatment Systems",
            "Thermal Management",
            "Power Electronics"
        ],
        "Alkaline Electrolysis": [
            "PEM Electrolyzer",
            "Green Hydrogen Production",
            "Cost Comparison"
        ],
        "Water Treatment": [
            "Ultrapure Water Demand",
            "RO Optimization",
            "EDI Systems"
        ],
        "Thermal Management": [
            "Cooling Systems",
            "Heat Recovery",
            "Efficiency Optimization"
        ]
    }

    @staticmethod
    def find_internal_links(current_topic: str, available_articles: List[str]) -> List[Dict]:
        """Find relevant internal linking opportunities."""
        links = []

        # Exact topic matches
        related = InternalLinkingStrategy.TOPIC_CONNECTIONS.get(current_topic, [])

        for article in available_articles:
            for related_topic in related:
                if related_topic.lower() in article.lower():
                    links.append({
                        "anchor_text": related_topic,
                        "target_article": article,
                        "relevance": "high"
                    })
                    break

        return links

    @staticmethod
    def inject_internal_links(
        content: str,
        links: List[Dict],
        max_links: int = 5
    ) -> str:
        """Inject internal links into content."""
        modified = content

        for link in links[:max_links]:
            # Create link HTML
            link_html = (
                f'<a href="/articles/{link["target_article"].lower().replace(" ", "-")}" '
                f'title="{link["target_article"]}">{link["anchor_text"]}</a>'
            )

            # Replace first occurrence of anchor text (case-insensitive)
            pattern = re.compile(re.escape(link["anchor_text"]), re.IGNORECASE)
            modified = pattern.sub(link_html, modified, count=1)

        return modified


class ReadabilityAnalyzer:
    """Analyze and score readability using Flesch-Kincaid metrics."""

    @staticmethod
    def count_sentences(text: str) -> int:
        """Count sentences in text."""
        sentences = re.split(r'[.!?]+', text)
        return len([s for s in sentences if s.strip()])

    @staticmethod
    def count_syllables(word: str) -> int:
        """Estimate syllable count for a word."""
        word = word.lower()
        syllable_count = 0

        vowels = "aeiou"
        previous_was_vowel = False

        for char in word:
            is_vowel = char in vowels
            if is_vowel and not previous_was_vowel:
                syllable_count += 1
            previous_was_vowel = is_vowel

        # Adjust for silent e
        if word.endswith("e"):
            syllable_count -= 1

        if word.endswith("le") and len(word) > 2 and word[-3] not in vowels:
            syllable_count += 1

        return max(1, syllable_count)

    @staticmethod
    def analyze_readability(text: str) -> Dict:
        """Analyze text readability."""
        sentences = ReadabilityAnalyzer.count_sentences(text)
        words = len(text.split())
        syllables = sum(
            ReadabilityAnalyzer.count_syllables(word)
            for word in text.split()
        )

        if sentences == 0 or words == 0:
            return {"error": "Text too short"}

        # Flesch-Kincaid Grade Level
        # 0.39 * (words/sentences) + 11.8 * (syllables/words) - 15.59
        grade_level = (
            0.39 * (words / sentences) +
            11.8 * (syllables / words) -
            15.59
        )

        # Flesch Reading Ease
        # 206.835 - 1.015 * (words/sentences) - 84.6 * (syllables/words)
        reading_ease = (
            206.835 -
            1.015 * (words / sentences) -
            84.6 * (syllables / words)
        )

        # Clamp reading ease between 0-100
        reading_ease = max(0, min(100, reading_ease))

        # Interpret readability
        if reading_ease >= 90:
            difficulty = "Very Easy (5th grade)"
        elif reading_ease >= 80:
            difficulty = "Easy (6th grade)"
        elif reading_ease >= 70:
            difficulty = "Fairly Easy (7th grade)"
        elif reading_ease >= 60:
            difficulty = "Standard (8th-9th grade)"
        elif reading_ease >= 50:
            difficulty = "Fairly Difficult (10th-12th grade)"
        elif reading_ease >= 30:
            difficulty = "Difficult (College level)"
        else:
            difficulty = "Very Difficult (College graduate)"

        return {
            "word_count": words,
            "sentence_count": sentences,
            "syllable_count": syllables,
            "grade_level": f"{grade_level:.1f}",
            "reading_ease_score": f"{reading_ease:.1f}",
            "difficulty": difficulty,
            "avg_words_per_sentence": f"{words / sentences:.1f}",
            "recommendation": "Good for technical audience" if grade_level > 10 else "Simplify language"
        }


class KeywordDensityAnalyzer:
    """Analyze and optimize keyword density."""

    @staticmethod
    def analyze_density(text: str, keywords: List[str]) -> Dict:
        """Analyze keyword density in text."""
        words = text.lower().split()
        total_words = len(words)

        density = {}
        for keyword in keywords:
            keyword_lower = keyword.lower()
            count = len([w for w in words if keyword_lower in w])
            percentage = (count / total_words) * 100 if total_words > 0 else 0
            density[keyword] = {
                "count": count,
                "percentage": f"{percentage:.2f}%",
                "status": "Good" if 1 <= percentage <= 3 else "Adjust"
            }

        return {
            "total_words": total_words,
            "keyword_density": density,
            "recommendation": "Keywords are well-balanced" if all(
                1 <= float(d["percentage"].rstrip("%")) <= 3
                for d in density.values()
            ) else "Adjust keyword usage"
        }


def main():
    """Test SEO optimizer."""
    print("\n" + "=" * 80)
    print("🔍 SEO OPTIMIZER")
    print("=" * 80 + "\n")

    # Test schema markup
    print("1️⃣  SCHEMA MARKUP GENERATION")
    print("-" * 80)

    article_schema = SchemaMarkupGenerator.generate_article_schema(
        title="PEM Electrolyzer Architecture and Efficiency Gains",
        description="Deep technical review of modern PEM electrolyzer designs",
        content_length=3500,
        image_url="https://example.com/image.jpg",
        keywords=["electrolyzer", "PEM", "hydrogen", "efficiency"]
    )
    print("✓ Article schema generated")
    print("  Type: Article")

    job_schema = SchemaMarkupGenerator.generate_job_posting_schema(
        title="Senior Electrochemist",
        company="GreenHydrogen Corp",
        location="San Francisco, CA",
        description="Join our team building next-gen electrolyzers",
        salary_min=120000,
        salary_max=180000
    )
    print("✓ JobPosting schema generated")
    print("  Type: JobPosting")

    # Test meta tags
    print("\n2️⃣  META TAG OPTIMIZATION")
    print("-" * 80)

    meta_tags = MetaTagOptimizer.generate_meta_tags(
        title="PEM Electrolyzer Architecture and Efficiency Gains",
        description="Deep technical review of modern PEM electrolyzer designs",
        keywords=["electrolyzer", "PEM", "hydrogen", "efficiency", "architecture"],
        canonical_url="https://avoltium.in/pem-electrolyzer-architecture",
        image_url="https://example.com/image.jpg"
    )
    print("✓ Meta tags optimized")
    for key, value in list(meta_tags.items())[:5]:
        print(f"  {key}: {value[:50]}...")

    # Test internal linking
    print("\n3️⃣  INTERNAL LINKING STRATEGY")
    print("-" * 80)

    available = [
        "Water Treatment Systems",
        "Thermal Management Cooling",
        "Power Electronics for Electrolysis",
        "Green Hydrogen Production"
    ]

    internal_links = InternalLinkingStrategy.find_internal_links(
        "PEM Electrolyzer",
        available
    )
    print(f"✓ Found {len(internal_links)} internal linking opportunities")
    for link in internal_links:
        print(f"  - {link['anchor_text']} → {link['target_article']}")

    # Test readability
    print("\n4️⃣  READABILITY ANALYSIS")
    print("-" * 80)

    sample_text = """
    PEM electrolyzers represent a significant advancement in hydrogen production technology.
    They operate with high efficiency and rapid response times. This makes them ideal for
    intermittent renewable energy sources. The technology continues to improve every year.
    """

    readability = ReadabilityAnalyzer.analyze_readability(sample_text)
    print("✓ Readability analyzed")
    for key, value in readability.items():
        print(f"  {key}: {value}")

    # Test keyword density
    print("\n5️⃣  KEYWORD DENSITY ANALYSIS")
    print("-" * 80)

    keywords = ["electrolyzer", "hydrogen", "efficiency"]
    density = KeywordDensityAnalyzer.analyze_density(sample_text, keywords)
    print("✓ Keyword density analyzed")
    print(f"  Total words: {density['total_words']}")
    for keyword, stats in density["keyword_density"].items():
        print(f"  {keyword}: {stats['percentage']} ({stats['status']})")


if __name__ == "__main__":
    main()
