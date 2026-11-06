"""Two pages added to docs/figures/cirp-figures.drawio (6 Nov), the others left byte for byte:

- pipeline-planning: Fig. 1 (the page "pipeline") with the planning spelled out: Match and plan, a Plan
  card with its four steps, the capabilities that feed it, a planned skill S' with a parallel block;
- planned-bottom-up: how the planner makes BottomUpFilling for the syringe from the module's primitives
  (one column, 440 px = 8.4 cm, no text below 12 px), the needle rising with the liquid in time.

    python planning_pages.py <cirp-figures.drawio>      # replaces the two pages if they are there
"""
import copy
import math
import re
import sys
import xml.etree.ElementTree as ET

PATH = sys.argv[1]
INK, GREY, LINE = "#252B2D", "#6E777B", "#8F989D"
GREEN, RUN = "#5B963B", "#E3F1DA"
PINK, PINK_LINE = "#F6DDD6", "#C47A68"
BLUE, BLUE_FILL = "#6C91B2", "#E1EAF2"
FB, FB_LINE = "#EEF3F7", "#7D93A6"
PURPLE, PURPLE_FILL = "#9080B7", "#EEEAF5"
AAS = "#2A918B"
GOLD = "#B88A1C"


# ---- cells ------------------------------------------------------------------------------------------
class Page:
    def __init__(self, name, width, height):
        self.diagram = ET.Element("diagram", id=f"{name}-0", name=name)
        self.model = ET.SubElement(self.diagram, "mxGraphModel", dx=str(width), dy=str(height), grid="0", gridSize="10",
                                   guides="1", tooltips="1", connect="1", arrows="1", fold="1", page="1", pageScale="1",
                                   pageWidth=str(width), pageHeight=str(height), background="#FFFFFF", math="0", shadow="0")
        self.root = ET.SubElement(self.model, "root")
        ET.SubElement(self.root, "mxCell", id="0")
        ET.SubElement(self.root, "mxCell", id="1", value="Figure", parent="0")
        self.n = 0

    def id(self):
        self.n += 1
        return f"b{self.n}"

    def vertex(self, x, y, w, h, value, style, parent="1"):
        c = ET.SubElement(self.root, "mxCell", id=self.id(), value=value, style=style, vertex="1", parent=parent)
        ET.SubElement(c, "mxGeometry", x=f"{x:g}", y=f"{y:g}", width=f"{w:g}", height=f"{h:g}", **{"as": "geometry"})
        return c.get("id")

    def group(self, x, y, w, h, name):
        return self.vertex(x, y, w, h, "", f"group;tooltip={name};")

    def edge(self, pts, style, value="", parent="1"):
        c = ET.SubElement(self.root, "mxCell", id=self.id(), value=value, style=style, edge="1", parent=parent)
        g = ET.SubElement(c, "mxGeometry", relative="1", **{"as": "geometry"})
        ET.SubElement(g, "mxPoint", x=f"{pts[0][0]:g}", y=f"{pts[0][1]:g}", **{"as": "sourcePoint"})
        ET.SubElement(g, "mxPoint", x=f"{pts[-1][0]:g}", y=f"{pts[-1][1]:g}", **{"as": "targetPoint"})
        if len(pts) > 2:
            a = ET.SubElement(g, "Array", **{"as": "points"})
            for x, y in pts[1:-1]:
                ET.SubElement(a, "mxPoint", x=f"{x:g}", y=f"{y:g}")
        return c.get("id")


def box(fill, stroke, size=12, arc=6, extra=""):
    return (f"rounded=1;arcSize={arc};whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth=1;"
            f"fontFamily=Arial;fontSize={size};fontColor={INK};align=center;spacingLeft=8;spacingRight=8;{extra}")


def label(size=12, color=INK, bold=False, align="left", valign="middle"):
    return (f"text;html=1;whiteSpace=wrap;fontFamily=Arial;fontSize={size};fontColor={color};align={align};"
            f"verticalAlign={valign};strokeColor=none;fillColor=none;" + ("fontStyle=1;" if bold else ""))


def arrow(color=INK, width=1.0, dashed=False, end=True, size=12):
    return (f"html=1;rounded=1;strokeColor={color};strokeWidth={width};" + ("endArrow=block;endFill=1;endSize=6;" if end else "endArrow=none;")
            + ("dashed=1;" if dashed else "") + f"fontFamily=Arial;fontSize={size};fontColor={color};labelBackgroundColor=#FFFFFF;")


# ---- page 1: the pipeline with the planning ---------------------------------------------------------
def pipeline_planning(source: ET.Element) -> ET.Element:
    d = copy.deepcopy(source)
    d.set("name", "pipeline-planning")
    d.set("id", "pipeline-planning-0")
    model = d.find("mxGraphModel")
    model.set("pageHeight", "292")
    model.set("dy", "292")
    root = model.find("root")
    cells = {c.get("id"): c for c in root}

    def geo(cid, x=None, y=None, w=None, h=None):
        g = cells[cid].find("mxGeometry")
        for k, v in (("x", x), ("y", y), ("width", w), ("height", h)):
            if v is not None:
                g.set(k, f"{v:g}")

    def points(cid, a, b):
        g = cells[cid].find("mxGeometry")
        for p, (x, y) in zip(g.findall("mxPoint"), (a, b)):
            p.set("x", f"{x:g}"), p.set("y", f"{y:g}")

    def value(cid, v):
        cells[cid].set("value", v)

    # Bands: the module band taller, the components below it.
    geo("c7", h=140), geo("c8", x=-56, y=149, w=140)
    geo("c9", y=232), geo("c10", y=253)
    # Line: the requirement states its bounds; Match plans what nothing matches.
    value("c17", "Required C: p, bounds")
    value("c21", "Match and plan")
    # Module: S' planned, with a parallel block; S and its steps above the components.
    geo("n31", h=128), geo("c32", h=128)
    geo("c39", x=6, y=56, w=96)
    geo("c38", x=6, y=88)
    for cid in ("c40", "c41", "c42"):
        geo(cid, y=108)
    points("c43", (94.5, 205), (141.5, 205)), points("c44", (197.5, 205), (244.5, 205))
    # Author becomes Plan: its four steps.
    geo("n45", h=86), geo("c46", h=86)
    value("c47", "Plan"), geo("c47", w=34)
    value("c49", "or written by hand"), geo("c49", x=40, y=1, w=102, h=17)
    geo("n50", y=182)
    geo("n55", h=128), geo("c56", h=128)
    # Arrows between the AAS, the tools and the running system.
    points("c88", (362, 152), (322, 152))
    points("c89", (322, 196), (362, 196)), points("c90", (362, 214), (322, 214))
    points("c91", (526, 196), (566, 196)), points("c92", (566, 214), (526, 214))
    for cid, x in (("c95", 66.5), ("c96", 169.5), ("c97", 272.5)):
        points(cid, (x, 212), (x, 236))
    for cid in ("n63", "n69", "n75", "n81"):
        geo(cid, y=236)
    # Every id of the page made its own, so that nothing clashes with the page it was copied from.
    for c in root.iter("mxCell"):
        for k in ("id", "parent"):
            if c.get(k) not in (None, "0", "1"):
                c.set(k, "pp-" + c.get(k))

    pink = cells["c39"].get("style")
    chip = cells["c24"].get("style")
    small = cells["c49"].get("style")
    edge = cells["c88"].get("style")
    n = 0

    def add(parent, x, y, w, h, v, style):
        nonlocal n
        n += 1
        c = ET.SubElement(root, "mxCell", id=f"pp-new{n}", value=v, style=style, vertex="1", parent=parent)
        ET.SubElement(c, "mxGeometry", x=f"{x:g}", y=f"{y:g}", width=f"{w:g}", height=f"{h:g}", **{"as": "geometry"})

    def line(pts, style, v=""):
        nonlocal n
        n += 1
        c = ET.SubElement(root, "mxCell", id=f"pp-new{n}", value=v, style=style, edge="1", parent="pp-n1")
        g = ET.SubElement(c, "mxGeometry", relative="1", **{"as": "geometry"})
        ET.SubElement(g, "mxPoint", x=f"{pts[0][0]:g}", y=f"{pts[0][1]:g}", **{"as": "sourcePoint"})
        ET.SubElement(g, "mxPoint", x=f"{pts[1][0]:g}", y=f"{pts[1][1]:g}", **{"as": "targetPoint"})

    # S' in the module: P1, then P2 beside P1, then P1 (relative to the module's card).
    add("pp-n31", 110, 56, 30, 15, "P1", pink)
    add("pp-n31", 148, 44, 74, 39, "", "rounded=1;arcSize=14;whiteSpace=wrap;html=1;fillColor=none;dashed=1;"
                                        f"strokeColor={PINK_LINE};strokeWidth=1;")
    add("pp-n31", 154, 47, 62, 14, "P2", pink)
    add("pp-n31", 154, 66, 62, 14, "P1", pink)
    add("pp-n31", 230, 56, 30, 15, "P1", pink)
    thin = f"html=1;rounded=1;strokeColor={PINK_LINE};strokeWidth=1.2;endArrow=block;endFill=1;endSize=6;"
    line([(158, 153.5), (166, 153.5)], thin), line([(240, 153.5), (248, 153.5)], thin)
    # The Plan card's steps (relative to it).
    left = chip + "align=left;spacingLeft=6;"
    for k, s in enumerate(("task C from the vocabulary", "regress to the primitives", "track a bound: ∥, rates set",
                           "check it in time")):
        add("pp-n45", 6, 20 + 16 * k, 152, 14, s, left)
    # The planner reads the module's capabilities.
    line([(322, 120), (362, 120)], edge, "capabilities")
    # In the runtime: what a parallel block does.
    add("pp-n55", 6, 64, 198, 28, "a parallel block's branches start together, each at its rate", small)
    return d


# ---- page 2: BottomUpFilling planned ----------------------------------------------------------------
def planned_bottom_up() -> ET.Element:
    P = Page("planned-bottom-up", 440, 700)
    W = 432
    # The requirement.
    P.vertex(4, 4, W, 58, "<b>Required</b> by the syringe's filling step: <b>BottomUpFilling</b>, 1.0 mL;<br>"
             "the needle at most 2 mm above, 3 mm below the liquid;<br>the barrel 6.35 mm wide, its bottom 11 mm above the nest",
             box(PURPLE_FILL, PURPLE, extra="align=left;spacingLeft=10;"))
    P.edge([(220, 62), (220, 72)], arrow())
    # The task, from the vocabulary.
    P.vertex(4, 72, W, 62, "", box("#F7F8F9", LINE, 16))
    P.vertex(12, 76, 416, 18, "<b>Task</b> from the vocabulary: BottomUpFilling ⊑ Filling", label(13))
    P.vertex(12, 102, 100, 22, "pre: empty", box(RUN, GREEN, arc=30))
    P.vertex(118, 102, 150, 22, "post: content 1.0 mL", box(RUN, GREEN, arc=30))
    P.vertex(274, 102, 154, 22, "keep: −2 ≤ immersion ≤ 3", box(PURPLE_FILL, PURPLE, arc=30))
    P.edge([(220, 134), (220, 144)], arrow())
    # The actions, from the module's Capability Description (the module's nest, the product's bottom).
    P.vertex(4, 144, W, 98, "", box("#F7F8F9", LINE, 16))
    P.vertex(12, 148, 416, 18, "<b>Actions</b> from the Capability Description", label(13))
    P.vertex(12, 170, 416, 36, "<b>Dosing</b>: content += V at a rate r, 0.1 to 5 mL/s;<br>"
             "immersion = y − (70 − 11) + 31.6 · content", box(BLUE_FILL, BLUE, arc=4, extra="align=left;spacingLeft=8;"))
    P.vertex(12, 212, 416, 22, "<b>Positioning</b>: the needle to y at 12.5 mm/s; y ≤ 70 − 11 − 1",
             box(BLUE_FILL, BLUE, arc=4, extra="align=left;spacingLeft=8;"))
    P.edge([(220, 242), (220, 254)], arrow())
    # The goal regression: the dose alone refused, then tracking.
    P.vertex(4, 254, W, 124, "", box("#F7F8F9", LINE, 16))
    P.vertex(12, 258, 416, 18, "<b>Goal regression</b>: content = 1.0 mL", label(13))
    P.vertex(12, 282, 176, 44, "<b>Dosing alone</b> at 40 mm:<br>immersion −19 → +12.6",
             box(PINK, PINK_LINE, arc=4, extra="dashed=1;align=left;spacingLeft=8;"))
    P.vertex(12, 330, 176, 44, "broken at its start and its end, so not applied: the next method",
             label(12, GREY, valign="top"))
    P.edge([(188, 304), (204, 304)], arrow(GREY))
    P.vertex(204, 282, 224, 88, "", box(RUN, GREEN, arc=4))
    P.vertex(212, 284, 212, 18, "<b>Tracking</b>: Dosing ∥ Positioning", label(12))
    for k, s in enumerate(("31.6 · r = 12.5, so r = 0.396 mL/s", "starts at y<sub>0</sub> in [57, 58]: 57.5",
                           "rises 31.6 mm in 2.53 s, to 25.9")):
        P.vertex(212, 304 + 21 * k, 208, 19, s, box("#FFFFFF", LINE, arc=4, extra="align=left;spacingLeft=6;"))
    P.edge([(316, 378), (316, 390)], arrow())
    # In time: how deep the needle is in the liquid, the dose alone against the tracking.
    P.vertex(4, 390, W, 160, "", box("#FFFFFF", LINE, 16))
    P.vertex(12, 394, 416, 18, "<b>In time</b>: how deep the needle is in the liquid", label(13))
    x0, x1, t1, y0, y1, top, bottom = 60, 280, 2.75, 440, 524, 15, -20      # 0 to 2.75 s, +15 to -20 mm

    def X(t):
        return x0 + (x1 - x0) * t / t1

    def Y(mm):
        return y0 + (y1 - y0) * (top - mm) / (top - bottom)

    area = math.pi * 6.35 ** 2 / 4
    rise, took = 1000 / area, 1.0 / 0.396
    P.vertex(x0, Y(3), x1 - x0, Y(-2) - Y(3), "", f"rounded=0;html=1;fillColor={RUN};strokeColor=none;")   # the bounds
    axes = f"html=1;rounded=0;strokeColor={LINE};strokeWidth=1;endArrow=none;"
    P.edge([(x0, y0), (x0, y1), (x1, y1)], axes)
    P.edge([(x0, Y(0)), (x1, Y(0))], f"html=1;rounded=0;strokeColor={LINE};strokeWidth=0.75;dashed=1;endArrow=none;")
    for mm, s in ((15, "+15"), (0, "0"), (-20, "−20")):
        P.vertex(20, Y(mm) - 8, 36, 16, s, label(12, GREY, align="right"))
    for tick in (0, 1, 2):
        P.vertex(X(tick) - 15, y1 + 2, 30, 16, str(tick), label(12, GREY, align="center"))
    P.vertex(X(2.6) - 10, y1 + 2, 30, 16, "s", label(12, GREY))
    P.vertex(12, 412, 200, 16, "mm, + in the liquid", label(12, GREY))
    line = lambda color, dashed=False: (f"html=1;rounded=0;strokeColor={color};strokeWidth=2;endArrow=none;"  # noqa: E731
                                        + ("dashed=1;" if dashed else ""))
    P.edge([(X(0), Y(40 - 59)), (X(1.0), Y(40 - 59 + rise))], line(PINK_LINE, True))     # the dose alone: 1 mL/s
    P.edge([(X(0), Y(-1.5)), (X(took), Y(-1.5))], line(GREEN))                           # tracked: as it started
    for k, (style, s) in enumerate(((line(PINK_LINE, True), "the dose alone"), (line(GREEN), "tracking"))):
        y = 440 + 24 * k
        P.edge([(296, y), (320, y)], style)
        P.vertex(326, y - 9, 104, 18, s, label(12))
    P.vertex(296, 479, 24, 12, "", f"rounded=0;html=1;fillColor={RUN};strokeColor=none;")
    P.vertex(326, 476, 104, 18, "the bounds", label(12))
    P.vertex(296, 500, 134, 34, "the dose takes 1 s alone, 2.53 s tracked", label(12, GREY, valign="top"))
    P.edge([(220, 550), (220, 562)], arrow())
    # The planned skill, lifted.
    P.vertex(4, 562, W, 82, "", box("#FFFFFF", LINE, 16))
    P.vertex(12, 566, 416, 18, "<b>The planned skill</b>: the pair a parallel block", label(13))
    P.vertex(12, 602, 100, 24, "MoveAxis 57.5", box(FB, FB_LINE, arc=4))
    P.vertex(124, 588, 206, 52, "", "rounded=1;arcSize=10;whiteSpace=wrap;html=1;fillColor=none;dashed=1;"
                                     f"strokeColor={FB_LINE};strokeWidth=1;")
    P.vertex(130, 592, 194, 20, "Dispense 1.0 at 0.396 mL/s", box(FB, FB_LINE, arc=4))
    P.vertex(130, 616, 194, 20, "MoveAxis 25.9", box(FB, FB_LINE, arc=4))
    P.vertex(342, 602, 86, 24, "Home", box(FB, FB_LINE, arc=4))
    P.edge([(112, 614), (124, 614)], arrow(GREEN, 1.25)), P.edge([(330, 614), (342, 614)], arrow(GREEN, 1.25))
    P.edge([(107, 644), (107, 656)], arrow())
    # Described, and offered.
    P.vertex(4, 656, 206, 46, "<b>Checked in time</b>, described:<br>Skills, <i>Described</i>",
             box("#FFFFFF", AAS, extra="strokeWidth=1.25;align=left;spacingLeft=8;"))
    P.edge([(210, 679), (230, 679)], arrow())
    P.vertex(230, 656, 206, 46, "<b>Offered</b> BottomUpFilling<br>after a reconfiguration",
             box(PINK, PINK_LINE, extra="align=left;spacingLeft=8;"))
    return P.diagram


text = open(PATH, encoding="utf-8", newline="").read()
for name in ("pipeline-planning", "planned-bottom-up"):          # run again: the pages replaced
    text = re.sub(r'\s*<diagram id="' + name + r'-0".*?</diagram>', "", text, flags=re.S)
source = next(d for d in ET.fromstring(text).findall("diagram") if d.get("name") == "pipeline")
pages = "".join("\n  " + ET.tostring(p, encoding="unicode") for p in (pipeline_planning(source), planned_bottom_up()))
end = text.rindex("</mxfile>")
newline = "\r\n" if "\r\n" in text else "\n"
open(PATH, "w", encoding="utf-8", newline="").write(text[:end].rstrip() + pages.replace("\n", newline) + newline + text[end:])
print("written", PATH)
