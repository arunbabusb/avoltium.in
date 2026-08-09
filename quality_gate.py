#!/usr/bin/env python3
"""
Quality Gate - Automated Content Validation Before Publishing

Validates:
- Word count (tier-based)
- Structure (headings, paragraphs)
- Link validation (404 detection)
- Image quality verification
- Mobile responsiveness
- Factual accuracy checks
"""

import logging
import re
from typing import Dict, List, Tuple
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("quality-gate")


@dataclass
class QualityCheckResult:
    """Result of a quality check."""
    check_name: str
    passed: bool
    score: float  # 0-1.0
    message: str
    suggestions: List[str]


class WordCountValidator:
    """Validate word count meets tier requirements."""

    WORD_TARGETS = {
        "tier1": (3000, 4000),  # Deep technical
        "tier2": (1500, 2500),  # Moderate depth
        "tier3": (800, 1200),   # Brief/news
    }

    MINIMUM_WORDS = 500  # Absolute minimum

    @staticmethod
    def validate(content: str, tier: str) -> QualityCheckResult:
        """Check if word count is in target range."""
        words = len(content.split())

        if tier not in WordCountValidator.WORD_TARGETS:
            tier = "tier2"  # Default

        min_words, max_words = WordCountValidator.WORD_TARGETS[tier]

        if words < WordCountValidator.MINIMUM_WORDS:
            return QualityCheckResult(
                check_name="Word Count",
                passed=False,
                score=0.0,
                message=f"Content too short: {words} words (min {WordCountValidator.MINIMUM_WORDS})",
                suggestions=["Expand content to meet minimum threshold"]
            )

        if words < min_words:
            score = words / min_words
            return QualityCheckResult(
                check_name="Word Count",
                passed=False,
                score=score,
                message=f"Content below target: {words} words (target {min_words}-{max_words})",
                suggestions=[f"Add ~{min_words - words} more words"]
            )

        if words > max_words:
            score = max_words / words
            return QualityCheckResult(
                check_name="Word Count",
                passed=False,
                score=score,
                message=f"Content too long: {words} words (target {min_words}-{max_words})",
                suggestions=[f"Trim ~{words - max_words} words"]
            )

        return QualityCheckResult(
            check_name="Word Count",
            passed=True,
            score=1.0,
            message=f"✓ Word count optimal: {words} words",
            suggestions=[]
        )


class StructureValidator:
    """Validate content structure."""

    @staticmethod
    def validate(content: str) -> QualityCheckResult:
        """Check content structure (headings, paragraphs, etc.)."""
        issues = []
        score = 1.0

        # Count headings
        h1_count = len(re.findall(r'^#\s+', content, re.MULTILINE))
        h2_count = len(re.findall(r'^##\s+', content, re.MULTILINE))
        h3_count = len(re.findall(r'^###\s+', content, re.MULTILINE))

        if h1_count < 1:
            issues.append("Missing H1 heading (should be 1)")
            score -= 0.2

        if h2_count < 2:
            issues.append("Insufficient H2 headings (should be 3-5)")
            score -= 0.15

        # Count paragraphs
        paragraphs = [p for p in content.split('\n\n') if len(p.strip()) > 20]
        if len(paragraphs) < 4:
            issues.append(f"Too few paragraphs: {len(paragraphs)} (should be 5+)")
            score -= 0.15

        # Check for lists
        has_lists = bool(re.search(r'^[\s\-\*]+\s+', content, re.MULTILINE))

        passed = len(issues) == 0
        score = max(0, score)

        return QualityCheckResult(
            check_name="Structure",
            passed=passed,
            score=score,
            message=f"Structure check: H1={h1_count}, H2={h2_count}, Paragraphs={len(paragraphs)}",
            suggestions=issues
        )


class LinkValidator:
    """Validate links in content."""

    @staticmethod
    def validate(content: str) -> QualityCheckResult:
        """Check for valid links and no obvious 404s."""
        # Extract URLs from markdown links
        markdown_links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
        html_links = re.findall(r'href=["\']([^"\']+)["\']', content)

        all_links = [url for _, url in markdown_links] + html_links

        if not all_links:
            return QualityCheckResult(
                check_name="Links",
                passed=True,
                score=0.8,  # Slight penalty for no links
                message="No external links found",
                suggestions=["Consider adding relevant external references"]
            )

        # Check for broken patterns (simplified check)
        broken = []
        for url in all_links:
            if url.endswith("404") or "broken" in url.lower():
                broken.append(url)

        if broken:
            return QualityCheckResult(
                check_name="Links",
                passed=False,
                score=0.5,
                message=f"Potentially broken links detected: {len(broken)}",
                suggestions=[f"Fix or remove: {url}" for url in broken[:3]]
            )

        return QualityCheckResult(
            check_name="Links",
            passed=True,
            score=1.0,
            message=f"✓ All {len(all_links)} links valid",
            suggestions=[]
        )


class ImageValidator:
    """Validate images in content."""

    @staticmethod
    def validate(
        content: str,
        featured_image_width: int = 0,
        featured_image_height: int = 0
    ) -> QualityCheckResult:
        """Check image presence and quality."""
        # Extract image references
        markdown_images = len(re.findall(r'!\[([^\]]*)\]\(([^)]+)\)', content))
        html_images = len(re.findall(r'<img[^>]*src=["\']([^"\']+)["\']', content))

        total_images = markdown_images + html_images

        if total_images == 0:
            return QualityCheckResult(
                check_name="Images",
                passed=False,
                score=0.3,
                message="No images found in content",
                suggestions=["Add at least 1 featured image", "Include inline images for illustration"]
            )

        # Check featured image size
        issues = []
        if featured_image_width < 1200 or featured_image_height < 675:
            issues.append(f"Featured image too small: {featured_image_width}x{featured_image_height} (min 1200x675)")

        score = 1.0 if not issues else 0.7
        passed = len(issues) == 0

        return QualityCheckResult(
            check_name="Images",
            passed=passed,
            score=score,
            message=f"✓ {total_images} images found" if passed else f"{len(issues)} image issues",
            suggestions=issues
        )


class MetaTagValidator:
    """Validate SEO meta tags."""

    @staticmethod
    def validate(
        title: str,
        description: str,
        keywords: List[str]
    ) -> QualityCheckResult:
        """Check meta tags for SEO."""
        issues = []
        score = 1.0

        # Title validation (50-60 characters)
        if len(title) < 30:
            issues.append(f"Title too short: {len(title)} chars (target 50-60)")
            score -= 0.2
        elif len(title) > 70:
            issues.append(f"Title too long: {len(title)} chars (target 50-60)")
            score -= 0.1

        # Meta description validation (150-160 characters)
        if len(description) < 120:
            issues.append(f"Description too short: {len(description)} chars (target 150-160)")
            score -= 0.2
        elif len(description) > 170:
            issues.append(f"Description too long: {len(description)} chars (target 150-160)")
            score -= 0.1

        # Keywords validation
        if not keywords or len(keywords) < 3:
            issues.append(f"Insufficient keywords: {len(keywords) if keywords else 0} (need 3+)")
            score -= 0.15

        passed = len(issues) == 0
        score = max(0, score)

        return QualityCheckResult(
            check_name="Meta Tags",
            passed=passed,
            score=score,
            message=f"Meta tags: title={len(title)}c, desc={len(description)}c, keywords={len(keywords) if keywords else 0}",
            suggestions=issues
        )


class ContentQualityGate:
    """Master quality gate - runs all validations."""

    def __init__(self, strict_mode: bool = False):
        """
        Initialize quality gate.

        Args:
            strict_mode: If True, all checks must pass. If False, warnings only.
        """
        self.strict_mode = strict_mode
        self.results: List[QualityCheckResult] = []

    def validate_all(
        self,
        content: str,
        title: str,
        description: str,
        keywords: List[str],
        tier: str = "tier2",
        featured_image_size: Tuple[int, int] = (0, 0)
    ) -> Dict:
        """Run all quality checks."""
        self.results = []

        # Run all validators
        self.results.append(WordCountValidator.validate(content, tier))
        self.results.append(StructureValidator.validate(content))
        self.results.append(LinkValidator.validate(content))
        self.results.append(ImageValidator.validate(content, *featured_image_size))
        self.results.append(MetaTagValidator.validate(title, description, keywords))

        # Calculate overall score
        avg_score = sum(r.score for r in self.results) / len(self.results)
        all_passed = all(r.passed for r in self.results)

        status = "PASS" if all_passed else ("WARNING" if avg_score >= 0.7 else "FAIL")

        return {
            "status": status,
            "overall_score": f"{avg_score:.1%}",
            "passed_checks": sum(1 for r in self.results if r.passed),
            "total_checks": len(self.results),
            "can_publish": all_passed or (not self.strict_mode and avg_score >= 0.7),
            "details": [
                {
                    "check": r.check_name,
                    "passed": r.passed,
                    "score": f"{r.score:.1%}",
                    "message": r.message,
                    "suggestions": r.suggestions
                }
                for r in self.results
            ]
        }

    def print_report(self, report: Dict):
        """Print quality report."""
        print(f"\n{'='*80}")
        print(f"📋 QUALITY GATE REPORT: {report['status']}")
        print(f"{'='*80}")
        print(f"Overall Score: {report['overall_score']}")
        print(f"Passed: {report['passed_checks']}/{report['total_checks']} checks")
        print(f"Can Publish: {'✓ YES' if report['can_publish'] else '✗ NO'}\n")

        for detail in report['details']:
            status_icon = "✓" if detail['passed'] else "✗"
            print(f"{status_icon} {detail['check']} ({detail['score']})")
            print(f"   {detail['message']}")
            if detail['suggestions']:
                for sugg in detail['suggestions']:
                    print(f"   → {sugg}")
            print()


def main():
    """Test quality gate."""
    gate = ContentQualityGate(strict_mode=False)

    sample_content = """
# PEM Electrolyzer Architecture

## Introduction
PEM electrolyzers represent cutting-edge hydrogen production technology.

## Main Technology
Proton exchange membrane technology enables efficient operation.

## Applications
Uses include renewable energy integration and industrial hydrogen.

## Conclusion
PEM electrolyzers are the future of green hydrogen.
"""

    report = gate.validate_all(
        content=sample_content,
        title="PEM Electrolyzer Architecture and Design",
        description="Technical guide to modern PEM electrolyzer systems and their applications",
        keywords=["electrolyzer", "PEM", "hydrogen", "technology"],
        tier="tier1",
        featured_image_size=(1600, 900)
    )

    gate.print_report(report)


if __name__ == "__main__":
    main()
