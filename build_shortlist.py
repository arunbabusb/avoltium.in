#!/usr/bin/env python3
"""Propose featured images for existing posts using whole-article context.

Writes nothing to WordPress. It produces shortlist.json (for apply_shortlist.py)
and shortlist.html (a contact sheet to look at), so a person picks the image.

How the subject is chosen
-------------------------
backfill_images.py searches on the post title. Commons treats a full title as
a conjunction, so "Compressor Technologies for High-Pressure Green Hydrogen
Storage" matches twelve results and every one is a PDF of a research paper.

Here the subject comes from the body instead, ranked by tf-idf across the whole
corpus rather than raw frequency. Raw frequency does not work: "water treatment"
and "green hydrogen" appear in nearly every article on this site, so ranking by
count proposed the same waste-water photograph for eight unrelated posts. tf-idf
keeps what is distinctive to one article — "plate heat exchanger" for the
cooling piece, "wind turbines" for the offshore piece.

How a candidate is rejected
---------------------------
Two gates, because token overlap alone is far too weak. Measured on this
corpus, overlap-only accepted a monitor *lizard* for "Water Quality
Monitoring" and the foraminifera "Ammonia beccarii" for "Green Ammonia" —
"water monitor" and "ammonia" are real token matches.

  1. The file name must contain the phrase that was searched for, so the
     picture depicts the subject rather than sharing a stray word with it.
  2. At least half the file name's remaining words must also appear in the
     article body. The body is ~10k characters of domain vocabulary, which is
     what makes this test sharp: an industrial photograph's caption is largely
     words the article also uses, and a wildlife caption is not.

A JUNK pattern drops charts, maps, logos and scanned pages, which are common
on Commons and are never a featured photograph.

Even with all of that the subject is sometimes simply the wrong one for the
article, which is why the output is a shortlist and not an edit.

Usage:
    python3 build_shortlist.py                # all published posts
    python3 build_shortlist.py --limit 10
"""
from __future__ import annotations

import argparse
import collections
import html
import json
import logging
import math
import re
import sys

import image_sourcing
from backfill_images import session, POSTS_READ

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("shortlist")

STOP = set("""the a an and or of for to in on with by from as at is are be been this that these those
their its it we you they which who whose what when where how why not no than then so such can could
may might will would shall should must about into over under between across per via using used use
more most less least other another each both all any some many much very also however therefore thus
because while during before after above below within without through against among along around
engineering insight article table figure source note key takeaway summary conclusion introduction
process design operation cost costs data value values case study approach method sub
requires require required provides provide typical typically significant increase reduce reduction
one two three first second new news update year years india indian global market projects project""".split())

# A subject worth photographing names a physical thing. Without this the top
# tf-idf phrases are abstractions — "cost sensitivity", "market outlook" —
# which have no honest photograph and only produce stock-photo noise.
CONCRETE = set("""plant plants facility station stack stacks tank tanks vessel vessels pump pumps
valve valves pipe pipes piping compressor compressors exchanger tower towers membrane membranes
electrolyser electrolyzer electrolysis desalination osmosis filtration turbine turbines generator
substation transformer rectifier pipeline reactor column skid module modules cell cells
plate plates electrode electrodes catalyst separator dryer cooling condenser boiler
refinery terminal storage pipework instrumentation sensor sensors analyzer bearing seal gasket
solar panel wind""".split())

JUNK = re.compile(r"\b(chart|graph|diagram|map|logo|poster|flag|seal of|coat of arms|"
                  r"size of|share of|number of|statistic|infographic|screenshot|"
                  r"cover|title page|page \d|scan|portrait|signature|stamp|"
                  r"curve|plot|timeline|table)\b", re.I)

MIN_BODY_SUPPORT = 0.4
TOPN = 3


def toks(text: str) -> list[str]:
    """Lowercase word tokens, minus stop words and anything under three letters."""
    return [w for w in re.findall(r"[a-z][a-z0-9-]+", (text or "").lower())
            if len(w) > 2 and w not in STOP]


def bigrams(words: list[str]) -> list[str]:
    """Adjacent word pairs, the unit this scores relevance on.

    Single words are too ambiguous to search on — "cell" alone returns
    biology — so the shortlist works in two-word phrases throughout.
    """
    return [" ".join(words[i:i + 2]) for i in range(len(words) - 1)]


def fetch_posts(s, per_page: int = 100) -> list[dict]:
    """Every published post with title, body and current image, paginated."""
    out, page = [], 1
    while True:
        r = s.get(POSTS_READ, params={"per_page": per_page, "page": page,
                                      "_fields": "id,title,content,link,featured_media"},
                  timeout=60)
        if r.status_code != 200:
            break
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
    return out


def prepare(posts: list[dict]):
    """Tokenise the corpus and count in how many documents each bigram appears.

    Returns (docs, document-frequency counter, document count) — the three
    inputs tf-idf needs.
    """
    docs = []
    for p in posts:
        title = re.sub(r"<[^>]+>", "", p["title"]["rendered"])
        body = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p["content"]["rendered"]))
        words = toks(f"{title} {body}")
        docs.append({
            "id": p["id"], "title": html.unescape(title), "link": p.get("link", ""),
            "tokset": set(words), "counts": collections.Counter(bigrams(words)),
        })
    df = collections.Counter()
    for d in docs:
        for bg in set(d["counts"]):
            df[bg] += 1
    return docs, df, len(docs)


def subjects(doc: dict, df: collections.Counter, n_docs: int, k: int = 6) -> list[str]:
    """The `k` most distinctive concrete noun phrases in one document.

    Scored tf-idf, so a phrase that appears in every article on the site
    scores near zero however often this one repeats it. Phrases are kept only
    when one of the two words names something photographable; an abstraction
    produces a search query no image can satisfy.
    """
    scored = []
    for phrase, tf in doc["counts"].items():
        a, b = phrase.split()
        if not (a in CONCRETE or b in CONCRETE) or tf < 2:
            continue
        idf = math.log(n_docs / (1 + df[phrase]))
        if idf > 0:
            scored.append((tf * idf, phrase))
    scored.sort(reverse=True)
    return [p for _, p in scored[:k]]


def accepts(cand, query: str, doc: dict) -> bool:
    """Whether a candidate image is close enough to the article to offer.

    Two gates. The query has to appear in the candidate's own title, and
    enough of the remaining words in that title have to occur in the article
    body — the second is what rejects a correctly-named photograph of a
    different subject.
    """
    name = cand.title.lower()
    if JUNK.search(name):
        return False
    words = toks(name)
    if not words or query not in " ".join(words):
        return False
    support = len([w for w in words if w in doc["tokset"]]) / len(words)
    return support >= MIN_BODY_SUPPORT


def candidates_for(doc, df, n_docs, used: set) -> list[tuple]:
    """Up to TOPN unused candidates for one document, largest first.

    Search failures are logged and skipped rather than raised: one dead
    subject must not cost the other thirty-seven posts their shortlist.
    """
    found = []
    for query in subjects(doc, df, n_docs):
        try:
            pool = image_sourcing.search_wikimedia(query) + image_sourcing.search_openverse(query)
        except Exception as exc:
            logger.debug("search failed for %r: %s", query, exc)
            continue
        found += [(c, query) for c in pool
                  if c.url not in used and accepts(c, query, doc)]
        if len(found) >= TOPN:
            break
    found.sort(key=lambda x: x[0].width * x[0].height, reverse=True)
    return found[:TOPN]


def render_html(rows: list[dict], path: str) -> None:
    """Write the contact sheet — every candidate, clickable, with its licence.

    The point of the page is that a human sees the actual pictures before any
    of them go near the site. Filenames were trusted once and produced a
    street with a scooter on it under the caption "IISc hydrogen plant".
    """
    css = ("body{font:14px/1.45 system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem}"
           "img{width:230px;height:150px;object-fit:cover;border-radius:6px;background:#eee}"
           "figure{margin:0}.row{border-top:1px solid #ddd;padding:14px 0}"
           ".c{display:inline-block;width:240px;margin:0 12px 12px 0;vertical-align:top}"
           "small{color:#555;display:block}"
           # Selection UI. Clicking a picture is the whole interaction — hand
           # -editing approvals into a 70 KB JSON for 38 posts is not usable.
           ".c{cursor:pointer;border:3px solid transparent;border-radius:9px;padding:3px}"
           ".c.sel{border-color:#1a7f37;background:#eaf6ec}"
           ".skip{cursor:pointer;font-size:12px;color:#777;margin-left:4px}"
           "#bar{position:sticky;bottom:0;background:#fff;border-top:2px solid #333;"
           "padding:10px 0;margin-top:20px}"
           "textarea{width:100%;height:80px;font:12px ui-monospace,monospace}")
    out = ["<!doctype html><meta charset=utf-8><title>Image shortlist</title>",
           f"<style>{css}</style>",
           "<h1>Context-matched image shortlist</h1>",
           "<p><b>Click a picture to choose it for that article.</b> Click it again to "
           "unchoose. Anything you leave unchosen keeps the image it has now — skipping "
           "is a fine answer, and for a wrong-looking subject it is the right one. "
           "When you are done, copy the box at the bottom into "
           "<code>approvals.json</code> and run "
           "<code>python3 apply_shortlist.py --approvals approvals.json --execute</code>.</p>",
           "<p>Nothing here has been applied to the site.</p>"]
    for r in rows:
        out.append(f"<div class='row'><b>{html.escape(r['title'])}</b> "
                   f"<small>post {r['id']} · subjects: {html.escape(', '.join(r['subjects']))}</small>")
        if not r["candidates"]:
            out.append("<p><i>no defensible photo — leave the diagram or generated image</i></p>")
        for i, c in enumerate(r["candidates"]):
            out.append(
                f"<div class='c' data-post='{r['id']}' data-idx='{i}'>"
                f"<figure><img loading='lazy' src='{html.escape(c['url'])}' alt=''>"
                f"<figcaption><small><b>[{i}] {html.escape(c['query'])}</b>"
                f"{html.escape(c['title'][:70])}<br>{html.escape(c['licence'])} · {c['w']}x{c['h']}"
                f"<br><a href='{html.escape(c['page'])}' target='_blank' rel='noopener'>source</a>"
                f"</small></figcaption></figure></div>")
        out.append("</div>")
    hits = sum(1 for r in rows if r["candidates"])
    out.append(f"<p><b>{hits}/{len(rows)} posts have at least one candidate.</b></p>")
    out.append(
        "<div id=bar><b>Chosen: <span id=n>0</span></b>"
        " &nbsp;<button id=copy>Copy</button>"
        "<textarea id=outjson readonly>{}</textarea></div>"
        "<script>"
        "const sel={};"
        "document.querySelectorAll('.c').forEach(el=>el.addEventListener('click',e=>{"
        "  if(e.target.tagName==='A')return;"
        "  const p=el.dataset.post,i=+el.dataset.idx;"
        "  const on=sel[p]===i;"
        "  document.querySelectorAll(`.c[data-post='${p}']`).forEach(x=>x.classList.remove('sel'));"
        "  if(on){delete sel[p];}else{sel[p]=i;el.classList.add('sel');}"
        "  render();"
        "}));"
        "function render(){"
        "  document.getElementById('n').textContent=Object.keys(sel).length;"
        "  document.getElementById('outjson').value=JSON.stringify(sel,null,1);"
        "}"
        "document.getElementById('copy').addEventListener('click',()=>{"
        "  const t=document.getElementById('outjson');t.select();"
        "  try{document.execCommand('copy')}catch(e){}"
        "});"
        "render();"
        "</script>")
    with open(path, "w") as fh:
        fh.write("\n".join(out))


def main() -> int:
    """Build the shortlist and contact sheet. Writes nothing to WordPress."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--json", default="shortlist.json")
    ap.add_argument("--html", default="shortlist.html")
    args = ap.parse_args()

    s = session()
    posts = fetch_posts(s)
    logger.info("fetched %d posts", len(posts))
    docs, df, n_docs = prepare(posts)
    if args.limit:
        docs = docs[:args.limit]

    rows, used = [], set()
    for i, doc in enumerate(docs, 1):
        cands = candidates_for(doc, df, n_docs, used)
        if cands:
            used.add(cands[0][0].url)
        rows.append({
            "id": doc["id"], "title": doc["title"], "link": doc["link"],
            "subjects": subjects(doc, df, n_docs)[:4],
            "approved": None,
            "candidates": [{
                "url": c.url, "title": c.title, "licence": c.licence,
                "creator": c.creator, "source": c.source, "page": c.source_page,
                "w": c.width, "h": c.height, "query": q, "credit": c.needs_credit,
            } for c, q in cands],
        })
        logger.info("[%d/%d] %s — %d candidate(s)", i, len(docs), doc["title"][:56], len(cands))

    with open(args.json, "w") as fh:
        json.dump(rows, fh, indent=1)
    render_html(rows, args.html)
    hits = sum(1 for r in rows if r["candidates"])
    logger.info("%d/%d posts have candidates — review %s, then apply_shortlist.py",
                hits, len(rows), args.html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
