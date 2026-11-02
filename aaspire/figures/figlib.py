"""The drawing kit of the site's figures: the style of the figures in docs/figures (Arial, grey lanes,
white cards, rounded pills, small coloured tags, black step numbers, dashed for what is planned) as
functions that write draw.io cells.

A page is built in absolute coordinates; a cell placed inside a container (a lane, a card) is stored
relative to it, as draw.io wants, so that a card moves with its contents when the figure is edited.
"""
from __future__ import annotations

import base64
import html
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

FONT = "Arial"
INK = "#252B2D"          # text, the plain arrows
SOFT = "#6E777B"         # secondary text, column heads
LINE = "#8F989D"         # a card's border, references
LANE_FILL, LANE_LINE = "#F3F4F5", "#D3D7DA"

# The pillars' colours (docs/framework-plan.md, section 8) and a light tint of each.
COLOR = {"aas": "#2A918B", "planning": "#F07D2E", "integration": "#B88A1C", "reconfiguration": "#5B963B",
         "execution": "#6C91B2", "interfaces": "#56708A", "deployment": "#4A5560", "lines": "#9080B7",
         "product": "#9080B7", "process": "#F07D2E", "resource": "#2A918B", "grey": "#8F989D", "ink": INK}
TINT = {"aas": "#D9EEE5", "planning": "#FCE6D4", "integration": "#F4EBD3", "reconfiguration": "#E3F1DA",
        "execution": "#D8E6F3", "interfaces": "#DEE5EC", "deployment": "#E2E5E8", "lines": "#EEEAF5",
        "product": "#EEEAF5", "process": "#FCE6D4", "resource": "#D9EEE5", "grey": "#F3F4F5", "ink": "#E8EAEB"}
NEW_FILL, NEW_LINE = "#F6DDD6", "#C47A68"          # new, planned or offered only after a reconfiguration

# What an arrow means, by colour (the figures' legend): the same meaning has the same colour everywhere.
ARROW = {
    "flow": (INK, False, "flow"),
    "change": ("#B88A1C", False, "IEC 61499 management protocol"),
    "operate": ("#6C91B2", False, "operate: OPC UA"),
    "step": ("#5B963B", False, "a step runs a primitive"),
    "aas": ("#2A918B", False, "reads or writes an AAS"),
    "message": ("#F07D2E", False, "message: XMPP, I4.0 language"),
    "ref": (LINE, True, "reference, part of"),
    "planned": (NEW_LINE, True, "planned"),
}

AAS_SHELL = ("shape=stencil(zVXbboMwDP0aHpECESV9rHr5gX1BRg1ESwlKskL/fkHuNhKNqA+r6JuPfXByHGwndG9a3kOSk45fIKGHJM93uzeHT"
             "QtSOuTMAf0ZIYhbxGyDkJseKou+K9eCv0vAiLFafcAgzvb+ieha0MJOUXpM6L5WGhqtPrsz4p5PzMm6qOt0q/H7aEx4Q4johEwpuhlzG2FyXbmI"
             "DnLqm4/HlI/CpFpZboXq5nmI5LqB1OVJa8kbL2QGgH7mzu7Zgtr5h/0pIeSybFlE4WsonihhW/i32iwrYCxCXU0Ao5GyBgJ8KmXLApgvgP2rA"
             "OIJKP0XoJF/KI9RVxOQlZGyBk1QvmIPZPnDPVC8YguQhzsgNq5WnaPL472SysAPcsbvNqmFlLiM5vFw+zgXbkN6/AI=);")

LIBRARY = Path(__file__).resolve().parents[2] / "docs" / "figures" / "library" / "tools.xml"


def style(**kv) -> str:
    return "".join(f"{k}={v};" for k, v in kv.items() if v is not None)


def lines(text: str, width: float, size: float = 12) -> int:
    """How many lines ``text`` takes in a box ``width`` wide (Arial, an average glyph about half the
    font size wide; words wrap)."""
    per = max(1, int(width / (size * 0.52)))
    n = 0
    for para in re.sub(r"\*", "", text).split("\n"):
        line, count = 0, 1
        for word in para.split():
            if line and line + 1 + len(word) > per:
                count, line = count + 1, len(word)
            else:
                line += (1 if line else 0) + len(word)
        n += count
    return n


def height(text: str, width: float, size: float = 12) -> float:
    """The height ``text`` takes in a box ``width`` wide."""
    return lines(text, width, size) * size * 1.2


def label(text: str) -> str:
    """A label as draw.io's HTML: ``**bold**`` and ``*italic*`` marks, ``\\n`` breaks a line."""
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", text)
    return text.replace("\n", "<br>")


def icons() -> dict[str, ET.Element]:
    """The framework's icons (docs/figures/library/tools.xml) by name: each an mxGraphModel."""
    text = LIBRARY.read_text(encoding="utf-8")
    found = {}
    for item in json.loads(re.search(r"<mxlibrary>(.*)</mxlibrary>", text, re.S).group(1)):
        xml = item["xml"]
        if not xml.lstrip().startswith("<"):
            xml = urllib.parse.unquote(zlib.decompress(base64.b64decode(xml), -15).decode("utf-8"))
        found[item["title"].split(" ", 2)[-1]] = ET.fromstring(xml)
    return found


class Page:
    """One page of the drawing: cells in absolute coordinates, written as draw.io's mxGraphModel."""

    _icons: dict | None = None

    def __init__(self, name: str, width: int, height: int):
        self.name, self.width, self.height = name, width, height
        self.root = ET.Element("root")
        ET.SubElement(self.root, "mxCell", id="0")
        ET.SubElement(self.root, "mxCell", id="1", parent="0")
        self.where: dict[str, tuple[float, float, float, float]] = {"1": (0, 0, width, height)}
        self.n = 0

    # -- cells --------------------------------------------------------------------------------------

    def _id(self) -> str:
        self.n += 1
        return f"{re.sub(r'[^a-z0-9]', '', self.name.lower())[:12]}-{self.n}"

    def vertex(self, x, y, w, h, value="", st="", parent="1") -> str:
        cid = self._id()
        px, py = self.where[parent][:2]
        cell = ET.SubElement(self.root, "mxCell", id=cid, value=value, style=st, vertex="1", parent=parent)
        ET.SubElement(cell, "mxGeometry", {"x": _n(x - px), "y": _n(y - py), "width": _n(w), "height": _n(h),
                                           "as": "geometry"})
        self.where[cid] = (x, y, w, h)
        return cid

    def text(self, x, y, w, h, value, size=12, color=INK, bold=False, align="left", valign="top", parent="1",
             italic=False) -> str:
        st = "text;" + style(html=1, whiteSpace="wrap", overflow="visible", spacing=0, fontFamily=FONT,
                             fontSize=size, fontColor=color, align=align, verticalAlign=valign,
                             strokeColor="none", fillColor="none", fontStyle=(1 if bold else 0) + (2 if italic else 0))
        return self.vertex(x, y, w, h, label(value), st, parent)

    def lane(self, x, y, w, h, title=None, fill=LANE_FILL, line=LANE_LINE, dashed=False) -> str:
        """A grey band that holds cards, its name at the top left."""
        lid = self.vertex(x, y, w, h, "", style(rounded=1, absoluteArcSize=1, arcSize=10, whiteSpace="wrap",
                                                html=1, fillColor=fill, strokeColor=line, strokeWidth=1,
                                                dashed=1 if dashed else None, container=1, collapsible=0,
                                                recursiveResize=0, fontFamily=FONT))
        if title:
            self.text(x + 12, y + 8, w - 24, 18, title, size=13, bold=True, valign="middle", parent=lid)
        return lid

    def head(self, x, y, w, value, align="left") -> str:
        """A column's name above the lanes."""
        return self.text(x, y, w, 18, value, size=12, color=SOFT, bold=True, align=align, valign="middle")

    def card(self, x, y, w, h=None, title=None, body=None, icon=None, shell=None, tag=None, tag_color="execution",
             dashed=False, line=LINE, fill="#FFFFFF", parent="1", size=12, title_size=13) -> str:
        """A white card: an icon or an AAS shell, a bold title, a tag at the top right, a body below.
        Without ``h`` the card is as high as its body needs; a body that does not fit is reported."""
        top = 34 if title else 10
        need = top + (height(body, w - 20, size) if body else 0) + 10
        if h is None:
            h = round(need)
        elif body and need > h + 2:
            print(f"  {self.name}: '{title}' needs {need:.0f} high, has {h}")
        cid = self.vertex(x, y, w, h, "", style(rounded=1, absoluteArcSize=1, arcSize=12, whiteSpace="wrap",
                                                html=1, fillColor=fill, strokeColor=NEW_LINE if dashed else line,
                                                strokeWidth=1, dashed=1 if dashed else None, container=1,
                                                collapsible=0, recursiveResize=0, fontFamily=FONT), parent)
        tx = x + 10
        if icon:
            self.icon(icon, x + 9, y + 7, 22, parent=cid)
            tx = x + 38
        elif shell:
            self.shell(x + 10, y + 10, shell, parent=cid)
            tx = x + 35
        tw = x + w - tx - 8
        if tag:
            tg = self.tag(0, 0, tag, tag_color, parent=cid, measure_only=True)
            self.tag(x + w - tg - 8, y + 9, tag, tag_color, parent=cid)
            tw -= tg + 6
        if title:
            self.text(tx, y + 8, tw, 20, title, size=title_size, bold=True, valign="middle", parent=cid)
        if body:
            self.text(x + 10, y + top, w - 20, h - top - 8, body, size=size, parent=cid)
        return cid

    def bottom(self, cid: str) -> float:
        x, y, w, h = self.where[cid]
        return y + h

    def side(self, cid: str, which: str, at: float | None = None) -> tuple[float, float]:
        """A point on a cell's outline for ``exit``/``entry``: its ``left``, ``right``, ``top`` or
        ``bottom`` side, at the absolute coordinate ``at`` along it (the middle without)."""
        x, y, w, h = self.where[cid]
        if which in ("left", "right"):
            f = 0.5 if at is None else (at - y) / h
            return (0 if which == "left" else 1, f)
        f = 0.5 if at is None else (at - x) / w
        return (f, 0 if which == "top" else 1)

    def pill(self, x, y, w, value, kind="plain", h=18, size=11, parent="1", bold=False, dashed=None) -> str:
        """A rounded pill: plain, a pillar's colour (``aas``, ``reconfiguration``, ...), ``new`` (dashed
        salmon: new or planned), ``bar`` (a submodel: grey bar, white bold text) or ``dark``."""
        if kind == "plain":
            fill, line, color = "#FFFFFF", LINE, INK
        elif kind == "new":
            fill, line, color, dashed = NEW_FILL, NEW_LINE, INK, True if dashed is None else dashed
        elif kind == "bar":
            fill, line, color, bold = "#9AA2A6", "none", "#FFFFFF", True
        elif kind == "dark":
            fill, line, color, bold = INK, "none", "#FFFFFF", True
        elif kind.startswith("outline-"):
            fill, line, color = "#FFFFFF", COLOR[kind[8:]], INK
        else:
            fill, line, color = TINT[kind], COLOR[kind], INK
        arc = 3 if kind == "bar" else h / 2
        return self.vertex(x, y, w, h, label(value), style(
            rounded=1, absoluteArcSize=1, arcSize=_n(arc * 2), whiteSpace="wrap", html=1, fillColor=fill,
            strokeColor=line, strokeWidth=1, dashed=1 if dashed else None, fontFamily=FONT, fontSize=size,
            fontColor=color, fontStyle=1 if bold else 0, align="center", verticalAlign="middle", spacingLeft=2,
            spacingRight=2), parent)

    def tag(self, x, y, value, color="execution", parent="1", measure_only=False):
        """A small tag, as the figures name the tool of a step: a pillar's colour, bold, 10 px."""
        w = round(len(value) * 6.1 + 12)
        if measure_only:
            return w
        return self.vertex(x, y, w, 16, label(value), style(
            rounded=1, absoluteArcSize=1, arcSize=6, fillColor=TINT[color], strokeColor=COLOR[color],
            strokeWidth=0.8, html=1, whiteSpace="wrap", fontFamily=FONT, fontSize=10, fontColor=COLOR[color],
            fontStyle=1, align="center", verticalAlign="middle"), parent)

    def num(self, x, y, n, parent="1") -> str:
        """A step's number: a black circle."""
        return self.vertex(x, y, 18, 18, str(n), "ellipse;" + style(whiteSpace="wrap", html=1, fillColor=INK,
                                                                    strokeColor="none", fontColor="#FFFFFF",
                                                                    fontStyle=1, fontSize=11, fontFamily=FONT),
                           parent)

    def shell(self, x, y, kind="resource", parent="1", w=19, h=16) -> str:
        """The AAS shell: teal for a resource, purple for a product, orange for a process."""
        return self.vertex(x, y, w, h, "", AAS_SHELL + style(whiteSpace="wrap", html=1, fillColor=COLOR[kind],
                                                              strokeColor="none"), parent)

    def icon(self, name: str, x, y, size=22, parent="1") -> str:
        """A repository's icon from the framework's library, scaled to ``size``."""
        if Page._icons is None:
            Page._icons = icons()
        model = Page._icons[name]
        cells = [c for c in model.iter("mxCell") if c.get("id") not in ("0", "1")]
        group = cells[0]
        k = size / float(group.find("mxGeometry").get("width"))
        gid = self.vertex(x, y, size, size, "", group.get("style"), parent)
        ids = {group.get("id"): gid}
        for c in cells[1:]:
            ids[c.get("id")] = self._id()
        for c in cells[1:]:
            new = ET.SubElement(self.root, "mxCell", {k_: v for k_, v in c.attrib.items()})
            new.set("id", ids[c.get("id")])
            new.set("parent", ids.get(c.get("parent"), gid))
            for end in ("source", "target"):
                if c.get(end):
                    new.set(end, ids[c.get(end)])
            new.set("style", _scale_style(c.get("style") or "", k))
            g = c.find("mxGeometry")
            if g is not None:
                ng = ET.SubElement(new, "mxGeometry", {a: (_n(float(v) * k) if a in ("x", "y", "width", "height")
                                                           else v) for a, v in g.attrib.items()})
                for sub in g:
                    ng.append(_scale_points(sub, k))
        return gid

    def edge(self, src, tgt, value="", kind="flow", exit=None, entry=None, points=(), label_bg="#FFFFFF",
             width=1.25, color=None, dashed=None, size=11, end="block", start=None, curved=False,
             label_pos=None) -> str:
        """An arrow from ``src`` to ``tgt`` (ids); ``kind`` gives its colour and dash (``ARROW``);
        ``exit``/``entry``: (x, y) on the shapes' outlines, 0 to 1; ``points``: waypoints, absolute."""
        c, d, _ = ARROW[kind]
        color = color or c
        dashed = d if dashed is None else dashed
        st = style(edgeStyle="orthogonalEdgeStyle", rounded=1, orthogonalLoop=1, jettySize="auto", html=1,
                   strokeColor=color, strokeWidth=width, dashed=1 if dashed else None,
                   endArrow=end, endFill=1, endSize=6, startArrow=start, startFill=1 if start else None,
                   startSize=6 if start else None, fontFamily=FONT, fontSize=size, fontColor=INK,
                   labelBackgroundColor=label_bg, curved=1 if curved else None)
        if exit:
            st += style(exitX=_n(exit[0]), exitY=_n(exit[1]), exitDx=0, exitDy=0)
        if entry:
            st += style(entryX=_n(entry[0]), entryY=_n(entry[1]), entryDx=0, entryDy=0)
        eid = self._id()
        cell = ET.SubElement(self.root, "mxCell", id=eid, value=label(value), style=st, edge="1", parent="1",
                             source=src, target=tgt)
        g = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
        if label_pos is not None:
            g.set("x", _n(label_pos))
        if points:
            arr = ET.SubElement(g, "Array", {"as": "points"})
            for px, py in points:
                ET.SubElement(arr, "mxPoint", x=_n(px), y=_n(py))
        return eid

    def line(self, x1, y1, x2, y2, kind="flow", value="", width=1.25, end="block", dashed=None) -> str:
        """A free arrow between two points (for the legend and for arrows that point at a lane)."""
        c, d, _ = ARROW[kind]
        st = style(html=1, rounded=1, strokeColor=c, strokeWidth=width, dashed=1 if (d if dashed is None else dashed)
                   else None, endArrow=end, endFill=1, endSize=6, fontFamily=FONT, fontSize=11, fontColor=INK,
                   labelBackgroundColor="#FFFFFF")
        eid = self._id()
        cell = ET.SubElement(self.root, "mxCell", id=eid, value=label(value), style=st, edge="1", parent="1")
        g = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
        ET.SubElement(g, "mxPoint", {"x": _n(x1), "y": _n(y1), "as": "sourcePoint"})
        ET.SubElement(g, "mxPoint", {"x": _n(x2), "y": _n(y2), "as": "targetPoint"})
        return eid

    def legend(self, x, y, kinds, extra=(), gap=None) -> None:
        """The arrows a figure uses, in a row: ``kinds`` from ``ARROW``; ``extra``: (pill kind, text)."""
        items = [("arrow", k, ARROW[k][2]) for k in kinds] + [("pill", k, t) for k, t in extra]
        cx = x
        for what, k, t in items:
            w = round(len(t) * 6.0) + 10
            if what == "arrow":
                self.line(cx, y + 9, cx + 34, y + 9, k)
            else:
                self.pill(cx, y + 2, 34, "", k, h=14)
            self.text(cx + 42, y, w, 18, t, size=11, color=INK, valign="middle")
            cx += 42 + w + (gap or 22)

    # -- output -------------------------------------------------------------------------------------

    def model(self) -> ET.Element:
        m = ET.Element("mxGraphModel", dx="0", dy="0", grid="1", gridSize="10", guides="1", tooltips="1",
                       connect="1", arrows="1", fold="1", page="1", pageScale="1", pageWidth=str(self.width),
                       pageHeight=str(self.height), background="#FFFFFF", math="0", shadow="0")
        m.append(self.root)
        return m


def _n(v: float) -> str:
    v = round(float(v), 2)
    return str(int(v)) if v == int(v) else str(v)


def _scale_style(st: str, k: float) -> str:
    def scale(m):
        return f"{m.group(1)}={_n(float(m.group(2)) * k)}"
    return re.sub(r"\b(strokeWidth|endSize|startSize|fontSize|spacing\w*)=([0-9.]+)", scale, st)


def _scale_points(el: ET.Element, k: float) -> ET.Element:
    new = ET.Element(el.tag, {a: (_n(float(v) * k) if a in ("x", "y") else v) for a, v in el.attrib.items()})
    for sub in el:
        new.append(_scale_points(sub, k))
    return new


def write(path: Path, pages: list[Page], redraw=()) -> list[str]:
    """Write the pages into a draw.io file. A page the file has already (perhaps edited in draw.io
    since) stays as it is unless it is in ``redraw``; pages it lacks are added. Returns the names drawn."""
    old = {}
    if path.exists():
        for d in ET.parse(path).getroot().findall("diagram"):
            old[d.get("name")] = d
    root = ET.Element("mxfile", host="aaspire build_figures.py", type="device")
    written = []
    for i, p in enumerate(pages):
        if p.name in old and p.name not in redraw:
            root.append(old[p.name])
            continue
        d = ET.SubElement(root, "diagram", id=f"page-{i + 1}", name=p.name)
        d.append(p.model())
        written.append(p.name)
    names = {p.name for p in pages}
    for name, d in old.items():               # pages drawn by hand in the file stay too
        if name not in names:
            root.append(d)
    ET.indent(root, space="  ")
    path.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
    return written
