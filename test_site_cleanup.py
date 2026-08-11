#!/usr/bin/env python3
"""Offline tests for the three repairs made after the AdSense rejection.

No network. Every case here is built from what was actually on the live site
on 11 August 2026, because the failures being tested for were all things that
looked correct in the code and wrong on the page.
"""
from __future__ import annotations

import unittest

import json
import os

import editorial_provenance
import fix_image_credits
import fix_internal_links
import prune_low_value
from publish_image_credits import clean_caption, credit_html


class TestCleanCaption(unittest.TestCase):
    """Recovering a name from whatever Wikimedia and WordPress did to it."""

    def test_escaped_anchor_becomes_a_name(self):
        """The exact string that rendered as markup on seven live pages."""
        raw = ("&lt;a href=&#8221;//commons.wikimedia.org/wiki/User:Kyy0602&#8243; "
               "title=&#8221;User:Kyy0602&#8243;&gt;Scarlett Kang&lt;/a&gt; "
               "/ CC BY-SA 4.0 via Wikimedia Commons")
        self.assertEqual(clean_caption(raw),
                         "Scarlett Kang / CC BY-SA 4.0 via Wikimedia Commons")

    def test_no_angle_brackets_survive(self):
        """Whatever comes out must never be able to look like a tag again."""
        raw = "&amp;lt;a href=&amp;#8221;x&amp;#8243;&amp;gt;Chris Allen&amp;lt;/a&amp;gt;"
        self.assertNotIn("<", clean_caption(raw))
        self.assertIn("Chris Allen", clean_caption(raw))

    def test_real_tags_are_stripped_too(self):
        """A caption that arrives as genuine HTML, not escaped HTML."""
        self.assertEqual(clean_caption('<a href="/u/x">H. Zell</a> / CC BY-SA 3.0'),
                         "H. Zell / CC BY-SA 3.0")

    def test_plain_text_is_left_alone(self):
        self.assertEqual(clean_caption("Government of India / GODL-India"),
                         "Government of India / GODL-India")

    def test_terminates_on_pathological_input(self):
        """Bounded loop: this must return, not hang."""
        self.assertIsInstance(clean_caption("&amp;" * 200), str)

    def test_credit_html_emits_no_visible_markup(self):
        """The regression that started all of this, asserted end to end."""
        raw = "&lt;a href=&#8221;x&#8243;&gt;Scarlett Kang&lt;/a&gt; / CC BY-SA 4.0"
        out = credit_html(raw, "")
        self.assertIn("Scarlett Kang", out)
        self.assertNotIn("&lt;a", out)
        self.assertNotIn("href=&#8221;", out)


class TestRepairCredits(unittest.TestCase):
    """Deciding what to do with a legacy credit block."""

    LEGACY = ('<div style="margin-top:30px;padding:10px;"><strong>Featured Image '
              'Credit:</strong> &lt;a href=&#8221;//commons.wikimedia.org/wiki/'
              'User:R&#8221;&gt;Rhododendrites&lt;/a&gt; / CC BY-SA 4.0 via '
              'Wikimedia Commons</div>')
    MODERN = ('<!-- avoltium:image-credit --><p class="image-credit"><small>'
              'Image: Port crane by Flocci Nivis, licensed under CC BY 4.0.'
              '</small></p><!-- /avoltium:image-credit -->')

    def test_untouched_when_there_is_nothing_to_fix(self):
        self.assertIsNone(fix_image_credits.repair("<p>An ordinary article.</p>"))

    def test_rewritten_as_text_when_it_is_the_only_credit(self):
        new, note = fix_image_credits.repair(f"<p>Body.</p>{self.LEGACY}")
        self.assertIn("Rhododendrites", new)
        self.assertNotIn("&lt;a", new)
        self.assertIn("avoltium:image-credit", new)
        self.assertIn("rewrote", note)

    def test_stale_block_removed_when_a_current_credit_exists(self):
        """The legacy line names a photograph that is no longer the featured
        image, so keeping it would credit the wrong photographer."""
        new, note = fix_image_credits.repair(f"<p>Body.</p>{self.LEGACY}{self.MODERN}")
        self.assertNotIn("Rhododendrites", new)
        self.assertIn("Flocci Nivis", new)
        self.assertIn("stale", note)

    def test_article_body_is_never_touched(self):
        body = "<p>Electrolyzer stacks degrade.</p>"
        new, _ = fix_image_credits.repair(body + self.LEGACY)
        self.assertIn("Electrolyzer stacks degrade.", new)


class TestResolveLinks(unittest.TestCase):
    """Matching a broken internal link back to a page that exists."""

    LIVE = {p: p for p in (
        "/electrolyzer-calculator/",
        "/water-consumption-treatment-calculator/",
        "/2026/07/22/batteries-and-hydrogen-competitors-or-partners/",
        "/2026/08/02/balance-of-plant-bop-strategies-for-large-scale-green-hydrogen-facilities-2/",
    )}

    def test_working_link_is_left_alone(self):
        self.assertIsNone(fix_internal_links.resolve("/electrolyzer-calculator/", self.LIVE))

    def test_dehyphenated_link_is_resolved(self):
        self.assertEqual(
            fix_internal_links.resolve(
                "/2026/07/22/batteriesandhydrogencompetitorsorpartners/", self.LIVE),
            "/2026/07/22/batteries-and-hydrogen-competitors-or-partners/")

    def test_wordpress_numeric_suffix_is_tolerated(self):
        """The link was written from the intended slug; WordPress published
        the post under a -2 because the slug was taken."""
        self.assertEqual(
            fix_internal_links.resolve(
                "/2026/08/02/balanceofplantbopstrategiesforlargescalegreenhydrogenfacilities/",
                self.LIVE),
            "/2026/08/02/balance-of-plant-bop-strategies-for-large-scale-green-hydrogen-facilities-2/")

    def test_suffix_tolerance_does_not_run_backwards(self):
        """/project-2/ and /project/ are two articles, not one."""
        self.assertIsNone(fix_internal_links.resolve("/project-2/", {"/project/": "/project/"}))

    def test_ambiguous_match_is_refused(self):
        """Two real slugs collapsing to one squashed key must resolve to
        neither, rather than to whichever the set happened to yield."""
        live = {"/a-b/": "/a-b/", "/ab/": "/ab/"}
        self.assertIsNone(fix_internal_links.resolve("/a-b-/", live))

    def test_unknown_link_is_not_guessed(self):
        self.assertIsNone(fix_internal_links.resolve("/nothing-like-this/", self.LIVE))

    def test_calculator_link_is_repaired_by_name(self):
        """No amount of hyphen removal turns the old slug into the real one,
        because the real one has a word the link never had."""
        body = ('<p>See our <a href="https://www.avoltium.in/water-consumption-calculator/"'
                ' style="color:#0056b3;">water treatment</a> tool.</p>')
        new, fixes = fix_internal_links.repair_body(body, self.LIVE)
        self.assertIn("/water-consumption-treatment-calculator/", new)
        self.assertEqual(len(fixes), 1)

    def test_external_links_are_untouched(self):
        body = '<p><a href="https://pib.gov.in/release/">PIB</a></p>'
        new, fixes = fix_internal_links.repair_body(body, self.LIVE)
        self.assertEqual(new, body)
        self.assertEqual(fixes, [])

    def test_surrounding_attributes_survive_the_rewrite(self):
        body = ('<a href="https://www.avoltium.in/water-consumption-calculator/" '
                'style="color:#0056b3; font-weight:bold;">Water Treatment</a>')
        new, _ = fix_internal_links.repair_body(body, self.LIVE)
        self.assertIn('style="color:#0056b3; font-weight:bold;"', new)
        self.assertIn(">Water Treatment</a>", new)


class TestPrunePlan(unittest.TestCase):
    """What the retire manifest resolves to against a live archive."""

    def _item(self, slug, status="publish", kind="post"):
        base = "https://www.avoltium.in"
        link = f"{base}/2026/07/17/{slug}/" if kind == "post" else f"{base}/{slug}/"
        return {"id": abs(hash(slug)) % 9999, "link": link, "status": status,
                "date": "2026-07-17T00:00:00", "title": {"rendered": slug}}

    def test_manifest_keeps_and_retires_are_disjoint(self):
        """A slug in both lists would retire the post meant to survive."""
        self.assertFalse(set(prune_low_value.TRAIN_KEEP) & set(prune_low_value.TRAIN_RETIRE))

    def test_every_retire_entry_has_a_stated_reason(self):
        for slug in prune_low_value.TRAIN_RETIRE + prune_low_value.DEMO_PAGES:
            self.assertIn(slug, prune_low_value.RETIRE_REASON)

    def test_keepers_are_never_targeted(self):
        posts = [self._item(s) for s in
                 prune_low_value.TRAIN_KEEP + prune_low_value.TRAIN_RETIRE]
        targets, _ = prune_low_value.plan(posts, [])
        hit = {t["slug"] for t in targets}
        self.assertEqual(hit, set(prune_low_value.TRAIN_RETIRE))
        for keeper in prune_low_value.TRAIN_KEEP:
            self.assertNotIn(keeper, hit)

    def _demo_pages(self, status="publish"):
        """The three theme pages, so a post-focused case reports only posts."""
        return [self._item(s, status=status, kind="page")
                for s in prune_low_value.DEMO_PAGES]

    def test_already_drafted_posts_are_not_touched_again(self):
        posts = [self._item(s, status="draft") for s in prune_low_value.TRAIN_RETIRE]
        targets, missing = prune_low_value.plan(posts, self._demo_pages(status="draft"))
        self.assertEqual(targets, [])
        self.assertEqual(missing, [])

    def test_a_slug_that_no_longer_exists_is_reported(self):
        """Silently doing ten of eleven things is how a cleanup half-happens."""
        posts = [self._item(s) for s in prune_low_value.TRAIN_RETIRE[:-1]]
        _, missing = prune_low_value.plan(posts, self._demo_pages())
        self.assertEqual(missing, [prune_low_value.TRAIN_RETIRE[-1]])

    def test_demo_pages_are_planned_against_the_pages_endpoint(self):
        pages = [self._item(s, kind="page") for s in prune_low_value.DEMO_PAGES]
        targets, _ = prune_low_value.plan([], pages)
        self.assertEqual(len(targets), len(prune_low_value.DEMO_PAGES))
        for t in targets:
            self.assertEqual(t["kind"], "page")
            self.assertIn("pages", t["endpoint"])

    def test_journal_entry_carries_what_restore_needs(self):
        """--restore replays these fields; missing one makes a run one-way."""
        targets, _ = prune_low_value.plan([self._item(prune_low_value.TRAIN_RETIRE[0])], [])
        for field in ("id", "endpoint", "status", "title"):
            self.assertIn(field, targets[0])
        self.assertEqual(targets[0]["status"], "publish")


class TestCitations(unittest.TestCase):
    """Rendering verified sources into the provenance block."""

    CITES = {
        "a-post": {
            "checked": "2026-08-11",
            "verified": "Rs 797.17 crore, 4 MTPA.",
            "note": "Source is dated 27 February 2026; this post ran 16 July 2026.",
            "sources": [{"title": "Centre clears Rs 797 crore jetty",
                         "url": "https://ddnews.gov.in/en/story/",
                         "publisher": "DD News", "date": "27 February 2026"}],
        },
    }

    def test_sources_render_with_publisher_and_date(self):
        """A citation is only checkable if you can see who published it, when."""
        out = editorial_provenance.sources_html("a-post", self.CITES)
        self.assertIn("https://ddnews.gov.in/en/story/", out)
        self.assertIn("DD News", out)
        self.assertIn("27 February 2026", out)

    def test_stale_dateline_note_is_surfaced(self):
        out = editorial_provenance.sources_html("a-post", self.CITES)
        self.assertIn("this post ran 16 July 2026", out)

    def test_post_without_citations_gets_no_sources_section(self):
        self.assertEqual(editorial_provenance.sources_html("other", self.CITES), "")

    def test_cited_post_does_not_disclaim_its_own_citations(self):
        """The generic note says these links cite nothing in particular. On a
        post that now carries real sources that reads as a disclaimer against
        them, so the wording has to change."""
        block = editorial_provenance.build_block(
            "T", "Arun", "Chief Engineer", "11 August 2026",
            slug="a-post", citations=self.CITES)
        self.assertIn("<h3>Sources</h3>", block)
        self.assertNotIn("These are not citations for individual statements", block)

    def test_uncited_post_keeps_the_honest_note(self):
        block = editorial_provenance.build_block(
            "T", "Arun", "Chief Engineer", "11 August 2026",
            slug="other", citations=self.CITES)
        self.assertNotIn("<h3>Sources</h3>", block)
        self.assertIn("These are not citations for individual statements", block)

    def test_urls_are_escaped(self):
        cites = {"p": {"sources": [{"title": 'X"onclick=', "url": 'https://e.com/"x',
                                    "publisher": "P", "date": "2026"}]}}
        out = editorial_provenance.sources_html("p", cites)
        self.assertNotIn('href="https://e.com/"x"', out)
        self.assertIn("&quot;", out)

    def test_a_broken_citations_file_does_not_break_the_run(self):
        """A bad JSON file must cost citations, not the byline on 51 posts."""
        self.assertEqual(editorial_provenance.load_citations("/nonexistent.json"), {})

    def test_readme_keys_are_not_treated_as_posts(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"_README": ["notes"], "real-slug": {"sources": []}}, fh)
            path = fh.name
        try:
            self.assertEqual(set(editorial_provenance.load_citations(path)), {"real-slug"})
        finally:
            os.unlink(path)


class TestShippedCitationsFile(unittest.TestCase):
    """The research artifact itself, checked as data."""

    @classmethod
    def setUpClass(cls):
        cls.data = editorial_provenance.load_citations("citations.json")

    def test_file_is_present_and_populated(self):
        self.assertGreater(len(self.data), 0)

    def test_every_entry_records_what_was_verified_and_when(self):
        """An entry without this is a URL someone guessed at."""
        for slug, entry in self.data.items():
            self.assertTrue(entry.get("verified"), f"{slug} records no verified claim")
            self.assertTrue(entry.get("checked"), f"{slug} records no check date")

    def test_every_source_is_complete_and_absolute(self):
        for slug, entry in self.data.items():
            self.assertTrue(entry.get("sources"), f"{slug} has no sources")
            for s in entry["sources"]:
                for field in ("title", "url", "publisher", "date"):
                    self.assertTrue(s.get(field), f"{slug}: source missing {field}")
                self.assertTrue(s["url"].startswith("https://"), f"{slug}: {s['url']}")

    def test_no_source_is_a_bare_landing_page(self):
        """The whole problem being fixed was citing institutional home pages.
        A citation has to point at the item, not at the publisher."""
        for slug, entry in self.data.items():
            for s in entry["sources"]:
                path = s["url"].split("//", 1)[1]
                self.assertIn("/", path.rstrip("/"),
                              f"{slug}: {s['url']} is a bare domain")


if __name__ == "__main__":
    unittest.main(verbosity=2)
