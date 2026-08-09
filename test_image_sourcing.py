#!/usr/bin/env python3
"""Tests for image sourcing.

The bug these exist to prevent shipped to production: the featured image on
the Electrodeionization article was a photograph of a bed, because FLUX read
"mixed-bed ion exchange ... room" as a bedroom. QC passed it because a bed is
a file over 10 KB.

So the tests below are not about whether the HTTP calls work. They are about
whether a wrong image can still reach a published post.

Run: python3 test_image_sourcing.py    (exits non-zero on failure)
Live source checks run only with --live.
"""
import sys

import image_sourcing as m

FAIL = 0


def check(label, got, want):
    global FAIL
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}: {label}" + ("" if ok else f" -> got {got!r}, want {want!r}"))
    if not ok:
        FAIL += 1


print("\nthe bed must not pass the relevance gate")
edi = "Electrodeionization (EDI) vs Mixed-Bed Polishing for Electrolyzer Feedwater"
check("bedroom photo rejected",
      m.is_relevant(edi, "Hotel bedroom with double bed and side table"), False)
check("clean room water plant accepted",
      m.is_relevant(edi, "Electrodeionization module in ultrapure water plant"), True)

print("\nOpenverse's real junk results are rejected")
# These are genuine titles Openverse returns for these queries.
check("'Superheroes of our time' vs PEM electrolyzer",
      m.is_relevant("PEM electrolyzer", "Superheroes of our time"), False)
check("'Ecobus as Whiteman Park' vs hydrogen electrolysis plant",
      m.is_relevant("hydrogen electrolysis plant", "Ecobus as Whiteman Park"), False)
check("'Copper cathode' vs hydrogen electrolysis plant",
      m.is_relevant("hydrogen electrolysis plant", "Copper cathode"), False)
check("real match still accepted",
      m.is_relevant("industrial heat exchanger", "Disassembled chiller heat exchanger"), True)

print("\ngeneric words alone cannot satisfy the gate")
# Without stopwords, "industrial hydrogen plant" would match any "plant" photo
# — including a potted one.
check("'plant' alone is not a match",
      m.is_relevant("industrial hydrogen plant", "Potted plant on a windowsill"), False)
check("'system' alone is not a match",
      m.is_relevant("cooling system design", "Solar system model"), False)

print("\nlicence filtering")
for good in ("CC BY-SA 4.0", "CC BY 4.0", "Public domain", "CC0", "Attribution"):
    check(f"{good!r} allowed", m.licence_allowed(good), True)
for bad in ("CC BY-NC 4.0", "by-nc", "by-nc-nd", "All rights reserved", "GFDL"):
    check(f"{bad!r} refused", m.licence_allowed(bad), False)

print("\nattribution is rendered when the licence demands it")
share_alike = m.SourcedImage(url="u", width=2000, height=1200, title="Findlay Water Plant",
                             creator="Jane Doe", licence="CC BY-SA 4.0",
                             source="Wikimedia Commons", source_page="https://commons.example/x")
cc0 = m.SourcedImage(url="u", width=2000, height=1200, title="Something", creator="Anon",
                     licence="CC0", source="Wikimedia Commons", source_page="p")
check("CC BY-SA needs credit", share_alike.needs_credit, True)
check("CC0 needs no credit", cc0.needs_credit, False)
html_out = share_alike.attribution_html()
for needed in ("Jane Doe", "CC BY-SA 4.0", "Findlay Water Plant", "commons.example"):
    check(f"credit line contains {needed!r}", needed in html_out, True)
check("CC0 renders no credit line", cc0.attribution_html(), "")

print("\ncredit lines escape untrusted metadata")
# Creator and title come from a wiki anyone can edit.
nasty = m.SourcedImage(url="u", width=2000, height=1200,
                       title='<script>alert(1)</script>', creator='"><img src=x>',
                       licence="CC BY 4.0", source="Wikimedia Commons", source_page="p")
out = nasty.attribution_html()
check("no raw <script> in credit", "<script>" in out, False)
check("no raw injected <img> in credit", "<img src=x>" in out, False)

print("\nkeyword extraction")
check("stopwords dropped",
      m.keywords("The next of an industrial plant technology guide"), set())
check("hyphenated compounds stay whole",
      "bed" in m.keywords("mixed-bed polishing"), False)
check("hyphenated compound kept as one term",
      "mixed-bed" in m.keywords("mixed-bed polishing"), True)
check("technical terms kept",
      m.keywords("PEM electrolyzer stack"), {"pem", "electrolyzer", "stack"})

if "--live" in sys.argv:
    print("\nlive source checks")
    hit = m.find_image("hydrogen refuelling station")
    check("finds a real refuelling station photo", hit is not None, True)
    if hit:
        print(f"    -> {hit.source} {hit.width}x{hit.height} {hit.licence}: {hit.title[:50]}")
        check("meets minimum width", hit.width >= m.MIN_WIDTH, True)
        check("licence is commercially usable", m.licence_allowed(hit.licence), True)
    # No honest photograph exists for this; None is the correct answer and
    # tells the caller to draw a diagram.
    obscure = m.find_image("mixed-bed ion exchange polishing vessel resistivity loop")
    print(f"    obscure subject -> {'None (diagram needed)' if obscure is None else obscure.title[:50]}")
else:
    print("\n(skipping live source checks; pass --live to run them)")

print()
if FAIL:
    print(f"{FAIL} test(s) FAILED")
    sys.exit(1)
print("All image-sourcing tests passed.")
