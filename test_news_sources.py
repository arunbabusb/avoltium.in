#!/usr/bin/env python3
"""Tests for the news filter, the region split and the duplicate check.

Every case here is a real headline that reached a dry run, not an invented
one. Three of them were selected for publication before the rule that now
rejects them existed:

  * "Philippines eases rules for own-use solar systems" — the topic filter
    listed solar as a standalone alternative, so a solar trade feed filled all
    three slots.
  * "Centre awards 30 KTPA ... to four oil refineries" arrived twice from two
    wires, one word apart, and exact-match de-duplication kept both.
  * "Ethanol, EVs must coexist in India's clean mobility transition" passed
    because its summary listed hydrogen among five fuels.

The point of pinning them is that the next regression in this module is a
wrong article on a live site at 04:10 UTC, with no one watching.
"""
from __future__ import annotations

import unittest

from news_sources import (
    NOISE, _is_duplicate, _norm, _sig, is_relevant, region_of,
)


class TestRelevance(unittest.TestCase):
    """A green hydrogen publication publishes hydrogen stories."""

    def test_hydrogen_headlines_are_relevant(self):
        """A CORE term in the headline is what earns a place."""
        for title in (
            "Centre awards 30 KTPA green hydrogen capacity to four refineries",
            "India's Prozeal starts construction of ultra-high-purity green ammonia plant",
            "Sasol commissions Envision Energy to study green hydrogen project",
            "Thyssenkrupp Nucera wins 100 MW electrolyser order",
            "Fuel-cell trucks enter service at Rotterdam",
            "Power-to-X plant reaches financial close in Denmark",
            "Green steel venture signs H2 supply deal",
        ):
            with self.subTest(title=title):
                self.assertTrue(is_relevant(title))

    def test_adjacent_energy_alone_is_not_relevant(self):
        """Solar and wind stories belong to somebody else's publication."""
        for title in (
            "Philippines eases rules for own-use solar systems",
            "Solar developer secures $78 million for UK battery projects",
            "Offshore wind auction clears at record low price",
            "Desalination plant opens in Chennai",
        ):
            with self.subTest(title=title):
                self.assertFalse(is_relevant(title))

    def test_passing_mention_in_summary_does_not_qualify(self):
        """The headline decides. A summary name-check is not a story.

        This exact item was picked for publication: hydrogen appears once, as
        the fifth item in a list of fuels, in a piece about ethanol and EVs.
        """
        title = ("Ethanol, EVs must coexist in India's clean mobility "
                 "transition; E20 mileage impact limited: IFGE")
        summary = ("IFGE said India needs a diversified energy strategy "
                   "comprising ethanol, electric vehicles, hybrids, CNG and "
                   "hydrogen, particularly as nearly 300 million internal "
                   "combustion engine vehicles remain on the country's roads.")
        self.assertFalse(is_relevant(title, summary))

    def test_adjacent_terms_ride_along_with_a_core_term(self):
        """Solar is welcome in a hydrogen story, just not on its own."""
        self.assertTrue(is_relevant("Solar-powered electrolyser starts up in Oman"))


class TestNoise(unittest.TestCase):
    """Wire copy that is not a story about the sector."""

    def test_investment_commentary_is_rejected(self):
        """An engineering site does not tell readers which shares to buy."""
        for title in (
            "Prediction: You Won't Recognize Plug Power in 2028. Should You Buy the Stock?",
            "3 Best Stocks to buy in hydrogen right now",
            "Plug Power price target raised by analyst",
            "Nikola downgraded to sell",
            "Ballard Power Q3 earnings call transcript",
        ):
            with self.subTest(title=title):
                self.assertTrue(NOISE.search(title), f"NOISE missed: {title}")

    def test_real_stories_are_not_noise(self):
        """The noise filter must not eat the news."""
        for title in (
            "Centre awards 30 KTPA green hydrogen capacity to four refineries",
            "Marginal costs for hydrogen are falling",
            "NTPC commissions green hydrogen plant in Andhra Pradesh",
        ):
            with self.subTest(title=title):
                self.assertIsNone(NOISE.search(title))


class TestRegion(unittest.TestCase):
    """Region comes from the story, never from the publisher."""

    def test_india_signals(self):
        """Places, companies, institutions and currency all count."""
        for text in (
            "Centre awards 30 KTPA green hydrogen capacity under National Green Hydrogen Mission",
            "Haryana Govt set to introduce Green Hydrogen Policy",
            "NTPC commissions electrolyser at Pudimadaka",
            "Adani signs ammonia offtake worth 4,000 crore",
            "Green hydrogen plant announced in Tamil Nadu",
        ):
            with self.subTest(text=text):
                self.assertEqual(region_of(text), "india")

    def test_an_india_feed_does_not_make_a_story_indian(self):
        """Mercom India ran this UK story; the feed's region filed it wrong."""
        self.assertEqual(
            region_of("European Energy Secures $78 Million for UK Solar and "
                      "Battery Projects"),
            "global",
        )

    def test_global_stories(self):
        """No India signal means global, with no publisher tiebreak."""
        for text in (
            "Marginal costs for hydrogen are falling",
            "EU could pump green hydrogen through natural gas pipelines",
            "Sasol commissions Envision Energy to study green hydrogen project",
        ):
            with self.subTest(text=text):
                self.assertEqual(region_of(text), "global")


class TestDuplicates(unittest.TestCase):
    """Two wires filing one announcement do not write the same headline."""

    def test_same_announcement_from_two_wires(self):
        """The pair that filled two of three slots in a live dry run."""
        a = _sig("Centre awards 30 KTPA green hydrogen capacity to four oil "
                 "refineries under National Green Hydrogen Mission")
        b = _sig("Centre awards 30 KTPA green hydrogen capacity to four "
                 "refineries under National Green Hydrogen Mission")
        self.assertTrue(_is_duplicate(b, [a]))

    def test_reworded_coverage_of_one_event(self):
        """Different words, same event — the hydrogen-train pattern."""
        a = _sig("India's first hydrogen train completes trial run in Haryana")
        b = _sig("Indian Railways' first hydrogen train completes trial run")
        self.assertTrue(_is_duplicate(b, [a]))

    def test_two_companies_doing_the_same_thing_are_two_stories(self):
        """Shape is not identity. These share three words of four."""
        a = _sig("Adani commissions 5 GW electrolyser factory")
        b = _sig("Reliance commissions 5 GW electrolyser factory")
        self.assertFalse(_is_duplicate(b, [a]))

    def test_short_headlines_are_not_judged_by_overlap(self):
        """A three-word headline is a subset of half the feed."""
        a = _sig("Hydrogen prices fall")
        b = _sig("Green hydrogen prices fall sharply in Europe as "
                 "electrolyser costs drop")
        self.assertFalse(_is_duplicate(b, [a]))

    def test_unrelated_stories_are_kept(self):
        """The de-duplicator must not thin out a real day's news."""
        kept = [_sig("Centre awards 30 KTPA green hydrogen capacity to four refineries"),
                _sig("India's Prozeal starts construction of ultra-high-purity "
                     "green ammonia plant")]
        self.assertFalse(
            _is_duplicate(_sig("Marginal costs for hydrogen are falling"), kept))

    def test_empty_signature_is_never_a_duplicate(self):
        """A headline of nothing but stopwords must not swallow the next one."""
        self.assertFalse(_is_duplicate(_sig("It is the one"), [_sig("And so on")]))

    def test_exact_key_still_catches_verbatim_syndication(self):
        """Punctuation and case differ; the story does not."""
        self.assertEqual(
            _norm("Centre Awards 30 KTPA Green Hydrogen Capacity!"),
            _norm("centre awards 30 ktpa green hydrogen capacity"),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
