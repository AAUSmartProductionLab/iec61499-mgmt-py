"""Pictures of a 4diac project's blocks, drawn from its files as the 4diac IDE shows them, for
docs/filling-program.md.

    python docs/filling-program/draw_blocks.py              (from the repository's root: the filling module)
    python docs/filling-program/draw_blocks.py --project cell/control/StopperingModule --app Stoppering_pi --out <folder>

It writes, into the output folder:

- ``type-<Type>.svg`` for every block type (and adapter type) of the project's type library: its interface, the event
  pins at the top, the data pins below, each data pin's type outside it and, as thin lines on the
  outside, which data pins go with which event;
- ``inside-<Type>.svg`` for every composite type: the blocks inside it;
- ``ecc-<Type>.svg`` for every basic type: its state machine, each state with its actions and each
  transition a curve through its condition, at the places the generator (``modgen/ecc.py``) gave them;
- ``app-<Application>.svg`` for the application, and ``app-<SubApp>.svg`` (``Dispensing.Execute``)
  for each subapplication in it: the blocks inside;
- ``channels-<Application>.svg``: who writes and who reads which local channel;
- ``legend.svg``: how to read the pictures.

The networks use the positions, groups and block sizes the IDE uses (``modgen/layout.py``): each
block's parameter values are written left of it, and every connection is drawn as the IDE draws a
hidden one, a label at the pin naming the other end (or, for several, how many). These are drawings
from the files, not screenshots: run it again after ``python -m modgen``.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "iec61499-skill-lib"))
from modgen import layout  # noqa: E402

FONT = "Segoe UI, Helvetica, Arial, sans-serif"
SIZE = 58                     # text, in IDE units (a pin row is 100)
WIDE = 0.56                   # average character width, per unit of text size
INK, MUTED, VALUE = "#1f2430", "#6b7280", "#0f6b6b"
EVENT = "#b5452b"
DATA = {"BOOL": "#2e8540", "STRING": "#7d3cb5", "WSTRING": "#7d3cb5", "ANY": "#6b7280"}
NUMBER = "#2563a8"
ADAPTER = "#c0761a"            # a plug or socket: one connection that carries a bundle of events and data
FB_FILL, FB_NECK, FB_LINE = "#eef2f8", "#dde5f1", "#56688a"
SUB_FILL, SUB_NECK, SUB_LINE = "#fbf3dc", "#f3e6bd", "#9a7618"
GROUP_FILL, GROUP_LINE = "#f6f6f1", "#c8c8b8"
LABEL_FILL, LABEL_LINE = "#ffffff", "#9aa3b5"


def colour(typ: str | None) -> str:
    if (typ or "").startswith("adapter:"):
        return ADAPTER
    typ = (typ or "").upper()
    if typ in ("EVENT", "EINIT"):
        return EVENT
    return DATA.get(typ, NUMBER)


def width_of(text: str, size: float = SIZE, bold: bool = False) -> float:
    return len(text) * size * (WIDE + (0.05 if bold else 0.0))


class Canvas:
    """SVG elements and the box they cover, in IDE units."""

    def __init__(self):
        self.parts: list[str] = []
        self.box = [math.inf, math.inf, -math.inf, -math.inf]

    def grow(self, x0, y0, x1, y1):
        b = self.box
        self.box = [min(b[0], x0), min(b[1], y0), max(b[2], x1), max(b[3], y1)]

    def rect(self, x, y, w, h, fill, line, rx=0, stroke=6, dash=None):
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="{rx}" '
                          f'fill="{fill}" stroke="{line}" stroke-width="{stroke}"{extra}/>')
        self.grow(x, y, x + w, y + h)

    def text(self, x, y, s, size=SIZE, anchor="start", bold=False, fill=INK, italic=False):
        w = width_of(s, size, bold)
        x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
        style = (' font-weight="bold"' if bold else "") + (' font-style="italic"' if italic else "")
        self.parts.append(f'<text x="{x:.0f}" y="{y:.0f}" font-size="{size}" text-anchor="{anchor}" '
                          f'fill="{fill}"{style}>{escape(s)}</text>')
        self.grow(x0, y - size, x0 + w, y + size * 0.3)

    def poly(self, points, fill):
        pts = " ".join(f"{px:.0f},{py:.0f}" for px, py in points)
        self.parts.append(f'<polygon points="{pts}" fill="{fill}"/>')
        for px, py in points:
            self.grow(px, py, px, py)

    def line(self, x0, y0, x1, y1, colour_, stroke=5):
        self.parts.append(f'<line x1="{x0:.0f}" y1="{y0:.0f}" x2="{x1:.0f}" y2="{y1:.0f}" '
                          f'stroke="{colour_}" stroke-width="{stroke}"/>')
        self.grow(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    def svg(self, scale: float, pad: float = 120) -> str:
        x0, y0, x1, y1 = self.box[0] - pad, self.box[1] - pad, self.box[2] + pad, self.box[3] + pad
        w, h = x1 - x0, y1 - y0
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w * scale:.0f}" height="{h * scale:.0f}" '
                f'viewBox="{x0:.0f} {y0:.0f} {w:.0f} {h:.0f}" font-family="{FONT}">\n'
                f'<rect x="{x0:.0f}" y="{y0:.0f}" width="{w:.0f}" height="{h:.0f}" fill="#ffffff"/>\n'
                + "\n".join(self.parts) + "\n</svg>\n")


# Interfaces

def pins_of(iface, sub: bool = False):
    """(event inputs, event outputs, data inputs, data outputs), each a list of (name, type, withs)."""
    if iface is None:
        return [], [], [], []
    ev_in, ev_out = ("SubAppEventInputs", "SubAppEventOutputs") if sub else ("EventInputs", "EventOutputs")

    def events(path):
        return [(e.get("Name"), e.get("Type") or "Event", [w.get("Var") for w in e.findall("With")])
                for e in iface.findall(f"{path}/*")]

    def data(path):
        return [(v.get("Name"), v.get("Type"), []) for v in iface.findall(f"{path}/VarDeclaration")]

    def adapters(path):          # sockets with the inputs, plugs with the outputs, drawn below the data
        return [(a.get("Name"), "adapter:" + short(a.get("Type")), []) for a in iface.findall(f"{path}/AdapterDeclaration")]
    return (events(ev_in), events(ev_out), data("InputVars") + adapters("Sockets"),
            data("OutputVars") + adapters("Plugs"))


def is_adapter(pin) -> bool:
    return (pin[1] or "").startswith("adapter:")


def short(typ: str) -> str:
    return typ.rpartition("::")[2]


def type_width(name: str, pins) -> float:
    ins = [p[0] for p in pins[0] + pins[2]]
    outs = [p[0] for p in pins[1] + pins[3]]
    return max(layout.CHAR * (layout.longest(ins) + layout.longest(outs)) + 100,
               layout.NAME_CHAR * len(name) + 150)


# One block

def block(cv: Canvas, x, y, width, pins, name=None, neck="", sub=False):
    """Draw a block whose top left is (x, y); with ``name`` the instance name above it (a row of
    100), as in a network. Returns the y of every pin's row, by (side, pin name)."""
    ei, eo, di, do = pins
    si, po = [q for q in di if is_adapter(q)], [q for q in do if is_adapter(q)]
    di, do = [q for q in di if not is_adapter(q)], [q for q in do if not is_adapter(q)]
    ne, nd, na = max(len(ei), len(eo)), max(len(di), len(do)), max(len(si), len(po))
    fill, neck_fill, line = (SUB_FILL, SUB_NECK, SUB_LINE) if sub else (FB_FILL, FB_NECK, FB_LINE)
    top = y
    if name is not None:
        cv.text(x + width / 2, y + 72, name, anchor="middle", bold=True)
        top = y + 100
    ev_bottom = top + 25 + ne * 100 + 25
    neck_bottom = ev_bottom + 100
    bottom = neck_bottom + (nd + na) * 100 + 50
    cv.rect(x, neck_bottom - 30, width, bottom - neck_bottom + 30, fill, line, rx=30)
    cv.rect(x, top, width, ev_bottom - top + 30, fill, line, rx=30)
    cv.rect(x + 45, ev_bottom, width - 90, 100, neck_fill, line, stroke=5)
    if neck:
        cv.text(x + width / 2, ev_bottom + 70, neck, anchor="middle", fill=INK)
    rows: dict[tuple[str, str], float] = {}
    for i, (pin, _, _) in enumerate(ei):
        yc = top + 25 + i * 100 + 50
        cv.poly([(x + 10, yc - 20), (x + 42, yc), (x + 10, yc + 20)], EVENT)
        cv.text(x + 55, yc + 20, pin)
        rows[("in", pin)] = yc
    for i, (pin, _, _) in enumerate(eo):
        yc = top + 25 + i * 100 + 50
        cv.poly([(x + width - 42, yc - 20), (x + width - 10, yc), (x + width - 42, yc + 20)], EVENT)
        cv.text(x + width - 55, yc + 20, pin, anchor="end")
        rows[("out", pin)] = yc
    for j, (pin, typ, _) in enumerate(di):
        yc = neck_bottom + j * 100 + 50
        cv.rect(x + 12, yc - 16, 32, 32, colour(typ), colour(typ), stroke=1)
        cv.text(x + 55, yc + 20, pin)
        rows[("in", pin)] = yc
    for j, (pin, typ, _) in enumerate(do):
        yc = neck_bottom + j * 100 + 50
        cv.rect(x + width - 44, yc - 16, 32, 32, colour(typ), colour(typ), stroke=1)
        cv.text(x + width - 55, yc + 20, pin, anchor="end")
        rows[("out", pin)] = yc
    for j, (pin, typ, _) in enumerate(si):          # a socket: a notch on the left
        yc = neck_bottom + (nd + j) * 100 + 50
        cv.rect(x + 6, yc - 24, 44, 48, "#ffffff", ADAPTER, rx=8, stroke=7)
        cv.text(x + 62, yc + 20, pin, fill=ADAPTER, bold=True)
        rows[("in", pin)] = yc
    for j, (pin, typ, _) in enumerate(po):          # a plug: a filled tab on the right
        yc = neck_bottom + (nd + j) * 100 + 50
        cv.rect(x + width - 50, yc - 24, 44, 48, ADAPTER, ADAPTER, rx=8, stroke=7)
        cv.text(x + width - 62, yc + 20, pin, anchor="end", fill=ADAPTER, bold=True)
        rows[("out", pin)] = yc
    return rows


def label(cv: Canvas, x, yc, text, side):
    """A hidden connection's label at a pin: left of an input, right of an output. Returns its far edge."""
    w = width_of(text, 48) + 60
    x0 = x - 25 - w if side == "in" else x + 25
    cv.rect(x0, yc - 38, w, 76, LABEL_FILL, LABEL_LINE, rx=14, stroke=4)
    cv.text(x0 + w / 2, yc + 17, text, size=48, anchor="middle", fill=MUTED)
    return x0 if side == "in" else x0 + w


def type_picture(root) -> str:
    """A block type's interface: the pins, their types outside, and the WITH lines."""
    cv = Canvas()
    name = root.get("Name")
    pins = pins_of(root.find("InterfaceList"))
    width = type_width(name, pins)
    rows = block(cv, 0, 0, width, pins, neck=name)
    types = {(side, p[0]): p[1] for side, group in (("in", pins[2]), ("out", pins[3])) for p in group}
    for side, events in (("in", pins[0]), ("out", pins[1])):
        withs = [e for e in events if e[2]]
        for k, (event, _, vars_) in enumerate(withs):
            xk = -40 - k * 28 if side == "in" else width + 40 + k * 28
            ys = [rows[(side, event)]] + [rows[(side, v)] for v in vars_ if (side, v) in rows]
            cv.line(xk, min(ys), xk, max(ys), MUTED, stroke=4)
            for yv in ys:
                cv.rect(xk - 10, yv - 10, 20, 20, MUTED, MUTED, stroke=1)
        reach = 40 + len(withs) * 28 + 20
        for (pin_side, pin), typ in types.items():
            if pin_side == side:
                yc = rows[(side, pin)]
                if side == "in":
                    cv.text(-reach, yc + 18, typ.removeprefix("adapter:"), size=50, anchor="end", fill=MUTED)
                else:
                    cv.text(width + reach, yc + 18, typ.removeprefix("adapter:"), size=50, fill=MUTED)
    return cv.svg(0.25)


# A network

def comment_lines(group) -> list[str]:
    """A group's comment wrapped as modgen/layout.py's ``header`` wraps it."""
    fits = max(1, int((float(group.get("width")) - 2 * layout.PAD) // layout.COMMENT_CHAR))
    lines, line = [], ""
    for word in (group.get("Comment") or "").split():
        if line and len(line) + 1 + len(word) > fits:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}" if line else word
    return lines + ([line] if line else [])


def ends(net) -> dict[tuple[str, str, str], list[str]]:
    """Every connected pin of the network's blocks, by (block, side, pin): the other ends."""
    found: dict[tuple[str, str, str], list[str]] = {}
    for group in net:
        if group.tag in layout.CONNECTIONS:
            for conn in group:
                src, dst = conn.get("Source"), conn.get("Destination")
                for here, there, side in ((dst, src, "in"), (src, dst, "out")):
                    blk, _, pin = here.rpartition(".")
                    if blk:
                        found.setdefault((blk, side, pin), []).append(there)
    return found


def network(net, types: dict, sizer, iface=None, sub_iface: bool = False) -> str:
    cv = Canvas()
    groups = {g.get("Name"): g for g in net.findall("Group")}
    for g in groups.values():
        gx, gy, gw, gh = (float(g.get(k)) for k in ("x", "y", "width", "height"))
        cv.rect(gx, gy, gw, gh, GROUP_FILL, GROUP_LINE, rx=40, stroke=6)
        cv.text(gx + layout.PAD / 2, gy + 140, g.get("Name"), size=70, bold=True, fill="#4b5320")
        for i, text in enumerate(comment_lines(g)):
            cv.text(gx + layout.PAD / 2, gy + layout.HEADER + 85 + i * layout.COMMENT_LINE, text, size=52,
                    fill=MUTED)
    connected = ends(net)
    for el in net:
        if el.tag not in ("FB", "SubApp"):
            continue
        g = groups.get(layout.group_of(el))
        ox, oy = (float(g.get("x")), float(g.get("y")) + layout.header(g)) if g is not None else (0.0, 0.0)
        x, y = ox + float(el.get("x")), oy + float(el.get("y"))
        room, width, _ = sizer(el)
        if el.tag == "SubApp":
            pins, neck, sub = pins_of(el.find("SubAppInterfaceList"), sub=True), "subapplication", True
        else:
            typ = short(el.get("Type"))
            root = types.get(typ)
            pins = pins_of(root.find("InterfaceList")) if root is not None else ([], [], [], [])
            neck, sub = typ, False
        rows = block(cv, x, y, width, pins, name=el.get("Name"), neck=neck, sub=sub)
        far_left: dict[str, float] = {}
        for (blk, side, pin), others in connected.items():
            if blk == el.get("Name") and (side, pin) in rows:
                text = others[0] if len(others) == 1 else f"×{len(others)}"
                edge = label(cv, x if side == "in" else x + width, rows[(side, pin)], text, side)
                if side == "in":
                    far_left[pin] = edge
        for p in el.findall("Parameter"):
            pin, value = p.get("Name"), p.get("Value") or ""
            if ("in", pin) not in rows:
                continue
            most = max(4, int((room - 60) / (48 * WIDE)))
            shown = value if len(value) <= most else value[: most - 1] + "…"
            cv.text(far_left.get(pin, x) - 30, rows[("in", pin)] + 17, shown, size=48, anchor="end", fill=VALUE)
    if iface is not None:
        interface_columns(cv, pins_of(iface, sub=sub_iface))
    return cv.svg(0.2)


def interface_columns(cv: Canvas, pins):
    """The network's own pins (a composite type's or a subapplication's interface), as the IDE draws
    them at the edges of the editor: inputs on the left, outputs on the right."""
    x0, y0, x1, _ = cv.box
    ei, eo, di, do = pins
    for side, events, data in (("in", ei, di), ("out", eo, do)):
        names = [p[0] for p in events + data]
        if not names:
            continue
        w = max(width_of(n) for n in names) + 120
        left = x0 - 300 - w if side == "in" else x1 + 300
        y = y0
        for n, (pin, typ, _) in enumerate(events + data):
            if n == len(events) and events:
                y += 60
            cv.rect(left, y, w, 80, "#ffffff", colour(typ), rx=12, stroke=5)
            mark = left + 20 if side == "in" else left + w - 50
            if n < len(events):
                cv.poly([(mark, y + 20), (mark + 30, y + 40), (mark, y + 60)], EVENT)
            elif (typ or "").startswith("adapter:"):
                cv.rect(mark - 4, y + 18, 38, 44, ADAPTER if side == "out" else "#ffffff", ADAPTER, rx=8, stroke=6)
            else:
                cv.rect(mark, y + 24, 30, 30, colour(typ), colour(typ), stroke=1)
            tx = left + 65 if side == "in" else left + w - 65
            cv.text(tx, y + 60, pin, anchor="start" if side == "in" else "end")
            y += 100


# How to read them

def legend(types: dict, sizer) -> str:
    cv = Canvas()
    root = types["SKILL_FailMerge"]
    pins = pins_of(root.find("InterfaceList"))
    width = type_width("SKILL_FailMerge", pins)
    x, y = 2400, 0
    rows = block(cv, x, y, width, pins, name="Fail1", neck="SKILL_FailMerge")
    edge = label(cv, x, rows[("in", "FAIL_1")], "NeedleDown.FAILURE", "in")
    cv.text(edge - 40, rows[("in", "FAIL_1")] + 18, "connection (hidden): the other end", size=50, anchor="end",
            fill=MUTED)
    edge = label(cv, x + width, rows[("out", "FAIL")], "×2", "out")
    cv.text(edge + 40, rows[("out", "FAIL")] + 18, "connected to two pins", size=50, fill=MUTED)
    cv.text(x - 30, rows[("in", "Error2")] + 17, "0", size=48, anchor="end", fill=VALUE)
    cv.text(x - 130, rows[("in", "Error2")] + 18, "a value set on the pin (a parameter)", size=50, anchor="end",
            fill=VALUE)
    right = x + width + 1050
    notes = [
        (y + 72, "instance name: this block in the program"),
        (rows[("in", "FAIL_2")] + 18, "event pins (triangles): \"now do this\""),
        (y + 100 + 250 + 70, "type: what kind of block it is"),
        (rows[("in", "Error1")] + 18, "data pins (squares): green BOOL, blue numbers,"),
        (rows[("in", "Error2")] + 18, "purple text (STRING, WSTRING), grey ANY"),
    ]
    for yy, text in notes:
        cv.text(right, yy, text, size=50, fill=INK)
    return cv.svg(0.25)


STATE_FILL, STATE_TEXT, ALG_FILL, OUT_FILL, ARROW = "#3f6fb5", "#ffffff", "#dfe7f3", "#dff0d0", "#8a93a6"


def edge(box, towards):
    """Where a line from the centre of ``box`` (x, y, w, h) towards a point leaves the box."""
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    dx, dy = towards[0] - cx, towards[1] - cy
    if dx == 0 and dy == 0:
        return cx, cy
    t = min(w / 2 / abs(dx) if dx else math.inf, h / 2 / abs(dy) if dy else math.inf)
    return cx + dx * t, cy + dy * t


def ecc_picture(root) -> str:
    """A basic type's state machine as the IDE draws it: each state with its actions (algorithm,
    output event), each transition a curve through its condition, at the transition's x and y."""
    cv = Canvas()
    ecc = root.find("BasicFB/ECC")
    from modgen.ecc import state_size
    boxes = {}
    for s in ecc.findall("ECState"):
        w, h = state_size(s)
        boxes[s.get("Name")] = (float(s.get("x", 0)), float(s.get("y", 0)), w, h)
    curves = []
    for t in ecc.findall("ECTransition"):
        src, dst = boxes[t.get("Source")], boxes[t.get("Destination")]
        px, py = float(t.get("x", 0)), float(t.get("y", 0))
        s0 = (src[0] + src[2] / 2, src[1] + src[3] / 2)
        d0 = (dst[0] + dst[2] / 2, dst[1] + dst[3] / 2)
        c = (2 * px - (s0[0] + d0[0]) / 2, 2 * py - (s0[1] + d0[1]) / 2)    # the curve passes the condition
        a, b = edge(src, c), edge(dst, c)
        curves.append(f'<path d="M{a[0]:.0f},{a[1]:.0f} Q{c[0]:.0f},{c[1]:.0f} {b[0]:.0f},{b[1]:.0f}" fill="none" '
                      f'stroke="{ARROW}" stroke-width="7"/>')
        ux, uy = b[0] - c[0], b[1] - c[1]
        n = math.hypot(ux, uy) or 1
        ux, uy = ux / n, uy / n
        tip = [(b[0], b[1]), (b[0] - 60 * ux - 30 * uy, b[1] - 60 * uy + 30 * ux),
               (b[0] - 60 * ux + 30 * uy, b[1] - 60 * uy - 30 * ux)]
        curves.append('<polygon points="' + " ".join(f"{x:.0f},{y:.0f}" for x, y in tip) + f'" fill="{ARROW}"/>')
        cv.grow(min(a[0], b[0], px), min(a[1], b[1], py), max(a[0], b[0], px), max(a[1], b[1], py))
    cv.parts += curves
    first = ecc.find("ECState").get("Name")
    for s in ecc.findall("ECState"):
        x, y, w, h = boxes[s.get("Name")]
        name_w = len(s.get("Name")) * layout.CHAR + 100
        cv.rect(x, y, name_w, h, STATE_FILL, STATE_FILL, rx=12)
        if s.get("Name") == first:
            cv.rect(x - 18, y - 18, name_w + 36, h + 36, "none", STATE_FILL, rx=18)
        cv.text(x + name_w / 2, y + h / 2 + 20, s.get("Name"), anchor="middle", fill=STATE_TEXT, bold=True)
        actions = s.findall("ECAction")
        alg_w = max((len(a.get("Algorithm") or "") for a in actions), default=0) * layout.CHAR
        alg_w = alg_w + 100 if alg_w else 0
        out_w = w - name_w - alg_w
        for i, a in enumerate(actions):
            ry = y + 30 + i * layout.PIN_ROW
            if alg_w:
                cv.rect(x + name_w, ry, alg_w, layout.PIN_ROW, ALG_FILL, FB_LINE, stroke=3)
                cv.text(x + name_w + 50, ry + 72, a.get("Algorithm") or "", size=52)
            if a.get("Output"):
                cv.rect(x + name_w + alg_w, ry, out_w, layout.PIN_ROW, OUT_FILL, FB_LINE, stroke=3)
                cv.text(x + name_w + alg_w + 50, ry + 72, a.get("Output"), size=52)
    for t in ecc.findall("ECTransition"):
        cond = t.get("Condition", "")
        if cond != "1":
            px, py = float(t.get("x", 0)), float(t.get("y", 0))
            w = width_of(cond, 46)
            cv.rect(px - w / 2 - 20, py - 50, w + 40, 70, "#ffffff", "#c9ced8", rx=8, stroke=2)
            cv.text(px, py + 4, cond, size=46, anchor="middle", fill=MUTED)
    return cv.svg(0.16)


# The local channels

def participants(app, types: dict, module: str):
    """Who writes and who reads which local channel, worked out from the application: the module
    level blocks, the equipment blocks, and every skill (its SKILL_Core, and for a primitive its
    port). Returns the channels in order and the columns: (title, members, {channel: "w" or "r"})."""
    found = []

    def walk(net, path):
        for fb in net.findall("FB"):
            found.append((path + fb.get("Name"), short(fb.get("Type")), fb))
        for sub in net.findall("SubApp"):
            walk(sub.find("SubAppNetwork"), path + sub.get("Name") + ".")
    walk(app.find("SubAppNetwork"), "")
    m = module
    items = [n for n, t, _ in found if t.startswith("EQ_")]
    channels = [f"{m}/owner", f"{m}/owner/query", f"{m}/state", f"{m}/state/query", f"{m}/activity",
                f"{m}/release"] + [f"{m}/{i}/{w}" for i in items for w in ("cmd", "state")]
    core = {f"{m}/owner": "r", f"{m}/owner/query": "w", f"{m}/state": "r", f"{m}/state/query": "w",
            f"{m}/activity": "w"}
    columns = []
    for name, typ, _ in found:
        if typ == "MOD_Occupation":
            columns.append((name, [name], {f"{m}/owner": "w", f"{m}/owner/query": "r"}))
        elif typ == "MOD_StateManager":
            columns.append((name, [name], {f"{m}/owner": "r", f"{m}/owner/query": "w", f"{m}/state": "w",
                                           f"{m}/state/query": "r", f"{m}/activity": "r"}))
    skills: dict[str, list[str]] = {}
    for name, typ, fb in found:
        if typ.startswith("SK_"):
            skills.setdefault(typ, []).append(name)
    for typ, names in skills.items():
        net = types[typ].find("FBNetwork")
        port = next((short(f.get("Type")) for f in net.findall("FB") if f.get("Name") == "Port"), "")
        item = port[len("EP_"):] if port.startswith("EP_") else None
        uses = dict(core)
        if item:
            uses.update({f"{m}/{item}/cmd": "w", f"{m}/{item}/state": "r"})
        columns.append((f"{typ[len('SK_'):]} ×{len(names)}", names, uses))
    for name, typ, fb in found:
        if typ == "SKILL_Core":            # a module level skill: it gives up all it holds when a run ends
            given = {p.get("Name"): p.get("Value") for p in fb.findall("Parameter")}
            columns.append((name.split(".")[0], [name], {**core, **({f"{m}/release": "w"}
                                                                   if given.get("ReleaseAll") == "TRUE" else {})}))
    for item in items:
        columns.append((item, [item], {f"{m}/state": "r", f"{m}/state/query": "w", f"{m}/release": "r",
                                       f"{m}/{item}/cmd": "r", f"{m}/{item}/state": "w"}))
    return channels, columns


def channel_map(app, types: dict, module: str) -> str:
    """The local channels as bus bars, one per channel, and every block that uses them as a column:
    an arrow down onto a bar writes on that channel, an arrow up from it reads."""
    channels, columns = participants(app, types, module)
    cv = Canvas()
    col_w, bar_gap, top = 1500, 260, 900
    left = 2600
    WRITE, READ = "#b5452b", "#2563a8"
    for j, (title, members, _) in enumerate(columns):
        x = left + j * col_w
        cv.rect(x - 640, 0, 1280, 620, FB_FILL, FB_LINE, rx=30)
        cv.text(x, 150, title, anchor="middle", bold=True)
        shown = members if len(members) <= 5 else members[:4] + [f"and {len(members) - 4} more"]
        for k, n in enumerate(shown if len(members) > 1 or title != members[0] else []):
            cv.text(x, 250 + k * 70, n, size=44, anchor="middle", fill=MUTED)
    right = left + (len(columns) - 1) * col_w + 700
    carries = {"owner": "who occupies the module", "owner/query": "\"tell me the owner\"",
               "state": "the module's PackML state", "state/query": "\"tell me the state\"",
               "activity": "+1 a skill starts, -1 it ends", "release": "a holder gives up all it holds",
               "cmd": "the holder and the output values", "state#": "the inputs and who holds it"}
    for i, ch in enumerate(channels):
        y = top + i * bar_gap
        cv.line(left - 700, y, right, y, "#9aa3b5", stroke=10)
        cv.text(left - 760, y + 20, f"loc[{ch}]", size=60, anchor="end", fill=INK, bold=True)
        tail = ch.split("/", 1)[1]
        key = tail if tail in carries else ("cmd" if tail.endswith("/cmd") else "state#")
        cv.text(right + 60, y + 20, carries[key], size=54, fill=MUTED)
    # Which columns are what.
    kinds = [("module level", lambda t: t in ("Occupation", "Module")),
             ("equipment blocks", lambda t: t.split(" ")[0] not in ("Occupation", "Module")
              and "×" not in t and t in {c[0] for c in columns[-3:]}),
             ("skills: each with its SKILL_Core; a primitive also with its port (EP_) to its equipment",
              lambda t: "×" in t or t not in ("Occupation", "Module"))]
    placed = set()
    for label_text, test in kinds:
        idx = [j for j, c in enumerate(columns) if test(c[0]) and j not in placed]
        if not idx:
            continue
        placed |= set(idx)
        x0, x1 = left + idx[0] * col_w - 640, left + idx[-1] * col_w + 640
        cv.line(x0, -60, x1, -60, MUTED, stroke=6)
        cv.text((x0 + x1) / 2, -100, label_text, size=56, anchor="middle", fill=MUTED)
    for j, (_, _, uses) in enumerate(columns):
        x = left + j * col_w
        bottom = top + max(i for i, ch in enumerate(channels) if ch in uses) * bar_gap
        cv.line(x, 620, x, bottom, "#c9ced8", stroke=6)
        for i, ch in enumerate(channels):
            if ch not in uses:
                continue
            y = top + i * bar_gap
            if uses[ch] == "w":     # onto the bar
                cv.poly([(x - 45, y - 95), (x + 45, y - 95), (x, y - 12)], WRITE)
            else:                   # off the bar, up to the block
                cv.poly([(x - 45, y - 12), (x + 45, y - 12), (x, y - 95)], READ)
    y = top + len(channels) * bar_gap + 60
    cv.poly([(left - 700, y - 40), (left - 610, y - 40), (left - 655, y + 40)], WRITE)
    cv.text(left - 580, y + 25, "writes (PUBLISH)", size=54, fill=WRITE)
    cv.poly([(left + 200, y + 40), (left + 290, y + 40), (left + 245, y - 40)], READ)
    cv.text(left + 320, y + 25, "reads (SUBSCRIBE)", size=54, fill=READ)
    return cv.svg(0.2)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project", default="cell/control/FillingModule")
    ap.add_argument("--app", default="Filling_pi")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent))
    args = ap.parse_args()
    project = (ROOT / args.project).resolve()
    library = project / "Type Library"
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    types = {p.stem: ET.parse(p).getroot() for p in sorted([*library.rglob("*.fbt"), *library.rglob("*.adp")])}
    sizer = layout.Sizer(library)
    written = 0

    def write(name: str, svg: str):
        nonlocal written
        (out / name).write_text(svg, encoding="utf-8", newline="\n")
        written += 1

    for name, root in types.items():
        write(f"type-{name}.svg", type_picture(root))
        net = root.find("FBNetwork")
        if net is not None:
            write(f"inside-{name}.svg", network(net, types, sizer, iface=root.find("InterfaceList")))
        if root.find("BasicFB/ECC") is not None:
            write(f"ecc-{name}.svg", ecc_picture(root))
    system = ET.parse(next(project.glob("*.sys"))).getroot()
    app = system.find(f"Application[@Name='{args.app}']")
    if app is None:
        raise SystemExit(f"no application {args.app} in {project}")
    write(f"app-{args.app}.svg", network(app.find("SubAppNetwork"), types, sizer))
    module = next((p.get("Value").strip('"') for p in app.iter("Parameter") if p.get("Name") == "Module"), args.app)
    write(f"channels-{args.app}.svg", channel_map(app, types, module))

    def subapps(net, trail):
        for sub in net.findall("SubApp"):
            inner = sub.find("SubAppNetwork")
            if inner is not None:
                path = [*trail, sub.get("Name")]
                write(f"app-{'.'.join(path)}.svg",
                      network(inner, types, sizer, iface=sub.find("SubAppInterfaceList"), sub_iface=True))
                subapps(inner, path)
    subapps(app.find("SubAppNetwork"), [])
    if "SKILL_FailMerge" in types:
        write("legend.svg", legend(types, sizer))
    print(f"{written} pictures in {out}")


if __name__ == "__main__":
    main()
