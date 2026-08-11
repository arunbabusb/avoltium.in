#!/usr/bin/env python3
"""Real headlines from real feeds, split India / global, deduped.

This exists because of what the audit found: not one of the 49 published posts
recorded a source, and the news among them had been written from topic prompts.
A Google News RSS query for "green hydrogen India" returns "Haryana Govt set to
introduce Green Hydrogen Policy" — a headline this site already published as an
article — which shows the stories were real but the provenance was thrown away.

Every item here keeps the source title, publisher, link and timestamp, so an
article written from one can cite it. That is the only honest route to
citations: record them at the moment of writing.

Feeds were checked before being listed. PIB, Business Standard and Saur Energy
403 or 404 to an automated fetch and are omitted rather than left in to fail
silently at 3am.
"""
from __future__ import annotations

import re
import urllib.request
try:
    # Remote XML from feeds we do not control; defusedxml blocks the entity
    # expansion attacks the stdlib parser is still open to.
    from defusedxml import ElementTree as ET
except ImportError:  # pragma: no cover - falls back where it is not installed
    import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import List

USER_AGENT = ("Mozilla/5.0 (compatible; avoltium-newsbot/1.0; "
              "+https://www.avoltium.in)")

INDIA_FEEDS = [
    ("ET EnergyWorld — Renewable", "https://energy.economictimes.indiatimes.com/rss/renewable"),
    ("ET EnergyWorld — Power", "https://energy.economictimes.indiatimes.com/rss/power"),
    ("ET EnergyWorld — Oil & Gas", "https://energy.economictimes.indiatimes.com/rss/oil-and-gas"),
    ("Mercom India", "https://www.mercomindia.com/feed"),
    ("Google News — green hydrogen India",
     "https://news.google.com/rss/search?q=green+hydrogen+India&hl=en-IN&gl=IN&ceid=IN:en"),
]

GLOBAL_FEEDS = [
    ("Hydrogen Central", "https://hydrogen-central.com/feed/"),
    ("PV Magazine", "https://www.pv-magazine.com/feed/"),
    ("Energy Storage News", "https://www.energy-storage.news/feed/"),
    ("Offshore Energy", "https://www.offshore-energy.biz/feed/"),
    ("Google News — green hydrogen",
     "https://news.google.com/rss/search?q=green+hydrogen&hl=en-US&gl=US&ceid=US:en"),
]

# The site is about hydrogen production and the plant around it. A power-sector
# feed carries plenty that is not, so items have to earn their place.
RELEVANT = re.compile(
    r"\b(hydrogen|h2|electroly[sz]|electrolyser|electrolyzer|fuel[- ]cell|"
    r"ammonia|methanol|desalination|ultrapure|renewab|solar|wind|"
    r"green\s+steel|power[- ]to[- ]x|offtake|gigafactory)\b", re.I)

# Wire copy that is not a story about the sector.
NOISE = re.compile(r"\b(webinar|podcast|subscribe|newsletter|photo of the day|"
                   r"jobs?|appointment|obituary|share price|stocks? to watch)\b", re.I)


@dataclass
class NewsItem:
    """One item from a publisher's feed, normalised across feed formats."""
    title: str
    link: str
    publisher: str
    published: datetime
    summary: str
    region: str          # "india" | "global"

    def age_hours(self) -> float:
        """Hours since publication."""
        return (datetime.now(timezone.utc) - self.published).total_seconds() / 3600


def _text(el, *names) -> str:
    """The first non-empty child element among `names`, tags stripped."""
    for n in names:
        v = el.findtext(n)
        if v:
            return re.sub(r"<[^>]+>", "", v).strip()
    return ""


def _parse_date(raw: str) -> datetime | None:
    """Parsed timestamp, or None when the feed did not give a usable one.

    Falling back to "now" for an unparseable date was the wrong default: it
    makes an item of unknown age look like the freshest thing in the feed, and
    collect() would then hand a months-old story to the publisher as news.
    ISO-8601 is tried first because the dc:date fallback field uses it.
    """
    if not raw:
        return None
    try:
        d = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    try:
        d = parsedate_to_datetime(raw)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, IndexError):
        return None


def fetch_feed(name: str, url: str, region: str) -> List[NewsItem]:
    """Parse one RSS feed into items. Returns [] rather than raising."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        root = ET.fromstring(urllib.request.urlopen(req, timeout=40).read())
    except Exception:
        # A dead feed must not take the run down with it; the caller reports
        # how many sources answered.
        return []

    out = []
    for it in root.findall(".//item"):
        title = _text(it, "title")
        link = _text(it, "link")
        if not title or not link:
            continue
        # Google News wraps the publisher in the title as "Headline - Publisher".
        publisher = name
        m = re.match(r"^(.*)\s+-\s+([^-]{2,40})$", title)
        if "news.google.com" in url and m:
            title, publisher = m.group(1).strip(), m.group(2).strip()
        published = _parse_date(_text(it, "pubDate",
                                      "{http://purl.org/dc/elements/1.1/}date"))
        if published is None:
            # Unknown age is not the same as fresh; drop it rather than guess.
            continue
        out.append(NewsItem(
            title=title, link=link, publisher=publisher,
            published=published,
            summary=_text(it, "description")[:600],
            region=region,
        ))
    return out


def _norm(t: str) -> str:
    """Title reduced to bare alphanumerics, truncated — the de-duplication key."""
    return re.sub(r"[^a-z0-9]+", "", t.lower())[:60]


def collect(max_age_hours: int = 36) -> tuple[List[NewsItem], List[NewsItem], int]:
    """Fresh, on-topic, de-duplicated items. Returns (india, global, feeds_ok)."""
    india, world, ok = [], [], 0
    for region, feeds, bucket in (("india", INDIA_FEEDS, india),
                                  ("global", GLOBAL_FEEDS, world)):
        for name, url in feeds:
            items = fetch_feed(name, url, region)
            if items:
                ok += 1
            bucket.extend(items)

    def clean(items: List[NewsItem]) -> List[NewsItem]:
        """Drop stale, off-topic and duplicate items, newest first."""
        seen, out = set(), []
        for i in sorted(items, key=lambda x: x.published, reverse=True):
            if i.age_hours() > max_age_hours:
                continue
            if not RELEVANT.search(f"{i.title} {i.summary}"):
                continue
            if NOISE.search(i.title):
                continue
            k = _norm(i.title)
            if k in seen:
                continue
            seen.add(k)
            out.append(i)
        return out

    return clean(india), clean(world), ok


if __name__ == "__main__":
    ind, glo, ok = collect()
    print(f"{ok} feed(s) answered\n")
    for label, items in (("INDIA", ind), ("GLOBAL", glo)):
        print(f"--- {label}: {len(items)} usable")
        for i in items[:6]:
            print(f"   [{i.age_hours():4.0f}h] {i.title[:64]}")
            print(f"           {i.publisher} — {i.link[:72]}")
