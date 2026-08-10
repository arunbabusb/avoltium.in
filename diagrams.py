#!/usr/bin/env python3
"""Draw accurate process diagrams for topics no honest photograph covers.

Why draw instead of search
--------------------------
image_sourcing.find_image returns None for subjects like an EDI polishing
train or a PEM stack cutaway, because no correctly-licensed photograph of one
exists. The previous pipeline answered that gap by asking FLUX for a
photorealistic render, which produced a bedroom for the mixed-bed article.

A diagram does not have that failure mode. It contains exactly the boxes we
put in it, in the order we put them, with the labels we wrote. It cannot
hallucinate equipment, and being ours it needs no licence and carries no
attribution. For a process article a correct schematic is also simply more
useful than any photo — a reader wants the train order and the conductivity
targets, not a picture of a grey vessel.

Rendering
---------
Drawn directly to PNG with Pillow. WordPress rejects SVG uploads by default
for security, and cairosvg is not installed, so PNG is the format that can
actually become a featured image. 1200x675 matches the 16:9 the theme already
uses.

Adding a diagram means adding a DIAGRAMS entry — a title, a caption and the
stages. Everything in it is asserted by whoever writes it, so the numbers must
come from the article, not from the renderer.
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 675

# Muted technical palette. Deliberately not the saturated blue-and-orange of
# stock infographics — this should read as a reference drawing.
BG = (247, 248, 250)
INK = (28, 34, 43)
MUTED = (104, 116, 132)
RULE = (206, 213, 222)
BOX_FILL = (255, 255, 255)
ACCENT = (10, 102, 148)
ACCENT_SOFT = (222, 236, 244)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = (["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"] if bold
             else ["DejaVuSans.ttf", "LiberationSans-Regular.ttf"])
    for name in names:
        for path in glob.glob(f"/usr/share/fonts/**/{name}", recursive=True):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    # Pillow's built-in bitmap font is unreadable at these sizes, but a poor
    # diagram still beats crashing the publish.
    return ImageFont.load_default()


@dataclass
class Stage:
    label: str
    detail: str = ""


@dataclass
class Diagram:
    title: str
    caption: str
    stages: List[Stage] = field(default_factory=list)
    footnote: str = ""
    # Arrows assert that one box leads to the next. That is true of a
    # feedwater train and false of a comparison: drawing AEL -> PEM -> SOEC
    # claims a progression between three alternatives that a reader is
    # supposed to choose between. Comparisons set this False.
    sequential: bool = True


@dataclass
class Layer:
    """One band in a cross-section, drawn to scale-ish thickness."""
    label: str
    detail: str = ""
    weight: int = 1          # relative thickness
    tint: tuple = (255, 255, 255)


@dataclass
class CrossSection:
    """A layered cutaway, for articles about what a cell is made of.

    The stage renderer draws a left-to-right process. A membrane electrode
    assembly is not a process — it is a sandwich, and the thing a reader needs
    is which layer sits against which, and how thick each is relative to its
    neighbours. Drawing that as five boxes with arrows between them would
    assert a flow that does not exist.
    """
    title: str
    caption: str
    layers: List[Layer] = field(default_factory=list)
    footnote: str = ""
    left_note: str = ""
    right_note: str = ""


def _wrap(draw, text, font, max_width) -> List[str]:
    """Word-wrap, honouring explicit newlines as hard breaks.

    Stage details hold separate facts on separate lines. Flowing them together
    reads as one garbled sentence — "Municipal or bore water Turbidity and
    hardness removal" — so a \\n has to stay a break rather than collapse into
    a space.
    """
    lines: List[str] = []
    for paragraph in (text or "").split("\n"):
        cur = ""
        for w in paragraph.split():
            trial = f"{cur} {w}".strip()
            if draw.textlength(trial, font=font) <= max_width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return [ln for ln in lines if ln]


def render(diagram: Diagram) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    d = ImageDraw.Draw(img)

    f_title = _font(38, bold=True)
    f_cap = _font(20)
    f_box = _font(21, bold=True)
    f_detail = _font(16)
    f_foot = _font(15)

    margin = 60
    # The title is one line by design. A long one used to run off the right
    # edge and get cropped by the canvas — "…repeat the solar cost curve"
    # lost its last two words — so step the size down until it fits.
    size = 38
    while size > 24 and d.textlength(diagram.title, font=f_title) > WIDTH - 2 * margin:
        size -= 2
        f_title = _font(size, bold=True)
    d.text((margin, 52 + (38 - size) // 2), diagram.title, font=f_title, fill=INK)

    y = 108
    for line in _wrap(d, diagram.caption, f_cap, WIDTH - 2 * margin)[:2]:
        d.text((margin, y), line, font=f_cap, fill=MUTED)
        y += 26

    d.line([(margin, y + 14), (WIDTH - margin, y + 14)], fill=RULE, width=2)

    n = len(diagram.stages)
    if n == 0:
        return img

    gap = 34
    total_gap = gap * (n - 1)
    box_w = (WIDTH - 2 * margin - total_gap) / n

    # Size the boxes to their content and centre the band in the space left
    # between the rule and the footnote. Stretching boxes to fill the frame
    # just moved the empty space inside them.
    LABEL_LH, DETAIL_LH, PAD_TOP, PAD_BOT, LABEL_GAP = 27, 21, 30, 26, 8

    # A label word longer than its box cannot be wrapped, so it used to be
    # drawn straight over the border — "Pre-commissioning" and
    # "Instrumentation" both spilled out in five-box diagrams. Shrink the
    # label font until the longest single word fits.
    longest = max((w for st in diagram.stages for w in st.label.split()),
                  key=lambda w: d.textlength(w, font=f_box), default="")
    # Track the size separately: the bitmap fallback from _font() does not
    # promise a .size attribute, and reading it would raise mid-render.
    box_size = 21
    while d.textlength(longest, font=f_box) > box_w - 28 and box_size > 15:
        box_size -= 1
        f_box = _font(box_size, bold=True)

    wrapped = []
    for stage in diagram.stages:
        lab = _wrap(d, stage.label, f_box, box_w - 28)[:3]
        det = _wrap(d, stage.detail, f_detail, box_w - 28)[:5] if stage.detail else []
        wrapped.append((lab, det))
    band_h = max(
        PAD_TOP + len(lab) * LABEL_LH + (LABEL_GAP + len(det) * DETAIL_LH if det else 0) + PAD_BOT
        for lab, det in wrapped
    )

    rule_y = y + 14
    foot_h = 44 if diagram.footnote else 0
    avail_top, avail_bot = rule_y + 30, HEIGHT - 18 - foot_h
    band_top = avail_top + max(0, (avail_bot - avail_top - band_h) / 2)

    for i, stage in enumerate(diagram.stages):
        lab, det = wrapped[i]
        x0 = margin + i * (box_w + gap)
        x1 = x0 + box_w
        d.rounded_rectangle([x0, band_top, x1, band_top + band_h],
                            radius=10, fill=BOX_FILL, outline=RULE, width=2)
        # Accent strip marks flow direction without needing a legend.
        d.rounded_rectangle([x0, band_top, x1, band_top + 7],
                            radius=3, fill=ACCENT)

        ty = band_top + PAD_TOP
        for line in lab:
            tw = d.textlength(line, font=f_box)
            d.text((x0 + (box_w - tw) / 2, ty), line, font=f_box, fill=INK)
            ty += LABEL_LH

        if det:
            ty += LABEL_GAP
            for line in det:
                tw = d.textlength(line, font=f_detail)
                d.text((x0 + (box_w - tw) / 2, ty), line, font=f_detail, fill=MUTED)
                ty += DETAIL_LH

        if diagram.sequential and i < n - 1:
            ax0 = x1 + 8
            ax1 = x1 + gap - 8
            ay = band_top + band_h / 2
            d.line([(ax0, ay), (ax1 - 5, ay)], fill=ACCENT, width=3)
            d.polygon([(ax1, ay), (ax1 - 11, ay - 7), (ax1 - 11, ay + 7)], fill=ACCENT)

    if diagram.footnote:
        fy = band_top + band_h + 34
        for line in _wrap(d, diagram.footnote, f_foot, WIDTH - 2 * margin)[:2]:
            d.text((margin, fy), line, font=f_foot, fill=MUTED)
            fy += 20

    d.rectangle([0, HEIGHT - 6, WIDTH, HEIGHT], fill=ACCENT_SOFT)
    return img


def render_cross_section(cs: CrossSection) -> Image.Image:
    """Draw a layered cutaway with the stack running left to right."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    d = ImageDraw.Draw(img)

    f_title = _font(38, bold=True)
    f_cap = _font(20)
    f_lab = _font(17, bold=True)
    f_det = _font(14)
    f_foot = _font(15)
    f_side = _font(16, bold=True)

    margin = 60
    size = 38
    while size > 24 and d.textlength(cs.title, font=f_title) > WIDTH - 2 * margin:
        size -= 2
        f_title = _font(size, bold=True)
    d.text((margin, 52 + (38 - size) // 2), cs.title, font=f_title, fill=INK)

    y = 108
    for line in _wrap(d, cs.caption, f_cap, WIDTH - 2 * margin)[:2]:
        d.text((margin, y), line, font=f_cap, fill=MUTED)
        y += 26
    d.line([(margin, y + 14), (WIDTH - margin, y + 14)], fill=RULE, width=2)

    if not cs.layers:
        return img

    # Bands run left-to-right; labels alternate above and below so adjacent
    # thin layers (a catalyst coat next to a membrane) do not collide. The
    # band has to start far enough down that a two-line label with a two-line
    # detail still clears the caption rule above it — at the first attempt the
    # "Cathode catalyst" label was drawn straight through the caption.
    rule_y = y + 14
    LEADER, MAX_LABEL_H = 14, 76
    top = rule_y + LEADER + MAX_LABEL_H + 16
    band_h = 150
    total_w = WIDTH - 2 * margin
    weights = sum(max(1, layer.weight) for layer in cs.layers)
    x = margin
    for i, layer in enumerate(cs.layers):
        w = total_w * max(1, layer.weight) / weights
        d.rectangle([x, top, x + w, top + band_h], fill=layer.tint, outline=RULE, width=2)

        above = i % 2 == 0
        cx = x + w / 2
        leader_y = top - 4 if above else top + band_h + 4
        tip_y = top - LEADER if above else top + band_h + LEADER
        d.line([(cx, leader_y), (cx, tip_y)], fill=RULE, width=2)

        lab = _wrap(d, layer.label, f_lab, max(w + 44, 120))[:2]
        det = _wrap(d, layer.detail, f_det, max(w + 44, 120))[:2] if layer.detail else []
        block_h = len(lab) * 20 + len(det) * 17
        ty = tip_y - block_h if above else tip_y
        for line in lab:
            tw = d.textlength(line, font=f_lab)
            d.text((cx - tw / 2, ty), line, font=f_lab, fill=INK)
            ty += 20
        for line in det:
            tw = d.textlength(line, font=f_det)
            d.text((cx - tw / 2, ty), line, font=f_det, fill=MUTED)
            ty += 17
        x += w

    # Electrode-side captions sit inside the outer faces, inset far enough not
    # to be clipped by the frame — right-aligning flush to the margin put
    # "H₂ out" half off the canvas.
    mid = top + band_h / 2
    INSET = 16
    if cs.left_note:
        d.text((margin + INSET, mid - 9), cs.left_note, font=f_side, fill=ACCENT)
    if cs.right_note:
        tw = d.textlength(cs.right_note, font=f_side)
        d.text((WIDTH - margin - INSET - tw, mid - 9), cs.right_note, font=f_side, fill=ACCENT)

    if cs.footnote:
        fy = HEIGHT - 58
        for line in _wrap(d, cs.footnote, f_foot, WIDTH - 2 * margin)[:2]:
            d.text((margin, fy), line, font=f_foot, fill=MUTED)
            fy += 20

    d.rectangle([0, HEIGHT - 6, WIDTH, HEIGHT], fill=ACCENT_SOFT)
    return img


# Cross-sections keyed the same way as DIAGRAMS. Every layer and figure is
# asserted by the articles these illustrate.
CROSS_SECTIONS: Dict[str, CrossSection] = {
    "pem electrolyzer": CrossSection(
        title="Inside a PEM electrolysis cell",
        caption="The membrane electrode assembly, anode on the left, cathode on the right.",
        left_note="O₂ out",
        right_note="H₂ out",
        layers=[
            Layer("Bipolar plate", "Titanium flow field", 3, (226, 232, 240)),
            Layer("Porous transport layer", "Sintered titanium", 2, (203, 213, 225)),
            Layer("Anode catalyst", "Iridium oxide", 1, (191, 219, 254)),
            Layer("PFSA membrane", "Proton conduction\nGas separation", 2, (255, 247, 214)),
            Layer("Cathode catalyst", "Platinum on carbon", 1, (187, 247, 208)),
            Layer("Porous transport layer", "Carbon paper", 2, (203, 213, 225)),
            Layer("Bipolar plate", "Flow field", 3, (226, 232, 240)),
        ],
        footnote="Band widths are relative, not to scale. The catalyst layers are the "
                 "thinnest and the most expensive part of the cell, and the two the "
                 "article's degradation section is about.",
    ),
    "bipolar plate": CrossSection(
        title="Where a bipolar plate sits, and what it has to survive",
        caption="The plate carries current and flow, and faces the harshest chemistry in the cell.",
        left_note="Anode side",
        right_note="Cathode side",
        layers=[
            Layer("Coating", "Passivation against\noxidation", 1, (254, 226, 226)),
            Layer("Substrate", "Titanium or coated\nstainless", 4, (226, 232, 240)),
            Layer("Flow field", "Machined or formed\nchannels", 3, (203, 213, 225)),
            Layer("Contact face", "Against the porous\ntransport layer", 2, (191, 219, 254)),
        ],
        footnote="Contact resistance at the plate interface and coating integrity set both "
                 "cell efficiency and how long the plate lasts under load cycling.",
    ),
}


def cross_section_for(title: str) -> Optional[CrossSection]:
    """Match an article title to a cross-section, longest key first."""
    t = (title or "").lower()
    for key in sorted(CROSS_SECTIONS, key=len, reverse=True):
        if key in t:
            return CROSS_SECTIONS[key]
    return None


# Diagrams keyed by a topic fragment matched case-insensitively against the
# article title. Every figure here is asserted by the article it illustrates;
# nothing is inferred by the renderer.
DIAGRAMS: Dict[str, Diagram] = {
    "mixed-bed": Diagram(
        title="Ultrapure feedwater train for PEM electrolysis",
        caption="Typical polishing sequence and the conductivity target at each stage.",
        stages=[
            Stage("Raw feed", "Municipal or bore water\nTurbidity and hardness removal"),
            Stage("Reverse osmosis", "Bulk ion rejection\n~95-99% of dissolved solids"),
            Stage("EDI", "Continuous electro-regeneration\nNo acid or caustic handling"),
            Stage("Mixed-bed polish", "Cation and anion resin\nFinal trace ion capture"),
            Stage("Stack feed", "Target >15 MΩ·cm\nContinuous resistivity monitoring"),
        ],
        footnote="EDI removes the regeneration chemistry a mixed bed needs; a polishing bed "
                 "downstream still guards the stack against resin bleed and EDI upset.",
    ),
    "electrodeionization": Diagram(
        title="Ultrapure feedwater train for PEM electrolysis",
        caption="Typical polishing sequence and the conductivity target at each stage.",
        stages=[
            Stage("Raw feed", "Municipal or bore water\nTurbidity and hardness removal"),
            Stage("Reverse osmosis", "Bulk ion rejection\n~95-99% of dissolved solids"),
            Stage("EDI", "Continuous electro-regeneration\nNo acid or caustic handling"),
            Stage("Mixed-bed polish", "Cation and anion resin\nFinal trace ion capture"),
            Stage("Stack feed", "Target >15 MΩ·cm\nContinuous resistivity monitoring"),
        ],
        footnote="EDI removes the regeneration chemistry a mixed bed needs; a polishing bed "
                 "downstream still guards the stack against resin bleed and EDI upset.",
    ),
    "balance of plant": Diagram(
        title="Balance of plant around the electrolyser island",
        caption="The systems outside the stack that determine plant availability.",
        stages=[
            Stage("Power conditioning", "Transformer and rectifier\nDC ripple control"),
            Stage("Water treatment", "RO, EDI and polishing\nFeed conductivity control"),
            Stage("Electrolyser island", "Stacks and process skids\nGas-liquid separation"),
            Stage("Gas processing", "Deoxygenation and drying\nPurity to specification"),
            Stage("Compression", "Storage or pipeline pressure\nBuffer management"),
        ],
        footnote="BOP typically dominates both installed cost and unplanned downtime, "
                 "which is why availability work rarely starts at the stack.",
    ),
    # Three separate BOP articles exist — strategies, pumps and
    # instrumentation, and testing and maintenance. Matching all of them to
    # one figure would put the identical image on three posts, which is the
    # duplicate-image problem the old pipeline carried a random seed to avoid.
    # More specific keys are checked first, so these win over "balance of plant".
    "pumps, cooling and instrumentation": Diagram(
        title="Pumps, cooling and instrumentation around the stack",
        caption="The rotating and measuring equipment an electrolyser island depends on.",
        stages=[
            Stage("Feedwater pumps", "Dosing and transfer duty\nNPSH margin at suction"),
            Stage("Circulation pumps", "Electrolyte or coolant loop\nSeal and material compatibility"),
            Stage("Control valves", "Flow and pressure regulation\nCv sizing to turndown"),
            Stage("Instrumentation", "Flow, pressure, temperature\nConductivity and gas purity"),
            Stage("Control system", "Interlocks and trips\nAlarm rationalisation"),
        ],
        footnote="Pump and valve selection sets the achievable turndown, which decides how "
                 "well the plant follows a variable renewable supply.",
    ),
    "testing and maintenance": Diagram(
        title="Balance of plant testing and maintenance cycle",
        caption="Commissioning through steady-state upkeep for an electrolyser plant.",
        stages=[
            Stage("Pre-commissioning", "Line flushing and cleanliness\nInstrument loop checks"),
            Stage("Functional testing", "Interlocks and trips\nControl loop tuning"),
            Stage("Performance test", "Output and purity against spec\nBaseline for later drift"),
            Stage("Planned maintenance", "Seals, filters and resin beds\nCalibration intervals"),
            Stage("Condition monitoring", "Vibration and leak detection\nTrend against baseline"),
        ],
        footnote="The performance test matters twice: once as acceptance, and again as the "
                 "baseline every later degradation measurement is compared against.",
    ),
    "thermal management": Diagram(
        title="Heat rejection path in an industrial electrolyser",
        caption="Where stack inefficiency ends up, and what removes it.",
        stages=[
            Stage("Stack losses", "Ohmic and overpotential heat\nRises with current density"),
            Stage("Process loop", "Deionised coolant\nStack outlet temperature control"),
            Stage("Heat exchanger", "Plate or shell-and-tube\nLoop isolation"),
            Stage("Rejection", "Cooling tower or dry cooler\nAmbient dependent"),
            Stage("Recovery", "Optional low-grade offtake\nDistrict or process heat"),
        ],
        footnote="Recovered heat is low grade. It is worth capturing only where an offtaker "
                 "sits close enough for the pipework to pay back.",
    ),
    # The six below cover articles whose subject is a comparison, a cost
    # structure or a shift in emphasis. None of them has an honest photograph:
    # a search for their subjects returns either abstractions or, in the worst
    # case, something actively misleading — "green hydrogen plant" on Commons
    # returns chlorophyll molecule renders. Every figure is taken from the
    # article it illustrates.
    "green hydrogen explained": Diagram(
        title="Three commercial electrolyser architectures",
        caption="How the mature routes differ where it matters for plant design.",
        stages=[
            Stage("Alkaline (AEL)", "KOH 20-30 wt%, nickel electrodes\n60-90 °C, up to 30 bar\n"
                                    "0.2-0.6 A/cm², slow to ramp"),
            Stage("PEM", "PFSA membrane, IrO₂ and Pt\n1.5-3.0 A/cm²\n"
                         "Sub-second ramp, 5-120% turndown"),
            Stage("Solid oxide (SOEC)", "Yttria-stabilised zirconia\n650-850 °C\n"
                                        "Trades electricity for heat"),
        ],
        footnote="Splitting water needs 33.3 kWh/kg H₂ on the lower heating value. Real "
                 "systems draw 48-65 kWh/kg once overpotentials, separation and rectification "
                 "are counted.",
        sequential=False,
    ),
    "lcoh": Diagram(
        title="What sets the levelised cost of hydrogen",
        caption="The five terms in the LCOH numerator, and the one that dominates.",
        stages=[
            Stage("Capital recovery", "CAPEX × capital recovery factor\nStack, power "
                                      "electronics, BoP"),
            Stage("Electricity", "Specific energy use × price\n65-85% of production cost"),
            Stage("Fixed O&M", "Annual operations\nIndependent of output"),
            Stage("Stack replacement", "Annualised set-aside\nDriven by degradation rate"),
            Stage("Feedwater", "Treatment to stack purity\nSmall but not zero"),
        ],
        footnote="Output scales as rated power × capacity factor × 8760 ÷ specific energy "
                 "consumption, so cheap intermittent power and high utilisation pull against "
                 "each other.",
    ),
    "degradation mitigation": Diagram(
        title="Where an electrolyser degrades, and what arrests it",
        caption="Three failure paths and the materials answer to each.",
        stages=[
            Stage("Anode catalyst", "Iridium dissolution\nPyrochlore-structured catalysts"),
            Stage("Porous transport layer", "Titanium oxidation\nALD-deposited coatings"),
            Stage("Membrane", "Radical attack on PFSA\nImmobilised radical scavengers"),
        ],
        footnote="The target is beyond 80,000 hours at 2.0-3.0 A/cm² under dynamic load "
                 "cycling, which no single one of these measures reaches alone.",
        sequential=False,
    ),
    "certification": Diagram(
        title="What a green hydrogen certificate has to prove",
        caption="Certification is continuous telemetry, not a post-audit paperwork step.",
        stages=[
            Stage("Renewable intake", "Power source and timing\nGrid coupling accounted"),
            Stage("Electrolyser", "Stack energy per kilogram\nDegradation tracked in service"),
            Stage("Water treatment", "Polishing energy included\nInside the system boundary"),
            Stage("Mass balance", "Metered production\nReconciled against inputs"),
            Stage("Certificate", "Issued against the record\nAuditable end to end"),
        ],
        footnote="India's National Green Hydrogen Mission caps lifecycle carbon intensity at "
                 "2.0 kg CO₂e per kg H₂, averaged over a rolling 12-month window.",
    ),
    "learning curve": Diagram(
        title="Why electrolysers will not repeat the solar cost curve",
        caption="Learning rates come from repeat-unit manufacturing, which a plant is not.",
        stages=[
            Stage("Solar PV", "~24% learning rate\nSolid-state modular product"),
            Stage("Li-ion cells", "Above 20% learning rate\nAutomated repeat-unit lines"),
            Stage("Electrolyser plant", "Electrochemical reactor plus\ndynamic chemical process"),
        ],
        footnote="The levers that remain are current-density intensification, power "
                 "electronics integration, and standardising the water treatment interface — "
                 "not assembly-line volume alone.",
        sequential=False,
    ),
    "pilot projects to commercial": Diagram(
        title="What changes between a megawatt pilot and a gigawatt plant",
        caption="The binding constraint moves off the stack.",
        stages=[
            Stage("Megawatt pilot", "Cell chemistry and stack\nefficiency dominate attention"),
            Stage("Water treatment", "High-recovery duty\nFeedstock at stack purity"),
            Stage("Thermal rejection", "Heat grows with capacity\nAmbient-limited"),
            Stage("Power conditioning", "Dynamic conversion\nRipple and ramp control"),
        ],
        footnote="Announced pipelines convert into operable assets on balance-of-plant "
                 "engineering, which is where utility-scale schedules are won or lost.",
    ),
}


def diagram_for(title: str) -> Optional[Diagram]:
    """Match an article title to a diagram, longest key first.

    Longest-first matters: "mixed-bed" and "electrodeionization" can both
    appear in one title and must not resolve by dict order.
    """
    t = (title or "").lower()
    for key in sorted(DIAGRAMS, key=len, reverse=True):
        if key in t:
            return DIAGRAMS[key]
    return None


def render_for_title(title: str, out_path: str) -> Optional[str]:
    diagram = diagram_for(title)
    if diagram is None:
        return None
    render(diagram).save(out_path, "PNG", optimize=True)
    return out_path


if __name__ == "__main__":
    import sys
    title = " ".join(sys.argv[1:]) or "Electrodeionization (EDI) vs Mixed-Bed Polishing"
    out = render_for_title(title, "diagram_preview.png")
    print(f"wrote {out}" if out else f"no diagram defined for {title!r}")
