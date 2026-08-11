#!/usr/bin/env python3
"""Tests for the model fallback chain.

Written after reading the logs of a live publish run that reported success.
It had worked, but the shape of the work was wrong in three ways, and none of
them showed up as a failure:

  * OMNIROUTE_BASE_URL pointed at localhost:20128, which exists on a
    developer's machine and never on a GitHub runner. Every article paid nine
    connection refusals — three models times three retries — before falling
    back to Gemini and succeeding. The fallback hid it.
  * gemini-2.0-flash was first in the chain and failed instantly and
    non-retryably on all three articles, so every article wasted a call before
    reaching the model that answers.
  * Both a 404 and a 503 printed "exhausted", so a dead model name and a busy
    endpoint were indistinguishable in the output.

These pin the behaviour, since the failure mode here is a slower run that
still says "success".
"""
from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

import requests

import resilient


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status_code=200, payload=None):
        """Hold a status and the JSON body to hand back."""
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        """The decoded body."""
        return self._payload


GEMINI_OK = {"candidates": [{"content": {"parts": [{"text": "drafted"}]}}]}
OMNI_OK = {"choices": [{"message": {"content": "drafted"}}]}


class ChainTestCase(unittest.TestCase):
    """Shared plumbing: swap requests.request and reset module state."""

    def setUp(self):
        """Install a recording fake transport and clear the down-flag."""
        resilient._omniroute_down = False
        self.calls = []
        self._real = requests.request
        requests.request = self._dispatch
        # Backoff sleeps would make the suite take minutes.
        self._real_sleep = resilient.sleep_backoff
        resilient.sleep_backoff = lambda *a, **k: None

    def tearDown(self):
        """Put the real transport and sleep back."""
        requests.request = self._real
        resilient.sleep_backoff = self._real_sleep
        resilient._omniroute_down = False

    def _dispatch(self, method, url, **kwargs):
        """Route a fake request to whatever the test configured."""
        self.calls.append(url)
        return self.handler(url)

    def gateway_calls(self):
        """How many requests went to the OmniRoute gateway."""
        return sum("chat/completions" in u for u in self.calls)

    def gemini_calls(self):
        """How many requests went to Google directly."""
        return sum("generativelanguage" in u for u in self.calls)


class TestUnreachableGateway(ChainTestCase):
    """A gateway that is not listening must be abandoned, not retried."""

    def handler(self, url):
        """Refuse the gateway, answer Google."""
        if "chat/completions" in url:
            raise requests.ConnectionError("Connection refused")
        return FakeResponse(200, GEMINI_OK)

    def test_it_still_produces_text(self):
        """The fallback is the point; the article must still get written."""
        with redirect_stdout(io.StringIO()):
            text, model = resilient.generate_text(
                "k", "p", omniroute_base_url="http://localhost:20128/v1",
                omniroute_api_key="x")
        self.assertEqual(text, "drafted")
        self.assertEqual(model, "gemini-flash-latest")

    def test_it_gives_up_after_one_model_not_nine_attempts(self):
        """Nine refusals per article was forty seconds of nothing."""
        with redirect_stdout(io.StringIO()):
            resilient.generate_text("k", "p",
                                    omniroute_base_url="http://localhost:20128/v1",
                                    omniroute_api_key="x")
        self.assertEqual(self.gateway_calls(), 3,
                         "should stop after the first model's retries, not try all three")

    def test_later_articles_do_not_probe_it_again(self):
        """The gateway was down for the whole run, and stays down."""
        with redirect_stdout(io.StringIO()):
            for _ in range(4):
                resilient.generate_text("k", "p",
                                        omniroute_base_url="http://localhost:20128/v1",
                                        omniroute_api_key="x")
        self.assertEqual(self.gateway_calls(), 3,
                         "only the first article should pay for the discovery")
        self.assertEqual(self.gemini_calls(), 4)

    def test_it_says_so_once(self):
        """Silence would leave the misconfiguration invisible again."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            for _ in range(3):
                resilient.generate_text("k", "p",
                                        omniroute_base_url="http://localhost:20128/v1",
                                        omniroute_api_key="x")
        self.assertEqual(buf.getvalue().count("OmniRoute is unreachable"), 1)


class TestGatewayThatAnswers(ChainTestCase):
    """A gateway that answers and refuses is a different problem."""

    def handler(self, url):
        """Answer the gateway with 500, answer Google normally."""
        if "chat/completions" in url:
            return FakeResponse(500)
        return FakeResponse(200, GEMINI_OK)

    def test_a_refusing_gateway_is_retried_next_time(self):
        """500 is transient. Do not write the gateway off for the run."""
        with redirect_stdout(io.StringIO()):
            resilient.generate_text("k", "p", omniroute_base_url="http://gw/v1",
                                    omniroute_api_key="x")
            first = self.gateway_calls()
            resilient.generate_text("k", "p", omniroute_base_url="http://gw/v1",
                                    omniroute_api_key="x")
        self.assertFalse(resilient._omniroute_down)
        self.assertGreater(self.gateway_calls(), first,
                           "second article should try the gateway again")


class TestWorkingGateway(ChainTestCase):
    """When the gateway works it is used, and Google is not called."""

    def handler(self, url):
        """Answer the gateway successfully."""
        if "chat/completions" in url:
            return FakeResponse(200, OMNI_OK)
        return FakeResponse(200, GEMINI_OK)

    def test_gateway_is_preferred(self):
        """OmniRoute exists for its routing; use it when it is there."""
        with redirect_stdout(io.StringIO()):
            text, _ = resilient.generate_text("k", "p", omniroute_base_url="http://gw/v1",
                                              omniroute_api_key="x")
        self.assertEqual(text, "drafted")
        self.assertEqual(self.gemini_calls(), 0)


class TestUnconfigured(ChainTestCase):
    """No gateway configured must behave exactly as before it existed."""

    def handler(self, url):
        """Answer Google normally."""
        return FakeResponse(200, GEMINI_OK)

    def test_goes_straight_to_gemini(self):
        """An unconfigured run must not be affected by any of this."""
        with redirect_stdout(io.StringIO()):
            text, model = resilient.generate_text("k", "p")
        self.assertEqual(text, "drafted")
        self.assertEqual(self.gateway_calls(), 0)
        self.assertEqual(self.gemini_calls(), 1)


class TestDiagnosability(ChainTestCase):
    """A dead model and a busy one must not print the same thing."""

    def handler(self, url):
        """404 the first model, answer with the second."""
        if "gemini-flash-latest" in url:
            return FakeResponse(404)
        return FakeResponse(200, GEMINI_OK)

    def test_the_status_code_is_reported(self):
        """Without it, a bad model name reads as an unlucky afternoon."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            resilient.generate_text("k", "p")
        self.assertIn("HTTP 404", buf.getvalue())

    def test_the_chain_moves_on(self):
        """A dead model must not take the run down with it."""
        with redirect_stdout(io.StringIO()):
            text, model = resilient.generate_text("k", "p")
        self.assertEqual(text, "drafted")
        self.assertEqual(model, "gemini-2.0-flash")


class TestModelOrder(unittest.TestCase):
    """The model that answers should be tried first."""

    def test_working_model_leads(self):
        """gemini-flash-latest wrote every article in the live run."""
        self.assertEqual(resilient.DEFAULT_GEMINI_MODELS[0], "gemini-flash-latest")


if __name__ == "__main__":
    unittest.main(verbosity=2)
