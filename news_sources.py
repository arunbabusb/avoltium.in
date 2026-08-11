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

import html
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
# This is a green hydrogen publication, so a story has to be about hydrogen.
# The first version listed solar, wind and renewables as standalone
# alternatives, which is not a filter at all on feeds that are mostly solar
# trade press: a dry run picked "Philippines eases rules for own-use solar
# systems" and two solar financing stories, three for three.
CORE = re.compile(
    r"\b(hydrogen|h2|electroly[sz]\w*|electrolyser|electrolyzer|fuel[- ]cell|"
    r"ammonia|methanol|power[- ]to[- ]x|green\s+steel)\b", re.I)

# Only count when CORE is present too. "Solar" earns a place in a hydrogen
# story about solar-powered electrolysis; on its own it is somebody else's
# beat.
ADJACENT = re.compile(
    r"\b(desalination|ultrapure|offtake|gigafactory|renewab\w*|solar|wind)\b", re.I)


def is_relevant(title: str, summary: str = "") -> bool:
    """Whether an item belongs on a green hydrogen site.

    The hydrogen term has to be in the headline. Searching the summary as well
    sounds more generous and is actually the bug: "Ethanol, EVs must coexist in
    India's clean mobility transition" was selected for publication because its
    summary listed "ethanol, electric vehicles, hybrids, CNG and hydrogen". One
    mention among five fuels is not a hydrogen story, and an article written
    around it would have had nothing to say.

    Adjacent energy vocabulary rides along with a CORE term but never qualifies
    a story by itself.
    """
    return bool(CORE.search(title))


# Which country a story is about, which is not the same as which publication
# ran it. Mercom India carried "European Energy Secures $78 Million for UK
# Solar and Battery Projects", and taking the region from the feed filed a UK
# story under India.
INDIA_SIGNAL = re.compile(
    r"\b(india|indian|bharat|modi|centre|niti\s*aayog|sebi|ongc|bpcl|iocl|ntpc|"
    r"sail|gail|adani|reliance|jsw|greenko|acme|avaada|ohmium|"
    r"andhra|assam|bihar|delhi|gujarat|haryana|karnataka|kerala|madhya|"
    r"maharashtra|odisha|punjab|rajasthan|tamil\s*nadu|telangana|"
    r"uttar|bengal|ladakh|kandla|paradip|kochi|tuticorin|"
    r"crore|lakh|rupee|\u20b9)\b", re.I)


def region_of(text: str) -> str:
    """"india" or "global", decided by the story rather than the publisher.

    No fallback to the feed's own region. Letting an India-specific feed claim
    its unsignalled items is what filed "European Energy Secures $78 Million
    for UK Solar and Battery Projects" under India in the first place.
    """
    return "india" if INDIA_SIGNAL.search(text) else "global"

# Wire copy that is not a story about the sector.
# Investment commentary keeps arriving on the hydrogen feeds — a dry run
# picked "Prediction: You Won't Recognize Plug Power in 2028. Should You Buy
# the Stock?" from a syndicated stock-tip column. Plug Power is a hydrogen
# company, so the topic filter passes it; this is what says no. An
# engineering publication does not tell readers which shares to buy.
NOISE = re.compile(r"\b(webinar|podcast|subscribe|newsletter|photo of the day|"
                   r"jobs?|appointment|obituary|share price|stocks? to watch|"
                   r"should you buy|buy the stock|stock to buy|best stocks?|"
                   r"price target|analyst rating|upgraded to|downgraded to|"
                   r"motley fool|zacks|q[1-4] earnings|earnings call)\b", re.I)


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
    """The first non-empty child element among `names`, as plain text.

    Unescaped twice on purpose. Feeds routinely double-escape, so a headline
    arrives as "India&amp;#039;s" and one pass leaves "India&#039;s" — which
    is what would then be published, entity and all.
    """
    for n in names:
        v = el.findtext(n)
        if v:
            v = html.unescape(html.unescape(v))
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


def fetch_feed(name: str, url: str) -> List[NewsItem]:
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
        summary = _text(it, "description")[:600]
        out.append(NewsItem(
            title=title, link=link, publisher=publisher,
            published=published,
            summary=summary,
            region=region_of(f"{title} {summary}"),
        ))
    return out


def _norm(t: str) -> str:
    """Title reduced to bare alphanumerics, truncated — an exact-match key."""
    return re.sub(r"[^a-z0-9]+", "", t.lower())[:60]


# Words that carry no story identity, so two headlines about the same event
# are not judged similar merely for sharing them.
_DUP_STOP = frozenset("""
a an and are as at be by for from has have in is it its of on or that the to
with new news says said after over into up out first
""".split())


def _sig(t: str) -> frozenset:
    """The significant words of a headline, for comparing two stories."""
    return frozenset(w for w in re.findall(r"[a-z0-9]+", t.lower())
                     if len(w) > 2 and w not in _DUP_STOP)


# Two wires filing the same announcement do not write the same headline.
# "Centre awards 30 KTPA green hydrogen capacity to four oil refineries" and
# "...to four refineries" differ by one word, so an exact key kept both and a
# dry run selected the same government announcement twice out of three slots.
# Overlap, not equality, is what identifies a duplicate.
DUP_OVERLAP = 0.7

# Ratio alone is not enough on short headlines. "Adani commissions 5 GW
# electrolyser factory" and "Reliance commissions 5 GW electrolyser factory"
# share three words of four and score 0.75, but they are two companies and two
# stories. Below this many shared words a headline is too small to be judged
# by overlap, and only the exact key applies.
DUP_MIN_SHARED = 5


def _is_duplicate(sig: frozenset, kept: list) -> bool:
    """Whether this headline restates one already kept.

    Containment rather than Jaccard: a wire that adds detail produces a
    superset, and "A to four oil refineries" should still match the shorter
    "A to four refineries" even though the union has grown.
    """
    if len(sig) < DUP_MIN_SHARED:
        return False
    for other in kept:
        if len(other) < DUP_MIN_SHARED:
            continue
        shared = len(sig & other)
        if shared >= DUP_MIN_SHARED and shared / min(len(sig), len(other)) >= DUP_OVERLAP:
            return True
    return False


def collect(max_age_hours: int = 36) -> tuple[List[NewsItem], List[NewsItem], int]:
    """Fresh, on-topic, de-duplicated items. Returns (india, global, feeds_ok)."""
    india, world, ok = [], [], 0
    for name, url in INDIA_FEEDS + GLOBAL_FEEDS:
        items = fetch_feed(name, url)
        if items:
            ok += 1
        # File by what the story is about, not by who published it. The two
        # feed lists decide what gets fetched, nothing more.
        for item in items:
            (india if item.region == "india" else world).append(item)

    def clean(items: List[NewsItem]) -> List[NewsItem]:
        """Drop stale, off-topic and duplicate items, newest first."""
        seen, sigs, out = set(), [], []
        for i in sorted(items, key=lambda x: x.published, reverse=True):
            if i.age_hours() > max_age_hours:
                continue
            if not is_relevant(i.title, i.summary):
                continue
            if NOISE.search(i.title):
                continue
            k = _norm(i.title)
            if k in seen:
                continue
            sig = _sig(i.title)
            if _is_duplicate(sig, sigs):
                continue
            seen.add(k)
            sigs.append(sig)
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
