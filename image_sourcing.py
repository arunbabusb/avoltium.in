#!/usr/bin/env python3
"""Source real, correctly-licensed images instead of generating them.

Why this replaces Pollinations
------------------------------
The generated images were not merely generic, they were wrong. The featured
image on "Electrodeionization (EDI) vs Mixed-Bed Polishing for Electrolyzer
Feedwater" was a photograph of a bed in a room. The prompt was correct
engineering English:

    "electrodeionization EDI modules and mixed-bed ion exchange polishing
     vessels in ultrapure water treatment room, ..."

FLUX does not know "mixed-bed" is an ion-exchange term. It read "bed" and
"room" and rendered a bedroom. Nothing downstream caught it, because QC only
asked whether a file existed and exceeded 10 KB — a bed satisfies both.

For a technical hydrogen audience a wrong photograph is worse than no
photograph: an engineer who sees a bedroom on an EDI article concludes the
article is machine-written too, and stops reading.

What this module does instead
-----------------------------
Searches sources that return photographs of things that actually exist, and
refuses anything it cannot tie back to the article:

  1. Wikimedia Commons  — no key, CC/public domain, real industrial plant
                          photography. Best hit rate for generic subjects
                          (water treatment plants, heat exchangers).
  2. Openverse          — no key, wider CC pool including Flickr. Noisier:
                          a "PEM electrolyzer" query returns "Superheroes of
                          our time". Used only after Wikimedia, and only
                          through the same relevance gate.
  3. Pexels             — optional, needs PEXELS_API_KEY. High quality but
                          generic stock; no attribution required.

Where no real photograph exists — PEM stack cutaways, EDI train schematics —
callers should fall back to a generated diagram rather than settle for a
loosely related photo. `find_image` returning None is a normal outcome and
means "draw it instead", not "give up".

Licensing
---------
Every result carries the licence and the creator. CC BY and CC BY-SA require
visible credit, so `attribution_html` renders a caption line. Publishing a
CC BY-SA photo without it is a licence breach, not a style choice.
"""

from __future__ import annotations

import html
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import List, Optional

USER_AGENT = os.environ.get(
    "AVOLTIUM_UA",
    "avoltium-image-sourcing/1.0 (https://avoltium.in; green hydrogen editorial)",
)

# Wikimedia asks for a descriptive User-Agent and will throttle generic ones.
_HEADERS = {"User-Agent": USER_AGENT}

MIN_WIDTH = 1000
MIN_HEIGHT = 560
PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

# Words that carry no topical signal, so they must not be allowed to satisfy
# the relevance gate on their own. "industrial hydrogen plant" overlapping on
# "plant" alone is not a match.
STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "of", "in", "on", "to", "with", "vs",
    "versus", "at", "by", "from", "into", "how", "what", "why", "is", "are",
    "new", "next", "using", "use", "guide", "deep", "dive", "overview",
    "industrial", "professional", "photo", "photograph", "image", "system",
    "systems", "technology", "technologies", "plant", "project", "projects",
}

# Licences that permit commercial reuse. Anything else is skipped outright —
# a non-commercial photo on a site carrying advertising is a breach.
ALLOWED_LICENCES = {
    "cc0", "public domain", "pdm", "cc-zero",
    "cc by", "cc-by", "by",
    "cc by-sa", "cc-by-sa", "by-sa",
    "attribution", "attribution-sharealike",
}
# Licences requiring a visible credit line.
NEEDS_CREDIT = {"cc by", "cc-by", "by", "cc by-sa", "cc-by-sa", "by-sa",
                "attribution", "attribution-sharealike"}


@dataclass
class SourcedImage:
    """One candidate image and everything needed to credit and filter it."""
    url: str
    width: int
    height: int
    title: str
    creator: str
    licence: str
    source: str
    source_page: str

    @property
    def needs_credit(self) -> bool:
        """Whether the licence obliges a visible credit line."""
        return _licence_key(self.licence) in NEEDS_CREDIT

    def attribution_html(self) -> str:
        """Caption line. CC BY and BY-SA require this to be visible."""
        if not self.needs_credit:
            return ""
        creator = html.escape(self.creator or "Unknown")
        title = html.escape(self.title or "Image")
        page = html.escape(self.source_page or self.url)
        lic = html.escape(self.licence)
        return (
            f'<p class="image-credit"><small>Image: '
            f'<a href="{page}" rel="nofollow noopener" target="_blank">{title}</a> '
            f"by {creator}, licensed under {lic}.</small></p>"
        )


def _licence_key(lic: str) -> str:
    """Normalise a licence string to a comparable key, e.g. "cc by-sa"."""
    k = (lic or "").strip().lower()
    # Drop the version only when it is a separate word: "CC BY-SA 4.0" -> "cc by-sa".
    # Matching without requiring the space turned "cc0" into "cc" and silently
    # refused every public-domain image on Commons.
    k = re.sub(r"\s+\d+(\.\d+)?$", "", k)
    k = re.sub(r"^(cc\s+)", "cc ", k)
    return k.strip()


def licence_allowed(lic: str) -> bool:
    """Whether this licence permits use on the site at all."""
    return _licence_key(lic) in ALLOWED_LICENCES


def keywords(text: str) -> set:
    """Content-bearing lowercase words, stopwords and short tokens removed.

    Hyphenated technical compounds stay whole. This is the entire fix for the
    bedroom: splitting "mixed-bed" into "mixed" + "bed" lets a photograph of a
    bed share the token "bed" with an ion-exchange article and pass the
    relevance gate — which is how the wrong image got published in the first
    place. "mixed-bed" is one term and only matches "mixed-bed".
    """
    text = (text or "").lower()
    # Keep internal hyphens, drop everything else that is not alphanumeric.
    tokens = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text)
    return {t for t in tokens if len(t) > 2 and t not in STOPWORDS}


def is_relevant(query: str, candidate_text: str, min_overlap: int = 1) -> bool:
    """Require the candidate to share real topical vocabulary with the query.

    This is the gate that a bedroom fails. It also rejects Openverse's
    "Superheroes of our time" for a PEM electrolyzer query, which is a real
    result that source really returns.
    """
    q, c = keywords(query), keywords(candidate_text)
    return len(q & c) >= min_overlap


def _get_json(url: str, timeout: int = 45):
    """GET a URL and parse the JSON body."""
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _strip_tags(s: str) -> str:
    """Strip HTML tags from a metadata string."""
    return re.sub(r"<[^>]+>", "", s or "").strip()


def search_wikimedia(query: str, limit: int = 12) -> List[SourcedImage]:
    """Search Wikimedia Commons. Returns [] on any API failure."""
    url = (
        "https://commons.wikimedia.org/w/api.php?action=query&format=json"
        "&generator=search&gsrnamespace=6"
        f"&gsrsearch={urllib.parse.quote(query)}&gsrlimit={limit}"
        "&prop=imageinfo&iiprop=url|extmetadata|size|mime&iiurlwidth=1600"
    )
    try:
        data = _get_json(url)
    except Exception:
        return []

    results = []
    for page in (data.get("query", {}).get("pages") or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        title = page.get("title", "")
        # Commons search happily returns PDFs and scanned reports — a search
        # for "reverse osmosis" comes back as four research papers.
        if not (info.get("mime") or "").startswith("image/"):
            continue
        if not title.lower().endswith(PHOTO_EXTENSIONS):
            continue
        if (info.get("width") or 0) < MIN_WIDTH or (info.get("height") or 0) < MIN_HEIGHT:
            continue
        meta = info.get("extmetadata") or {}
        lic = (meta.get("LicenseShortName", {}) or {}).get("value", "")
        if not licence_allowed(lic):
            continue
        results.append(SourcedImage(
            url=info.get("thumburl") or info.get("url", ""),
            width=info.get("width", 0),
            height=info.get("height", 0),
            title=_strip_tags(title[5:]),  # strip the "File:" prefix
            creator=_strip_tags((meta.get("Artist", {}) or {}).get("value", "")) or "Wikimedia contributor",
            licence=lic,
            source="Wikimedia Commons",
            source_page=info.get("descriptionurl", ""),
        ))
    return results


def search_openverse(query: str, limit: int = 12) -> List[SourcedImage]:
    """Search Openverse. Returns [] on any API failure."""
    url = (
        "https://api.openverse.org/v1/images/"
        f"?q={urllib.parse.quote(query)}&page_size={limit}"
    )
    try:
        data = _get_json(url)
    except Exception:
        return []

    results = []
    for r in data.get("results", []):
        lic = r.get("license", "")
        if not licence_allowed(lic):
            continue
        if (r.get("width") or 0) < MIN_WIDTH or (r.get("height") or 0) < MIN_HEIGHT:
            continue
        results.append(SourcedImage(
            url=r.get("url", ""),
            width=r.get("width", 0),
            height=r.get("height", 0),
            title=r.get("title", "") or "",
            creator=r.get("creator", "") or "Unknown",
            licence=lic.upper() if len(lic) <= 6 else lic,
            source="Openverse",
            source_page=r.get("foreign_landing_url", "") or r.get("url", ""),
        ))
    return results


def search_pexels(query: str, limit: int = 10) -> List[SourcedImage]:
    """Optional. Requires PEXELS_API_KEY; returns [] when unset."""
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return []
    url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(query)}&per_page={limit}"
    req = urllib.request.Request(url, headers={**_HEADERS, "Authorization": key})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.load(resp)
    except Exception:
        return []

    results = []
    for p in data.get("photos", []):
        if (p.get("width") or 0) < MIN_WIDTH:
            continue
        results.append(SourcedImage(
            url=(p.get("src") or {}).get("large2x") or (p.get("src") or {}).get("large", ""),
            width=p.get("width", 0), height=p.get("height", 0),
            title=p.get("alt", "") or query,
            creator=p.get("photographer", "") or "Pexels",
            licence="Pexels licence",
            source="Pexels",
            source_page=p.get("url", ""),
        ))
    return results


def find_image(query: str, extra_context: str = "") -> Optional[SourcedImage]:
    """Best licensed photo for a topic, or None when nothing is defensible.

    Wikimedia first: it has the highest proportion of real plant photography
    and the cleanest licence metadata. Openverse and Pexels follow.

    None is a legitimate answer. Some subjects — a PEM stack cutaway, an EDI
    train schematic — have no honest photograph available, and the caller
    should draw a diagram rather than accept a vaguely industrial picture.
    """
    haystack = f"{query} {extra_context}".strip()
    for search in (search_wikimedia, search_openverse, search_pexels):
        try:
            candidates = search(query)
        except Exception:
            continue
        relevant = [c for c in candidates if is_relevant(haystack, f"{c.title} {c.creator}")]
        if relevant:
            # Largest wins: these are featured images, and upscaling is worse
            # than downscaling.
            return max(relevant, key=lambda c: c.width * c.height)
    return None


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "hydrogen refuelling station"
    img = find_image(q)
    if not img:
        print(f"no defensible image for {q!r} — draw a diagram instead")
    else:
        print(f"{img.source}: {img.width}x{img.height} {img.licence}")
        print(f"  {img.title}")
        print(f"  {img.url}")
        if img.needs_credit:
            print(f"  credit: {img.attribution_html()}")
