#!/usr/bin/env python3
"""Tests for news selection.

The bug these exist to prevent nearly shipped: the first dry run of the news
pipeline selected three solar-financing items — a stake sale, a funding round
and a rooftop rule change — for a green-hydrogen engineering site, while
"Marginal costs for hydrogen are falling" sat unselected in the same candidate
pool. Nothing had crashed. RELEVANT is a pass/fail gate, the survivors were
sorted by publication time and sliced, so a story that cleared the gate an
hour ago beat a better one that cleared it two hours ago.

Ranking that on topic then exposed two more: the same PIB announcement reached
the top of the India and global lists at once, and a "Should You Buy?" stock
tip ranked first globally because it names a hydrogen company.

So these tests are not about whether the feeds parse. They are about whether
the wrong story can still reach a published post.

Run: python3 test_news_sources.py    (exits non-zero on failure)
Live feed checks run only with --live.
"""
import sys
from datetime import datetime, timedelta, timezone

import news_sources as m

FAIL = 0


def check(label, got, want):
    """Record one assertion, printing PASS or FAIL and counting failures."""
    global FAIL
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}: {label}" + ("" if ok else f" -> got {got!r}, want {want!r}"))
    if not ok:
        FAIL += 1


def item(title, hours_old=1, summary="", region="india"):
    """A NewsItem with only the fields selection actually reads."""
    return m.NewsItem(
        title=title, link="https://example.com/x", publisher="Test",
        published=datetime.now(timezone.utc) - timedelta(hours=hours_old),
        summary=summary, region=region,
    )


print("\nthe beats the site covers outrank generic renewables")
hydrogen = item("Marginal costs for hydrogen are falling")
policy = item("Centre awards 30 KTPA green hydrogen capacity to four refineries")
bop = item("Prozeal starts construction of ultra-high-purity water treatment skid")
standards = item("BIS notifies revised safety code for hydrogen storage")
solar = item("European Energy Secures $78 Million for UK Solar and Battery Project")

check("hydrogen subject scores top band", hydrogen.topic_score(), 5)
check("central government policy scores", policy.topic_score(), 5)
check("balance-of-plant scores", bop.topic_score() >= 4, True)
check("standards story scores", standards.topic_score() >= 3, True)
check("solar financing outranked by hydrogen",
      hydrogen.rank() > solar.rank(), True)
check("solar financing outranked by policy",
      policy.rank() > solar.rank(), True)

print("\nrecency breaks ties but never beats the subject")
stale_hydrogen = item("Marginal costs for hydrogen are falling", hours_old=30)
fresh_solar = item("Solar park commissioned in Rajasthan", hours_old=0)
check("a 30h hydrogen story still beats a fresh solar one",
      stale_hydrogen.rank() > fresh_solar.rank(), True)
fresh_hydrogen = item("Electrolyser stack degradation study published", hours_old=1)
old_hydrogen = item("Electrolyser membrane research published", hours_old=30)
check("within a band, fresher wins",
      fresh_hydrogen.rank() > old_hydrogen.rank(), True)

print("\nthe same story must not be published twice")
# The exact pair that ranked first in both regions on 11 August.
ani = "Centre awards 30 KTPA green hydrogen capacity to four oil refineries"
dd = "Centre awards 30 KTPA green hydrogen capacity to four refineries"
check("wire rewrite caught as a near-duplicate",
      m._is_near_duplicate(dd, [m._tokens(ani)]), True)
check("exact title caught", m._norm(ani) == m._norm(ani), True)
check("a genuinely different story is kept",
      m._is_near_duplicate("EU could pump green hydrogen through gas pipelines",
                           [m._tokens(ani)]), False)
check("empty title cannot match anything",
      m._is_near_duplicate("", [m._tokens(ani)]), False)

print("\ninvestment copy is not engineering analysis")
for tip in ("Prediction: You Won't Recognize Plug Power in 2028. Should You Buy?",
            "3 Hydrogen Stocks to Buy Right Now",
            "Plug Power shares surge on earnings beat",
            "Analyst rating: hydrogen sector price target raised"):
    check(f"rejected: {tip[:44]}", bool(m.NOISE.search(tip)), True)
# A real story that happens to name a company must survive the same filter.
check("company engineering story kept",
      bool(m.NOISE.search("Sasol commissions Envision Energy to study green hydrogen")),
      False)

print("\nthe relief valve admits policy without a technology keyword")
mnre = item("MNRE notifies revised guidelines for electrolyser manufacturing")
check("policy item scores above the gate threshold", mnre.topic_score() >= 3, True)

if "--live" in sys.argv:
    print("\nlive feeds")
    india, world, ok = m.collect()
    check("at least half the feeds answered", ok >= 5, True)
    check("india list is non-empty", len(india) > 0, True)
    check("global list is non-empty", len(world) > 0, True)
    # The defect this file exists for: the slice a --count 3 run actually takes
    # must not contain the same story twice.
    picked = india[:2] + world[:1]
    kept = []
    dupes = 0
    for p in picked:
        if m._is_near_duplicate(p.title, kept):
            dupes += 1
        kept.append(m._tokens(p.title))
    check("no duplicate inside a --count 3 selection", dupes, 0)
    for p in picked:
        print(f"    [score {p.topic_score()}] {p.title[:60]}")
else:
    print("\n(skipping live feed checks; pass --live to run them)")

print()
if FAIL:
    print(f"{FAIL} test(s) FAILED")
    sys.exit(1)
print("All news-selection tests passed.")
