"""The icons of the framework's repositories and apps, and the organization's map.

    python docs/presentation/source/build_icons.py .

Writes docs/figures/framework-icons.drawio (pages Icons and Organization) and the draw.io library
docs/figures/library/tools.xml. Every icon is a tile in its family's colour with a white sign drawn from
plain shapes, so it stays editable in draw.io; the plan is docs/framework-plan.md, section 7.
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

GOLD = "#B88A1C"
SLATE = "#4A5560"
W = "#FFFFFF"


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

def skillshell(i):
    i.shell(12, 14, 72, 64)
    i.fb(35, 44, 26, 30)


def ontologies(i):
    nodes = [(30, 30), (68, 36), (44, 70)]
    for a, b in ((0, 1), (1, 2), (2, 0)):
        i.stroke([nodes[a], nodes[b]], width=5)
    for cx, cy in nodes:
        i.dot(cx, cy, 11)


def aas_model(i):
    i.shell(22, 14, 52, 45)
    i.label(10, 58, 76, 30, "{ }", 30)


def aas_generator(i):
    i.shell(14, 30, 54, 47)
    i.shape(62, 10, 20, 30, f"rhombus;fillColor={W};strokeColor=none;")
    i.shape(76, 42, 12, 18, f"rhombus;fillColor={W};strokeColor=none;")


def modreg(i):
    i.shell(12, 16, 60, 52)
    i.dot(66, 66, 18, W, AAS, 4)
    i.stroke([(57, 66), (64, 73), (76, 59)], AAS, 5)


def skill_lib(i):
    for x, y in ((16, 16), (54, 16), (16, 54), (54, 54)):
        i.fb(x, y, 26, 26)


def modgen(i):
    i.shape(10, 26, 30, 40, f"shape=document;size=0.15;fillColor={W};strokeColor=none;")
    for y in (35, 43, 51):
        i.solid(16, y, 18, 3, GREEN)
    i.stroke([(43, 46), (55, 46)], width=4, arrow=True)
    i.fb(60, 26, 28, 40)


def forte_runtime(i):
    i.solid(26, 26, 44, 44, W, 12)
    for p in (36, 48, 60):
        i.solid(p - 2.5, 14, 5, 12), i.solid(p - 2.5, 70, 5, 12)
        i.solid(14, p - 2.5, 12, 5), i.solid(70, p - 2.5, 12, 5)
    i.fb(37, 36, 22, 24, GREEN)


def iec61499_mgmt(i):
    i.solid(12, 20, 72, 56, W, 12)
    i.solid(12, 20, 72, 12, "#E9DDBE", 0)
    i.label(18, 36, 50, 34, "&gt;_", 30, GOLD)


def modsync(i):
    i.shell(12, 12, 38, 33)
    i.fb(54, 52, 30, 32)
    i.stroke([(31, 50), (31, 70), (46, 70)], width=5, arrow=True)
    i.stroke([(69, 46), (69, 26), (55, 26)], width=5, arrow=True)


def modplan(i):
    root, leaves = (48, 22), [(20, 72), (48, 72), (76, 72)]
    for leaf in leaves:
        i.stroke([root, leaf], width=5)
    i.dot(*root, 12)
    for cx, cy in leaves:
        i.dot(cx, cy, 9)


def modlink(i):
    for cx, cy in ((38, 58), (58, 38)):
        i.outline(cx - 12, cy - 23, 24, 46, W, 7, 50, "rotation=45;")


def lineagents(i):
    i.dot(34, 30, 11)
    i.shape(16, 46, 36, 28, f"shape=or;direction=north;fillColor={W};strokeColor=none;")
    i.dot(62, 40, 11, W, ORANGE, 3)
    i.shape(44, 56, 36, 28, f"shape=or;direction=north;fillColor={W};strokeColor={ORANGE};strokeWidth={i.sw(3)};")


def web_ui(i):
    i.solid(10, 18, 76, 60, W, 10)
    for x in (18, 26, 34):
        i.dot(x, 26, 3, BLUE)
    i.solid(10, 33, 76, 2, BLUE)
    i.stroke([(28, 56), (68, 56)], BLUE, 3)
    for x in (18, 41, 62):
        i.solid(x, 49, 16, 14, BLUE, 20)


def planner(i):
    for x in (8, 34, 60):
        i.shape(x, 34, 30, 28, f"shape=step;perimeter=stepPerimeter;size=0.3;fixedSize=0;fillColor={W};"
                f"strokeColor={BLUE};strokeWidth={i.sw(2)};")


def skill_editor(i):
    i.fb(14, 14, 40, 44, W, True)
    i.solid(61, 40, 10, 38, W, 0, "rotation=45;")
    i.shape(43.5, 74, 10, 9, f"triangle;direction=south;fillColor={W};strokeColor=none;rotation=45;")


def hmi(i):
    i.shape(14, 26, 68, 46, f"shape=or;direction=north;fillColor=none;strokeColor={W};strokeWidth={i.sw(6)};")
    i.stroke([(48, 70), (66, 42)], width=5)
    i.dot(48, 70, 7)


def orders(i):
    i.solid(20, 16, 56, 68, W, 10)
    i.solid(36, 10, 24, 12, "#C4D3E0", 30)
    for y in (32, 48, 64):
        i.solid(28, y, 9, 9, BLUE, 20)
        i.solid(42, y + 3, 26, 3, BLUE)


def dmp(i):
    i.shell(8, 30, 32, 28)
    i.stroke([(44, 44), (56, 44)], width=4, arrow=True)
    i.shape(60, 24, 28, 40, f"shape=cylinder3;boundedLbl=1;size=6;fillColor={W};strokeColor={BLUE};"
            f"strokeWidth={i.sw(2)};")


def planar(i):
    for x, y in ((14, 14), (50, 14), (14, 50), (50, 50)):
        i.outline(x, y, 32, 32, W, 3, 10)
    i.solid(20, 20, 20, 20, W, 20)
    i.solid(56, 56, 20, 20, W, 20)


def deploy_server(i):
    for y in (16, 39, 62):
        i.solid(18, y, 60, 18, W, 20)
        i.dot(64, y + 9, 3, SLATE), i.dot(56, y + 9, 3, SLATE)
        i.solid(25, y + 7.5, 22, 3, SLATE)


def deploy_module(i):
    i.solid(12, 22, 68, 52, W, 10)
    for x in range(20, 72, 7):
        i.dot(x, 28, 2.2, SLATE)
    i.solid(22, 42, 22, 22, SLATE, 10)
    i.solid(70, 40, 16, 10, "#C9CDD2"), i.solid(70, 56, 16, 10, "#C9CDD2")


def docs(i):
    i.solid(14, 22, 32, 52, W, 6)
    i.solid(50, 22, 32, 52, W, 6)
    for y in (32, 40, 48, 56):
        i.solid(20, y, 20, 3, SLATE), i.solid(56, y, 20, 3, SLATE)


def pharma_line(i):
    i.solid(37, 10, 22, 11, W, 20)
    i.solid(41, 21, 14, 6, W)
    i.solid(31, 27, 34, 58, W, 18)
    i.solid(36, 54, 24, 26, PURPLE_D, 14)


# (key, title, colour, family, sign)
ICONS = [
    ("skillshell", "Skillshell", AAS, "the framework", skillshell),
    ("ontologies", "ontologies", AAS, "definitions", ontologies),
    ("aas-model", "aas-model", AAS, "definitions (fork)", aas_model),
    ("aas-generator", "aas-generator", AAS, "engineering", aas_generator),
    ("modreg", "modreg", AAS, "engineering", modreg),
    ("iec61499-skill-lib", "iec61499-skill-lib", GREEN, "module", skill_lib),
    ("modgen", "modgen", GREEN, "module", modgen),
    ("forte-runtime", "forte-runtime", GREEN, "module", forte_runtime),
    ("modsync", "modsync", GREEN, "engineering", modsync),
    ("iec61499-mgmt-py", "iec61499-mgmt-py", GOLD, "module", iec61499_mgmt),
    ("modplan", "modplan", ORANGE, "engineering", modplan),
    ("lineagents", "lineagents", ORANGE, "operation", lineagents),
    ("modlink", "modlink", BLUE, "operation", modlink),
    ("basyx-aas-web-ui", "basyx-aas-web-ui", BLUE, "operation (fork)", web_ui),
    ("planner", "Planner", BLUE, "web UI app", planner),
    ("skill-editor", "Skill Editor", BLUE, "web UI app", skill_editor),
    ("hmi", "HMI", BLUE, "web UI app", hmi),
    ("orders", "Orders", BLUE, "web UI app", orders),
    ("aas-camel-dmp", "aas-camel-dmp", BLUE, "operation (fork)", dmp),
    ("planar-controller", "planar-controller", BLUE, "operation", planar),
    ("deploy-server", "deploy-server", SLATE, "deployment", deploy_server),
    ("deploy-module", "deploy-module", SLATE, "deployment", deploy_module),
    ("docs", "docs", SLATE, "documentation", docs),
    ("pharma-line", "pharma-line", PURPLE, "the line", pharma_line),
]
BY_KEY = {k: (t, c, f, s) for k, t, c, f, s in ICONS}


def icon(node, key, x, y, size):
    title, color, _, sign = BY_KEY[key]
    g = node.group(f"Icon {title}")
    i = Icon(g, x, y, size, color)
    i.tile()
    sign(i)
    return g


# ---- Page: every icon with its name -----------------------------------------------------------------

def icons_page():
    layer = Node("Icons")
    cols, cw, rh = 6, 210, 190
    for n, (key, title, _, family, _) in enumerate(ICONS):
        cx, y = 30 + (n % cols) * cw + cw / 2, 40 + (n // cols) * rh
        icon(layer, key, cx - 48, y, 96)
        text(layer, cx - cw / 2, y + 104, cw, 22, title, 15, INK, True, "center")
        text(layer, cx - cw / 2, y + 126, cw, 18, family, 12, GREY, False, "center")
    rows = -(-len(ICONS) // cols)
    return ("Icons", 60 + cols * cw, 40 + rows * rh + 10, [layer])


# ---- Page: the organization -----------------------------------------------------------------------

FAMILIES = [
    ("Definitions", AAS, [
        (["ontologies"], "ontologies", "ARSO, APSO, AProSO, PPRL, vocabularies"),
        (["aas-model"], "aas-model (fork)", "the lab's pydantic AAS model")]),
    ("Module", GREEN, [
        (["iec61499-skill-lib", "modgen"], "iec61499-skill-lib", "ModLib, modgen, the module rules"),
        (["forte-runtime"], "forte-runtime", "FORTE per platform, releases"),
        (["iec61499-mgmt-py"], "iec61499-mgmt-py", "the management client")]),
    ("Engineering", "#1F6F6A", [
        (["modsync", "modsync", "modreg", "modplan"], "aas61499-tools", "modsync, modreg, modplan"),
        (["aas-generator"], "aas-generator", "AAS from spec sheets")]),
    ("Operation", BLUE, [
        (["modlink"], "modlink", "skills from the AAS over OPC UA"),
        (["lineagents"], "lineagents", "order, product, resource agents"),
        (["basyx-aas-web-ui", "planner", "skill-editor", "hmi", "orders"], "basyx-aas-web-ui (fork)", "Planner, Skill Editor, HMI, Orders"),
        (["aas-camel-dmp"], "aas-camel-dmp (fork)", "AAS operations to OPC UA, InfluxDB"),
        (["planar-controller"], "planar-controller", "the planar table")]),
    ("Deployment", SLATE, [
        (["deploy-server"], "deploy-server", "the lab's server stack"),
        (["deploy-module"], "deploy-module", "a Raspberry Pi as a module")]),
    ("The line", PURPLE, [
        (["pharma-line"], "pharma-line", "specs, simulators, products, demo")]),
]


def organization_page():
    layer = Node("Organization")
    colw, gap, top, rowh, s = 262, 18, 200, 76, 40
    width = len(FAMILIES) * colw + (len(FAMILIES) - 1) * gap + 80
    main_w = 420
    mx = (width - main_w) / 2
    g = layer.group("Main repository")
    box(g, mx, 30, main_w, 104, f"rounded=1;arcSize=14;fillColor=#FFFFFF;strokeColor={AAS};strokeWidth=2.5;")
    icon(g, "skillshell", mx + 18, 46, 72)
    text(g, mx + 104, 44, main_w - 120, 30, "skillshell", 24, INK, True)
    text(g, mx + 104, 76, main_w - 120, 44, "the main repository: every repository below as a submodule, "
         "the documentation, the whole line in simulation", 13, GREY)
    tallest = max(len(rows) for _, _, rows in FAMILIES)
    colh = 52 + tallest * rowh
    bus = top - 34
    line(layer, [(40 + colw / 2, bus), (width - 40 - colw / 2, bus)], f"html=1;endArrow=none;strokeColor={GREY};"
         "strokeWidth=2;")
    line(layer, [(width / 2, 134), (width / 2, bus)], f"html=1;endArrow=none;strokeColor={GREY};strokeWidth=2;")
    for n, (name, color, rows) in enumerate(FAMILIES):
        x = 40 + n * (colw + gap)
        line(layer, [(x + colw / 2, bus), (x + colw / 2, top)], f"html=1;endArrow=block;endFill=1;endSize=6;"
             f"strokeColor={GREY};strokeWidth=2;")
        f = layer.group(name)
        box(f, x, top, colw, colh, f"rounded=1;arcSize=4;absoluteArcSize=0;fillColor=#F7F8F9;strokeColor={color};"
            "strokeWidth=2;")
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
    return ("Organization", width, top + colh + 40, [layer])


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
