"""AASPIRE's logo, the icons of its repositories and apps, and the AP2030 organization's map.

    python docs/presentation/source/build_icons.py .

Writes docs/figures/framework-icons.drawio (pages Icons and Organization) and the draw.io library
docs/figures/library/tools.xml. Every icon is a tile in its pillar's colour with a white sign drawn from
plain shapes, so it stays editable in draw.io; the plan is docs/framework-plan.md, section 8.
"""
import base64
import json
import sys
import urllib.parse
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from drawlib import (AAS, BLUE, GREEN, GREY, INK, ORANGE, PURPLE, PURPLE_D, SHELL_STYLE, Node, box, line,  # noqa
                     text, write)

REPO = Path(sys.argv[1])
FIG = REPO / "docs" / "figures"

W = "#FFFFFF"
GOLD = "#B88A1C"
UI = "#56708A"
SLATE = "#4A5560"

# The pillars: AAS, then the letters of AASPIRE after it, and the parts beside them.
PILLARS = {
    "AAS": AAS,
    "Planning": ORANGE,
    "Integration": GOLD,
    "Reconfiguration": GREEN,
    "Execution": BLUE,
    "Interfaces": UI,
    "Deployment": SLATE,
    "Lines": PURPLE,
}
WORDMARK = (f'<font color="{AAS}">AAS</font><font color="{ORANGE}">P</font><font color="{GOLD}">I</font>'
            f'<font color="{GREEN}">R</font><font color="{BLUE}">E</font>')
EXPANSION = (f'AAS-based <b><font color="{ORANGE}">P</font></b>lanning, <b><font color="{GOLD}">I</font></b>ntegration, '
             f'<b><font color="{GREEN}">R</font></b>econfiguration and <b><font color="{BLUE}">E</font></b>xecution')


class Icon:
    """Draws in the icon's own 96 x 96 units, placed at (x, y) at a size of `size` pixels."""

    def __init__(self, node, x, y, size, color):
        self.node, self.x, self.y, self.k, self.color = node, x, y, size / 96, color

    def _at(self, x, y):
        return self.x + x * self.k, self.y + y * self.k

    def sw(self, w):
        return f"{w * self.k:.2f}"

    def shape(self, x, y, w, h, style, value=""):
        px, py = self._at(x, y)
        box(self.node, px, py, w * self.k, h * self.k, style, value)

    def solid(self, x, y, w, h, fill=W, arc=0, extra=""):
        self.shape(x, y, w, h, f"rounded={1 if arc else 0};arcSize={arc or 10};fillColor={fill};strokeColor=none;"
                   + extra)

    def outline(self, x, y, w, h, stroke=W, width=4, arc=0, extra=""):
        self.shape(x, y, w, h, f"rounded={1 if arc else 0};arcSize={arc or 10};fillColor=none;strokeColor={stroke};"
                   f"strokeWidth={self.sw(width)};" + extra)

    def dot(self, cx, cy, r, fill=W, stroke="none", width=0):
        self.shape(cx - r, cy - r, 2 * r, 2 * r, f"ellipse;fillColor={fill};strokeColor={stroke};"
                   f"strokeWidth={self.sw(width)};")

    def stroke(self, pts, color=W, width=4, arrow=False, dashed=False):
        style = (f"html=1;rounded=0;strokeColor={color};strokeWidth={self.sw(width)};endFill=1;"
                 + (f"endArrow=block;endSize={self.sw(4)};" if arrow else "endArrow=none;")
                 + ("dashed=1;" if dashed else ""))
        line(self.node, [self._at(x, y) for x, y in pts], style)

    def label(self, x, y, w, h, value, size, color=W):
        px, py = self._at(x, y)
        text(self.node, px, py, w * self.k, h * self.k, value, max(6, round(size * self.k)), color, True, "center")

    def tile(self):
        self.solid(0, 0, 96, 96, self.color, 22)

    def shell(self, x, y, w, h, fill=W):
        self.shape(x, y, w, h, SHELL_STYLE.replace(AAS, fill))

    def fb(self, x, y, w, h, fill=W, pins=False):
        """A function block: head, waist and body; with `pins`, a stub for each side's events and data."""
        head, waist = h * 0.36, h * 0.1
        self.solid(x, y, w, head, fill)
        self.solid(x + w * 0.18, y + head, w * 0.64, waist, fill)
        self.solid(x, y + head + waist, w, h - head - waist, fill)
        if pins:
            stub, t = w * 0.22, max(2.5, h * 0.07)
            for py in (y + head / 2, y + head + waist + (h - head - waist) / 2):
                self.solid(x - stub, py - t / 2, stub, t, fill)
                self.solid(x + w, py - t / 2, stub, t, fill)


# ---- The signs -------------------------------------------------------------------------------------

def aaspire(i):
    """The logo: the AAS shell on four pillars, one per letter after the AAS."""
    i.shape(0, 0, 96, 96, f"rounded=1;arcSize=22;fillColor={W};strokeColor=#D5DADC;strokeWidth={i.sw(2)};")
    i.shell(12, 12, 72, 62, AAS)
    for n, color in enumerate((ORANGE, GOLD, GREEN, BLUE)):
        i.solid(28.5 + n * 10.6, 38, 7, 36, color, 30)


def aas_model(i):
    i.shell(22, 14, 52, 45)
    i.label(10, 58, 76, 30, "{ }", 30)


def ontologies(i):
    nodes = [(30, 30), (68, 36), (44, 70)]
    for a, b in ((0, 1), (1, 2), (2, 0)):
        i.stroke([nodes[a], nodes[b]], width=5)
    for cx, cy in nodes:
        i.dot(cx, cy, 11)


def skill_model(i):
    i.stroke([(48, 30), (48, 66)], width=4)
    i.solid(28, 12, 40, 18, W, 30)
    i.shape(35, 37, 26, 22, f"rhombus;fillColor={W};strokeColor=none;")
    i.solid(28, 66, 40, 18, W, 30)


def aas_generator(i):
    i.shell(14, 30, 54, 47)
    i.shape(62, 10, 20, 30, f"rhombus;fillColor={W};strokeColor=none;")
    i.shape(76, 42, 12, 18, f"rhombus;fillColor={W};strokeColor=none;")


def fond_aas(i):
    """One action, several outcomes: planning under non-determinism."""
    i.stroke([(26, 48), (64, 26)], width=5, arrow=True)
    i.stroke([(26, 48), (64, 70)], width=5, arrow=True)
    i.dot(22, 48, 11)
    i.dot(74, 22, 9)
    i.dot(74, 74, 9)


def modplan(i):
    root, leaves = (48, 22), [(20, 72), (48, 72), (76, 72)]
    for leaf in leaves:
        i.stroke([root, leaf], width=5)
    i.dot(*root, 12)
    for cx, cy in leaves:
        i.dot(cx, cy, 9)


def planner(i):
    for x in (8, 34, 60):
        i.shape(x, 34, 30, 28, f"shape=step;perimeter=stepPerimeter;size=0.3;fixedSize=0;fillColor={W};"
                f"strokeColor={i.color};strokeWidth={i.sw(2)};")


def registration(i):
    i.shell(12, 16, 60, 52)
    i.dot(66, 66, 18, W, i.color, 4)
    i.stroke([(57, 66), (64, 73), (76, 59)], i.color, 5)


def dmp(i):
    i.shell(8, 30, 32, 28)
    i.stroke([(44, 44), (56, 44)], width=4, arrow=True)
    i.shape(60, 24, 28, 40, f"shape=cylinder3;boundedLbl=1;size=6;fillColor={W};strokeColor={i.color};"
            f"strokeWidth={i.sw(2)};")


def uns_schemas(i):
    """The broker and its publishers and subscribers: one namespace."""
    spokes = [(48, 16), (76, 32), (76, 64), (48, 80), (20, 64), (20, 32)]
    for p in spokes:
        i.stroke([(48, 48), p], width=4)
    i.dot(48, 48, 13)
    for cx, cy in spokes:
        i.dot(cx, cy, 7)


def modlink(i):
    for cx, cy in ((38, 58), (58, 38)):
        i.outline(cx - 12, cy - 23, 24, 46, W, 7, 50, "rotation=45;")


def modsync(i):
    i.shell(12, 12, 38, 33)
    i.fb(54, 52, 30, 32)
    i.stroke([(31, 50), (31, 70), (46, 70)], width=5, arrow=True)
    i.stroke([(69, 46), (69, 26), (55, 26)], width=5, arrow=True)


def skill_lib(i):
    for x, y in ((16, 16), (54, 16), (16, 54), (54, 54)):
        i.fb(x, y, 26, 26)


def modgen(i):
    i.shape(10, 26, 30, 40, f"shape=document;size=0.15;fillColor={W};strokeColor=none;")
    for y in (35, 43, 51):
        i.solid(16, y, 18, 3, i.color)
    i.stroke([(43, 46), (55, 46)], width=4, arrow=True)
    i.fb(60, 26, 28, 40)


def iec61499_mgmt(i):
    i.solid(12, 20, 72, 56, W, 12)
    i.solid(12, 20, 72, 12, "#DCE3E6", 0)
    i.label(18, 36, 50, 34, "&gt;_", 30, i.color)


def forte_runtime(i):
    i.solid(26, 26, 44, 44, W, 12)
    for p in (36, 48, 60):
        i.solid(p - 2.5, 14, 5, 12), i.solid(p - 2.5, 70, 5, 12)
        i.solid(14, p - 2.5, 12, 5), i.solid(70, p - 2.5, 12, 5)
    i.fb(37, 36, 22, 24, i.color)


def skill_editor(i):
    i.fb(14, 14, 40, 44, W, True)
    i.solid(61, 40, 10, 38, W, 0, "rotation=45;")
    i.shape(43.5, 74, 10, 9, f"triangle;direction=south;fillColor={W};strokeColor=none;rotation=45;")


def bt_controller(i):
    """A behaviour tree: a sequence over three children."""
    for cx in (21, 48, 75):
        i.stroke([(48, 32), (cx, 62)], width=4)
    i.solid(32, 12, 32, 22, W, 20)
    i.label(32, 12, 32, 22, "&#8594;", 20, i.color)
    for x in (10, 37, 64):
        i.solid(x, 62, 22, 20, W, 20)


def lineagents(i):
    i.dot(34, 30, 11)
    i.shape(16, 46, 36, 28, f"shape=or;direction=north;fillColor={W};strokeColor=none;")
    i.dot(62, 40, 11, W, i.color, 3)
    i.shape(44, 56, 36, 28, f"shape=or;direction=north;fillColor={W};strokeColor={i.color};strokeWidth={i.sw(3)};")


def packml_stations(i):
    """A station's state machine: states around a cycle."""
    i.outline(22, 22, 52, 52, W, 5, 0, "shape=ellipse;perimeter=ellipsePerimeter;")
    for cx, cy in ((48, 22), (74, 48), (48, 74), (22, 48)):
        i.dot(cx, cy, 9, W, i.color, 3)


def planar(i):
    for x, y in ((14, 14), (50, 14), (14, 50), (50, 50)):
        i.outline(x, y, 32, 32, W, 3, 10)
    i.solid(20, 20, 20, 20, W, 20)
    i.solid(56, 56, 20, 20, W, 20)


def hmi(i):
    i.shape(14, 26, 68, 46, f"shape=or;direction=north;fillColor=none;strokeColor={W};strokeWidth={i.sw(6)};")
    i.stroke([(48, 70), (66, 42)], width=5)
    i.dot(48, 70, 7)


def orders(i):
    i.solid(20, 16, 56, 68, W, 10)
    i.solid(36, 10, 24, 12, "#C4D3E0", 30)
    for y in (32, 48, 64):
        i.solid(28, y, 9, 9, i.color, 20)
        i.solid(42, y + 3, 26, 3, i.color)


def web_ui(i):
    i.solid(10, 18, 76, 60, W, 10)
    for x in (18, 26, 34):
        i.dot(x, 26, 3, i.color)
    i.solid(10, 33, 76, 2, i.color)
    i.stroke([(28, 56), (68, 56)], i.color, 3)
    for x in (18, 41, 62):
        i.solid(x, 49, 16, 14, i.color, 20)


def deploy_server(i):
    for y in (16, 39, 62):
        i.solid(18, y, 60, 18, W, 20)
        i.dot(64, y + 9, 3, i.color), i.dot(56, y + 9, 3, i.color)
        i.solid(25, y + 7.5, 22, 3, i.color)


def deploy_module(i):
    i.solid(12, 22, 68, 52, W, 10)
    for x in range(20, 72, 7):
        i.dot(x, 28, 2.2, i.color)
    i.solid(22, 42, 22, 22, i.color, 10)
    i.solid(70, 40, 16, 10, "#C9CDD2"), i.solid(70, 56, 16, 10, "#C9CDD2")


def docs(i):
    i.solid(14, 22, 32, 52, W, 6)
    i.solid(50, 22, 32, 52, W, 6)
    for y in (32, 40, 48, 56):
        i.solid(20, y, 20, 3, i.color), i.solid(56, y, 20, 3, i.color)


def aseptic_line(i):
    i.solid(37, 10, 22, 11, W, 20)
    i.solid(41, 21, 14, 6, W)
    i.solid(31, 27, 34, 58, W, 18)
    i.solid(36, 54, 24, 26, PURPLE_D, 14)


# (key, title, pillar, what it is, sign)
ICONS = [
    ("aaspire", "AASPIRE", None, "the framework", aaspire),
    ("aas-model", "aas-model", "AAS", "repository", aas_model),
    ("ontologies", "ontologies", "AAS", "repository", ontologies),
    ("skill-model", "skill-model", "AAS", "repository", skill_model),
    ("aas-generator", "aas-generator", "AAS", "repository", aas_generator),
    ("fond-aas", "fond-aas", "Planning", "repository", fond_aas),
    ("modplan", "modplan", "Planning", "repository", modplan),
    ("planner", "Planner", "Planning", "web UI app", planner),
    ("registration-service", "registration-service", "Integration", "repository", registration),
    ("aas-camel-dmp", "aas-camel-dmp", "Integration", "repository", dmp),
    ("uns-schemas", "uns-schemas", "Integration", "repository", uns_schemas),
    ("modlink", "modlink", "Integration", "repository", modlink),
    ("modsync", "modsync", "Reconfiguration", "repository", modsync),
    ("iec61499-skill-lib", "iec61499-skill-lib", "Reconfiguration", "repository", skill_lib),
    ("modgen", "modgen", "Reconfiguration", "tool in iec61499-skill-lib", modgen),
    ("iec61499-mgmt-py", "iec61499-mgmt-py", "Reconfiguration", "repository", iec61499_mgmt),
    ("forte-runtime", "forte-runtime", "Reconfiguration", "repository", forte_runtime),
    ("skill-editor", "Skill Editor", "Reconfiguration", "web UI app", skill_editor),
    ("bt-controller", "bt-controller", "Execution", "repository", bt_controller),
    ("lineagents", "lineagents", "Execution", "repository", lineagents),
    ("packml-stations", "packml-stations", "Execution", "repository", packml_stations),
    ("planar-controller", "planar-controller", "Execution", "repository", planar),
    ("hmi", "HMI", "Execution", "web UI app", hmi),
    ("orders", "Orders", "Execution", "web UI app", orders),
    ("basyx-aas-web-ui", "basyx-aas-web-ui", "Interfaces", "repository (fork)", web_ui),
    ("deploy-server", "deploy-server", "Deployment", "repository", deploy_server),
    ("deploy-module", "deploy-module", "Deployment", "repository", deploy_module),
    ("docs", "docs", "Deployment", "the documentation", docs),
    ("aseptic-line", "aseptic-line", "Lines", "repository", aseptic_line),
]
BY_KEY = {k: (t, p, s) for k, t, p, _, s in ICONS}


def icon(node, key, x, y, size):
    title, pillar, sign = BY_KEY[key]
    g = node.group(f"Icon {title}")
    i = Icon(g, x, y, size, PILLARS.get(pillar, AAS))
    if pillar:
        i.tile()
    sign(i)
    return g


# ---- Page: the logo and every icon, a row per pillar ------------------------------------------------

def icons_page():
    layer = Node("Icons")
    left, cw, rh = 230, 170, 172
    head = layer.group("Logo and name")
    icon(head, "aaspire", 40, 30, 128)
    text(head, 196, 34, 760, 70, WORDMARK, 54, INK, True)
    text(head, 198, 102, 760, 30, EXPANSION, 18, GREY)
    text(head, 198, 132, 760, 26, "plug and produce with the Asset Administration Shell", 15, GREY)
    rows = [["AAS"], ["Planning"], ["Integration"], ["Reconfiguration"], ["Execution"],
            ["Interfaces", "Deployment", "Lines"]]
    y = 200
    for pillars in rows:
        keys = [k for k, _, p, _, _ in ICONS if p in pillars]
        names = " · ".join(f'<font color="{PILLARS[p]}">{p}</font>' for p in pillars)
        text(layer, 40, y + 30, left - 50, 40, names, 17, INK, True)
        for n, key in enumerate(keys):
            title, pillar, _ = BY_KEY[key]
            what = next(w for k, _, _, w, _ in ICONS if k == key)
            cx = left + n * cw + cw / 2
            icon(layer, key, cx - 44, y, 88)
            text(layer, cx - cw / 2, y + 94, cw, 22, title, 14, INK, True, "center")
            text(layer, cx - cw / 2, y + 115, cw, 18, what, 11, GREY, False, "center")
        y += rh
    return ("Icons", left + 6 * cw + 40, y + 10, [layer])


# ---- Page: the organization -----------------------------------------------------------------------

COLUMNS = [
    ("AAS", [
        (["aas-model"], "aas-model", "the lab's pydantic AAS model"),
        (["ontologies"], "ontologies", "ARSO, APSO, AProSO, PPRL, vocabularies"),
        (["skill-model"], "skill-model", "skills and flows every tool reads"),
        (["aas-generator"], "aas-generator", "AAS from spec sheets")]),
    ("Planning", [
        (["fond-aas"], "fond-aas", "policies by FOND planning (PDDL)"),
        (["modplan"], "modplan", "new skills by HTN planning")]),
    ("Integration", [
        (["registration-service"], "registration-service", "build, check, discover, publish"),
        (["aas-camel-dmp"], "aas-camel-dmp (fork)", "AAS operations and data mapped"),
        (["uns-schemas"], "uns-schemas", "the namespace's MQTT messages"),
        (["modlink"], "modlink", "skills from the AAS over OPC UA")]),
    ("Reconfiguration", [
        (["modsync"], "modsync", "a running program against its AAS"),
        (["iec61499-skill-lib", "modgen"], "iec61499-skill-lib", "ModLib, modgen, the module rules"),
        (["iec61499-mgmt-py"], "iec61499-mgmt-py", "the FORTE management client"),
        (["forte-runtime"], "forte-runtime", "FORTE per platform, releases")]),
    ("Execution", [
        (["bt-controller"], "bt-controller", "processes as behaviour trees"),
        (["lineagents"], "lineagents", "order, product, resource agents"),
        (["packml-stations"], "packml-stations", "PackML stations over MQTT"),
        (["planar-controller"], "planar-controller", "the planar table")]),
]
COLUMNS_2 = [
    ("Interfaces", [
        (["basyx-aas-web-ui", "planner", "skill-editor", "hmi", "orders"], "basyx-aas-web-ui (fork)",
         "Planner, Skill Editor, HMI, Orders")]),
    ("Deployment", [
        (["deploy-server"], "deploy-server", "the server stack"),
        (["deploy-module"], "deploy-module", "a Raspberry Pi as a module")]),
    ("Lines", [
        (["aseptic-line"], "aseptic-line", "AP2030's line, its AASs and trees")]),
]


def column(layer, x, top, colw, colh, name, rows, s=40, rowh=76):
    color = PILLARS[name]
    f = layer.group(name)
    box(f, x, top, colw, colh, f"rounded=1;arcSize=4;fillColor=#F7F8F9;strokeColor={color};strokeWidth=2;")
    box(f, x, top, colw, 36, f"rounded=1;arcSize=20;fillColor={color};strokeColor=none;")
    text(f, x + 12, top, colw - 24, 36, name, 16, "#FFFFFF", True)
    for r, (keys, title, role) in enumerate(rows):
        y = top + 50 + r * rowh
        row = f.group(title)
        icon(row, keys[0], x + 12, y, s)
        tx = x + 12 + s + 10
        text(row, tx, y - 2, x + colw - tx - 8, 22, title, 14, INK, True)
        text(row, tx, y + 20, x + colw - tx - 8, 18, role, 12, GREY, False, valign="top")
        for k, key in enumerate(keys[1:]):         # what the repository holds, small under its name
            icon(row, key, tx + k * 26, y + 42, 20)


def organization_page():
    layer = Node("Organization")
    colw, gap, rowh = 262, 18, 76
    n1 = len(COLUMNS)
    width = n1 * colw + (n1 - 1) * gap + 80
    main_w, top1 = 640, 230
    mx = (width - main_w) / 2
    g = layer.group("Main repository")
    box(g, mx, 30, main_w, 130, f"rounded=1;arcSize=12;fillColor=#FFFFFF;strokeColor={AAS};strokeWidth=2.5;")
    icon(g, "aaspire", mx + 20, 47, 96)
    text(g, mx + 134, 40, main_w - 150, 40, WORDMARK, 30, INK, True)
    text(g, mx + 134, 78, main_w - 150, 22, EXPANSION, 13, GREY)
    text(g, mx + 134, 102, main_w - 150, 44, "<b>aaspire</b>, the main repository of the AP2030 organization: "
         "every repository below as a submodule, the documentation, the whole line in simulation", 12, GREY)
    gray = f"html=1;endArrow=none;strokeColor={GREY};strokeWidth=2;"
    arrow = f"html=1;endArrow=block;endFill=1;endSize=6;strokeColor={GREY};strokeWidth=2;"
    colh1 = 52 + max(len(r) for _, r in COLUMNS) * rowh
    bus1 = top1 - 34
    xs1 = [40 + n * (colw + gap) for n in range(n1)]
    line(layer, [(width / 2, 160), (width / 2, bus1)], gray)
    line(layer, [(xs1[0] + colw / 2, bus1), (xs1[-1] + colw / 2, bus1)], gray)
    for x, (name, rows) in zip(xs1, COLUMNS):
        line(layer, [(x + colw / 2, bus1), (x + colw / 2, top1)], arrow)
        column(layer, x, top1, colw, colh1, name, rows)
    n2 = len(COLUMNS_2)
    top2 = top1 + colh1 + 70
    colh2 = 52 + max(len(r) for _, r in COLUMNS_2) * rowh
    x0 = (width - (n2 * colw + (n2 - 1) * gap)) / 2
    xs2 = [x0 + n * (colw + gap) for n in range(n2)]
    bus2 = top2 - 34
    line(layer, [(xs1[0] + colw / 2, bus1), (18, bus1), (18, bus2), (xs2[-1] + colw / 2, bus2)], gray)
    for x, (name, rows) in zip(xs2, COLUMNS_2):
        line(layer, [(x + colw / 2, bus2), (x + colw / 2, top2)], arrow)
        column(layer, x, top2, colw, colh2, name, rows)
    return ("Organization", width, top2 + colh2 + 40, [layer])


# ---- The library -----------------------------------------------------------------------------------

def compress(xml):
    data = urllib.parse.quote(xml, safe="-_.!~*'()")
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return base64.b64encode(c.compress(data.encode()) + c.flush()).decode()


def library():
    entries = []
    for key, title, _, _, _ in ICONS:
        holder = Node("holder", layer=False)
        icon(holder, key, 0, 0, 96)
        out = []
        holder.items[0].emit(out, parent="1")
        xml = '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(out) + '</root></mxGraphModel>'
        entries.append({"xml": compress(xml), "w": 96, "h": 96, "aspect": "fixed", "title": f"Icon · {title}"})
    return "<mxlibrary>" + json.dumps(entries, ensure_ascii=False) + "</mxlibrary>"


if __name__ == "__main__":
    write(FIG / "framework-icons.drawio", [icons_page(), organization_page()])
    (FIG / "library" / "tools.xml").write_text(library(), encoding="utf-8", newline="\n")
    print("docs/figures/framework-icons.drawio, docs/figures/library/tools.xml")
