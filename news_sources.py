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
#
# The investment-advice clauses were added after "Prediction: You Won't
# Recognize Plug Power in 2028. Should You Buy?" ranked top of the global
# list. It names a hydrogen company, so it scores like a hydrogen story, but
# there is no engineering in it to analyse — and rewriting a stock tip as
# plant analysis is the kind of thing that costs a technical publication its
# readers.
NOISE = re.compile(r"\b(webinar|podcast|subscribe|newsletter|photo of the day|"
                   r"jobs?|appointment|obituary|share price|stocks? to watch|"
                   r"should you buy|stocks?\s+to\s+(buy|own)|motley\s+fool|"
                   r"price\s+target|analyst\s+rating|buy\s+the\s+dip|"
                   r"(best|top)\s+\w+\s+stocks?|shares?\s+(jump|surge|plunge|soar|"
                   r"tumble|rally)|prediction:)\b", re.I)

# RELEVANT is a gate, not a ranking, and on its own it published the wrong
# things. A dry run picked three solar-financing items — a stake sale, a
# funding round, a rooftop rule change — while "Marginal costs for hydrogen
# are falling" sat unselected in the same pool. Nothing was broken: the list
# was sorted by publication time and sliced, so a story that cleared the gate
# an hour ago beat a better one that cleared it two hours ago.
#
# These are the beats the site actually covers, heaviest first. An item's
# score is the highest band it matches, so a hydrogen policy story is not
# penalised for failing to mention a compressor.
TOPIC_BANDS = [
    # The subject itself.
    (5, re.compile(r"\b(hydrogen|h2|electroly[sz]\w*|fuel[- ]cell|ammonia|"
                   r"methanol|green\s+steel|power[- ]to[- ]x)\b", re.I)),
    # Balance of plant — the engineering the reader is here for.
    (4, re.compile(r"\b(balance[- ]of[- ]plant|bop|compressor|rectifier|"
                   r"desalination|ultrapure|demineralis\w*|water\s+treatment|"
                   r"cooling|thermal\s+management|piping|valve|gasket|sealing|"
                   r"stack|membrane|bipolar|offtake|storage\s+tank)\b", re.I)),
    # Government policy. Union ministries and central schemes carry further
    # than a state announcement, but both are on-beat.
    (4, re.compile(r"\b(mnre|pib|niti\s+aayog|cabinet|union\s+ministry|ministry\s+of|"
                   r"central\s+government|government\s+of\s+india|sight\s+scheme|"
                   r"national\s+green\s+hydrogen\s+mission|pli|subsid\w+|incentive|"
                   r"polic\w+|scheme|tender|notification|guidelines|mandate|"
                   r"regulat\w+)\b", re.I)),
    # Standards and certification — small stories that change how plants are
    # built and sold.
    (3, re.compile(r"\b(iso|iec|astm|bis\b|standard\w*|certification|certifie[sd]|"
                   r"accreditat\w+|guarantee[s]?\s+of\s+origin|protocol|"
                   r"complian\w+|safety\s+code)\b", re.I)),
    # Company activity with something concrete behind it. Ranked below policy
    # because a funding round rarely changes a design decision.
    (2, re.compile(r"\b(commission\w+|awarded|contract|signs?|signed|mou|"
                   r"joint\s+venture|acquisition|acquires|electroly[sz]er\s+order|"
                   r"gigafactory|manufactur\w+|plant|facility|project)\b", re.I)),
]


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

    def topic_score(self) -> int:
        """The heaviest TOPIC_BANDS band this item matches, or 0.

        The title is weighted above the summary: feed summaries are often the
        publisher's boilerplate sign-off, and matching "policy" in a footer
        would promote a story that is not about one.
        """
        for weight, pattern in TOPIC_BANDS:
            if pattern.search(self.title):
                return weight
        for weight, pattern in TOPIC_BANDS:
            if pattern.search(self.summary):
                return max(weight - 1, 0)
        return 0

    def rank(self) -> float:
        """Sort key: what the story is about, with recency as the tiebreak.

        Age is divided by 24 so that within the 36-hour window it can only
        ever reorder items of the same band — a fresher compressor story beats
        a staler one, but no amount of freshness lifts a stake sale above a
        policy notification.
        """
        return self.topic_score() - self.age_hours() / 24


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


# Words that carry no signal about which story this is, so they are excluded
# before two headlines are compared.
_STOPWORDS = frozenset("""a an and are as at be by for from has have in into is it
its of on or that the to with will would after over amid new first""".split())


def _tokens(title: str) -> frozenset:
    """Significant lowercase words in a headline, for near-duplicate matching."""
    words = re.findall(r"[a-z0-9]+", title.lower())
    return frozenset(w for w in words if w not in _STOPWORDS and len(w) > 2)


def _is_near_duplicate(candidate: str, kept: List[frozenset],
                       threshold: float = 0.6) -> bool:
    """True when `candidate` retells a story already kept.

    Exact-title matching was not enough. The same PIB announcement reached the
    India list twice as "Centre awards 30 KTPA green hydrogen capacity to four
    oil refineries" (ANI) and "...to four refineries" (DD India) — different
    strings, so both survived, and both would have been written up as separate
    articles on the same morning. Jaccard overlap of the significant words
    catches the wire-copy rewrites that a string compare misses.
    """
    tokens = _tokens(candidate)
    if not tokens:
        return False
    for other in kept:
        union = tokens | other
        if union and len(tokens & other) / len(union) >= threshold:
            return True
    return False


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

    # Shared across both regions, not one set per region. The Google News
    # India and global queries return overlapping results — ranking put
    # "Centre awards 30 KTPA green hydrogen capacity to four oil refineries"
    # at the top of both lists at once, and a --count 3 run slices two from
    # India and one from global, so the same story would have been written up
    # and published twice on the same morning. India is cleaned first, so a
    # story carried by both stays in the India slot.
    seen: set[str] = set()
    kept_tokens: List[frozenset] = []

    def clean(items: List[NewsItem]) -> List[NewsItem]:
        """Drop stale, off-topic and duplicate items, best-matching first.

        De-duplication runs newest-first so that when two feeds carry the same
        story the surviving copy is the freshest one; the survivors are then
        ordered by rank(), which is what the caller slices.
        """
        out = []
        for i in sorted(items, key=lambda x: x.published, reverse=True):
            if i.age_hours() > max_age_hours:
                continue
            # The keyword gate, with one relief valve: a policy or standards
            # item scoring 3+ passes even without a RELEVANT keyword. "MNRE
            # notifies revised guidelines" names no technology and would
            # otherwise be dropped, and every feed here is already scoped to
            # the sector, so the story it refers to is a sector story.
            if not RELEVANT.search(f"{i.title} {i.summary}") and i.topic_score() < 3:
                continue
            if NOISE.search(i.title):
                continue
            k = _norm(i.title)
            if k in seen or _is_near_duplicate(i.title, kept_tokens):
                continue
            seen.add(k)
            kept_tokens.append(_tokens(i.title))
            out.append(i)
        return sorted(out, key=lambda x: x.rank(), reverse=True)

    return clean(india), clean(world), ok


if __name__ == "__main__":
    ind, glo, ok = collect()
    print(f"{ok} feed(s) answered\n")
    for label, items in (("INDIA", ind), ("GLOBAL", glo)):
        print(f"--- {label}: {len(items)} usable")
        for i in items[:6]:
            print(f"   [score {i.topic_score()} | {i.age_hours():4.0f}h] {i.title[:60]}")
            print(f"           {i.publisher} — {i.link[:72]}")
