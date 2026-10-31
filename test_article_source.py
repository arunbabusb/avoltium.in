#!/usr/bin/env python3
"""Offline tests for source resolution, excerpts and tags. No network."""
from __future__ import annotations

import base64
import json
import unittest
from unittest import mock

import article_source as a
import publish_news as p


class FakeResp:
    def __init__(self, status=200, text="", js=None, ctype="text/html"):
        self.status_code, self.text, self._js = status, text, js
        self.headers = {"Content-Type": ctype}

    def json(self):
        return self._js


class TestResolve(unittest.TestCase):
    def test_non_google_link_is_unchanged(self):
        url = "https://www.tribuneindia.com/news/x/"
        self.assertEqual(a.resolve_google_news(url), url)

    def test_legacy_id_decodes_without_network(self):
        raw = b"\x08\x13\x22\x1ehttps://example.com/story-123\xd2\x01\x00"
        aid = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        s = mock.Mock()
        got = a.resolve_google_news(f"https://news.google.com/rss/articles/{aid}?oc=5", s)
        self.assertEqual(got, "https://example.com/story-123")
        s.get.assert_not_called()

    def test_batchexecute_path(self):
        page = '<c-wiz><div data-n-a-sg="SIG123" data-n-a-ts="1730000000"></div>'
        inner = json.dumps(["garturlres", "https://renewablewatch.in/news/abc"])
        body = ")]}'\n\n" + json.dumps([["wrb.fr", "Fbv4je", inner]])
        s = mock.Mock()
        s.get.return_value = FakeResp(text=page)
        s.post.return_value = FakeResp(text=body)
        got = a.resolve_google_news("https://news.google.com/rss/articles/CBMiAU_yqLNew?oc=5", s)
        self.assertEqual(got, "https://renewablewatch.in/news/abc")
        sent = s.post.call_args.kwargs["data"]
        self.assertIn("SIG123", sent)
        self.assertIn("1730000000", sent)

    def test_unresolvable_returns_none(self):
        s = mock.Mock()
        s.get.return_value = FakeResp(status=404)
        self.assertIsNone(a.resolve_google_news(
            "https://news.google.com/rss/articles/CBMiAU_yqLNew", s))

    def test_google_url_in_response_is_rejected(self):
        inner = json.dumps(["garturlres", "https://news.google.com/x"])
        self.assertIsNone(a.parse_batchexecute("x\n\n" + json.dumps([["a", "b", inner]])))


class TestHeadlineEcho(unittest.TestCase):
    def test_google_style_summary_is_an_echo(self):
        self.assertTrue(a.is_headline_echo(
            "Kandla Port invites global firms to develop green hydrogen projects",
            "Kandla Port invites global firms to develop green hydrogen projects  Prop News Time",
            "Prop News Time"))

    def test_empty_summary_is_an_echo(self):
        self.assertTrue(a.is_headline_echo("Anything", "   "))

    def test_real_summary_is_not(self):
        self.assertFalse(a.is_headline_echo(
            "GSFC seeks JV partner",
            "The company plans to commission the Sikka facility by December 2030, "
            "targeting export markets in Europe, Japan and South Korea."))


class TestExtractText(unittest.TestCase):
    def test_keeps_article_paragraphs_drops_boilerplate(self):
        page = ("<nav><p>" + "Menu item text that is long enough to count " * 2 + "</p></nav>"
                "<article><p>Short byline</p><p>" + "Real reporting sentence. " * 5 +
                "</p><script>var x</script></article>")
        t = a.extract_text(page)
        self.assertIn("Real reporting sentence.", t)
        self.assertNotIn("Menu item", t)
        self.assertNotIn("Short byline", t)


class TestExcerpt(unittest.TestCase):
    BODY = ('<div style="x"><strong>In brief:</strong> Greenzo Energy has raised '
            'Rs 1.3 billion to expand its electrolyser manufacturing capacity, '
            'according to Renewable Watch. For plant engineers this can shorten '
            'procurement lead times considerably.</div><p>Body</p>')

    def test_uses_in_brief_and_respects_limit(self):
        e = p.make_excerpt(self.BODY)
        self.assertTrue(e.startswith("Greenzo Energy has raised"))
        self.assertLessEqual(len(e), 155)
        self.assertNotIn("<", e)

    def test_short_brief_is_unchanged(self):
        self.assertEqual(p.make_excerpt('<strong>In brief:</strong> Short one.</div>'),
                         "Short one.")


class TestTags(unittest.TestCase):
    def test_country_is_not_crowded_out(self):
        names = p.tag_names("India leads green hydrogen offtake",
                            "<p>PEM ammonia refinery pipeline policy fuel cell</p>")
        self.assertIn("India", names)

    def test_process_train_is_not_rail(self):
        names = p.tag_names("Offtake deals", "<p>two ammonia synthesis trains on track</p>")
        self.assertNotIn("hydrogen rail", names)

    def test_names_capped_at_five(self):
        names = p.tag_names("India PEM ammonia refinery pipeline policy in China",
                            "<p>green hydrogen fuel cell train storage</p>")
        self.assertEqual(len(names), 5)

    def test_existing_tag_reused_missing_tag_created(self):
        s = mock.Mock()

        def get(url, **kw):
            q = kw["params"]["search"]
            return FakeResp(js=[{"id": 48, "name": "India"}] if q == "India" else [])
        s.get.side_effect = get
        s.post.return_value = FakeResp(status=201, js={"id": 99})
        ids = p.tag_ids("India awards PEM order", "<p>body</p>", session=s)
        self.assertEqual(sorted(ids), [48, 99])
        created = [c.kwargs["json"]["name"] for c in s.post.call_args_list]
        self.assertEqual(created, ["PEM electrolyzer"])


class TestPickImage(unittest.TestCase):
    def _img(self, title, w=1600, h=900):
        return mock.Mock(title=title, width=w, height=h)

    def _item(self, title):
        return mock.Mock(title=title, summary="")

    def test_natural_hydrogen_gets_drilling_photo(self):
        rig = self._img("Drill rig-invergordon-12 hg.jpg")
        got = p.pick_image(self._item("Mantle8 to unlock natural hydrogen in Europe"),
                           search=lambda q: [rig] if q == "drilling rig" else [])
        self.assertIs(got, rig)

    def test_used_photo_is_skipped_for_a_fresh_one(self):
        old = self._img("Container-Terminal Bremerhaven 01.jpg")
        new = self._img("Port terminal at Kandla at dusk.jpg")
        got = p.pick_image(self._item("Kandla Port invites hydrogen bids"),
                           search=lambda q: [old, new],
                           used={p._image_key("Container-Terminal Bremerhaven 01")})
        self.assertIs(got, new)

    def test_article_subject_beats_broad_subject(self):
        steel = self._img("Steel plant blast furnace.jpg")
        elec = self._img("Electrolysis stack hall.jpg")
        got = p.pick_image(self._item("Green steel maker signs electrolyser deal"),
                           search=lambda q: [steel] if q == "steel plant" else [elec])
        self.assertIs(got, steel)

    def test_reuses_only_when_nothing_fresh(self):
        old = self._img("Wind farm offshore.jpg")
        got = p.pick_image(self._item("Offshore wind tender"),
                           search=lambda q: [old], used={p._image_key(old.title)})
        self.assertIs(got, old)

    def test_off_subject_and_portrait_hits_are_rejected(self):
        got = p.pick_image(self._item("Offshore wind tender"),
                           search=lambda q: [self._img("Monitor lizard.jpg"),
                                             self._img("Wind farm.jpg", 600, 900)])
        self.assertIsNone(got)

    def test_image_key_ignores_extension_and_case(self):
        self.assertEqual(p._image_key("Riyadh Skyline.JPG"), p._image_key("riyadh-skyline"))


class TestPrepareSource(unittest.TestCase):
    def _item(self, link, summary="x"):
        return mock.Mock(link=link, title="Title here", publisher="Pub", summary=summary)

    def test_unresolved_google_item_is_skipped(self):
        with mock.patch.object(a, "resolve_google_news", return_value=None):
            self.assertFalse(p.prepare_source(self._item("https://news.google.com/rss/articles/X")))

    def test_resolved_item_gets_publisher_link_and_text(self):
        item = self._item("https://news.google.com/rss/articles/X")
        with mock.patch.object(a, "resolve_google_news", return_value="https://pub.com/a"), \
             mock.patch.object(a, "fetch_article_text", return_value="t" * 800):
            self.assertTrue(p.prepare_source(item))
        self.assertEqual(item.link, "https://pub.com/a")
        self.assertEqual(len(item.summary), 800)

    def test_thin_item_is_skipped(self):
        item = self._item("https://pub.com/a", summary="Title here Pub")
        with mock.patch.object(a, "fetch_article_text", return_value=""):
            self.assertFalse(p.prepare_source(item))


if __name__ == "__main__":
    unittest.main(verbosity=2)
