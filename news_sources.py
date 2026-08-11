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

# Identify honestly, with somewhere to complain to. The previous value called
# itself "avoltium-newsbot" and publishers behind bot filters answered 403 —
# the literal token "bot" is enough to trip them. Verified against
# hydrogenfuelnews.com: 403 as newsbot, 200 and 26 KB of valid XML as this.
#
# Deliberately not a browser string. These are public RSS feeds and reading
# them is what they are published for, so the fetcher says who it is and how
# to reach us rather than pretending to be Chrome.
USER_AGENT = "avoltium-news/1.0 (+https://www.avoltium.in; hello@avoltium.in)"

# Indian coverage. The general energy feeds carry hydrogen only occasionally —
# measured over one day they produced 50 fresh items and no hydrogen story at
# all — but they are the only Indian source besides Google News, and Indian
# policy stories do surface there, so they stay.
INDIA_FEEDS = [
    ("ET EnergyWorld — Renewable", "https://energy.economictimes.indiatimes.com/rss/renewable"),
    ("ET EnergyWorld — Oil & Gas", "https://energy.economictimes.indiatimes.com/rss/oil-and-gas"),
    ("Mercom India", "https://www.mercomindia.com/feed"),
    ("Google News — green hydrogen India",
     "https://news.google.com/rss/search?q=green+hydrogen+India&hl=en-IN&gl=IN&ceid=IN:en"),
]

# Global coverage, and the reason this list changed. It used to be PV
# Magazine, Energy Storage News and Offshore Energy: solar, battery and
# offshore-wind trade press, which between them produced 32 fresh items and
# zero hydrogen stories in a day, because they do not cover hydrogen. Every
# story the site published was therefore coming from the Google News search
# feed, whose links are JavaScript redirect stubs — eleven characters, nothing
# to read — and whose summaries run to about ninety.
#
# These four are hydrogen trade press. They carry the beat, they give real
# article links rather than redirects, and Hydrogen Central's summaries are
# three to four times longer than Google News's.
GLOBAL_FEEDS = [
    ("Fuel Cells Works", "https://fuelcellsworks.com/feed"),
    ("Hydrogen Central", "https://hydrogen-central.com/feed/"),
    ("Hydrogen Tech World", "https://hydrogentechworld.com/feed"),
    ("Hydrogen Fuel News", "https://www.hydrogenfuelnews.com/feed/"),
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
# Words that mean India whatever their case. Kept to terms with no ordinary
# English sense: place names, institutions, currency.
INDIA_SIGNAL = re.compile(
    r"\b(india|indian|bharat|modi|niti\s*aayog|"
    r"andhra|assam|bihar|gujarat|haryana|karnataka|kerala|madhya\s+pradesh|"
    r"maharashtra|odisha|punjab|rajasthan|tamil\s*nadu|telangana|"
    r"uttar\s+pradesh|west\s+bengal|ladakh|kandla|paradip|kochi|tuticorin|"
    r"crore|lakh|rupee|\u20b9)\b", re.I)

# Company and agency abbreviations, matched case-sensitively because several
# are also ordinary words. Case-insensitively, "sail" filed "Ships sail to
# Rotterdam with first ammonia cargo" under India, and "acme" did the same for
# "Acme Corporation of Ohio".
INDIA_ACRONYM = re.compile(
    r"\b(ONGC|BPCL|IOCL|NTPC|SAIL|GAIL|JSW|SEBI|NHPC|BHEL|IOC|"
    r"Adani|Reliance|Greenko|Avaada|Ohmium|ACME)\b")

# "Centre" means the union government in Indian headlines and a building
# everywhere else. "German MPs Visit THWS Hydrogen Centre" was filed as an
# Indian story on the strength of that one word, so it now has to be doing
# something a government does.
INDIA_CENTRE = re.compile(
    r"\bcentre\s+(awards?|approves?|notifies|clears?|sanctions?|announces?|"
    r"allocates?|plans?|launches?|invites?|extends?|mandates?)\b", re.I)

# Delhi is a city and a metonym for the government, but it is also a common
# dateline on wire copy about anywhere. It counts only alongside something else
# Indian, which the two patterns above already supply.


def region_of(text: str) -> str:
    """"india" or "global", decided by the story rather than the publisher.

    No fallback to the feed's own region. Letting an India-specific feed claim
    its unsignalled items is what filed "European Energy Secures $78 Million
    for UK Solar and Battery Projects" under India in the first place.
    """
    return "india" if (INDIA_SIGNAL.search(text) or INDIA_ACRONYM.search(text)
                       or INDIA_CENTRE.search(text)) else "global"

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


# is_relevant is a gate, not a ranking, and a gate alone published the wrong
# things. The survivors were sorted by publication time and sliced, so a story
# that cleared the gate an hour ago beat a better one that cleared it two hours
# ago — a dry run took three solar-financing items while "Marginal costs for
# hydrogen are falling" sat unselected in the same pool.
#
# These are the beats the site covers, heaviest first. An item scores the
# highest band it matches, so a policy story is not penalised for failing to
# mention a compressor.
TOPIC_BANDS = [
    # The subject itself.
    (5, CORE),
    # Balance of plant — the engineering the reader is here for.
    (4, re.compile(r"\b(balance[- ]of[- ]plant|compressor|rectifier|desalination|"
                   r"ultrapure|demineralis\w*|water\s+treatment|thermal\s+management|"
                   r"piping|valve|gasket|sealing|stack|membrane|bipolar|"
                   r"storage\s+tank)\b", re.I)),
    # Government action. A scheme or a tender changes what gets built.
    (4, re.compile(r"\b(mnre|pib|niti\s+aayog|cabinet|union\s+ministry|ministry\s+of|"
                   r"central\s+government|government\s+of\s+india|sight\s+scheme|"
                   r"national\s+green\s+hydrogen\s+mission|pli|subsid\w+|incentive|"
                   r"polic\w+|scheme|tender|notification|guidelines|mandate|"
                   r"regulat\w+)\b", re.I)),
    # Standards and certification — small stories that change how plants are
    # built and sold.
    (3, re.compile(r"\b(iso|iec|astm|bis|standard\w*|certification|certifie[sd]|"
                   r"accreditat\w+|guarantee[s]?\s+of\s+origin|protocol|"
                   r"complian\w+|safety\s+code)\b", re.I)),
    # Company activity with something concrete behind it. Below policy because
    # a funding round rarely changes a design decision.
    (2, re.compile(r"\b(commission\w+|awarded|contract|signs?|signed|mou|"
                   r"joint\s+venture|acquisition|acquires|offtake|gigafactory|"
                   r"manufactur\w+|plant|facility|project)\b", re.I)),
]


# A summary at least this long gives the model something to write from.
# Measured across a day's candidates: Google News summaries have a median of
# 91 characters and every article written from one that short was rejected as
# too thin; Hydrogen Central's run 291-365.
WRITABLE_SUMMARY = 200


# Google News does not put the publisher's article URL in its feed. `link` is
# a redirect through news.google.com whose payload is an opaque protobuf token
# — it carries no URL to decode, and resolving it needs a round trip through
# Google's own endpoint that a publishing run should not depend on.
#
# It went out as a citation anyway: the 11 August refinery-award post cites
# "The Tribune" and links 668 characters of news.google.com/rss/articles/CBMi…
# A reader cannot tell what that points at, and neither can a reviewer.
GOOGLE_NEWS = re.compile(r"^https?://(?:www\.)?news\.google\.com/", re.I)


@dataclass
class NewsItem:
    """One item from a publisher's feed, normalised across feed formats."""
    title: str
    link: str
    publisher: str
    published: datetime
    summary: str
    region: str          # "india" | "global"
    # The publisher's own site, from the feed's <source url>. Not the article,
    # but real and checkable, which the redirect is not.
    publisher_home: str = ""

    @property
    def citable_link(self) -> str:
        """The URL worth putting in front of a reader, or "" if there is none.

        A citation exists so a reader can check the claim. An opaque redirect
        fails that test, so it is not offered as one — the publisher's own
        site is, and where even that is missing the citation stays text.
        """
        if self.link and not GOOGLE_NEWS.match(self.link):
            return self.link
        return self.publisher_home or ""

    @property
    def links_to_article(self) -> bool:
        """Whether citable_link is the story itself rather than a home page."""
        return bool(self.link) and not GOOGLE_NEWS.match(self.link)

    def age_hours(self) -> float:
        """Hours since publication."""
        return (datetime.now(timezone.utc) - self.published).total_seconds() / 3600

    def topic_score(self) -> int:
        """The heaviest TOPIC_BANDS band this item matches, or 0.

        The title outweighs the summary: feed summaries often carry the
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
        """Sort key: the beat first, then whether it can be written, then age.

        The two adjustments are deliberately bounded so their combined swing
        (0.9) stays under the smallest gap between bands (1.0). That makes the
        band strictly dominant: no amount of freshness or detail lifts a stake
        sale above a tender. The previous version divided age by 24, which at
        36 hours was a penalty of 1.5 and could cross a band.

        The detail term exists because selection was picking Google News items
        over hydrogen trade press. Both scored band 5, the Google items were
        fresher, and their summaries are about ninety characters against three
        hundred — so the pipeline consistently chose the stories it had the
        least to write from, and the model then refused them as too thin.
        """
        freshness = -min(self.age_hours(), 72) / 144          # 0 to -0.5
        detail = 0.4 if len(self.summary) >= WRITABLE_SUMMARY else 0.0
        return self.topic_score() + freshness + detail


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
        # <source url="https://newsonair.gov.in">News On AIR</source>. The one
        # part of a Google News item that names a real, reachable publisher.
        src = it.find("source")
        publisher_home = (src.get("url") or "").strip() if src is not None else ""
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
            publisher_home=publisher_home,
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


# One quantity, several ways to write it. The same award was filed as
# "30,000-Tonne", "30,000 tonnes" and "30 KTPA" by three different wires in a
# single morning. Scaling the prefixed units to their base makes all three
# produce the token 30000, which is what lets the figure check see them as one
# story. Values are multipliers into tonnes.
#
# Mass only. Scaling power ratings too was tried and had to be removed: it
# turned "Adani commissions 5 GW electrolyser factory" and "Reliance
# commissions 5 GW electrolyser factory" into a shared 5000 and merged two
# companies into one story. Plant capacities cluster on round numbers that
# many unrelated projects share, so they identify nothing; an annual tonnage
# belongs to one award.
_UNIT_SCALE = {
    "ktpa": 1_000, "kt": 1_000, "kilotonne": 1_000, "kilotonnes": 1_000,
    "mtpa": 1_000_000, "mt": 1_000_000, "million": 1_000_000,
}
_QUANTITY = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*-?\s*(" + "|".join(sorted(_UNIT_SCALE, key=len, reverse=True)) + r")\b")


def _scale_units(t: str) -> str:
    """Rewrite prefixed quantities to their base figure.

    "30 ktpa" becomes "30000", so it matches a wire that wrote "30,000
    tonnes". The unit word is kept — it still carries meaning for the word
    overlap check, and dropping it would make "30 GW" and "30 kt" identical.
    """
    def sub(m: re.Match) -> str:
        """Replace one matched quantity with its scaled equivalent."""
        value = float(m.group(1)) * _UNIT_SCALE[m.group(2)]
        return f"{int(value)} {m.group(2)}"
    return _QUANTITY.sub(sub, t)


def _sig(t: str) -> frozenset:
    """The significant words of a headline, for comparing two stories.

    Digit group separators are removed first, so "30,000-Tonne" and "30,000
    tonnes" both yield the token "30000" rather than the useless "000".
    """
    t = re.sub(r"(?<=\d)[,\s](?=\d)", "", t.lower())
    t = _scale_units(t)
    return frozenset(w for w in re.findall(r"[a-z0-9]+", t)
                     if len(w) > 2 and w not in _DUP_STOP)


def _figures(sig: frozenset) -> frozenset:
    """The distinctive quantities in a headline.

    Four digits and up, because that is where numbers stop being round. Two
    unrelated plants are both plausibly "600 MW"; two reports of "30,000
    tonnes" inside the same day are one award. Years are excluded even though
    they clear the length test — half the sector's headlines mention 2030.
    """
    return frozenset(w for w in sig
                     if w.isdigit() and len(w) >= 4 and not (1900 <= int(w) <= 2100))


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

# Word overlap only catches a rewrite that reuses the wording. It does not
# catch a genuine paraphrase: "India Awards 30,000-Tonne Green Hydrogen Supply
# Contracts" and "Indian oil companies to consume 30,000 tonnes of green
# hydrogen a year" are one announcement sharing three words, and both were
# selected in a live dry run. What they do share is the figure. A quantity
# this specific, reported twice inside the same 36-hour window with any topical
# words in common, is one story told twice.
#
# Deliberately biased toward dropping. A false positive costs one article that
# day; a false negative puts two versions of the same story on the site, which
# is what produced the eleven near-identical hydrogen-train posts already
# published.
DUP_FIGURE_SUPPORT = 2


def _is_duplicate(sig: frozenset, kept: list) -> bool:
    """Whether this headline restates one already kept.

    Two independent signals, because they fail on different things: word
    overlap catches wire rewrites and misses paraphrases, and a shared figure
    catches paraphrases of anything with a number in it.
    """
    figures = _figures(sig)
    for other in kept:
        shared = len(sig & other)
        # Containment rather than Jaccard: a wire that adds detail produces a
        # superset, and "A to four oil refineries" should still match the
        # shorter "A to four refineries" even though the union has grown.
        if (len(sig) >= DUP_MIN_SHARED and len(other) >= DUP_MIN_SHARED
                and shared >= DUP_MIN_SHARED
                and shared / min(len(sig), len(other)) >= DUP_OVERLAP):
            return True
        common_figures = figures & _figures(other)
        if common_figures and shared - len(common_figures) >= DUP_FIGURE_SUPPORT:
            return True
    return False


class SeenStories:
    """Stories already covered, so a later run does not retell one.

    collect() de-duplicates within a single run. This is the other half of the
    memory, for the caller that knows what is already published: a story picked
    up again the next morning under a reworded headline is a new string and
    would otherwise sail straight through.
    """

    def __init__(self, titles=()):
        """Seed from titles already covered, in any order."""
        self._keys = set()
        self._sigs = []
        for t in titles:
            self.add(t)

    def add(self, title: str) -> None:
        """Record one title as covered."""
        self._keys.add(_norm(title))
        self._sigs.append(_sig(title))

    def covers(self, title: str) -> bool:
        """Whether this headline retells something already recorded."""
        return _norm(title) in self._keys or _is_duplicate(_sig(title), self._sigs)


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

    # One set of duplicate state across both regions, not one per region. A
    # story reported with an India signal and again without one lands in
    # different buckets, and a --count 3 run slices two from India and one from
    # global — so the same announcement gets written up twice in one morning.
    # India is cleaned first, so a story carried by both keeps the India slot.
    seen: set[str] = set()
    sigs: List[frozenset] = []

    def clean(items: List[NewsItem]) -> List[NewsItem]:
        """Drop stale, off-topic and duplicate items, best first.

        De-duplication runs newest-first, so when two wires carry one story the
        surviving copy is the freshest. The survivors are then ordered by
        rank(), which is what the caller slices.
        """
        out = []
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
