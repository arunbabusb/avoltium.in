#!/usr/bin/env python3
"""Turn a feed item into something an article can honestly be written from.

Three problems this exists to fix, all seen on the live site:

1. Google News RSS links are redirects (news.google.com/rss/articles/CBMi...),
   not the publisher's article. Every "Source" link on a published post pointed
   at Google rather than at the reporting it credits.
2. The Google News "summary" is just the headline and the publisher name, so
   the model was writing from the headline alone.
3. Excerpts were built from that summary, so they read "Headline Publisher".

resolve_google_news() recovers the publisher URL, fetch_article_text() pulls
the article body to write from, and is_headline_echo() spots a summary that
carries no information beyond the title.
"""
from __future__ import annotations

import base64
import html
import json
import logging
import re
import urllib.parse

import requests

logger = logging.getLogger("news")

USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_GN_HOST = "news.google.com"
_BATCH_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute"

# Below this many characters of article text there is nothing to analyse.
MIN_ARTICLE_CHARS = 600
# Enough for the model to work from without flooding the prompt.
MAX_ARTICLE_CHARS = 6000


def is_google_news(url: str) -> bool:
    """True for a news.google.com redirect link."""
    try:
        return urllib.parse.urlparse(url).netloc.endswith(_GN_HOST)
    except ValueError:
        return False


def _article_id(url: str) -> str | None:
    """The opaque CBMi... id from a Google News article URL."""
    path = urllib.parse.urlparse(url).path.split("/")
    for marker in ("articles", "read"):
        if marker in path:
            i = path.index(marker)
            if i + 1 < len(path) and path[i + 1]:
                return path[i + 1]
    return None


def _decode_legacy(article_id: str) -> str | None:
    """Old-format ids carry the URL inside the base64 payload itself."""
    try:
        raw = base64.urlsafe_b64decode(article_id + "=" * (-len(article_id) % 4))
    except (ValueError, TypeError):
        return None
    m = re.search(rb"https?://[\x21-\x7e]+", raw)
    if not m:
        return None
    url = m.group(0).decode("ascii", "ignore")
    # The new format starts with "AU_yqL" and holds no URL; anything left that
    # still points at Google is not the publisher.
    return None if _GN_HOST in url else url


def _decoding_params(article_id: str, session) -> tuple[str, str] | None:
    """Signature and timestamp Google embeds in the article page."""
    for path in (f"https://news.google.com/articles/{article_id}",
                 f"https://news.google.com/rss/articles/{article_id}"):
        try:
            r = session.get(path, timeout=30, headers={"User-Agent": USER_AGENT})
        except requests.RequestException:
            continue
        if r.status_code != 200:
            continue
        sg = re.search(r'data-n-a-sg="([^"]+)"', r.text)
        ts = re.search(r'data-n-a-ts="([^"]+)"', r.text)
        if sg and ts:
            return sg.group(1), ts.group(1)
    return None


def _batchexecute(article_id: str, signature: str, timestamp: str, session) -> str | None:
    """Ask Google's own decoder endpoint for the publisher URL."""
    inner = (
        '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,'
        'null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],'
        f'"{article_id}",{timestamp},"{signature}"]'
    )
    payload = [[["Fbv4je", inner, None, "generic"]]]
    try:
        r = session.post(
            _BATCH_URL, timeout=30,
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                     "User-Agent": USER_AGENT},
            data="f.req=" + urllib.parse.quote(json.dumps(payload)))
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    return parse_batchexecute(r.text)


def parse_batchexecute(text: str) -> str | None:
    """Pull the URL out of a batchexecute response body."""
    try:
        chunk = text.split("\n\n", 1)[1]
        data = json.loads(chunk)
        inner = json.loads(data[0][2])
        url = inner[1]
    except (IndexError, ValueError, TypeError, KeyError):
        m = re.search(r'\\"garturlres\\",\\"(https?://[^\\"]+)', text)
        url = m.group(1) if m else None
    if not url or _GN_HOST in url:
        return None
    return url


def resolve_google_news(url: str, session=None) -> str | None:
    """The publisher URL behind a Google News link, or None if it cannot be had.

    Non-Google links are returned unchanged. A None means the caller must not
    publish the item: a post that credits a publisher but links to Google is
    the failure this function exists to prevent.
    """
    if not is_google_news(url):
        return url
    article_id = _article_id(url)
    if not article_id:
        return None
    legacy = _decode_legacy(article_id)
    if legacy:
        return legacy
    s = session or requests.Session()
    params = _decoding_params(article_id, s)
    if not params:
        logger.warning("    could not read decoding params for %s", article_id[:24])
        return None
    return _batchexecute(article_id, params[0], params[1], s)


_DROP_BLOCKS = re.compile(
    r"<(script|style|noscript|nav|header|footer|aside|form|figure|svg)\b.*?</\1>",
    re.S | re.I)


def extract_text(page_html: str) -> str:
    """Readable paragraph text from an article page, boilerplate removed."""
    body = _DROP_BLOCKS.sub(" ", page_html)
    m = re.search(r"<article\b.*?</article>", body, re.S | re.I)
    if m:
        body = m.group(0)
    paras = []
    for p in re.findall(r"<p\b[^>]*>(.*?)</p>", body, re.S | re.I):
        t = html.unescape(re.sub(r"<[^>]+>", "", p))
        t = re.sub(r"\s+", " ", t).strip()
        # Short fragments are bylines, captions, share prompts and cookie text.
        if len(t) >= 60:
            paras.append(t)
    return "\n\n".join(paras)


def fetch_article_text(url: str, session=None) -> str:
    """The publisher's article text, trimmed; "" when it cannot be fetched."""
    s = session or requests.Session()
    try:
        r = s.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
    except requests.RequestException:
        return ""
    if r.status_code != 200 or "html" not in r.headers.get("Content-Type", "html"):
        return ""
    return extract_text(r.text)[:MAX_ARTICLE_CHARS]


def _words(t: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", html.unescape(t).lower())


def is_headline_echo(title: str, summary: str, publisher: str = "") -> bool:
    """True when the summary says nothing the headline does not.

    Google News descriptions are "<a>Headline</a>&nbsp;&nbsp;Publisher": strip
    the headline and the publisher and almost nothing is left.
    """
    if not summary.strip():
        return True
    title_w = set(_words(title)) | set(_words(publisher))
    rest = [w for w in _words(summary) if w not in title_w]
    return len(rest) < 8
