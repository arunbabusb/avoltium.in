#!/usr/bin/env python3
"""
Monetization Engine - Multi-Channel Revenue Optimization

Manages:
- AdSense placement (optimal RPM positioning)
- Sponsored article/listing detection
- Referral link injection
- Revenue tracking & reporting
- A/B testing for ad placements
"""

import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("monetization")


@dataclass
class AdPlacement:
    """Define AdSense ad placement."""
    position: str  # above_fold, mid_content, below_content, sidebar
    ad_format: str  # responsive, fixed_300x250, fixed_728x90
    revenue_tier: str  # premium, standard, low
    estimated_rpm: float  # Revenue per 1000 impressions


class AdSenseOptimizer:
    """Optimize AdSense placement for maximum RPM while maintaining UX."""

    # Industry RPM benchmarks for tech/engineering content
    RPM_BENCHMARKS = {
        "above_fold": 4.50,  # Highest visibility
        "mid_content": 3.20,  # Good engagement
        "below_content": 1.80,  # Lower visibility
        "sidebar": 2.50,  # Moderate engagement
    }

    # Premium tier: technical audience, high engagement
    PREMIUM_PLACEMENTS = [
        AdPlacement("above_fold", "responsive", "premium", 5.50),
        AdPlacement("mid_content", "responsive", "premium", 4.20),
        AdPlacement("below_content", "responsive", "premium", 2.50),
    ]

    # Standard tier: general content
    STANDARD_PLACEMENTS = [
        AdPlacement("above_fold", "responsive", "standard", 3.50),
        AdPlacement("mid_content", "fixed_300x250", "standard", 2.50),
        AdPlacement("below_content", "responsive", "standard", 1.50),
    ]

    # Low tier: news/brief content
    LOW_PLACEMENTS = [
        AdPlacement("mid_content", "responsive", "low", 1.50),
        AdPlacement("below_content", "responsive", "low", 0.80),
    ]

    @classmethod
    def get_placements_for_tier(cls, content_tier: str) -> List[AdPlacement]:
        """Get optimal ad placements for content tier."""
        tier_map = {
            "tier1": cls.PREMIUM_PLACEMENTS,
            "tier2": cls.STANDARD_PLACEMENTS,
            "tier3": cls.LOW_PLACEMENTS,
        }
        return tier_map.get(content_tier, cls.STANDARD_PLACEMENTS)

    @classmethod
    def inject_ads(cls, content: str, placements: List[AdPlacement]) -> Tuple[str, Dict]:
        """
        Inject AdSense codes into content at optimal positions.

        Returns: (modified_content, metadata)
        """
        metadata = {
            "placements": len(placements),
            "estimated_rpm": sum(p.estimated_rpm for p in placements),
            "estimated_monthly_revenue": 0
        }

        # Split content into paragraphs
        paragraphs = content.split("\n\n")
        if len(paragraphs) < 3:
            return content, metadata

        modified = []

        for i, para in enumerate(paragraphs):
            modified.append(para)

            # Insert ads at strategic points
            if len(placements) > 0 and i == len(paragraphs) // 4:
                # First ad: after 25% of content
                ad = placements[0]
                modified.append(f"\n<!-- AdSense: {ad.position} ({ad.ad_format}) -->\n"
                              f"<ins class='adsbygoogle' style='display:block' "
                              f"data-ad-client='ca-pub-xxxxxxxxxxxxxxxx' "
                              f"data-ad-slot='xxxxxxxxxx' "
                              f"data-ad-format='{ad.ad_format}'></ins>\n")

            elif len(placements) > 1 and i == len(paragraphs) // 2:
                # Second ad: middle of content
                ad = placements[1]
                modified.append(f"\n<!-- AdSense: {ad.position} ({ad.ad_format}) -->\n"
                              f"<ins class='adsbygoogle' style='display:block' "
                              f"data-ad-client='ca-pub-xxxxxxxxxxxxxxxx' "
                              f"data-ad-slot='xxxxxxxxxx' "
                              f"data-ad-format='{ad.ad_format}'></ins>\n")

            elif len(placements) > 2 and i == len(paragraphs) * 3 // 4:
                # Third ad: near end
                ad = placements[2]
                modified.append(f"\n<!-- AdSense: {ad.position} ({ad.ad_format}) -->\n"
                              f"<ins class='adsbygoogle' style='display:block' "
                              f"data-ad-client='ca-pub-xxxxxxxxxxxxxxxx' "
                              f"data-ad-slot='xxxxxxxxxx' "
                              f"data-ad-format='{ad.ad_format}'></ins>\n")

        modified_content = "\n\n".join(modified)

        # Estimate monthly revenue (assume 1000 pageviews/month per article)
        avg_rpm = metadata["estimated_rpm"] / len(placements) if placements else 0
        metadata["estimated_monthly_revenue"] = (1000 * avg_rpm) / 1000

        return modified_content, metadata


class SponsoredListingManager:
    """Manage sponsored job listings and articles (TechJobs360)."""

    # Pricing tiers for sponsored listings
    PRICING = {
        "featured_24h": 200,  # $200 for 24-hour featured
        "sponsored_week": 500,  # $500 for 7-day sponsored
        "sponsored_month": 1500,  # $1500 for 30-day sponsored
        "premium_placement": 2000,  # $2000 for premium homepage
    }

    def __init__(self):
        self.sponsored_listings: Dict[str, Dict] = {}

    def mark_sponsored(
        self,
        listing_id: str,
        listing_type: str,  # job, company, article
        tier: str,  # featured_24h, sponsored_week, etc.
        company_name: str
    ) -> Dict:
        """Mark a listing as sponsored."""
        if tier not in self.PRICING:
            raise ValueError(f"Invalid sponsorship tier: {tier}")

        sponsored = {
            "listing_id": listing_id,
            "listing_type": listing_type,
            "tier": tier,
            "company_name": company_name,
            "price": self.PRICING[tier],
            "markup": self._get_markup(tier),
            "created_at": datetime.now().isoformat(),
            "expires_at": self._calculate_expiry(tier)
        }

        self.sponsored_listings[listing_id] = sponsored
        log.info(f"✓ Sponsored: {listing_id} ({tier}) - ${self.PRICING[tier]}")

        return sponsored

    def _get_markup(self, tier: str) -> str:
        """Get HTML markup to display sponsorship badge."""
        if tier == "featured_24h":
            return '<span class="badge badge-danger">Featured (24h)</span>'
        elif tier == "sponsored_week":
            return '<span class="badge badge-warning">Sponsored</span>'
        elif tier == "sponsored_month":
            return '<span class="badge badge-warning">Sponsored</span>'
        elif tier == "premium_placement":
            return '<span class="badge badge-gold">Premium Placement ⭐</span>'
        return ""

    def _calculate_expiry(self, tier: str) -> str:
        """Calculate expiry date based on sponsorship tier."""
        from datetime import timedelta

        hours = {
            "featured_24h": 24,
            "sponsored_week": 7 * 24,
            "sponsored_month": 30 * 24,
            "premium_placement": 30 * 24,
        }

        expiry = datetime.now() + timedelta(hours=hours.get(tier, 24))
        return expiry.isoformat()

    def is_active_sponsorship(self, listing_id: str) -> bool:
        """Check if listing sponsorship is still active."""
        if listing_id not in self.sponsored_listings:
            return False

        sponsored = self.sponsored_listings[listing_id]
        expiry = datetime.fromisoformat(sponsored["expires_at"])
        return datetime.now() < expiry


class ReferralLinkManager:
    """Manage affiliate/referral links for revenue."""

    # Common affiliate programs for industrial/engineering content
    REFERRAL_PROGRAMS = {
        "amazon": {
            "base_url": "https://amazon.com/s?k=",
            "commission_rate": 0.04,  # 4%
            "category": "industrial_equipment"
        },
        "grainger": {
            "base_url": "https://www.grainger.com/search?searchQuery=",
            "commission_rate": 0.05,  # 5%
            "category": "industrial_supplies"
        },
        "ebay_affiliate": {
            "base_url": "https://ebay.com/sch/i.html?_nkw=",
            "commission_rate": 0.05,  # 5%
            "category": "industrial_parts"
        }
    }

    def __init__(self):
        self.injected_links: List[Dict] = []

    def get_referral_url(self, keyword: str, program: str = "amazon") -> str:
        """Generate affiliate URL for keyword."""
        if program not in self.REFERRAL_PROGRAMS:
            program = "amazon"

        prog = self.REFERRAL_PROGRAMS[program]
        return f"{prog['base_url']}{keyword.replace(' ', '+')}"

    def inject_referral_links(
        self,
        content: str,
        keywords: List[str],
        program: str = "amazon"
    ) -> str:
        """Inject referral links into content for keywords."""
        modified = content

        for keyword in keywords:
            if keyword.lower() in content.lower():
                referral_url = self.get_referral_url(keyword, program)
                # Replace first occurrence of keyword with linked version
                modified = modified.replace(
                    keyword,
                    f'<a href="{referral_url}" target="_blank" rel="noopener">{keyword}</a>',
                    1
                )

                self.injected_links.append({
                    "keyword": keyword,
                    "program": program,
                    "url": referral_url
                })

        return modified


class RevenueTracker:
    """Track and report revenue across all channels."""

    def __init__(self):
        self.revenue_log = []

    def log_revenue(
        self,
        source: str,  # adsense, sponsored_listing, referral, newsletter
        amount: float,
        details: Dict
    ):
        """Log revenue transaction."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "amount": amount,
            "details": details
        }
        self.revenue_log.append(entry)
        log.info(f"💰 Revenue logged: {source} = ${amount:.2f}")

    def estimate_monthly_revenue(self) -> Dict:
        """Estimate monthly revenue by channel."""
        estimates = {
            "adsense_tier1": 50 * 5.50,  # 50 articles * $5.50 RPM
            "adsense_tier2": 30 * 2.50,  # 30 articles * $2.50 RPM
            "adsense_tier3": 20 * 1.50,  # 20 articles * $1.50 RPM
            "sponsored_listings": 500 * 0.10,  # 500 jobs, 10% sponsored
            "referral_commissions": 200,  # Estimated referral revenue
            "newsletter": 50,  # Newsletter sponsorships
        }

        estimates["total_monthly"] = sum(estimates.values())
        estimates["total_annual"] = estimates["total_monthly"] * 12

        return estimates

    def get_report(self) -> Dict:
        """Generate revenue report."""
        estimates = self.estimate_monthly_revenue()

        return {
            "timestamp": datetime.now().isoformat(),
            "revenue_sources": {
                "avoltium": {
                    "adsense": estimates["adsense_tier1"] + estimates["adsense_tier2"],
                    "sponsored": estimates["sponsored_listings"],
                    "referral": estimates["referral_commissions"],
                    "newsletter": estimates["newsletter"],
                },
                "techjobs360": {
                    "adsense": estimates["adsense_tier3"],
                    "sponsored_listings": estimates["sponsored_listings"],
                    "referral_hires": 500,  # $20-50 per hire
                }
            },
            "monthly_estimate": estimates["total_monthly"],
            "annual_estimate": estimates["total_annual"],
            "breakdown": estimates
        }


def main():
    """Test monetization engine."""
    print("\n" + "=" * 80)
    print("💰 MONETIZATION ENGINE")
    print("=" * 80 + "\n")

    # Test AdSense optimization
    print("1️⃣  ADSENSE PLACEMENT OPTIMIZATION")
    print("-" * 80)

    sample_content = """
Article introduction paragraph. This is where readers first engage with the content.
It should be compelling and clear.

Main section 1. This is the first major section of the article.
It contains important information and technical details.

Main section 2. This section goes deeper into the topic.
It includes examples, data, and evidence.

Conclusion section. This wraps up the article with key takeaways.
"""

    placements = AdSenseOptimizer.get_placements_for_tier("tier1")
    modified, metadata = AdSenseOptimizer.inject_ads(sample_content, placements)

    print(f"✓ Ad placements: {metadata['placements']}")
    print(f"  Estimated RPM: ${metadata['estimated_rpm']:.2f}")
    print(f"  Monthly revenue (1K views): ${metadata['estimated_monthly_revenue']:.2f}")

    # Test sponsored listings (TechJobs360)
    print("\n2️⃣  SPONSORED LISTING MANAGEMENT")
    print("-" * 80)

    manager = SponsoredListingManager()
    sponsored = manager.mark_sponsored(
        "job_12345",
        "job",
        "sponsored_week",
        "TechCorp Inc"
    )
    print(f"✓ Sponsored job #{sponsored['listing_id']}")
    print(f"  Tier: {sponsored['tier']}")
    print(f"  Price: ${sponsored['price']}")
    print(f"  Badge: {sponsored['markup']}")

    # Test referral links
    print("\n3️⃣  REFERRAL LINK INJECTION")
    print("-" * 80)

    referral_mgr = ReferralLinkManager()
    keywords = ["electrolyzer", "compressor", "pump"]
    modified_content = referral_mgr.inject_referral_links(
        sample_content,
        keywords,
        "amazon"
    )
    print(f"✓ Injected {len(referral_mgr.injected_links)} referral links")
    for link in referral_mgr.injected_links:
        print(f"  - {link['keyword']} → {link['program']}")

    # Revenue tracking
    print("\n4️⃣  REVENUE TRACKING")
    print("-" * 80)

    tracker = RevenueTracker()
    report = tracker.get_report()

    print(f"Monthly Revenue Estimate: ${report['monthly_estimate']:.2f}")
    print(f"Annual Revenue Estimate: ${report['annual_estimate']:.2f}")
    print("\nBreakdown:")
    for source, amount in report["breakdown"].items():
        if isinstance(amount, (int, float)):
            print(f"  {source}: ${amount:.2f}")


if __name__ == "__main__":
    main()
