#!/usr/bin/env python3
"""
OmniRoute Cost-Optimized Content Generator

Routes content generation requests to cheapest qualified API:
- 40% to Gemini API (cheapest, good quality)
- 30% to Claude (premium quality for critical articles)
- 30% to cache (repeated topics)

Dramatically reduces content generation costs while maintaining quality.
"""

import os
import json
import time
import random
import logging
import hashlib
import requests
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("omniroute-generator")


class CostOptimizer:
    """Analyzes content type and decides which API is best fit."""

    # Tier 1: Deep technical (3000-4000 words) - needs Claude
    TIER_1_KEYWORDS = {
        "architecture", "electrolyzer", "compressor", "optimization",
        "thermal management", "efficiency", "degradation", "electrodeionization"
    }

    # Tier 2: Moderate depth (1500-2500 words) - Gemini is fine
    TIER_2_KEYWORDS = {
        "overview", "guide", "comparison", "selection", "design",
        "management", "system", "integration"
    }

    # Tier 3: News/brief (800-1200 words) - always use Gemini
    TIER_3_KEYWORDS = {
        "news", "update", "report", "announcement", "brief", "latest"
    }

    @classmethod
    def analyze_topic(cls, topic: str) -> Tuple[str, str, int]:
        """
        Analyze article topic and recommend tier + API.
        Returns: (tier, recommended_api, estimated_cost_cents)
        """
        topic_lower = topic.lower()

        # Determine tier
        if any(kw in topic_lower for kw in cls.TIER_1_KEYWORDS):
            tier = "tier1"
            words = 3500
            api_choice = cls._select_tier1_api()
            cost = {"claude": 35, "gemini": 8}.get(api_choice, 8)
        elif any(kw in topic_lower for kw in cls.TIER_2_KEYWORDS):
            tier = "tier2"
            words = 2000
            api_choice = cls._select_tier2_api()
            cost = {"claude": 20, "gemini": 5}.get(api_choice, 5)
        else:
            tier = "tier3"
            words = 1000
            api_choice = "gemini"  # Always cheap for tier 3
            cost = 3

        return tier, api_choice, cost

    @classmethod
    def _select_tier1_api(cls) -> str:
        """Tier 1: 70% Claude (quality) + 30% Gemini (cost)."""
        return "claude" if random.random() < 0.7 else "gemini"

    @classmethod
    def _select_tier2_api(cls) -> str:
        """Tier 2: 50% Claude + 50% Gemini (balanced)."""
        return "claude" if random.random() < 0.5 else "gemini"


class CacheManager:
    """Simple cache for repeated topics (30-day TTL)."""

    def __init__(self, cache_dir: str = "/tmp/content_cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def get_cache_key(self, topic: str) -> str:
        """Generate deterministic cache key from topic."""
        return hashlib.md5(topic.lower().encode()).hexdigest()

    def get(self, topic: str) -> Optional[Dict]:
        """Retrieve cached content if valid."""
        cache_key = self.get_cache_key(topic)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        if not os.path.exists(cache_file):
            return None

        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)

            # Check if cache is still valid (30 days)
            cached_time = datetime.fromisoformat(data.get("timestamp", "2000-01-01"))
            if datetime.now() - cached_time > timedelta(days=30):
                log.info(f"Cache expired for topic: {topic}")
                return None

            log.info(f"✓ Cache hit for: {topic}")
            return data["content"]

        except Exception as e:
            log.warning(f"Cache retrieval failed: {e}")
            return None

    def set(self, topic: str, content: str):
        """Store generated content in cache."""
        cache_key = self.get_cache_key(topic)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        try:
            with open(cache_file, 'w') as f:
                json.dump({
                    "topic": topic,
                    "content": content,
                    "timestamp": datetime.now().isoformat()
                }, f)
            log.info(f"✓ Cached content for: {topic}")
        except Exception as e:
            log.warning(f"Cache write failed: {e}")


class OmniRouteGateway:
    """Cost-optimized routing gateway for content generation."""

    GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    CLAUDE_API = "https://api.anthropic.com/v1/messages"

    def __init__(self):
        self.cache = CacheManager()
        self.gemini_key = os.environ.get("GEMINI_API_KEY")
        self.claude_key = os.environ.get("ANTHROPIC_API_KEY")
        self.stats = {
            "gemini_used": 0,
            "claude_used": 0,
            "cache_hits": 0,
            "total_requests": 0,
            "total_cost_cents": 0
        }

    def generate(self, topic: str, context: str = "") -> Tuple[str, Dict]:
        """
        Generate article content with intelligent routing.

        Returns: (content, metadata)
        Metadata includes: api_used, tier, cost_cents, generation_time
        """
        self.stats["total_requests"] += 1
        metadata = {
            "topic": topic,
            "api_used": None,
            "tier": None,
            "cost_cents": 0,
            "generation_time_seconds": 0,
            "source": "omniroute"
        }

        start_time = time.time()

        # Try cache first (30% hit rate expected)
        cached = self.cache.get(topic)
        if cached:
            self.stats["cache_hits"] += 1
            metadata["api_used"] = "cache"
            metadata["generation_time_seconds"] = time.time() - start_time
            return cached, metadata

        # Analyze topic to determine tier and API
        tier, api_choice, cost = CostOptimizer.analyze_topic(topic)
        metadata["tier"] = tier
        metadata["api_used"] = api_choice
        metadata["cost_cents"] = cost

        # Fallback: if API key missing, use whatever is available
        if not self.gemini_key and not self.claude_key:
            log.error("No API keys configured. Set GEMINI_API_KEY or ANTHROPIC_API_KEY")
            raise RuntimeError("No API keys available")

        # Generate content
        try:
            if api_choice == "gemini" and self.gemini_key:
                content = self._call_gemini(topic, context, tier)
                self.stats["gemini_used"] += 1
            elif api_choice == "claude" and self.claude_key:
                content = self._call_claude(topic, context, tier)
                self.stats["claude_used"] += 1
            else:
                # Fallback to whatever API is available
                if self.gemini_key:
                    content = self._call_gemini(topic, context, tier)
                    self.stats["gemini_used"] += 1
                else:
                    content = self._call_claude(topic, context, tier)
                    self.stats["claude_used"] += 1

            # Cache successful generation
            self.cache.set(topic, content)
            self.stats["total_cost_cents"] += cost

            metadata["generation_time_seconds"] = time.time() - start_time
            return content, metadata

        except Exception as e:
            log.error(f"Content generation failed: {e}")
            raise

    def _call_gemini(self, topic: str, context: str, tier: str) -> str:
        """Generate content via Gemini API (cheap)."""
        word_targets = {"tier1": 3500, "tier2": 2000, "tier3": 1000}
        word_target = word_targets.get(tier, 2000)

        system_prompt = f"""You are a technical content writer for industrial/engineering audiences.
Write a comprehensive, professional article on the given topic.
Target length: {word_target} words.
Style: Technical but accessible, with examples and data.
Structure: Title, introduction, main sections (3-5), conclusion.
Avoid fluff: every sentence should add value."""

        messages = [
            {
                "role": "user",
                "content": f"Topic: {topic}\n\n{context if context else ''}\n\nWrite the article now."
            }
        ]

        try:
            response = requests.post(
                self.GEMINI_API,
                headers={"Content-Type": "application/json"},
                json={
                    "contents": messages,
                    "systemInstruction": {"parts": [{"text": system_prompt}]},
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": word_target * 1.3,  # ~1.3 tokens per word
                    }
                },
                params={"key": self.gemini_key},
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

        except Exception as e:
            log.error(f"Gemini API call failed: {e}")
            raise

    def _call_claude(self, topic: str, context: str, tier: str) -> str:
        """Generate content via Claude API (premium quality)."""
        word_targets = {"tier1": 3500, "tier2": 2000, "tier3": 1000}
        word_target = word_targets.get(tier, 2000)

        system_prompt = f"""You are a technical content writer for industrial/engineering audiences.
Write a comprehensive, professional article on the given topic.
Target length: {word_target} words.
Style: Technical but accessible, with examples and data.
Structure: Title, introduction, main sections (3-5), conclusion.
Avoid fluff: every sentence should add value."""

        user_message = f"Topic: {topic}\n\n{context if context else ''}\n\nWrite the article now."

        try:
            response = requests.post(
                self.CLAUDE_API,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.claude_key,
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": int(word_target * 1.3),
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_message}]
                },
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

        except Exception as e:
            log.error(f"Claude API call failed: {e}")
            raise

    def get_stats(self) -> Dict:
        """Get current routing statistics."""
        total = self.stats["total_requests"]
        if total == 0:
            return self.stats

        return {
            **self.stats,
            "gemini_percentage": f"{self.stats['gemini_used'] / total * 100:.1f}%",
            "claude_percentage": f"{self.stats['claude_used'] / total * 100:.1f}%",
            "cache_hit_rate": f"{self.stats['cache_hits'] / total * 100:.1f}%",
            "average_cost_per_article": f"${self.stats['total_cost_cents'] / max(1, total) / 100:.2f}",
            "total_savings_vs_claude": f"${(self.stats['claude_used'] * 25 - self.stats['total_cost_cents']) / 100:.2f}"
        }


def main():
    """Test OmniRoute gateway."""
    gateway = OmniRouteGateway()

    topics = [
        "PEM Electrolyzer Architecture",
        "Water Treatment Systems",
        "Green Hydrogen Compressors",
    ]

    print("\n" + "=" * 80)
    print("🚀 OMNIROUTE COST-OPTIMIZED CONTENT GENERATOR")
    print("=" * 80 + "\n")

    for topic in topics:
        print(f"📝 Generating: {topic}")
        print("-" * 80)

        try:
            content, metadata = gateway.generate(topic)

            print(f"✓ Generated ({metadata['api_used']})")
            print(f"  Tier: {metadata['tier']}")
            print(f"  Cost: ${metadata['cost_cents'] / 100:.2f}")
            print(f"  Time: {metadata['generation_time_seconds']:.1f}s")
            print(f"  Length: {len(content.split())} words")
            print()

        except Exception as e:
            print(f"❌ Failed: {e}\n")

    # Print statistics
    print("=" * 80)
    print("📊 ROUTING STATISTICS")
    print("=" * 80)
    for key, value in gateway.get_stats().items():
        print(f"{key.replace('_', ' ').title()}: {value}")


if __name__ == "__main__":
    main()
