"""Builds docs/presentation/deck.drawio: every figure of the talk, one page per slide, in story order.
New pages are drawn here; earlier figures are copied from docs/figures and regrouped."""
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

    def scale(self, s, dx, dy):
        """Scale every cell by s about the page's origin, then move it by (dx, dy)."""
        for c in self.cells:
            geo = c.find("mxGeometry")
            if geo is None or c.get("parent") not in [l.get("id") for l in self.layers]:
                continue
            if c.get("edge"):
                for p in geo.iter("mxPoint"):
                    p.set("x", f"{float(p.get('x', 0)) * s + dx:g}"), p.set("y", f"{float(p.get('y', 0)) * s + dy:g}")
            else:
                geo.set("x", f"{float(geo.get('x', 0)) * s + dx:g}"), geo.set("y", f"{float(geo.get('y', 0)) * s + dy:g}")
                geo.set("width", f"{float(geo.get('width')) * s:g}"), geo.set("height", f"{float(geo.get('height')) * s:g}")

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

# ==== 03b The production system, layer by layer (the illustrated layers, one draw.io layer per plane) ====
pl = Copied("module-tools.drawio", 6, "the line")
num = lambda c: int(c.get("id")[1:])
pl.cells = [c for c in pl.cells if 4 <= num(c) <= 190]          # without the page title, side boxes, legend
PLANES = [(4, 47, "The line: table, shuttles, stations, robots"),
          (48, 93, "Digital assets: each module's parts and its Pi"),
          (94, 114, "Behaviour · IEC 61499: the modules' programs on FORTE"),
          (115, 157, "AAS models and orchestration"),
          (158, 190, "HMI, MES, planning and scheduling")]
# A line belongs to the plane of its upper end: it appears with the thing it reaches up to.
UP = {**{n: 1 for n in range(44, 48)}, **{n: 2 for n in range(90, 94)},
      **{n: 3 for n in [95, 96, 97, 98, 99, 100, 113, 114]}, **{n: 4 for n in (155, 156, 157)}}
plane_of = lambda c: UP.get(num(c), next(k for k, (a, b, _) in enumerate(PLANES) if a <= num(c) <= b))
for k, (a, b, name) in enumerate(PLANES):
    lid = "1" if k == 0 else pl.layer(name.split(":")[0])
    cells = [c for c in pl.cells if plane_of(c) == k]
    pl.move(cells, lid)
    pl.group(cells, name, lid)
copied_page("03b The production system, layer by layer", pl)

# ==== 03c The production system in layers, isometric ==================================================
# The line's floor is an isometric slab (edges at 30°). Each layer is a plane over the row of stations,
# raised RISE above the one below; a plane is shallower (DEPTH) than RISE, so no plane hides what stands
# on the plane below. A thing stands at plane coordinates (a along the line, b across it, in px along the
# axes): what belongs to a station stands straight above it, and the lines between layers are vertical.
# Each line is in the layer of its upper end.
ICON = {c.get("id"): c.get("style") for c in load("module-tools.drawio", 6).find("root")}
LDX, LDY, RISE = 341.5, 894, 240                 # the line drawing's place; the height between two planes
FT = (422.4 + LDX, 205.7 + LDY)                  # the floor's top corner
EA, EB = (0.866, 0.5), (-0.866, 0.5)             # the isometric axes: along the line, across it
A0, A1, B0, B1 = 30, 850, -40, 150               # a plane: from A0 to A1 along, B0 to B1 across
STATIONS = [273, 394, 515, 636]                  # each station's foot, along the line (across: 50)


def iso(a, b, k=0):
    return FT[0] + a * EA[0] + b * EB[0], FT[1] + a * EA[1] + b * EB[1] - k * RISE


def plane(node, k, fill, stroke):
    polygon(node.group("Plane"), [iso(A0, B0, k), iso(A1, B0, k), iso(A1, B1, k), iso(A0, B1, k)], fill, stroke,
            2.5, "fillOpacity=55;")


def icon(node, ids, x, base, w, h):
    """An isometric icon from the detailed figure, standing with its foot at (x, base)."""
    for cid in ids:
        box(node, x - w / 2, base - h, w, h, ICON[cid])


def caption(node, x, y, value, size=30, color=INK, w=300):
    text(node, x - w / 2, y, w, size + 10, value, size, color, True, "center")
    node.items[-1]["xml"] = (lambda f: lambda p, ox, oy: f(p, ox, oy).replace(
        "fillColor=none;", "fillColor=none;labelBackgroundColor=#FFFFFF;"))(node.items[-1]["xml"])


def layer_name(node, k, name, sub, color, at=None):
    g = node.group(f"Name: {name}")
    x, y = at or iso(A0, B1, k)
    text(g, 0, y - 56, x - 24, 52, name, 42, color, True, "right", valign="bottom")
    text(g, 0, y, x - 24, 40, sub, 28, GREY, False, "right")


ln3 = Copied("slides.drawio", 2, "the line")
ln3.cells = [c for c in ln3.cells if 2 <= num(c) <= 41]
ln3.scale(1, LDX, LDY)
ln3.group([c for c in ln3.cells if c.get("parent") == "1"], "The line: table, shuttles, stations, robots")
line_name = Node("name of the line")
layer_name(line_name, 0, "The line", "modules around a maglev table", ORANGE_D, (98.5 + LDX, 392.7 + LDY + 40))
ROOF = 156                                       # a station's height above its foot

assets = Node("digital assets")
plane(assets, 1, "#DCE8F5", BLUE)
layer_name(assets, 1, "Digital assets", "each module's parts and its Pi", BLUE_D)
for k, a in enumerate(STATIONS):
    g = assets.group(f"Module {k + 1}: Pi and parts")
    x, y = iso(a, 50)
    line(g, [(x, y - ROOF), (x, y - RISE)], "endArrow=none;html=1;strokeColor=#B08A4A;strokeWidth=2.5;dashed=1;")
    mx, my = iso(a - 40, 20, 1)
    icon(g, ["c53", "c54"], mx, my + 14, 60, 70)
    px, py = iso(a, 50, 1)
    icon(g, ["c59", "c60"], px, py + 30, 116, 83)

beh = Node("behaviour · IEC 61499")
plane(beh, 2, "#E3F1DA", GREEN)
layer_name(beh, 2, "Behaviour · IEC 61499", "programs on FORTE", GREEN_D)
FORTE_TOP = []
for k, a in enumerate(STATIONS):
    g = beh.group(f"Module {k + 1}: FORTE")
    x, y1 = iso(a, 50, 1)
    _, y2 = iso(a, 50, 2)
    line(g, [(x, y1 - 30), (x, y2)], f"endArrow=none;html=1;strokeColor={GREEN};strokeWidth=2.5;")
    icon(g, ["c104", "c105"], x, y2 + 30, 120, 116)
    FORTE_TOP.append((x, y2 + 30 - 116))

aasl = Node("AAS models and orchestration")
plane(aasl, 3, "#DDF0EE", AAS)
layer_name(aasl, 3, "AAS models and orchestration", "describe, coordinate", "#0F726C")
g = aasl.group("AAS server and the AASs")
x, y = iso(70, 110, 3)
icon(g, ["c141", "c142"], x, y + 30, 96, 130)
SHELL_TOP = {}
for i, lab in enumerate(["Product", "Process", "Resource"]):
    sx, sy = iso(160 + i * 125, 110, 3)
    shell(g, sx - 52, sy - 70, 104, 89, lab, 17, name=f"{lab} AAS")
    SHELL_TOP[lab] = (sx, sy - 70)
cx, cy = iso(70, 110, 3)
caption(g, cx, cy - 150, "AAS server", 32, "#0F726C", 240)
SERVER = iso(410, 110, 3)
tools = {}
for name, a, color in [("modsync", 600, GOLD), ("modlink", 780, BLUE)]:
    g = aasl.group(f"Tool: {name}")
    x, y = iso(a, 110, 3)
    icon(g, ["c172"], x, y + 30, 104, 100)
    caption(g, x, y - 112, name, 30, color, 170)
    tools[name] = (x, y)
g = aasl.group("Links: the tools to the programs, to the AASs")
for k, (fx, fy) in enumerate(FORTE_TOP):
    mx, my = tools["modsync"]
    line(g, [(mx - 20, my + 30), (fx - 20, fy + 20)], f"endArrow=block;endSize=6;html=1;strokeColor={GOLD};strokeWidth=2.5;")
    lx, ly = tools["modlink"]
    line(g, [(lx - 20, ly + 30), (fx + 24, fy + 34)], f"endArrow=block;endSize=6;html=1;strokeColor={BLUE};strokeWidth=2.5;")
for name in ("modsync", "modlink"):
    x, y = tools[name]
    line(g, [(x - 54, y - 30), (SERVER[0] + 54, SERVER[1] - 40)],
         f"endArrow=block;endSize=6;startArrow=block;startSize=6;html=1;strokeColor={INK};strokeWidth=2;")
g = aasl.group("Agents (planned)")
ax, ay = iso(830, -10, 3)
rect(g, ax - 78, ay - 50, 156, 52, "#FFFFFF", INK, 2, 12, "dashed=1;", "<b>Agents</b>", 28, INK)

hmi = Node("HMI, planning and scheduling")
plane(hmi, 4, "#ECE7F4", PURPLE)
layer_name(hmi, 4, "HMI, planning, MES", "plan, change, operate", PURPLE_D)
for name, a, ids, to in [("Planner", 110, ["c170", "c171"], "Process"), ("Skill editor", 320, ["c172", "c173"], "Resource"),
                         ("HMI", 530, ["c172"], "Resource"), ("MES · ERP", 740, ["c170"], None)]:
    live = to is not None
    g = hmi.group(f"Application: {name}")
    x, y = iso(a, 110, 4)
    icon(g, ids, x, y + 30, 112, 106)
    caption(g, x, y - 118, name, 30, PURPLE_D if live else GREY, 210)
    if live:
        tx, ty = SHELL_TOP[to]
        line(g, [(x, y + 34), (tx + (a - 320) * 0.06, ty)],
             f"endArrow=block;endSize=7;html=1;strokeColor={INK};strokeWidth=2.2;dashed=1;")
page("03c The production system in layers", "\n".join(ln3.xml()), line_name, assets, beh, aasl, hmi, w=1620, h=1760)

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
import page10  # noqa: E402


def filling_panel(layer_id, at=(20, 100)):
    """The FillingModuleAAS panel of the hierarchy page, as one group on the given layer."""
    cp = Copied("skill-hierarchies.drawio", 0)
    cp.icons_to_shells(20)
    for c in cp.cells:
        if c.get("value") == "OperationalData":
            c.set("value", "Variables")
    area = (450, 150, 450, 693)
    cells = cp.pick(area=area)
    dx, dy = at[0] - area[0], at[1] - area[1]
    rows = {}
    for c in cells:
        v, b = label_of(c), geo_box(c)
        if not b or c.get("edge"):
            continue
        key = ("Dispensing" if v.startswith("Dispensing") and "Composite" in v else
               "Start" if v == "Start" and b[0] > 410 else v.split(" ")[0] if v.startswith("Step_000") else None)
        if key and key not in rows:
            rows[key] = (at[0] + area[2], b[1] + b[3] / 2 + dy)
    g = cp.group(cells, "FillingModuleAAS (from the hierarchy page)")
    geo = g.find("mxGeometry")
    geo.set("x", f"{float(geo.get('x')) + dx:g}"), geo.set("y", f"{float(geo.get('y')) + dy:g}")
    members = [g] + cells
    for c in members:
        c.set("id", "h" + c.get("id"))
        for attr in ("source", "target"):
            if c.get(attr):
                c.set(attr, "h" + c.get(attr))
        if c is not g:
            c.set("parent", "h" + c.get("parent"))
    g.set("parent", layer_id)
    return "\n".join(ET.tostring(c, encoding="unicode") for c in members), rows


page("10 From the AAS to function blocks: modsync", *page10.build(filling_panel), w=2420)

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

# ==== 12 Matching, a missing effect, replanning, checking again ======================================
RED, RED_FILL, GOOD_FILL = "#C0392B", "#FBE3E1", "#E3F1DA"


def badge(node, cx, cy, mark, fill, r=28, size=34):
    box(node, cx - r, cy - r, 2 * r, 2 * r, f"ellipse;whiteSpace=wrap;html=1;fillColor={fill};strokeColor=#FFFFFF;"
        f"strokeWidth=3;fontFamily=Arial;fontSize={size};fontColor=#FFFFFF;fontStyle=1;", mark)


def two_line(title, sub, size=28, sub_size=21):
    return f"<b>{title}</b><br><font style=\"font-size:{sub_size}px\" color=\"{GREY}\">{sub}</font>"


ROW = {"fill": 110, "new": 232, "stopper": 372, "cap": 492}
base = Node("recipe and capabilities")
g = base.group("Header: the product's recipe")
shell(g, 40, 22, 64, 55, name="Product AAS")
text(g, 118, 26, 420, 48, "The product's recipe", 28, INK, True)
g = base.group("Header: what the modules offer")
shell(g, 1040, 22, 64, 55, name="Resource AASs")
text(g, 1118, 26, 460, 48, "What the modules offer", 28, INK, True)
for key, title, sub in [("fill", "1 · Fill 12 mL", "requires Filling, 12 mL"),
                        ("stopper", "2 · Stopper", "requires Stoppering"), ("cap", "3 · Cap", "requires Capping")]:
    pill(base.group(f"Step {title}"), 40, ROW[key], 460, 100, two_line(title, sub), PROD_FILL, PURPLE, 2.5, 28)
for key, title, sub in [("fill", "Filling · 0.5 to 10 mL", "Filling module, by Dispensing"),
                        ("stopper", "Stoppering", "Stoppering module"), ("cap", "Capping", "Capping module")]:
    pill(base.group(f"Offered: {title}"), 1040, ROW[key], 520, 100, two_line(title, sub), OPC_FILL, BLUE, 2.5, 28)

match = Node("match", False)
for key in ("fill", "stopper", "cap"):
    g = match.group(f"Match {key}")
    cy = ROW[key] + 50
    arrow(g, [(500, cy), (1040, cy)], GREY, 2.5, True)
    if key != "fill":
        badge(g, 770, cy, "✓", GREEN)

missing = Node("missing", False)
g = missing.group("Fill 12 mL: the effect is missing")
badge(g, 770, ROW["fill"] + 50, "✗", RED)
rect(g, 40, 222, 460, 96, RED_FILL, RED, 2, 16, "",
     two_line("Missing: 12 mL into the vial", "Dispensing doses 0.5 to 10 mL", 24, 20), 24, INK, False, "left")

replan = Node("replan", False)
g = replan.group("Replanned: DoubleDose from the primitives")
rect(g, 560, 640, 1000, 220, "#FBF5E6", GOLD, 2.5, 16)
text(g, 590, 652, 940, 40, "<b>Replanned:</b> a new skill from the filling module's primitives", 24, INK)
chips = ["NeedleDown", "Dispense", "Dispense", "Home", "Weigh"]
for i, s in enumerate(chips):
    x = 590 + i * 192
    rect(g, x, 712, 160, 60, STEP_FILL, ORANGE, 2, 14, "", f"<b>{s}</b>", 21, INK)
    if i:
        arrow(g, [(x - 32, 742), (x, 742)], INK, 2)
text(g, 590, 790, 940, 54, "DoubleDose: two doses of up to 10 mL each, so 1 to 20 mL", 21, GREY)
arrow(g, [(1560, 700), (1586, 700), (1586, 282), (1562, 282)], GOLD, 3)
pill(g, 1040, ROW["new"], 520, 100, two_line("Filling · 1 to 20 mL", "by DoubleDose, after a reconfiguration"),
     "#FFFFFF", GOLD, 2.5, 28, dashed=True)

check = Node("check", False)
g = check.group("Checked against the recipe")
arrow(g, [(500, ROW["fill"] + 50), (1040, ROW["new"] + 50)], GREEN, 3.5)
badge(g, 800, ROW["fill"] + 115, "✓", GREEN)
rect(g, 40, 640, 470, 220, GOOD_FILL, GREEN, 2.5, 16, "",
     two_line("Checked against the recipe", "every step is offered: the order can run once DoubleDose is built",
              26, 21), 26, INK, False, "left")
page("12 Matching, a missing effect, replanning", base, match, missing, replan, check)

# ==== 12b, 12c Inside an agent: the active part, the passive part (the AAS), what it talks to ===========
# After the I4.0 language demonstrator: a messenger, an interaction manager with a role's state machine,
# the agent's own functions, and below them the AAS it reads and writes. Every line is in the layer of
# the later of its two ends.
AGENT_FILL, PASSIVE_FILL = "#F3F6FA", "#EEF4F3"


def step_box(node, x, y, w, h, title, sub, stroke=INK, fill="#FFFFFF"):
    rect(node, x, y, w, h, fill, stroke, 2, 12, "", two_line(title, sub, 22, 18), 22, INK)


def proto(node, pts, color, label, dashed=False, both=False):
    arrow(node, pts, color, 2.5, dashed, label, 18, start="block" if both else None, label_color=INK)


def agent_frame(node, title, who, badge_mark, badge_fill, role, messages):
    """The frame, the messenger, the interaction manager with its role, the messages between them."""
    g = node.group("Agent frame")
    rect(g, 160, 20, 1420, 580, AGENT_FILL, BLUE, 2, 14, "dashed=1;")
    text(g, 184, 28, 1000, 40, f"<b>{title}</b> · the active part: a SPADE agent, planned", 26, INK)
    g = node.group("Outside: who it talks to")
    badge(g, 70, 300, badge_mark, badge_fill, 26, 26)
    text(g, 10, 334, 140, 60, who, 18, INK, False, "center")
    proto(g, [(100, 300), (180, 300)], INK, "", both=True)
    g = node.group("Messenger")
    rect(g, 180, 80, 120, 500, "#FFFFFF", INK, 2, 12)
    text(g, 180, 96, 120, 30, "<b>Messenger</b>", 20, INK, False, "center")
    rect(g, 200, 280, 80, 44, "#FCE6D6", ORANGE, 2, 8, "", "<b>XMPP</b>", 18, INK)
    text(g, 186, 470, 108, 90, "I4.0 language<br>VDI/VDE 2193", 15, GREY, False, "center")
    g = node.group("Interaction manager")
    rect(g, 410, 80, 240, 500, "#FFFFFF", INK, 2, 12)
    text(g, 410, 96, 240, 30, "<b>Interaction manager</b>", 20, INK, False, "center")
    rect(g, 430, 140, 200, 220, GOOD_FILL, GREEN, 2, 12, "", two_line(role, "the bidding protocol, a state machine", 22, 17), 22, INK)
    rect(g, 430, 390, 200, 100, GOOD_FILL, GREEN, 2, 12, "", two_line("Inform", "states, results", 22, 17), 22, INK)
    for i, (label, to_im) in enumerate(messages):
        y = 160 + i * 52
        proto(g, [(300, y), (430, y)] if to_im else [(430, y), (300, y)], INK, label)


# ---- 12b The agent of a module ----
ra_base, ra_agent, ra_bid, ra_rec, ra_run = (Node("the passive part and the module"), Node("the agent", False),
                                             Node("bidding", False), Node("reconfiguration", False),
                                             Node("execution", False))
g = ra_base.group("The module's AAS on the AAS server")
rect(g, 160, 630, 560, 250, PASSIVE_FILL, AAS, 2, 14)
shell(g, 180, 646, 70, 60, name="AAS shell")
text(g, 262, 650, 450, 50, two_line("The module's AAS", "the passive part, on the AAS server", 22, 17), 22, INK)
for i, s in enumerate(["Capability Description", "Skills", "Asset Interfaces Description", "Interfaces Mapping",
                       "Variables"]):
    sm_bar(g, 180 + (i % 2) * 265, 720 + (i // 2) * 52, 255, 40, s, 16)
g = ra_base.group("The module")
rect(g, 760, 630, 480, 250, STEP_FILL, ORANGE, 2, 14)
text(g, 780, 640, 440, 50, two_line("Filling module", "FORTE on its Pi", 22, 17), 22, INK)
for i, (s, c) in enumerate([("IEC 61499 program: skills, PackML", GREEN), ("OPC UA server", BLUE),
                            ("management interface", GOLD)]):
    rect(g, 780, 708 + i * 56, 440, 44, "#FFFFFF", c, 2, 10, "", s, 18, INK)
g = ra_base.group("DMP")
rect(g, 1280, 680, 300, 150, "#FFFFFF", BLUE, 2, 12, "",
     two_line("DMP", "an Operation of the AAS<br>becomes an OPC UA call", 22, 17), 22, INK)
proto(ra_base.group("Link: DMP to the module"), [(1280, 786), (1220, 786)], BLUE, "")
agent_frame(ra_agent, "The agent of a module", "product agents,<br>the table", "P", PURPLE, "Service provider",
            [("cfp", True), ("proposal", False), ("accept", True), ("inform", False)])
g = ra_bid.group("Bidding")
text(g, 690, 80, 600, 34, "<b>Bidding</b>: can it do the step, and when?", 22, INK)
for i, (ti, sub) in enumerate([("Capability check", "required against offered: meaning, range"),
                               ("Availability", "occupation, bookings"), ("Time", "from the skill's steps")]):
    step_box(g, 690 + i * 300, 124, 260, 120, ti, sub)
    if i:
        arrow(g, [(690 + i * 300 - 40, 184), (690 + i * 300, 184)], INK, 2)
proto(g, [(1430, 244), (1430, 268), (650, 268)], INK, "proposal: now, after a reconfiguration, or refuse")
proto(g, [(720, 244), (720, 300), (670, 300), (670, 630)], INK, "")
text(g, 540, 602, 124, 26, "HTTP: read", 18, INK, False, "right")
g = ra_rec.group("Reconfiguration")
text(g, 690, 330, 440, 34, "<b>Reconfiguration</b>: on accept, if needed", 22, INK)
step_box(g, 690, 374, 200, 150, "Compose", "a skill from the primitives: the planner")
arrow(g, [(890, 449), (930, 449)], INK, 2)
step_box(g, 930, 374, 200, 150, "modsync", "create online, verify, record", GOLD)
proto(g, [(705, 524), (705, 630)], INK, "")
text(g, 712, 602, 110, 26, "HTTP: write", 18, INK, False, "left")
proto(g, [(1030, 524), (1030, 630)], GOLD, "")
text(g, 820, 600, 204, 26, "management protocol", 18, INK, False, "right")
g = ra_run.group("Execution")
text(g, 1180, 330, 380, 34, "<b>Execution</b>", 22, INK)
step_box(g, 1180, 374, 380, 150, "modlink", "occupy, start the skill, follow its states", BLUE)
proto(g, [(1200, 524), (1200, 630)], BLUE, "")
text(g, 1206, 600, 90, 26, "OPC UA", 18, INK, False, "left")
proto(g, [(1430, 524), (1430, 680)], BLUE, "", dashed=True)
text(g, 1440, 606, 140, 50, "or HTTP,<br>through the DMP", 18, INK, False, "left")
page("12b Inside the agent of a module", ra_base, ra_agent, ra_bid, ra_rec, ra_run)

# ---- 12c The agent of a product ----
pa_base, pa_agent, pa_req, pa_rec = (Node("the passive part and the vial"), Node("the agent", False),
                                     Node("requesting", False), Node("recording", False))
g = pa_base.group("The order's AASs on the AAS server")
rect(g, 160, 630, 1000, 250, PASSIVE_FILL, AAS, 2, 14)
for x, name, sms in [(180, "Product AAS", ["Production Sequence", "Required Capabilities", "Process Parameters"]),
                     (680, "Process AAS", ["Step Bindings", "Process Information"])]:
    shell(g, x, 646, 70, 60, name=name)
    text(g, x + 82, 650, 380, 50, two_line(name, "the passive part", 22, 17), 22, INK)
    for i, s in enumerate(sms):
        sm_bar(g, x, 718 + i * 52, 440, 40, s, 17)
g = pa_base.group("The vial")
rect(g, 1200, 630, 380, 250, PROD_FILL, PURPLE, 2, 14, "", two_line("The vial", "no interface of its own: the table moves it", 22, 17), 22, INK)
agent_frame(pa_agent, "The agent of a product", "module agents,<br>the table", "R", BLUE, "Service requester",
            [("cfp", False), ("proposal", True), ("accept", False), ("inform", True)])
g = pa_req.group("Requesting")
text(g, 690, 80, 600, 34, "<b>Requesting</b>: one step after the other", 22, INK)
for i, (ti, sub) in enumerate([("Next step", "from the Production Sequence"),
                               ("Call", "the required capability and its values"),
                               ("Choose", "the best proposal: the earliest")]):
    step_box(g, 690 + i * 300, 124, 260, 120, ti, sub)
    if i:
        arrow(g, [(690 + i * 300 - 40, 184), (690 + i * 300, 184)], INK, 2)
proto(g, [(1430, 244), (1430, 268), (650, 268)], INK, "accept one, reject the others")
proto(g, [(720, 244), (720, 300), (670, 300), (670, 630)], INK, "")
text(g, 540, 602, 124, 26, "HTTP: read", 18, INK, False, "right")
g = pa_rec.group("Recording")
text(g, 690, 330, 600, 34, "<b>Recording and moving</b>", 22, INK)
step_box(g, 690, 374, 260, 150, "Bind", "the step to the module's skill")
step_box(g, 990, 374, 260, 150, "Record", "what was done to the vial")
step_box(g, 1290, 374, 270, 150, "Move", "ask the table's agent: to the next module", PURPLE)
proto(g, [(820, 524), (820, 630)], INK, "HTTP: write")
proto(g, [(1120, 524), (1120, 630)], INK, "HTTP: write")
proto(g, [(1425, 524), (1425, 630)], PURPLE, "via the table", dashed=True)
page("12c Inside the agent of a product", pa_base, pa_agent, pa_req, pa_rec)

# ==== 13 Agents on the line: call for proposals, proposals, accept ===================================
ln = Copied("slides.drawio", 2, "the line")
keep = lambda c: 2 <= num(c) <= 41 and not 11 <= num(c) <= 20      # no station vials, no flow arrows
ln.cells = [c for c in ln.cells if keep(c)]
S13, DX, DY = 0.9, -50, -40
T = lambda x, y: (x * S13 + DX, y * S13 + DY)
ln.scale(S13, DX, DY)
vial_layer = ln.layer("product: the vial on its shuttle")
vial = ln.pick(ids={"c10"})
ln.move(vial, vial_layer)
ln.group([c for c in ln.cells if c.get("parent") == "1"], "The line: table, stations, robots, empty shuttles")
ln_xml = "\n".join(ln.xml())

PA, MOD = T(400, 360), {"Filling": T(700, 186), "Stoppering": T(805, 246), "Capping": T(910, 307),
                        "Inspection": T(1015, 368)}
TA = T(330, 470)
ag = Node("agents")
for name, (x, y) in MOD.items():
    badge(ag.group(f"Resource agent: {name}"), x, y, "R", BLUE, 22, 22)
badge(ag.group("Transport agent: the table"), *TA, "T", BLUE_D, 22, 22)
g = ag.group("Legend")
for i, (mark, fill, txt) in enumerate([("P", PURPLE, "product agent: one per order"),
                                       ("R", BLUE, "resource agent: one per module"),
                                       ("T", BLUE_D, "transport agent: the table")]):
    badge(g, 62, 724 + i * 54, mark, fill, 20, 20)
    text(g, 94, 704 + i * 54, 420, 40, txt, 22, INK)
g = ag.group("The order")
rect(g, 520, 700, 480, 150, PROD_FILL, PURPLE, 2, 16, "",
     two_line("Order 17: a vial", "1 Fill 2.0 mL · 2 Stopper · 3 Inspect", 24, 21), 24, INK, False, "left")
pa = Node("product agent on the vial")
badge(pa.group("Product agent: the vial"), *PA, "P", PURPLE, 22, 22)

CARD_X, CARD_W = 1040, 530


def card(node, y, h, head, color, body):
    g = node.group(f"Message: {head}")
    rect(g, CARD_X, y, CARD_W, h, "#FFFFFF", color, 2.5, 14)
    text(g, CARD_X + 20, y + 10, CARD_W - 40, 34, head, 23, color, True)
    text(g, CARD_X + 20, y + 46, CARD_W - 40, h - 54, body, 20, INK, valign="top")
    return g


g = base13 = Node("messages header")
text(g, CARD_X, 20, CARD_W, 40, "The messages, in the I4.0 language", 24, INK, True)

msg = []


def message(n, title):
    """A message's card (it stays) and its arrows on the line (they go with the next message)."""
    C, A = Node(f"{n} {title}: card", False), Node(f"{n} {title}: arrows", False)
    msg.extend([C, A])
    return C, A


C, A = message(1, "call for proposals")
card(C, 70, 108, "callForProposal", PURPLE, "order 17 → every module:<br>Fill 2.0 mL · Stopper · Inspect")
for name, (x, y) in MOD.items():
    arrow(A.group(f"call to {name}"), [(PA[0] + 22, PA[1] - 6), (x - 26, y)], PURPLE, 2.5, True)
C, A = message(2, "proposals")
card(C, 192, 170, "proposal ×3 · refuse ×1", BLUE,
     "Filling: Fill 2.0 mL, 40 s<br>Stoppering: Stopper, 25 s · Inspection: Inspect, 10 s<br>"
     f"<font color=\"{GREY}\">Capping: refuse, it offers none of them</font>")
for name, (x, y) in MOD.items():
    if name == "Capping":
        badge(C.group("Capping refuses"), x + 30, y - 26, "✗", GREY, 14, 16)
    else:
        arrow(A.group(f"proposal from {name}"), [(x - 24, y + 12), (PA[0] + 24, PA[1] + 8)], BLUE, 2.5)
C, A = message(3, "accept")
card(C, 376, 108, "acceptProposal ×3", GREEN, "order 17 books its steps:<br>Filling, Stoppering, Inspection")
for i, name in enumerate(["Filling", "Stoppering", "Inspection"]):
    x, y = MOD[name]
    pill(C.group(f"Booked: {name}"), x + 18, y - 52, 40, 30, f"{i + 1}", GOOD_FILL, GREEN, 2, 18, INK, True)
    arrow(A.group(f"accept to {name}"), [(PA[0] + 22, PA[1] - 6), (x - 26, y)], GREEN, 2.5)
C, A = message(4, "transport")
card(C, 498, 140, "callForProposal · proposal · accept", BLUE_D,
     "order 17 → the table: from loading to Filling<br>the table: 6 s, now · accepted")
g = A.group("Transport: call and proposal")
arrow(g, [(PA[0] - 4, PA[1] + 26), (TA[0] - 4, TA[1] - 26)], PURPLE, 2.5, True)
arrow(g, [(TA[0] + 10, TA[1] - 24), (PA[0] + 18, PA[1] + 22)], BLUE, 2.5)
C, A = message(5, "move")
card(C, 652, 150, "The table moves the vial", INK,
     "to the filling module; there the module's<br>agent runs Dispensing: the next slide")
msg.remove(A)
page("13 Agents on the line: call for proposals, proposal, accept", ln_xml, base13, ag, pa, *msg)

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
