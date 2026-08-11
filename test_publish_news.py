#!/usr/bin/env python3
"""Tests for the parts of the publisher that shape what readers see.

The slug cases are real. "Strain-Engineered Cu₃Pt Catalyst Cuts Platinum by
75% in Hydrogen Fuel Cell Cathodes" published to
.../strain-engineered-cu%e2%82%83pt-catalyst-... because WordPress keeps the
subscript verbatim. On a green hydrogen site that is not an edge case: H₂,
H₂O, CO₂ and NH₃ all carry one.
"""
from __future__ import annotations

import unittest

from publish_news import url_slug


class TestUrlSlug(unittest.TestCase):
    """Formulae belong in headlines; percent-encoding does not belong in URLs."""

    def test_subscripts_become_digits(self):
        """The case that actually published."""
        self.assertEqual(
            url_slug("Strain-Engineered Cu₃Pt Catalyst Cuts Platinum by 75%"),
            "strain-engineered-cu3pt-catalyst-cuts-platinum-by-75")

    def test_the_common_formulae(self):
        """These turn up in hydrogen headlines constantly."""
        self.assertEqual(url_slug("H₂ demand rises"), "h2-demand-rises")
        self.assertEqual(url_slug("CO₂ capture at the stack"), "co2-capture-at-the-stack")
        self.assertEqual(url_slug("NH₃ cracking pilot"), "nh3-cracking-pilot")
        self.assertEqual(url_slug("H₂O purity targets"), "h2o-purity-targets")

    def test_superscripts_too(self):
        """A/cm² is a normal unit in electrolysis copy."""
        self.assertEqual(url_slug("Current density hits 3 A/cm²"),
                         "current-density-hits-3-a-cm2")

    def test_typographic_punctuation(self):
        """Curly quotes and en dashes must not survive into the URL."""
        self.assertEqual(url_slug("India’s first plant — commissioned"),
                         "indias-first-plant-commissioned")

    def test_result_is_ascii_and_url_safe(self):
        """Nothing left that a browser would percent-encode."""
        s = url_slug("Cu₃Pt, H₂ & “green” steel — 75% less platinum!")
        self.assertTrue(s.isascii(), s)
        self.assertRegex(s, r"^[a-z0-9-]+$")
        self.assertFalse(s.startswith("-") or s.endswith("-"))

    def test_long_titles_are_trimmed_on_a_word_boundary(self):
        """Long headlines must not end mid-word or leave a trailing dash."""
        s = url_slug("Centre awards thirty kilotonnes per annum of green "
                     "hydrogen capacity to four public sector oil refineries "
                     "under the National Green Hydrogen Mission")
        self.assertLessEqual(len(s), 90)
        self.assertFalse(s.endswith("-"))
        self.assertTrue(s.split("-")[-1] in
                        "centre awards thirty kilotonnes per annum of green hydrogen "
                        "capacity to four public sector oil refineries under the "
                        "national mission".split())

    def test_plain_titles_are_unchanged(self):
        """The ordinary case must stay ordinary."""
        self.assertEqual(url_slug("Marginal costs for hydrogen are falling"),
                         "marginal-costs-for-hydrogen-are-falling")


if __name__ == "__main__":
    unittest.main(verbosity=2)
