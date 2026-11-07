"""Two pages added to docs/figures/cirp-figures.drawio (6 Nov), the others left byte for byte:

- pipeline-planning: Fig. 1 (the page "pipeline") with the planning spelled out: Match and plan, a Plan
  card with its four steps, the capabilities that feed it, a planned skill S' with a parallel block;
- planned-bottom-up: how the planner makes BottomUpFilling for the syringe from the module's primitives
  (one column, 440 px = 8.4 cm, no text below 12 px), the needle rising with the liquid in time;
- primitives-to-composite: how a module's offered capabilities follow from its primitives' and the
  vocabulary (realizes, contributes, process or auxiliary, means, characterizes, narrower), or are
  planned from the classes' constraints (two columns, 206 mm).

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

    # Bands: the module band taller (it holds the Skills submodel), the components below it.
    model.set("pageHeight", "324"), model.set("dy", "324")
    geo("c5", h=80), geo("c6", y=47)          # the line band 14 px taller: see the shift at the end
    geo("c7", h=158), geo("c8", x=-65, y=158, w=158)
    geo("c9", y=250), geo("c10", y=271)
    # Line: the product names the submodels it uses (review of 7 Nov): the required capabilities with
    # their values and bounds are in its Capability Description, the recipe in its Production Sequence.
    value("c17", "Capability Description"), value("c18", "Production Sequence")
    value("c21", "Match and plan")
    # Module: its three submodels; the Skills submodel holds S' (planned, a parallel block) and S with its
    # steps above the components.
    geo("n31", h=146), geo("c32", h=146)
    geo("c36", x=6, w=140), geo("c37", x=152, w=146)
    value("c37", "Asset Interfaces Description")
    cells["c37"].set("style", cells["c37"].get("style").replace("fontSize=10", "fontSize=9")
                     .replace("spacingLeft=8;spacingRight=8", "spacingLeft=2;spacingRight=2"))
    geo("c39", x=12, y=66, w=88)
    geo("c38", x=12, y=102)
    for cid in ("c40", "c41", "c42"):
        geo(cid, y=122)
    points("c43", (94.5, 219), (141.5, 219)), points("c44", (197.5, 219), (244.5, 219))
    # Author becomes Plan: its four steps.
    geo("n45", h=86), geo("c46", h=86)
    value("c47", "Plan"), geo("c47", w=34)
    value("c49", "or written by hand"), geo("c49", x=40, y=1, w=102, h=17)
    geo("n50", y=182)
    # Reconcile becomes Synchronise, the paper's plainer word for it.
    value("c52", "Synchronise"), cells["n50"].set("style", "group;tooltip=Synchronise;")
    geo("n55", h=146), geo("c56", h=146)
    # In the runtime, S' is created online by the synchroniser: drawn in the management protocol's gold.
    value("c62", "S′ created online"), geo("c62", w=104)
    cells["c62"].set("style", cells["c62"].get("style").replace("fillColor=#F6DDD6", "fillColor=#FBF3DF")
                     .replace("strokeColor=#C47A68", f"strokeColor={GOLD}"))
    # Arrows between the AAS, the tools and the running system.
    points("c88", (362, 152), (322, 152))
    points("c89", (322, 196), (362, 196)), points("c90", (362, 214), (322, 214))
    points("c91", (526, 196), (566, 196)), points("c92", (566, 214), (526, 214))
    for cid, x in (("c95", 66.5), ("c96", 169.5), ("c97", 272.5)):
        points(cid, (x, 226), (x, 254))
    for cid in ("n63", "n69", "n75", "n81"):
        geo(cid, y=254)
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

    # The Skills submodel, drawn like the module's other submodels (a grey chip as its title) around the
    # skills, behind them: inserted before S's chip so that it is drawn first.
    grey = cells["c36"].get("style")
    first = list(root).index(cells["c38"])
    for k, (x, y, w, h, v, style) in enumerate((
            (6, 44, 292, 96, "", "rounded=1;arcSize=6;whiteSpace=wrap;html=1;fillColor=#F4F5F6;strokeColor=#A7ACB6;"
                                 "strokeWidth=1;"),
            (6, 44, 292, 16, "Skills", grey))):
        c = ET.Element("mxCell", id=f"pp-skills{k}", value=v, style=style, vertex="1", parent="pp-n31")
        ET.SubElement(c, "mxGeometry", x=f"{x:g}", y=f"{y:g}", width=f"{w:g}", height=f"{h:g}", **{"as": "geometry"})
        root.insert(first + k, c)
    # S' in the module: P1, then P2 beside P1, then P1 (relative to the module's card), 18 px between
    # them so that the arrows have a shaft and not only a head.
    add("pp-n31", 108, 66, 26, 15, "P1", pink)
    add("pp-n31", 152, 62, 70, 36, "", "rounded=1;arcSize=14;whiteSpace=wrap;html=1;fillColor=none;dashed=1;"
                                       f"strokeColor={PINK_LINE};strokeWidth=1;")
    add("pp-n31", 157, 64, 60, 14, "P2", pink)
    add("pp-n31", 157, 81, 60, 14, "P1", pink)
    add("pp-n31", 240, 66, 26, 15, "P1", pink)
    thin = f"html=1;rounded=1;strokeColor={PINK_LINE};strokeWidth=1.2;endArrow=block;endFill=1;endSize=6;"
    line([(152, 163.5), (170, 163.5)], thin), line([(240, 163.5), (258, 163.5)], thin)
    # The Plan card's steps (relative to it).
    left = chip + "align=left;spacingLeft=6;"
    for k, s in enumerate(("task C from the vocabulary", "regress to the primitives", "track a bound: ∥, rates set",
                           "check it in time")):
        add("pp-n45", 6, 20 + 16 * k, 152, 14, s, left)
    # The planner reads the module's capabilities.
    line([(322, 120), (362, 120)], edge, "capabilities")
    # In the runtime: what a parallel block does.
    add("pp-n55", 6, 64, 198, 28, "a parallel block's branches start together, each at its rate", small)
    # The module and component rows 14 px lower, so that the arrows from the line row (Match and plan to
    # Plan, OPC UA) are 28 px long, not a head alone. Groups' children are relative and stay put.
    for c in root.iter("mxCell"):
        if c.get("parent") != "pp-n1":
            continue
        g = c.find("mxGeometry")
        if c.get("vertex") == "1" and float(g.get("y", 0)) >= 84:
            g.set("y", f"{float(g.get('y')) + 14:g}")
        for p in g.iter("mxPoint"):
            if float(p.get("y", 0)) >= 84:
                p.set("y", f"{float(p.get('y')) + 14:g}")
    opc = next(c for c in root.iter("mxCell") if c.get("id") == "pp-c94").find("mxGeometry")
    opc.set("y", "83")
    return d


# ---- page 2: BottomUpFilling planned ----------------------------------------------------------------
def planned_bottom_up() -> ET.Element:
    """The paper's Fig. 2 (7 Nov): one column, 440 px wide and 528 tall (8.4 by 10.2 cm), no text below 12 px."""
    P = Page("planned-bottom-up", 440, 528)
    W = 432
    # The requirement, and the task the vocabulary makes of it.
    P.vertex(4, 4, W, 78, "", box(PURPLE_FILL, PURPLE, 16))
    P.vertex(12, 7, 416, 36, "<b>Required</b>: BottomUpFilling ⊑ Filling, 1.0 mL; the barrel<br>"
             "6.35 mm wide, its bottom 11 mm above the nest", label(12))
    P.vertex(12, 50, 100, 22, "pre: empty", box("#FFFFFF", GREEN, arc=30))
    P.vertex(118, 50, 150, 22, "post: content 1.0 mL", box("#FFFFFF", GREEN, arc=30))
    P.vertex(274, 50, 154, 22, "keep: −2 ≤ immersion ≤ 3", box("#FFFFFF", PURPLE, arc=30))
    P.edge([(220, 82), (220, 92)], arrow())
    # The actions, from the module's Capability Description (the module's nest, the product's bottom).
    P.vertex(4, 92, W, 88, "", box("#F7F8F9", LINE, 16))
    P.vertex(12, 95, 416, 18, "<b>Actions</b> from the Capability Description", label(13))
    P.vertex(12, 116, 416, 34, "<b>Dosing</b>: content += V at a rate r, 0.1 to 5 mL/s;<br>"
             "immersion = y − (70 − 11) + 31.6 · content", box(BLUE_FILL, BLUE, arc=4, extra="align=left;spacingLeft=8;"))
    P.vertex(12, 154, 416, 20, "<b>Positioning</b>: the needle to y at 12.5 mm/s; y ≤ 70 − 11 − 1",
             box(BLUE_FILL, BLUE, arc=4, extra="align=left;spacingLeft=8;"))
    P.edge([(220, 180), (220, 190)], arrow())
    # The goal regression: the dose alone refused, then tracking.
    P.vertex(4, 190, W, 112, "", box("#F7F8F9", LINE, 16))
    P.vertex(12, 193, 416, 18, "<b>Goal regression</b>: content = 1.0 mL", label(13))
    P.vertex(12, 215, 176, 40, "<b>Dosing alone</b> at 40 mm:<br>immersion −19 → +12.6",
             box(PINK, PINK_LINE, arc=4, extra="dashed=1;align=left;spacingLeft=8;"))
    P.vertex(12, 258, 176, 40, "breaks the bound at its start and end: not applied", label(12, GREY, valign="top"))
    P.edge([(188, 235), (204, 235)], arrow(GREY))
    P.vertex(204, 215, 224, 82, "", box(RUN, GREEN, arc=4))
    P.vertex(212, 216, 212, 18, "<b>Tracking</b>: Dosing ∥ Positioning", label(12))
    for k, s in enumerate(("31.6 · r = 12.5, so r = 0.396 mL/s", "starts at y<sub>0</sub> in [57, 58]: 57.5",
                           "rises 31.6 mm in 2.53 s, to 25.9")):
        P.vertex(212, 236 + 20 * k, 208, 18, s, box("#FFFFFF", LINE, arc=4, extra="align=left;spacingLeft=6;"))
    P.edge([(316, 302), (316, 312)], arrow())
    # In time: how deep the needle is in the liquid, the dose alone against the tracking.
    P.vertex(4, 312, W, 128, "", box("#FFFFFF", LINE, 16))
    P.vertex(12, 315, 416, 18, "<b>In time</b>: how deep the needle is in the liquid", label(13))
    x0, x1, t1, y0, y1, top, bottom = 60, 280, 2.75, 352, 418, 15, -20      # 0 to 2.75 s, +15 to -20 mm

    def X(t):
        return x0 + (x1 - x0) * t / t1

    def Y(mm):
        return y0 + (y1 - y0) * (top - mm) / (top - bottom)

    area = math.pi * 6.35 ** 2 / 4
    rise, took = 1000 / area, 1.0 / 0.396
    P.vertex(x0, Y(3), x1 - x0, Y(-2) - Y(3), "", f"rounded=0;html=1;fillColor={RUN};strokeColor=none;")   # the bounds
    P.edge([(x0, y0), (x0, y1), (x1, y1)], f"html=1;rounded=0;strokeColor={LINE};strokeWidth=1;endArrow=none;")
    P.edge([(x0, Y(0)), (x1, Y(0))], f"html=1;rounded=0;strokeColor={LINE};strokeWidth=0.75;dashed=1;endArrow=none;")
    for mm, s in ((15, "+15"), (0, "0"), (-20, "−20")):
        P.vertex(20, Y(mm) - 8, 36, 16, s, label(12, GREY, align="right"))
    for tick in (0, 1, 2):
        P.vertex(X(tick) - 15, y1 + 1, 30, 16, str(tick), label(12, GREY, align="center"))
    P.vertex(X(2.6) - 10, y1 + 1, 30, 16, "s", label(12, GREY))
    P.vertex(12, 333, 200, 16, "mm, + in the liquid", label(12, GREY))
    line = lambda color, dashed=False: (f"html=1;rounded=0;strokeColor={color};strokeWidth=2;endArrow=none;"  # noqa: E731
                                        + ("dashed=1;" if dashed else ""))
    P.edge([(X(0), Y(40 - 59)), (X(1.0), Y(40 - 59 + rise))], line(PINK_LINE, True))     # the dose alone: 1 mL/s
    P.edge([(X(0), Y(-1.5)), (X(took), Y(-1.5))], line(GREEN))                           # tracked: as it started
    for k, (style, s) in enumerate(((line(PINK_LINE, True), "the dose alone"), (line(GREEN), "tracking"))):
        y = 352 + 22 * k
        P.edge([(296, y), (320, y)], style)
        P.vertex(326, y - 9, 104, 18, s, label(12))
    P.vertex(296, 390, 24, 12, "", f"rounded=0;html=1;fillColor={RUN};strokeColor=none;")
    P.vertex(326, 387, 104, 18, "the bounds", label(12))
    P.vertex(296, 408, 134, 30, "1 s alone, 2.53 s tracked", label(12, GREY, valign="top"))
    P.edge([(220, 440), (220, 450)], arrow())
    # The planned skill, lifted, checked in time and described.
    P.vertex(4, 450, W, 74, "", box("#FFFFFF", AAS, 16, extra="strokeWidth=1.25;"))
    P.vertex(12, 453, 416, 18, "<b>The planned skill</b>, checked in time, <i>Described</i>", label(13))
    P.vertex(12, 484, 100, 24, "MoveAxis 57.5", box(FB, FB_LINE, arc=4))
    P.vertex(124, 474, 206, 46, "", "rounded=1;arcSize=10;whiteSpace=wrap;html=1;fillColor=none;dashed=1;"
                                     f"strokeColor={FB_LINE};strokeWidth=1;")
    P.vertex(130, 477, 194, 19, "Dispense 1.0 at 0.396 mL/s", box(FB, FB_LINE, arc=4))
    P.vertex(130, 498, 194, 19, "MoveAxis 25.9", box(FB, FB_LINE, arc=4))
    P.vertex(342, 484, 86, 24, "Home", box(FB, FB_LINE, arc=4))
    P.edge([(112, 496), (124, 496)], arrow(GREEN, 1.25)), P.edge([(330, 496), (342, 496)], arrow(GREEN, 1.25))
    return P.diagram


# ---- page 3: from primitives' capabilities to a composite's, and the vocabulary that says how ----------
SHELL = None                                    # the AAS shell icon, taken from the page "pipeline"


def primitives_to_composite() -> ET.Element:
    """Two columns, 780 px (206 mm): the AAS elements on the left, the vocabulary's relations they rest on
    on the right; four rows: a primitive realizes its component's capability, a composite's steps
    contribute capabilities, the process ones are offered and specified, and without a skill one is
    planned from the classes' constraints."""
    P = Page("primitives-to-composite", 780, 356)
    small, body, head = 10, 11, 12
    chip = lambda fill, stroke, dashed=False: (f"rounded=1;arcSize=40;whiteSpace=wrap;html=1;fillColor={fill};"   # noqa: E731
                                               f"strokeColor={stroke};strokeWidth=1;fontFamily=Arial;fontSize={body};"
                                               f"fontColor={INK};spacingLeft=3;spacingRight=3;" + ("dashed=1;" if dashed else ""))
    card = f"rounded=1;arcSize=6;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor={LINE};strokeWidth=1;"
    band = "rounded=1;arcSize=4;whiteSpace=wrap;html=1;fillColor=#F3F4F5;strokeColor=none;"
    badge = (f"ellipse;html=1;fillColor={INK};strokeColor=none;fontColor=#FFFFFF;fontFamily=Arial;fontSize=9;fontStyle=1;")
    SKILL = chip(FB, FB_LINE)                   # a skill type, or a step
    AUX = chip(BLUE_FILL, BLUE)                 # an auxiliary capability
    PROC = chip(RUN, GREEN)                     # a process capability
    PROP = chip(PURPLE_FILL, PURPLE)            # a property
    PRIM = chip(RUN, GREEN)                     # a primitive skill in a component's AAS
    LATER = chip(PINK, PINK_LINE, dashed=True)  # after a reconfiguration
    PLAIN = chip("#FFFFFF", LINE)

    def note(x, y, w, h, s, color=GREY, size=small):
        P.vertex(x, y, w, h, s, label(size, color, valign="top"))

    def aas(x, y, w, h, name):
        """An AAS card: the shell icon and the name."""
        P.vertex(x, y, w, h, "", card)
        P.vertex(x + 6, y + 5, 15, 12, "", SHELL)
        P.vertex(x + 25, y + 3, w - 30, 16, name, label(body, INK, bold=True))

    def triple(x, y, parts, h=18):
        """Chips joined by labelled arrows: (text, style, width) for a chip, (label, width) for an arrow."""
        for part in parts:
            if len(part) == 3:
                s, style, w = part
                P.vertex(x, y, w, h, s, style)
            else:
                said, w = part
                P.edge([(x, y + h / 2), (x + w, y + h / 2)], arrow(INK, 1, size=small) + "verticalAlign=bottom;spacingBottom=2;", said)
            x += part[-1]

    P.vertex(22, 0, 400, 14, "AAS: the module and its components", label(small, GREY, bold=True))
    P.vertex(470, 0, 300, 14, "Vocabulary: what the elements mean, and how they relate", label(small, GREY, bold=True))
    rows = ((16, 80, "A primitive realizes a capability of its component"),
            (102, 84, "A composite's steps contribute capabilities"),
            (192, 80, "The process capabilities are offered, specified by what the skill sets"),
            (278, 74, "No skill yet: planned from the classes' constraints"))
    for k, (y, h, title) in enumerate(rows):
        P.vertex(14, y, 762, h, "", band)
        P.vertex(20, y + 5, 14, 14, str(k + 1), badge)
        P.vertex(40, y + 3, 420, 17, title, label(head, INK, bold=True))
        if k < 2:
            P.edge([(233, y + h), (233, rows[k + 1][0])], arrow(INK, 1.2))

    # 1: Dispense in the pump's AAS realizes Dosing, the pump's capability in the module's description.
    y = 16
    aas(22, y + 24, 122, 48, "Pump")
    P.vertex(30, y + 48, 106, 17, "Dispense", PRIM)
    P.edge([(144, y + 56), (170, y + 56)], arrow(INK, 1.2))
    aas(170, y + 24, 274, 48, "Module: Capability Description")
    P.vertex(178, y + 48, 258, 17, "Dosing, realized by Dispense", AUX)
    triple(470, y + 26, [("Dispense", SKILL, 74), ("realizes", 64), ("Dosing", AUX, 70)])
    note(682, y + 22, 92, 40, "of the pump; never offered alone")
    note(470, y + 48, 300, 30, "Dosing: auxiliary, DIN 8580 pouring; its pre, post and keep,<br>and FlowRate the rate of the content")

    # 2: Dispensing's steps, and what each one's type contributes.
    y = 102
    aas(22, y + 24, 422, 54, "Module: Skills, Dispensing")
    steps = (("MoveAxis", 30, 74), ("Dispense", 118, 74), ("Home", 206, 58), ("Weigh", 278, 62))
    for s, x, w in steps:
        P.vertex(x, y + 50, w, 17, s, SKILL)
    for (_, xa, wa), (_, xb, _) in zip(steps, steps[1:]):
        P.edge([(xa + wa, y + 58.5), (xb, y + 58.5)], arrow(GREEN, 1.2))
    note(346, y + 46, 94, 28, "Volume means<br>FillVolume")
    for k, (s, cls, style, said, color) in enumerate((("MoveAxis, Home", "Positioning", AUX, "not offered", GREY),
                                                       ("Dispense", "Filling", PROC, "offered", GREEN),
                                                       ("Tare, Weigh", "Weighing", AUX, "not offered", GREY))):
        triple(470, y + 22 + 20 * k, [(s, SKILL, 96), ("contributes" if k == 0 else "", 58), (cls, style, 82)], h=17)
        P.vertex(710, y + 22 + 20 * k, 66, 17, said, label(small, color, bold=color == GREEN))

    # 3: Filling offered, by Dispensing, its FillVolume from the skill's Volume.
    y = 192
    aas(22, y + 24, 422, 48, "Module: Capability Description, offered")
    P.vertex(30, y + 48, 142, 17, "Filling, by Dispensing", PROC)
    P.vertex(178, y + 48, 136, 17, "FillVolume 0.5 to 10 mL", PROP)
    P.vertex(320, y + 48, 116, 17, "ContainerType: stated", PLAIN)
    triple(470, y + 24, [("Volume", SKILL, 54), ("means", 42), ("FillVolume", PROP, 74), ("characterizes", 76), ("Filling", PROC, 54)])
    triple(470, y + 55, [("BottomUpFilling", PROC, 104), ("⊑", 30), ("Filling", PROC, 54)])
    note(662, y + 51, 112, 28, "a skill written for it<br>offers it instead")

    # 4: no skill: planned from the class's constraints over row 1's capabilities.
    y = 278
    P.vertex(22, y + 26, 118, 32, "Filling 15 mL:<br>no skill covers it", PLAIN)
    P.edge([(140, y + 42), (168, y + 42)], arrow(INK, 1.2) + "verticalAlign=bottom;spacingBottom=2;fontSize=10;", "plan")
    P.vertex(168, y + 26, 152, 32, "MoveAxis, Dispense 7.5 ×2,<br>Home, Weigh: <i>Described</i>", LATER)
    P.edge([(320, y + 42), (334, y + 42)], arrow(INK, 1.2))
    P.vertex(334, y + 26, 110, 32, "offered after a<br>reconfiguration", LATER)
    triple(470, y + 24, [("Filling", PROC, 54)])
    note(530, y + 22, 244, 22, "pre: empty;  post: content = FillVolume", INK, body)
    note(470, y + 46, 304, 26, "regressed over the capabilities of row 1, their pre, post, keep<br>and rates; a narrower class keeps what it adds (BottomUpFilling)")
    return P.diagram


# ---- page 4: planning, generic (the paper's Fig. 2 since the review of 7 Nov) ---------------------------
def planning_generic() -> ET.Element:
    """Fig. 2 (as built, 8 Nov): what the planner builds from a requirement and a module's primitives, as
    numbered cases in BPMN: (1) a sequence, by goal regression; (2) a repetition; (3) a parallel block of
    independent steps; (4) steps in parallel at a matched rate; (5) a decision, greyed: drawn by hand and
    checked, not planned. The last cell: every flow is checked in time, then described. Reuse of a stated
    composition or an existing composite is left out: it is not read from the AAS (8 Nov). One column,
    440 by 346 px (8.4 by 6.6 cm), no text below 12 px."""
    P = Page("planning-generic", 440, 346)
    badge = (f"ellipse;html=1;fillColor={INK};strokeColor=none;fontColor=#FFFFFF;fontFamily=Arial;fontSize=10;"
             "fontStyle=1;align=center;verticalAlign=middle;")
    task = box(RUN, GREEN, 12, arc=24, extra="spacingLeft=2;spacingRight=2;")
    grey_task = box("#FFFFFF", LINE, 12, arc=24, extra=f"dashed=1;fontColor={GREY};spacingLeft=2;spacingRight=2;")
    flow = arrow(INK) + "endSize=5;"
    grey_flow = arrow(GREY) + "endSize=5;"
    left = lambda fill, stroke: box(fill, stroke, 12, extra="align=left;verticalAlign=top;spacingLeft=8;spacingTop=2;")  # noqa: E731

    # The inputs: the product's requirement and the module's primitives.
    P.vertex(4, 4, 208, 66, "<b>Product</b> requires C<br>goal: x = v<br>keep: l ≤ h ≤ u", left(PURPLE_FILL, PURPLE))
    P.vertex(228, 4, 208, 66, "<b>Module</b>: primitives A, B, C<br>pre, post, invariants, rates<br>h = a·x + b·y",
             left(BLUE_FILL, BLUE))
    P.edge([(108, 70), (108, 80), (210, 80), (210, 90)], arrow())
    P.edge([(332, 70), (332, 80), (230, 80), (230, 90)], arrow())

    # The planner and what it builds.
    P.vertex(4, 90, 432, 252, "", box("#F7F8F9", LINE, 16))
    P.vertex(12, 93, 416, 18, "<b>Planner</b>: flows built from the goal back to the start", label(12))

    def cell(k, col, row, title, when, planned=True):
        cx, cy = 10 + 216 * col, 114 + 76 * row
        P.vertex(cx, cy, 204, 70, "", box("#FFFFFF", LINE if planned else "#C9CED1", 16,
                                         extra="" if planned else "dashed=1;"))
        P.vertex(cx + 6, cy + 5, 15, 15, str(k), badge if planned else badge.replace(INK, GREY))
        P.vertex(cx + 26, cy + 3, 176, 18, f"<b>{title}</b>", label(12, INK if planned else GREY))
        P.vertex(cx + 8, cy + 19, 194, 16, when, label(12, GREY))
        return cx, cy

    def chain(cx, cy, names, style=task, w=40, gap=22, start=8):
        """Steps one after the other, centred on the cell's diagram row."""
        x = cx + start
        for i, s in enumerate(names):
            P.vertex(x, cy + 44, w, 16, s, style)
            if i < len(names) - 1:
                P.edge([(x + w, cy + 52), (x + w + gap, cy + 52)], flow)
            x += w + gap

    def block(cx, cy, top, bottom, symbol="+", style=task, edges=flow, w=60):
        """A gateway, two branches, a gateway (BPMN)."""
        gate = (f"rhombus;html=1;fillColor=#FFFFFF;strokeColor={INK if style == task else GREY};strokeWidth=1.2;"
                f"fontFamily=Arial;fontSize=13;fontStyle=1;fontColor={INK if style == task else GREY};")
        P.vertex(cx + 8, cy + 42, 20, 20, symbol, gate)
        tx = cx + 50
        P.vertex(tx, cy + 36, w, 15, top, style)
        P.vertex(tx, cy + 53, w, 15, bottom, style)
        jx = tx + w + 22
        P.vertex(jx, cy + 42, 20, 20, symbol, gate)
        for y in (cy + 43.5, cy + 60.5):
            P.edge([(cx + 28, cy + 52), (tx, y)], edges)
            P.edge([(tx + w, y), (jx, cy + 52)], edges)

    cx, cy = cell(1, 0, 0, "Sequence", "A needs what B gives: B first")
    chain(cx, cy, ("B", "A"))
    cx, cy = cell(2, 1, 0, "Repetition", "a goal beyond one step's range")
    chain(cx, cy, ("A", "A"))
    cx, cy = cell(3, 0, 1, "Parallel", "steps share no part or state")
    block(cx, cy, "A", "C")
    cx, cy = cell(4, 1, 1, "Matched rates", "a bound links two moving states")
    block(cx, cy, "A", "B, matched", w=76)
    cx, cy = cell(5, 0, 2, "Decision", "drawn by hand, then checked", planned=False)
    block(cx, cy, "A", "B", symbol="×", style=grey_task, edges=grey_flow)
    # What follows every flow, planned or drawn.
    P.vertex(226, 266, 204, 70, "<b>Every flow</b><br>checked over time against C,<br>then described in the AAS",
             box("#FFFFFF", AAS, 12, extra="strokeWidth=1.25;align=left;verticalAlign=top;spacingLeft=8;spacingTop=4;"))
    return P.diagram


text = open(PATH, encoding="utf-8", newline="").read()
for name in ("pipeline-planning", "planned-bottom-up", "primitives-to-composite", "planning-generic"):  # replaced
    text = re.sub(r'\s*<diagram id="' + name + r'-0".*?</diagram>', "", text, flags=re.S)
source = next(d for d in ET.fromstring(text).findall("diagram") if d.get("name") == "pipeline")
SHELL = next(c.get("style") for c in source.iter("mxCell") if (c.get("style") or "").startswith("shape=stencil("))
pages = "".join("\n  " + ET.tostring(p, encoding="unicode") for p in (pipeline_planning(source), planned_bottom_up(), primitives_to_composite(),
                                                                   planning_generic()))
end = text.rindex("</mxfile>")
newline = "\r\n" if "\r\n" in text else "\n"
open(PATH, "w", encoding="utf-8", newline="").write(text[:end].rstrip() + pages.replace("\n", newline) + newline + text[end:])
print("written", PATH)
