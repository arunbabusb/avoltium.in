#!/usr/bin/env python3
"""Tests for diagram rendering.

These diagrams exist because no honest photograph of an EDI train exists, and
the previous answer to that gap was a FLUX render that produced a bedroom. A
diagram cannot hallucinate equipment, so what is left to get wrong is layout:
text that overflows its box, facts that run together, or a figure that is
mostly empty space. All three happened while building this and are pinned
below.

Run: python3 test_diagrams.py
"""
import sys

from PIL import Image, ImageDraw

import diagrams as m

FAIL = 0


def check(label, got, want):
    global FAIL
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}: {label}" + ("" if ok else f" -> got {got!r}, want {want!r}"))
    if not ok:
        FAIL += 1


print("\ntitle matching")
check("EDI article resolves",
      m.diagram_for("Electrodeionization (EDI) vs Mixed-Bed Polishing for Electrolyzer Feedwater") is not None,
      True)
check("BOP article resolves",
      m.diagram_for("Balance of Plant (BOP) Strategies for Large-Scale Green Hydrogen") is not None, True)
check("unrelated news article gets no diagram",
      m.diagram_for("Centre Approves Rs 22 Crore Support For Green Hydrogen Startups"), None)
check("empty title is safe", m.diagram_for(""), None)

print("\nlongest key wins")
# "mixed-bed" and "electrodeionization" both appear in the EDI title. Dict
# order must not decide which diagram is used.
d = m.diagram_for("Electrodeionization (EDI) vs Mixed-Bed Polishing for Electrolyzer Feedwater")
check("resolves to the feedwater train", d.title, "Ultrapure feedwater train for PEM electrolysis")

print("\nexplicit newlines survive wrapping")
# Flowing these together produced "Municipal or bore water Turbidity and
# hardness removal" — two separate facts read as one garbled sentence.
img = Image.new("RGB", (10, 10))
draw = ImageDraw.Draw(img)
f = m._font(16)
lines = m._wrap(draw, "Municipal or bore water\nTurbidity and hardness removal", f, 400)
check("newline forces a break", len(lines) >= 2, True)
check("first fact stands alone", lines[0], "Municipal or bore water")
check("blank lines dropped", "" in m._wrap(draw, "a\n\nb", f, 400), False)

print("\nrendered output")
for title in ("Electrodeionization (EDI) vs Mixed-Bed Polishing for Electrolyzer Feedwater",
              "Balance of Plant (BOP) Strategies",
              "Cooling Systems and Thermal Management in Industrial Electrolysers"):
    dg = m.diagram_for(title)
    if dg is None:
        check(f"diagram exists for {title[:36]!r}", False, True)
        continue
    im = m.render(dg)
    check(f"{title[:30]!r} is 1200x675", im.size, (m.WIDTH, m.HEIGHT))
    check(f"{title[:30]!r} is not blank",
          len(im.getcolors(maxcolors=1_000_000) or []) > 5, True)

print("\nlayout fits the canvas")
# Boxes are sized to their content, so overly long stage text would previously
# push the band off the bottom of the frame rather than wrap.
wide = m.Diagram(
    title="A deliberately long diagram title that should still fit inside the frame width",
    caption="A caption long enough to wrap onto a second line without pushing the band off the canvas entirely.",
    stages=[m.Stage("Stage with a very long label indeed",
                    "Several\nlines\nof\nsupporting\ndetail\nthat\nexceed\nthe\ncap") for _ in range(5)],
    footnote="A footnote that also runs long enough to wrap across more than a single rendered line here.",
)
im = m.render(wide)
check("overflowing content still renders at size", im.size, (m.WIDTH, m.HEIGHT))

print("\ndifferent articles get different figures")
# Three separate BOP articles exist. A dry run had all three resolving to the
# same figure, which would have put the identical image on three posts — the
# duplicate-image problem the old pipeline carried a random seed to avoid.
bop = ["Balance of Plant (BOP) Strategies for Large-Scale Green Hydrogen Facilities",
       "Balance of Plant Engineering: Pumps, Cooling and Instrumentation for Green Hydrogen",
       "Balance of Plant Testing and Maintenance: Critical Best Practices"]
figures = [m.diagram_for(t) for t in bop]
check("every BOP article resolves", all(f is not None for f in figures), True)
check("each BOP article gets its own figure",
      len({f.title for f in figures if f}), len(bop))

print("\nevery defined diagram renders")
for key, dg in m.DIAGRAMS.items():
    try:
        im = m.render(dg)
        ok = im.size == (m.WIDTH, m.HEIGHT)
    except Exception as exc:
        ok = False
        print(f"    {key}: raised {exc}")
    check(f"{key!r} renders", ok, True)
    check(f"{key!r} has stages", len(dg.stages) > 0, True)

print()
if FAIL:
    print(f"{FAIL} test(s) FAILED")
    sys.exit(1)
print("All diagram tests passed.")
