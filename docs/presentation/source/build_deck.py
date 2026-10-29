"""Built the first version of docs/presentation/deck.drawio: every figure of the talk, one page per slide,
in story order. New pages are drawn here; earlier figures are copied from docs/figures and regrouped.
The pictures inside the PPR shells (ppr-*.png) are cut from the user's PPR figure.

    python docs/presentation/source/build_deck.py . docs/presentation/deck.drawio

Running it again OVERWRITES deck.drawio: edits made in draw.io since are lost. Edit the .drawio directly."""
import copy
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from drawlib import *  # noqa

REPO = Path(sys.argv[1])
FIG = REPO / "docs" / "figures"
HERE = Path(__file__).parent
PIC = {k: (png_uri(HERE / f"ppr-{k}.png"), __import__("PIL.Image").Image.open(HERE / f"ppr-{k}.png").size)
       for k in ("product", "process", "resource")}

pages = []


def page(name, *layers, w=1600, h=900):
    pages.append((name, w, h, list(layers)))


# ==== Copied pages: regroup, AAS icons to shells ===================================================
_g = [0]


def gid():
    _g[0] += 1
    return f"g{_g[0]}"


def load(file, idx):
    m = ET.parse(FIG / file).getroot().findall("diagram")[idx].find("mxGraphModel")
    return copy.deepcopy(m)


def geo_box(c):
    g = c.find("mxGeometry")
    if g is None:
        return None
    if c.get("edge"):
        pts = [(float(p.get("x", 0)), float(p.get("y", 0))) for p in g.iter("mxPoint")]
        if not pts:
            return None
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    return (float(g.get("x", 0)), float(g.get("y", 0)), float(g.get("width", 0)), float(g.get("height", 0)))


def inside(b, area):
    return b and b[0] >= area[0] - 0.5 and b[1] >= area[1] - 0.5 and b[0] + b[2] <= area[0] + area[2] + 0.5 \
        and b[1] + b[3] <= area[1] + area[3] + 0.5


class Copied:
    """A copied page: its cells, a layer for each name, groups made of cells by their place."""

    def __init__(self, file, idx, base="figure"):
        self.model = load(file, idx)
        root = self.model.find("root")
        self.cells = [c for c in root if c.get("id") not in ("0", "1")]
        self.layers = [ET.Element("mxCell", id="1", value=base, parent="0")]

    @property
    def size(self):
        return int(self.model.get("pageWidth")), int(self.model.get("pageHeight"))

    def layer(self, name, visible=True):
        el = ET.Element("mxCell", id=gid(), value=name, parent="0")
        if not visible:
            el.set("visible", "0")
        self.layers.append(el)
        return el.get("id")

    def pick(self, ids=None, area=None, where=None, parent="1"):
        out = []
        for c in self.cells:
            if c.get("parent") != parent:
                continue
            if ids is not None and c.get("id") not in ids:
                continue
            if area is not None and not inside(geo_box(c), area):
                continue
            if where is not None and not where(c):
                continue
            out.append(c)
        return out

    def move(self, cells, layer):
        for c in cells:
            c.set("parent", layer)

    def group(self, cells, name, layer="1"):
        """Group the cells (all on one layer) under a new group cell; their geometry becomes relative."""
        cells = [c for c in cells if c.get("parent") in ("1", layer) or c.get("parent", "").startswith("g")]
        if not cells:
            return None
        boxes = [geo_box(c) for c in cells if geo_box(c)]
        x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
        x1, y1 = max(b[0] + b[2] for b in boxes), max(b[1] + b[3] for b in boxes)
        g = ET.Element("mxCell", id=gid(), value="", style=f"group;tooltip={name.replace(';', ',')};",
                       vertex="1", connectable="0", parent=layer)
        ET.SubElement(g, "mxGeometry", x=f"{x0:g}", y=f"{y0:g}", width=f"{x1 - x0:g}", height=f"{y1 - y0:g}",
                      **{"as": "geometry"})
        first = self.cells.index(cells[0])
        for c in cells:
            self.cells.remove(c)
            c.set("parent", g.get("id"))
            geo = c.find("mxGeometry")
            if c.get("edge"):
                for p in geo.iter("mxPoint"):
                    p.set("x", f"{float(p.get('x', 0)) - x0:g}"), p.set("y", f"{float(p.get('y', 0)) - y0:g}")
            else:
                geo.set("x", f"{float(geo.get('x', 0)) - x0:g}"), geo.set("y", f"{float(geo.get('y', 0)) - y0:g}")
        self.cells[first:first] = [g] + cells
        return g

    def icons_to_shells(self, size=20):
        n = 0
        for c in self.cells:
            st = c.get("style") or ""
            b = geo_box(c)
            if "shape=image" in st and b and abs(b[2] - size) < 0.5 and abs(b[3] - size) < 0.5:
                g = c.find("mxGeometry")
                g.set("height", f"{size * SHELL_H / SHELL_W:g}"), g.set("y", f"{b[1] + size * 0.07:g}")
                c.set("style", SHELL_STYLE)
                n += 1
        return n

    def panels(self, min_w=250, min_h=60):
        """Top-level panels: big boxes not inside another big box."""
        big = [c for c in self.cells if c.get("vertex") and not (c.get("style") or "").startswith("text")
               and geo_box(c) and geo_box(c)[2] >= min_w and geo_box(c)[3] >= min_h
               and geo_box(c)[2] < float(self.model.get("pageWidth")) - 10]
        top = [c for c in big if not any(o is not c and inside(geo_box(c), geo_box(o)) for o in big)]
        return top

    def xml(self):
        order = {c.get("id"): i for i, c in enumerate(self.cells)}
        out = [ET.tostring(l, encoding="unicode") for l in self.layers]
        out += [ET.tostring(c, encoding="unicode") for c in self.cells]
        return out


def copied_page(name, cp):
    w, h = cp.size
    pages.append((name, w, h, ["\n".join(cp.xml())]))


def label_of(c):
    import re
    t = re.sub("&[a-z]+;", " ", re.sub("<[^>]+>", " ", c.get("value") or ""))
    return re.sub(" +", " ", t).strip()[:40] or "panel"


# ==== 01 The line ===================================================================================
line_pg = Copied("slides.drawio", 2, "line")
filling_layer = line_pg.layer("filling module (to pull out)")
filling = line_pg.pick(ids={"c3", "c26", "c34", "c35"})
line_pg.move(filling, filling_layer)
line_pg.group(filling, "Filling module: station, arm, name tag", filling_layer)
labels_layer = line_pg.layer("labels")
lab = line_pg.pick(ids={f"c{i}" for i in range(42, 60)})
line_pg.move(lab, labels_layer)
for ids, name in [((42, 43, 44), "Label Loading"), ((45, 46, 47), "Label table"), ((48, 49, 50), "Label Unloading"),
                  ((51, 52, 53), "Label built"), ((54, 55, 56), "Label planned"), ((57, 58, 59), "Label Pi")]:
    line_pg.group(line_pg.pick(ids={f"c{i}" for i in ids}, parent=labels_layer), name, labels_layer)
copied_page("01 The line", line_pg)

# ==== 02 Digital assets (kept as it was) ==========================================================
da = Copied("slides.drawio", 7, "digital assets")
da.group(da.pick(area=(600, 40, 1000, 250)), "The line")
for x0, name in [(30, "Filling"), (420, "Stoppering"), (810, "Capping"), (1200, "Inspection")]:
    da.group(da.pick(area=(x0, 280, 390, 500)), f"{name} module and its components")
copied_page("02 Digital assets: line, modules, components", da)

# ==== 03 The filling module, physical and digital ===================================================
src07 = load("slides.drawio", 7).find("root")
img07 = {c.get("id"): c.get("style") for c in src07}
station_style, axis_style, pump_style, scale_style = (img07[k] for k in ("c9", "c14", "c17", "c20"))

phys, aas_l, prog, links = Node("physical"), Node("AAS"), Node("IEC 61499 program"), Node("same part (links)")
ROWS = {"module": (96, 300), "axis": (330, 440), "pump": (470, 580), "scale": (610, 720), "pi": (750, 860)}


def head(node, x, title, sub):
    g = node.group(f"Header {title}")
    text(g, x, 18, 460, 34, title, 24, INK, True)
    text(g, x, 50, 460, 26, sub, 15)


head(phys, 40, "Physical", "the asset: a station of the line and its parts")
head(aas_l, 560, "Its AAS", "a shell per asset, delivered with the module")
head(prog, 1110, "Its IEC 61499 program", "on FORTE, on the module's Pi")

g = phys.group("Filling module (station)")
box(g, 50, 96, 153.5 * 0.9, 187.9 * 0.9, station_style)
text(g, 200, 130, 260, 60, "<b>Filling module</b><br><font color='#6E777B'>doses the liquid into the vial</font>", 20, INK)
spine = phys.group("Tree")
line(spine, [(119, 272), (119, 805)], f"endArrow=none;html=1;strokeColor={INK};strokeWidth=2;")
for key, style, (w0, h0), name, sub, dashed in [
        ("axis", axis_style, (108.1, 116.8), "Linear axis", "300 mm stage, ball screw<br>Nema 23 stepper, TB6600<br>home switch at the top", False),
        ("pump", pump_style, (108.1, 105.9), "Pump", "none wired yet:<br>dispensing is a time", True),
        ("scale", scale_style, (143.4, 103.2), "Scale", "simulated", True)]:
    y0, y1 = ROWS[key]
    cy = (y0 + y1) / 2
    line(spine, [(119, cy), (150, cy)], f"endArrow=none;html=1;strokeColor={INK};strokeWidth=2;")
    g = phys.group(name)
    s = min(110 / w0, 92 / h0)
    box(g, 155 + (110 - w0 * s) / 2, cy - h0 * s / 2, w0 * s, h0 * s, style)
    text(g, 285, y0 + 8, 200, 94, f"<b>{name}</b><br><font color='#6E777B' style='font-size:14px'>{sub}</font>", 18, INK)
y0, y1 = ROWS["pi"]
cy = (y0 + y1) / 2
line(spine, [(119, cy), (150, cy)], f"endArrow=none;html=1;strokeColor={INK};strokeWidth=2;")
g = phys.group("Raspberry Pi 5")
rect(g, 165, cy - 32, 96, 64, GREEN, GREEN_D, 1.5, 8)
rect(g, 199, cy - 20, 28, 22, "#2E3A2A", "none", 1, 3)
text(g, 285, y0 + 8, 200, 94, "<b>Raspberry Pi 5</b><br><font color='#6E777B' style='font-size:14px'>the module's controller:<br>runs FORTE</font>", 18, INK)

g = shell(aas_l, 560, 100, 150, 129, "Module", 20, name="Filling module AAS")
text(g, 548, 232, 176, 24, "FillingModuleAAS", 13, GREY, False, "center")
bars = aas_l.group("Module AAS submodels")
for i, s in enumerate(["Nameplate", "Hierarchical Structures", "Capability Description", "Skills",
                       "Asset Interfaces Description", "Interfaces Mapping", "Variables"]):
    sm_bar(bars, 740, 98 + i * 29, 300, 25, s, 13)
tree2 = aas_l.group("Tree")
line(tree2, [(635, 258), (635, 665)], f"endArrow=none;html=1;strokeColor={INK};strokeWidth=2;")
for key, label, skills in [("axis", "LinearAxis", "Skills: Home · MoveAxis"), ("pump", "Pump", "Skills: Dispense"),
                           ("scale", "Scale", "Skills: Tare · Weigh")]:
    y0, y1 = ROWS[key]
    cy = (y0 + y1) / 2
    line(tree2, [(635, cy), (665, cy)], f"endArrow=none;html=1;strokeColor={INK};strokeWidth=2;")
    g = shell(aas_l, 670, cy - 43, 100, 86, label, 12, name=f"{label} AAS")
    sm_bar(g, 790, cy - 15, 250, 30, skills, 14)
text(aas_l, 670, ROWS["pi"][0] + 30, 370, 50, "no AAS of its own: part of the module", 14, GREY, False, "center")

app = prog.group("Boot file: the application FillingModule")
rect(app, 1110, 96, 450, 210, "#F4F6F8", "#C9CDD0", 1.5, 4)
text(app, 1126, 100, 420, 30, "<b>forte.fboot</b> · application FillingModule", 15, INK)


def fb(node, x, y, w, h, name, typ, fill=FB_FILL, stroke=FB_STROKE, dashed=False):
    g = node.group(f"Block {name}")
    rect(g, x, y, w, h, fill, stroke, 1.5, 6, "dashed=1;" if dashed else "")
    text(g, x, y + 4, w, h / 2, name, 14, INK, True, "center")
    text(g, x, y + h / 2 - 2, w, h / 2, typ, 11, GREY, False, "center")
    return g


for i, (n, t) in enumerate([("Occupation", "one client at a time"), ("Module", "PackML state machine"),
                            ("Dispensing", "a skill: subapplication"), ("Resetting · Stopping", "procedures"),
                            ("OPC UA server", "methods and variables"), ("START", "the resource's start")]):
    fb(app, 1126 + (i % 2) * 214, 136 + (i // 2) * 54, 204, 46, n, t, RUN_FILL if n == "Dispensing" else FB_FILL,
       GREEN if n == "Dispensing" else FB_STROKE)
tree3 = prog.group("Tree")
line(tree3, [(1130, 306), (1130, 665)], f"endArrow=none;html=1;strokeColor={INK};strokeWidth=2;")
for key, eq, prims in [("axis", "LinearAxis", ["SK_Home", "SK_MoveAxis"]), ("pump", "Pump", ["SK_Dispense"]),
                       ("scale", "Scale", ["SK_Tare", "SK_Weigh"])]:
    y0, y1 = ROWS[key]
    cy = (y0 + y1) / 2
    line(tree3, [(1130, cy), (1150, cy)], f"endArrow=none;html=1;strokeColor={INK};strokeWidth=2;")
    g = prog.group(f"{eq}: equipment and primitives")
    fb(g, 1155, cy - 26, 150, 52, eq, "equipment IO", "#F6EFE6", "#B9A68E")
    for j, p in enumerate(prims):
        fb(g, 1320 + j * 122, cy - 26, 114, 52, p, "primitive type")
g = prog.group("FORTE runtime")
y0, y1 = ROWS["pi"]
rect(g, 1110, y0 + 10, 450, 90, "#F4F6F8", "#C9CDD0", 1.5, 4)
text(g, 1126, y0 + 14, 420, 82, "<b>FORTE 3.3</b>, built for the Pi<br><font color='#6E777B' style='font-size:14px'>"
     "the block types compiled in: the module library and the module's primitives and equipment</font>", 15, INK)

LINK = f"endArrow=none;html=1;strokeColor={GREY};strokeWidth=1.5;dashed=1;"
for key, (xa, xb), (xc, xd) in [("module", (470, 556), (1042, 1106)), ("axis", (480, 666), (1042, 1152)),
                                ("pump", (480, 666), (1042, 1152)), ("scale", (480, 666), (1042, 1152)),
                                ("pi", (480, 666), (1042, 1106))]:
    y0, y1 = ROWS[key]
    cy = (y0 + y1) / 2 if key != "module" else 165
    g = links.group(f"Links {key}")
    line(g, [(xa, cy), (xb, cy)], LINK)
    if key != "pi":
        line(g, [(xc, cy), (xd, cy)], LINK)
    else:
        line(g, [(480, cy), (660, cy)], LINK)
        line(g, [(1046, cy), (1106, cy)], LINK)
page("03 The filling module: physical and digital", phys, aas_l, prog, links)

# ==== 04 The IEC 61499 program's structure (module rules) =========================================
mr = Copied("slides.drawio", 8, "frame")
for ids, name in [(("c5", "c6"), "OPC UA server"), (("c7", "c8"), "Occupation"),
                  (("c9", "c10", "c11", "c12", "c13"), "Module state machine"),
                  (("c14", "c15", "c16", "c17", "c18", "c19", "c20"), "Module level skills"),
                  (("c21", "c22", "c23", "c24"), "Skill primitives"), (("c25", "c26", "c27", "c28"), "Equipment IO"),
                  (("c29", "c30"), "Bracket: the same in every module"), (("c31", "c32"), "Bracket: the module's own")]:
    lid = mr.layer(name)
    cells = mr.pick(ids=set(ids))
    mr.move(cells, lid)
    mr.group(cells, name, lid)
mr.group(mr.pick(ids={"c2", "c3", "c4"}), "Program frame and title")
copied_page("04 The IEC 61499 program: the module rules", mr)


# ==== 05, 06 The filling module in motion: with an orchestrator, with agents ===========================
def motion(agents):
    MM, DOWN = 6.5, 40 * 6.5
    L = []

    def layer(name, visible=True):
        n = Node(name, visible)
        L.append(n)
        return n

    WIRE = f"endArrow=none;html=1;strokeColor={GREY};strokeWidth=1.5;rounded=1;"
    base = layer("module")
    table = base.group("Planar table")
    rect(table, 50, 786, 720, 10, "#E6E8EA")
    rect(table, 40, 740, 740, 46, "#33393C", "#1F2325", 1.5, 4)
    text(table, 56, 744, 300, 38, "Planar table", 15, "#C9CDD0", True)
    frame = base.group("Frame")
    rect(frame, 460, 130, 297, 610, "#F4F5F6", "#C9CDD0", 1.5)
    rect(frame, 460, 130, 22, 610, "#9AA2A6", "#7D868B")
    rect(frame, 735, 130, 22, 610, "#9AA2A6", "#7D868B")
    rect(frame, 460, 130, 297, 40, "#8E979C", "#7D868B")
    lid = frame.group("Lid")
    rect(lid, 446, 92, 325, 40, ORANGE, ORANGE_D, 1.5, 12)
    text(lid, 446, 92, 325, 40, "Filling module", 20, "#FFFFFF", True, "center")
    axis = base.group("Linear axis")
    rect(axis, 519, 222, 62, 10, "#8E979C", "#7D868B")
    rect(axis, 525, 232, 50, 440, "#D3D7DA", "#8E979C", 1.5)
    rect(axis, 546, 238, 8, 428, "#7D868B", "none", 1, 0, "fillStyle=hatch;")
    motor = axis.group("Stepper motor")
    rect(motor, 514, 672, 72, 66, "#3A3F42", "#252B2D", 1.5, 6)
    text(motor, 514, 676, 72, 58, "Stepper<br>Nema 23", 12, "#FFFFFF", True, "center")
    switch = axis.group("Home switch")
    rect(switch, 578, 236, 22, 18, "#3A3F42", "#252B2D", 1, 3)
    line(switch, [(584, 254), (576, 264)], f"endArrow=none;html=1;strokeColor={INK};strokeWidth=2;")
    text(switch, 606, 252, 110, 24, "Home switch", 14)
    text(axis, 590, 340, 124, 40, "Linear axis<br>60 mm travel", 14)
    pi = base.group("Raspberry Pi")
    rect(pi, 596, 440, 112, 72, GREEN, GREEN_D, 1.5, 8)
    rect(pi, 636, 452, 32, 26, "#2E3A2A", "none", 1, 3)
    text(pi, 596, 482, 112, 26, "Pi 5 · FORTE", 13, "#FFFFFF", True, "center")
    wires = base.group("Wires")
    line(wires, [(708, 456), (718, 456), (718, 245), (600, 245)], WIRE)
    line(wires, [(708, 496), (724, 496), (724, 690), (586, 690)], WIRE)
    scale = base.group("Scale")
    box(scale, 596, 584, 112, 72, f"rounded=1;arcSize=8;html=1;fillColor=#FFFFFF;strokeColor={GREY};strokeWidth=1.5;dashed=1;")
    rect(scale, 606, 594, 92, 30, INK, "none", 1, 6)
    text(scale, 606, 594, 92, 30, "0.0 g", 16, "#9FD18B", True, "center", "Courier New")
    text(scale, 596, 626, 112, 26, "Scale · simulated", 12, GREY, False, "center")

    shuttle = layer("shuttle and vial").group("Shuttle with vial")
    rect(shuttle, 330, 722, 140, 16, "#E4E7E9", "#9AA2A6", 1.5, 30)
    vial = shuttle.group("Vial")
    rect(vial, 374, 624, 52, 98, "#F3F8FC", "#7F9DB8", 2, 12)
    rect(vial, 386, 607, 28, 20, "#F3F8FC", "#7F9DB8", 2)
    rect(vial, 381, 600, 38, 9, "#F3F8FC", "#7F9DB8", 2, 30)
    text(shuttle, 216, 684, 150, 40, "Vial 2 mL<br>on a shuttle", 14, GREY, False, "right")

    carriage = layer("carriage").group("Carriage")
    rect(carriage, 512, 268, 76, 62, "#8A9399", "#5C6366", 1.5, 6)
    rect(carriage, 430, 286, 84, 22, "#A7AFB4", "#5C6366", 1.5)
    pump = carriage.group("Pump")
    rect(pump, 366, 262, 68, 68, BLUE, BLUE_D, 1.5, 10)
    box(pump, 384, 270, 32, 32, f"ellipse;html=1;fillColor=#FFFFFF;strokeColor={BLUE_D};strokeWidth=2;")
    box(pump, 396, 282, 8, 8, f"ellipse;html=1;fillColor={BLUE_D};strokeColor=none;")
    text(pump, 366, 312, 68, 18, "Pump", 11, "#FFFFFF", True, "center")
    needle = carriage.group("Needle")
    rect(needle, 393, 330, 14, 10, "#5C6366", "none")
    rect(needle, 398, 340, 4, 60, "#B8BEC2", "#6E777B", 1)

    lit = layer("home switch pressed", False).group("AtHome")
    ring(lit, 572, 230, 34, 30, GREEN, 30)
    text(lit, 610, 220, 90, 22, "AtHome", 13, GREEN, True)
    pulses = layer("step pulses", False).group("Step pulses")
    pts = []
    for i, x in enumerate(604 + 8 * k for k in range(11)):
        pts += [(x, 686), (x, 674)] if i % 2 == 0 else [(x, 674), (x, 686)]
    line(pulses, pts, f"endArrow=none;html=1;strokeColor={ORANGE};strokeWidth=2.5;")
    text(pulses, 600, 696, 110, 22, "step pulses", 13, ORANGE, True)
    ring(pulses, 506, 664, 88, 82, ORANGE)
    travel = layer("travel 40 mm", False).group("Travel 40 mm")
    line(travel, [(340, 400), (340, 400 + DOWN)],
         f"html=1;strokeColor={ORANGE};strokeWidth=2;startArrow=block;endArrow=block;startSize=8;endSize=8;")
    text(travel, 262, 400 + DOWN / 2 - 14, 72, 28, "40 mm", 15, ORANGE, True, "right")
    pump_on = layer("pump running", False).group("Pump running")
    ring(pump_on, 358, 254 + DOWN, 84, 84, ORANGE, 14)
    line(pump_on, [(400, 400 + DOWN), (400, 676)], f"endArrow=none;html=1;strokeColor=#8DB8DE;strokeWidth=3;")
    rect(layer("liquid", False), 378, 668, 44, 50, "#8DB8DE", "none", 1, 14)
    weight = layer("weight 2.0 g", False).group("Weight 2.0 g")
    rect(weight, 606, 594, 92, 30, INK, "none", 1, 6)
    text(weight, 606, 594, 92, 30, "2.0 g", 16, "#9FD18B", True, "center", "Courier New")
    ring(weight, 590, 578, 124, 84, ORANGE, 10)

    X0, W = 830, 650
    panels = layer("state machines")
    if not agents:
        orch = panels.group("Orchestrator")
        rect(orch, X0, 24, 730, 76, OPC_FILL, BLUE, 2, 10)
        mon = orch.group("Screen")
        rect(mon, X0 + 20, 38, 58, 40, "#FFFFFF", BLUE_D, 2, 6)
        rect(mon, X0 + 42, 78, 14, 8, BLUE_D)
        rect(mon, X0 + 34, 86, 30, 4, BLUE_D)
        text(orch, X0 + 96, 30, 400, 34, "Orchestrator", 22, INK, True)
        text(orch, X0 + 96, 60, 620, 30, "the HMI, modlink, later an agent: commands to the module over OPC UA", 14)
    mod = panels.group("Module state machine")
    rect(mod, X0, 180, W, 170, "#F4F4F4", "#C9CDD0", 1.5, 6)
    text(mod, X0 + 22, 192, 380, 36, "Module · PackML", 21, INK, True)
    pill(mod, 1300, 190, 162, 36, "free", size=16, color=GREY, stroke="#9AA2A6")
    PACKML = ["Stopped", "Resetting", "Idle", "Starting", "Execute"]
    PW, PG = 112, 10
    px = [X0 + 22 + i * (PW + PG) for i in range(5)]
    states = mod.group("PackML states")
    for x, s in zip(px, PACKML):
        pill(states, x, 262, PW, 52, s, size=17)
    sk = panels.group("Dispensing skill")
    rect(sk, X0, 372, W, 330, "#DDEFE4", "#C9CDD0", 1.5, 4)
    text(sk, X0 + 22, 384, 420, 36, "Dispensing · a skill", 21, INK, True)
    SKILL = ["Idle", "Running", "Succeeded"]
    SW, SG = 190, 18
    sx = [X0 + 22 + i * (SW + SG) for i in range(3)]
    sstates = sk.group("Skill states")
    for x, s in zip(sx, SKILL):
        pill(sstates, x, 440, SW, 48, s)
    STEPS = [("NeedleDown", "MoveAxis 40 mm"), ("Dispense", "Pump runs"), ("Home", "up to the switch"),
             ("Weigh", "Scale weighs")]
    TW, TG = 140, 14
    tx = [X0 + 22 + i * (TW + TG) for i in range(4)]
    steps = sk.group("Steps")
    text(steps, X0 + 22, 506, 300, 22, "Steps, one after another", 13)
    for i, (x, (s, sub)) in enumerate(zip(tx, STEPS)):
        pill(steps, x, 532, TW, 52, s, size=17)
        text(steps, x - 6, 590, TW + 12, 30, sub, 14, GREY, False, "center")
        if i:
            line(steps, [(x - TG, 558), (x, 558)],
                 f"html=1;strokeColor={GREEN};strokeWidth=2.5;endArrow=block;endSize=5;endFill=1;")
    text(sk, X0 + 22, 640, W - 44, 48, "Each step is a primitive: one command on one equipment item, "
         "until a sensor, timer or timeout", 14)
    text(panels, X0, 716, 730, 50, "Every command is answered at once: Accepted, ErrorID (True, 0 is accepted).<br>"
         "An illustration of the order of things, not a recording.", 13)

    if agents:
        ag = layer("agents")
        g = ag.group("Resource agent: the filling module")
        rect(g, X0, 24, 730, 76, OPC_FILL, BLUE, 2, 10, "dashed=1;")
        text(g, X0 + 22, 30, 520, 34, "Resource agent · Filling module", 22, INK, True)
        text(g, X0 + 22, 60, 690, 30, "bids for process steps; once chosen, runs its skill over OPC UA · planned", 14)
        arrow(g, [(850, 100), (850, 112), (773, 112)], GREY, 1.5, True)
        g = ag.group("Product agent: the vial")
        rect(g, 40, 24, 380, 76, PROD_FILL, PURPLE, 2, 10, "dashed=1;")
        text(g, 60, 30, 340, 34, "Product agent · the vial", 22, INK, True)
        text(g, 60, 60, 340, 30, "asks for each process step, chooses a bid", 14)
        arrow(g, [(250, 100), (250, 660), (372, 660)], GREY, 1.5, True)
        g = ag.group("Transport agent: the shuttle")
        rect(g, 40, 430, 190, 70, OPC_FILL, BLUE, 2, 10, "dashed=1;")
        text(g, 52, 434, 170, 30, "Transport agent", 17, INK, True)
        text(g, 52, 462, 170, 32, "the shuttle (xbot)", 14)
        arrow(g, [(120, 500), (120, 730), (328, 730)], GREY, 1.5, True)
        MSG = [("01 call for proposals", "→", "Call for proposals: Filling 2.0 mL", PURPLE),
               ("02 proposal", "←", "Proposal: Dispensing, now", BLUE),
               ("03 accept", "→", "Accept", PURPLE),
               ("04 move to filling", "↓", "Move me to Filling", PURPLE),
               ("05 arrived", "↑", "Arrived", BLUE),
               ("06 done", "←", "Done: 2.0 mL, 2.0 g", BLUE),
               ("07 move on", "↓", "Move me on", PURPLE)]
        for key, d, msg, color in MSG:
            g = layer(f"message {key}", False).group(msg)
            if d in "→←":
                pts = [(424, 62), (826, 62)] if d == "→" else [(826, 62), (424, 62)]
                arrow(g, pts, color, 3, label=msg, size=15, above=True)
            else:
                pts = [(100, 102), (100, 426)] if d == "↓" else [(100, 426), (100, 102)]
                arrow(g, pts, color, 3)
                rect(g, 110, 240, 128, 46, "#FFFFFF", color, 2, 20, "", f"<b>{msg}</b>", 13)
    ACT = "Resource agent" if agents else "Orchestrator"

    HL = (f"rounded=1;arcSize=50;html=1;fillColor={RUN_FILL};strokeColor={GREEN};strokeWidth=3;fontFamily=Arial;"
          f"fontSize=17;fontColor={INK};fontStyle=1;")
    for x, s in zip(px, PACKML):
        box(layer(f"PackML {s}", False), x, 262, PW, 52, HL, s)
    pill(layer("occupied", False), 1300, 190, 162, 36, "occupied · s1", OPC_FILL, BLUE, 2.5, 16, INK, True)
    for x, s in zip(sx, SKILL):
        box(layer(f"skill {s}", False), x, 440, SW, 48, HL.replace("fontSize=17", "fontSize=18"), s)
    for x, (s, _) in zip(tx, STEPS):
        box(layer(f"step {s}", False), x, 532, TW, 52,
            HL.replace(RUN_FILL, STEP_FILL).replace(f"strokeColor={GREEN}", f"strokeColor={ORANGE}"), s)
    ARROW = f"html=1;strokeColor={BLUE};strokeWidth=3;endArrow=block;endSize=7;endFill=1;rounded=1;"
    TO = {"occupation": ([(1381, 100), (1381, 190)], (1196, 114, 176, 56)),
          "module": ([(1000, 100), (1000, 180)], (840, 114, 150, 56)),
          "skill": ([(1530, 100), (1530, 404), (1480, 404)], (1290, 382, 176, 50))}
    COMMANDS = [("skill", "Start(s1, 2.0 mL)", "False, 5 · not occupied", ORANGE),
                ("occupation", "Occupy(s1)", "True, 0", BLUE),
                ("module", "Reset(s1)", "True, 0 · homes", BLUE),
                ("module", "Start(s1)", "True, 0", BLUE),
                ("skill", "Start(s1, 2.0 mL)", "True, 0", BLUE),
                ("occupation", "Release(s1)", "True, 0", BLUE)]
    if agents:
        COMMANDS = COMMANDS[1:]      # the agent occupies first: no refused start
    for i, (to, cmd, answer, color) in enumerate(COMMANDS, 1):
        path, (cx, cy, cw, ch) = TO[to]
        g = layer(f"command {i:02d} {cmd.split('(')[0]} to {to}", False).group(f"{ACT}: {cmd} → {answer}")
        line(g, path, ARROW.replace(BLUE, color))
        box(g, cx, cy, cw, ch, f"rounded=1;arcSize=20;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor={color};"
            f"strokeWidth=2;fontFamily=Arial;fontSize=15;fontColor={INK};",
            f"<b>{cmd}</b><br><font style=\"font-size:13px\" color=\"{GREY}\">→ {answer}</font>")
    return L


page("05 The filling module in motion: an orchestrator", *motion(False))
page("06 The filling module in motion: agents bid (planned)", *motion(True))

# ==== 07 Product, process and resource AAS ========================================================
P = [("Product AAS", "product", 40, ["Production Sequence", "Process Parameters", "Bill of Material",
                                     "Required Capabilities"]),
     ("Process AAS", "process", 590, ["Step Bindings", "Process Information", "Validation", None]),
     ("Resource AAS", "resource", 1140, ["Skills", "Asset Interfaces", "Variables", "Offered Capabilities"])]
ppr_layers = []
ROW_Y = [430, 504, 578, 652]
for title, key, x, sms in P:
    L = Node(title)
    g = shell(L, x, 50, 380, 350, title, 34, picture=PIC[key][0], pic_size=PIC[key][1], name=title)
    sg = L.group(f"{title} submodels")
    for y, s in zip(ROW_Y, sms):
        if s:
            sm_bar(sg, x, y, 380, 58, s, 21)
    ppr_layers.append(L)
for name, pts, label, dashed in [
        ("recipe steps", [(420, 459), (590, 459)], "the steps", False),
        ("each step bound to a skill", [(970, 459), (1140, 459)], "a module's skill", False),
        ("required matches offered", [(420, 681), (1140, 681)], "matches: same meaning, value in range", True),
        ("offered realized by a skill", [(1520, 681), (1550, 681), (1550, 459), (1520, 459)], "", False)]:
    L = Node(f"link: {name}")
    g = L.group(name)
    arrow(g, pts, INK, 2.5, dashed, label, 17, label_color=INK, above=True)
    if name.startswith("offered"):
        box(g, 1508, 558, 120, 24, f"text;html=1;rotation=-90;fontFamily=Arial;fontSize=14;fontColor={INK};"
            "align=center;verticalAlign=middle;strokeColor=none;fillColor=none;", "realized by")
    ppr_layers.append(L)
page("07 Product, process and resource AAS", *ppr_layers)

# ==== 08 Equipment and skill hierarchies (copied) ==================================================
def tree_page(file, idx, name):
    cp = Copied(file, idx, "AAS trees")
    cp.icons_to_shells(20)
    for c in cp.cells:                      # ARSO 0.14: Variables in place of Operational Data
        if c.get("value") == "OperationalData":
            c.set("value", "Variables")
    tl = cp.layer("page title (the slide has its own)")
    tcells = cp.pick(where=lambda c: geo_box(c) and geo_box(c)[1] < 120 and not c.get("edge"))
    cp.move(tcells, tl)
    cp.group(tcells, "Title, subtitle, tag", tl)
    for p in cp.panels():
        b = geo_box(p)
        cells = cp.pick(area=b)
        if cells:
            cp.group(cells, f"Panel {label_of(next((c for c in cells if (c.get('value') or '').startswith('<b>')), p))}")
    copied_page(name, cp)


tree_page("skill-hierarchies.drawio", 0, "08 Equipment and skill hierarchies in the AAS")

# ==== 09 Primitive and composite skills ===========================================================
mod_l, comp_l = Node("module AAS: a composite skill"), Node("component AASs: primitive skills")
g = shell(mod_l, 60, 30, 150, 129, "Module", 20, name="Filling module AAS")
text(mod_l, 230, 40, 530, 110, "<b>Composite</b>: steps that run the components' skills.<br>"
     "<font color='#6E777B'>No type of its own: FORTE creates it online from instances.</font>", 18, INK)
card = mod_l.group("Skills: Dispensing (composite)")
rect(card, 60, 186, 700, 690, "#F4F4F4", "#C9CDD0", 1.5, 3)
text(card, 84, 196, 420, 40, "Skills · Dispensing", 24, INK, True)
pill(card, 600, 200, 136, 34, "Composite", "#FFFFFF", AAS, 2, 15, AAS, True)
rect(card, 84, 252, 320, 46, "#FFFFFF", BLUE, 2, 12, "", "<b>Start</b> · Volume 0.5–10 mL", 16)
rect(card, 418, 252, 318, 46, "#FFFFFF", BLUE, 2, 12, "", "<b>Result</b> · Weight (g)", 16)
text(card, 84, 312, 300, 26, "Steps, in order", 15)
STEP_CARDS = [("NeedleDown", "runs LinearAxis · MoveAxis", "Position = 40.0, a value"),
              ("Dispense", "runs Pump · Dispense", "Volume ← Start / Volume"),
              ("Home", "runs LinearAxis · Home", ""),
              ("Weigh", "runs Scale · Weigh", "Weight → the result")]
SC_Y = [344, 476, 608, 740]
for (n, runs, bind), y in zip(STEP_CARDS, SC_Y):
    s = card.group(f"Step {n}")
    rect(s, 84, y, 652, 110, "#FFFFFF", INK, 1.5, 8)
    text(s, 104, y + 8, 300, 32, n, 21, INK, True)
    text(s, 104, y + 40, 600, 28, runs, 16, INK)
    if bind:
        text(s, 104, y + 70, 600, 28, bind, 16, GREY)
for y in SC_Y[1:]:
    arrow(card, [(130, y - 22), (130, y)], GREEN, 2.5)

text(comp_l, 1000, 740, 560, 110, "<b>Primitive</b>: one command on one component, until a sensor, "
     "a timer or a timeout.<br><font color='#6E777B'>A block type, compiled into FORTE.</font>", 18, INK)
PRIM = {}
for label, aasname, y, skills in [("LinearAxis", "FillingLinearAxisAAS", 30, [("Home", "up until AtHome"),
                                                                           ("MoveAxis", "Position 0–60 mm")]),
                                  ("Pump", "FillingPumpAAS", 290, [("Dispense", "Volume, FlowRate")]),
                                  ("Scale", "FillingScaleAAS", 470, [("Tare", ""), ("Weigh", "out: Weight")])]:
    cg = comp_l.group(f"{label} AAS")
    shell(cg, 1000, y, 96, 83, label, 12, name=f"{label} shell")
    text(cg, 1110, y + 26, 300, 30, aasname, 15, GREY)
    for j, (sk, sub) in enumerate(skills):
        sy = y + 96 + j * 74
        k = cg.group(f"Skill {sk}")
        rect(k, 1110, sy, 430, 62, "#FFFFFF", INK, 1.5, 8)
        text(k, 1128, sy + 4, 200, 30, sk, 19, INK, True)
        text(k, 1128, sy + 32, 260, 26, sub, 14, GREY)
        pill(k, 1420, sy + 16, 104, 30, "Primitive", "#FFFFFF", AAS, 2, 13, AAS, True)
        PRIM[sk] = sy + 31
runs_layers = []
for i, ((n, *_), y, target, xv) in enumerate(zip(STEP_CARDS, SC_Y, ["MoveAxis", "Dispense", "Home", "Weigh"],
                                                  [870, 900, 930, 960])):
    L = Node(f"runs {i + 1}: {n} → {target}", True)
    arrow(L.group(f"{n} runs {target}"), [(736, y + 55), (xv, y + 55), (xv, PRIM[target]), (1108, PRIM[target])],
          GREEN, 2.5)
    runs_layers.append(L)
page("09 Primitive and composite skills in the AAS", mod_l, comp_l, *runs_layers)

# ==== 10 From the AAS to function blocks: modsync ==================================================
ent = Node("AAS: the skill's entries")
g = shell(ent, 40, 22, 96, 83, "AAS", 16, name="Filling module AAS")
text(ent, 150, 30, 330, 70, "<b>FillingModuleAAS</b><br><font color='#6E777B'>Skills · Dispensing</font>", 19, INK)
ENTRIES = [("e1", 0, "Dispensing · Composite"), ("e2", 0, "Start variable · Volume 0.5–10 mL"),
           ("e3", 0, "Step NeedleDown → MoveAxis"), ("e4", 1, "Binding · Position = 40.0"),
           ("e5", 0, "Step Dispense → Dispense"), ("e6", 1, "Binding · Volume ← Start/Volume"),
           ("e7", 0, "Step Home → Home"), ("e8", 0, "Step Weigh → Weigh"),
           ("e9", 0, "Order · 0, 1, 2, 3"), ("e10", 0, "Result · Weight ← Weigh"),
           ("e11", 0, "Deployment · Described")]
EY = {}
for i, (k, ind, label) in enumerate(ENTRIES):
    y = 124 + i * 64
    EY[k] = y + 24
    rect(ent.group(f"Entry {label}"), 40 + ind * 30, y, 430 - ind * 30, 48, "#E6F3F2", AAS, 2, 16, "", label, 16,
         INK, False, "left")

fr = Node("FORTE: the program")
g = fr.group("FORTE frame")
rect(g, 910, 22, 650, 856, "#FFFFFF", GREEN, 2, 2)
text(g, 930, 30, 600, 36, "FORTE on the Pi · subapplication Dispensing", 21, INK, True)
text(g, 930, 64, 600, 24, "modsync creates these blocks while the module runs", 14)


def fbk(node, x, y, w, h, name, typ, fill=FB_FILL):
    k = node.group(f"Block {name}")
    rect(k, x, y, w, h, fill, FB_STROKE, 1.5, 6)
    text(k, x, y + 6, w, 24, name, 16, INK, True, "center")
    text(k, x, y + 32, w, 20, typ, 12, GREY, False, "center")


maps = []


def mapping(n, title, entries, build, targets):
    """Two layers: the blocks it creates (shown in the still), and the arrow from the entry (animation)."""
    blocks = Node(f"map {n} · created: {title}")
    build(blocks.group(title))
    arrows = Node(f"map {n} · arrow: {title}", False)
    g = arrows.group(f"{title}: from the AAS through modsync")
    for i, (k, t) in enumerate(zip(entries, targets)):
        xv = 880 + 4 * n
        if len(t) == 3:                      # come down onto the block from above
            tx, ty, above = t
            arrow(g, [(470, EY[k]), (xv, EY[k]), (xv, above), (tx, above), (tx, ty)], GOLD, 2.5)
        else:
            tx, ty = t
            arrow(g, [(470, EY[k]), (xv, EY[k]), (xv, ty), (tx, ty)], GOLD, 2.5)
    for k in entries:
        ind = dict((e[0], e[1]) for e in ENTRIES)[k]
        ring(g, 36 + ind * 30, EY[k] - 28, 438 - ind * 30, 56, GOLD, 30)
    maps.append((blocks, arrows))


mapping(1, "skill → subapplication with Control, UaStart", ["e1"],
        lambda g: (fbk(g, 940, 110, 180, 60, "Control", "SKILL_Core"),
                   fbk(g, 1140, 110, 180, 60, "UaStart", "SERVER · OPC UA Start")), [(938, 140)])
mapping(2, "Start variable → parameter latch", ["e2"],
        lambda g: fbk(g, 1340, 110, 196, 60, "Volume", "SKILL_Param_LREAL"), [(1438, 108, 98)])


def steps_blocks(g):
    rect(g, 930, 220, 610, 300, "#F7FAF5", GREEN, 1.5, 3, "dashed=1;")
    text(g, 946, 226, 300, 26, "Execute", 15, INK, True)
    for i, (n, t) in enumerate([("NeedleDown", "SK_MoveAxis"), ("Dispense", "SK_Dispense"), ("Home", "SK_Home"),
                                ("Weigh", "SK_Weigh")]):
        fbk(g, 946 + i * 148, 300, 134, 62, n, t)


mapping(3, "steps → instances of the primitives", ["e3", "e5", "e7", "e8"], steps_blocks,
        [(1013, 298, 282), (1161, 298, 282), (1309, 298, 282), (1457, 298, 282)])
mapping(4, "binding value → input value", ["e4"],
        lambda g: text(g, 946, 366, 134, 26, "Position 40.0", 14, INK, True, "center"), [(944, 379)])


def source_conn(g):
    arrow(g, [(1438, 170), (1438, 270), (1161, 270), (1161, 298)], BLUE, 2, True)
    text(g, 1186, 248, 240, 22, "Volume.Value → Dispense.Volume", 12, BLUE)


mapping(5, "binding source → data connection", ["e6"], source_conn, [(1150, 270)])


def chain(g):
    for i in range(3):
        x = 946 + i * 148 + 134
        arrow(g, [(x, 331), (x + 14, 331)], GREEN, 3)
    text(g, 946, 410, 580, 26, "SUCCESS → START, step by step", 14, GREEN, True, "center")


mapping(6, "order → event chain", ["e9"], chain, [(944, 423)])
mapping(7, "result → publisher",
        ["e10"], lambda g: (fbk(g, 1340, 560, 196, 60, "PubResults", "PUBLISH · OPC UA"),
                            arrow(g, [(1513, 362), (1513, 558)], BLUE, 2, True)), [(1338, 590)])
g_ua = Node("OPC UA nodes")
g = g_ua.group("What the program publishes")
text(g, 940, 660, 600, 200, "<b>OPC UA, below /Objects/Filling</b><br>Skills/Dispensing/Start(Session, Volume)<br>"
     "Skills/Dispensing/State, ErrorID<br>Skills/Dispensing/Parameters/Volume<br>Skills/Dispensing/Results/Weight",
     14, INK, False, "left", "Arial", "top")

ms = Node("modsync")
g = ms.group("modsync reconfigure")
rect(g, 510, 22, 370, 856, "#FBF5E6", GOLD, 2.5, 3)
text(g, 530, 30, 330, 36, "modsync reconfigure", 22, INK, True)
text(g, 530, 64, 330, 24, "the AAS is the target; the program follows", 14)
for i, s in enumerate(["Read the AAS", "Compare with the running program", "Compile by the module rules",
                       "Create online:<br>CREATE · CONNECT · WRITE", "Read back and verify",
                       "Record: Deployment = Built"]):
    y = 110 + i * 126
    st = g.group(f"Stage {i + 1}")
    rect(st, 530, y, 330, 86, "#FFFFFF", GOLD, 2, 10, "", f"<b>{i + 1}</b>&nbsp;&nbsp;{s}", 17, INK, False, "left")
    if i:
        arrow(st, [(695, y - 40), (695, y)], GOLD, 2.5)
layers10 = [ent, fr] + [m[0] for m in maps] + [g_ua] + [m[1] for m in maps] + [ms]
page("10 From the AAS to function blocks: modsync", *layers10)

# ==== 11 The mapping rules ==========================================================================
rules = Node("rules")
text(rules, 60, 16, 600, 36, "In the AAS", 22, AAS, True)
text(rules, 790, 16, 700, 36, "In the IEC 61499 program", 22, GREEN, True)
RULES = [("A <b>composite</b> skill <i>Dispensing</i>", "A <b>subapplication</b> of instances: no new type, created online"),
         ("A <b>primitive</b> skill <i>MoveAxis</i>", "A <b>block type</b> <i>SK_MoveAxis</i>, compiled into FORTE"),
         ("A <b>Start variable</b> <i>Volume</i>, with limits", "A <b>parameter latch</b>: limits as values, an argument of Start"),
         ("A <b>step</b> <i>NeedleDown</i> that runs <i>MoveAxis</i>", "An <b>instance</b> <i>NeedleDown</i> of <i>SK_MoveAxis</i>"),
         ("A <b>binding</b> to a value <i>40.0</i>", "The <b>input's value</b> <i>NeedleDown.Position</i>"),
         ("A <b>binding</b> to a source <i>Start/Volume</i>", "A <b>data connection</b> <i>Volume → Dispense.Volume</i>"),
         ("The <b>order</b> of the steps", "The <b>event chain</b> SUCCESS → START"),
         ("<b>Parallel</b> and <b>decision</b> steps", "Library blocks: <b>Join</b>, <b>Condition</b>, <b>Merge</b>")]
rule_layers = [rules]
for i, (a, b) in enumerate(RULES):
    y = 64 + i * 74
    L = Node(f"rule {i + 1}")
    g = L.group(f"Rule {i + 1}")
    rect(g, 60, y, 640, 60, "#E6F3F2", AAS, 2, 14, "", a, 18, INK, False, "left")
    arrow(g, [(708, y + 30), (782, y + 30)], INK, 2.5)
    rect(g, 790, y, 750, 60, RUN_FILL, GREEN, 2, 14, "", b, 18, INK, False, "left")
    rule_layers.append(L)
L = Node("keys and limits")
g = L.group("Names are the keys")
rect(g, 60, 664, 1480, 84, "#F4F4F4", "#C9CDD0", 1.5, 8, "",
     "<b>Names are the keys.</b> A skill's idShort names its subapplication, a step's NodeId its instance; the OPC UA "
     "paths are made from the same names. So the program can be read back into the AAS's terms.", 17, INK, False, "left")
g = L.group("Online or restart")
rect(g, 60, 762, 1480, 100, "#FBF5E6", GOLD, 1.5, 8, "",
     "<b>Online, while it runs:</b> a value (WRITE), a new composite skill (CREATE, CONNECT).<br>"
     "<b>Restart:</b> a new primitive or new IO (a FORTE build), and removing or reordering what runs.", 17, INK,
     False, "left")
rule_layers.append(L)
page("11 The mapping rules", *rule_layers)

# ==== Backup pages ==================================================================================
tree_page("skill-hierarchies.drawio", 1, "Backup: from recipe to process")
mp = Copied("mapping.drawio", 0, "figure")
mp.icons_to_shells(20)
tl = mp.layer("page title (the slide has its own)")
tc = mp.pick(where=lambda c: geo_box(c) and geo_box(c)[1] < 120 and not c.get("edge"))
mp.move(tc, tl)
mp.group(tc, "Title, subtitle, tag", tl)
for p in mp.panels(400, 200):
    cells = mp.pick(area=geo_box(p))
    mp.group(cells, f"Panel at {geo_box(p)[0]:g},{geo_box(p)[1]:g}")
copied_page("Backup: a skill in the AAS and the blocks it is", mp)

write(sys.argv[2], pages)
print(len(pages), "pages")
for n, w, h, _ in pages:
    print(f"  {n}  ({w}×{h})")
