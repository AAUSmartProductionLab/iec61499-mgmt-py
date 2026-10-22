"""Compact layout of a system's networks: blocks in a grid inside their groups, groups side by side.

The 4diac IDE draws a block about 100 units high per pin row (the larger of the event and of the
data pins, in or out) plus 300, and about as wide as its longest pin names or its type and
instance name; its system check reports blocks that overlap with these sizes, which is how they
were measured. Left of a block the IDE writes the values of its parameters, and since every
connection is hidden, at each connected pin a label naming the other end (or how many there are):
a block gets room for the longest of them on each side. A block in a group is placed relative to
the group's content, which begins below the group's title and its wrapped comment.

``relayout`` lays out one network from scratch; ``place_new`` gives the blocks that a layout
arranged in the IDE does not have yet (a skill added since) a free place in their group.
"""
from __future__ import annotations

import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

PIN_ROW, BLOCK, CHAR, NAME_CHAR = 100, 300, 45, 60     # IDE units
GAP, TOP, PAD, GROUP_GAP, ROW_WIDTH = 200, 150, 200, 300, 12000
VALUE_ROOM = (100, 1500)                                 # room for parameter values, least and most
LABEL_CHAR, LABEL_PAD, LABEL_MOST = 40, 150, 40          # a hidden connection's label: per character, arrow
OUTER = 8                    # characters the IDE writes for the enclosing instance at an interface pin
HEADER, COMMENT_LINE, COMMENT_CHAR = 220, 110, 36        # a group's title, and per line of its comment
CONNECTIONS = ("EventConnections", "DataConnections", "AdapterConnections")
GENERIC = re.compile(r"(PUBLISH|SUBSCRIBE|SERVER|CLIENT)_(\d+)(?:_(\d+))?")


class Sizer:
    """The size of a block as the IDE draws it, from its interface: (room for values, width, height)."""

    def __init__(self, types: Path):
        self.files = {p.stem: p for p in Path(types).rglob("*.fbt")}
        self.pins: dict[str, tuple[list[str], list[str], int]] = {}

    def interface(self, typ: str) -> tuple[list[str], list[str], int]:
        """Input and output pin names of a block type, and how many rows its pins take."""
        name = typ.rpartition("::")[2]
        if name not in self.pins:
            if name in self.files:
                iface = ET.parse(self.files[name]).getroot().find("InterfaceList")
                self.pins[name] = pins(iface, "EventInputs", "EventOutputs")
            elif m := GENERIC.fullmatch(name):          # generic comm FBs are declared after the system
                kind, a, b = m[1], int(m[2]), int(m[3] or 0)
                sd, rd = {"PUBLISH": (a, 0), "SUBSCRIBE": (0, a), "SERVER": (b, a), "CLIENT": (a, b)}[kind]
                ins, outs = ["INIT", "REQ", "QI", "ID"] + [f"SD_{i}" for i in range(sd)], \
                    ["INITO", "CNF", "QO", "STATUS"] + [f"RD_{i}" for i in range(rd)]
                self.pins[name] = (ins, outs, 2 + max(2 + sd, 2 + rd))
            else:
                self.pins[name] = (["INPUT_PIN"] * 4, ["OUTPUT"] * 4, 8)
        return self.pins[name]

    def __call__(self, el) -> tuple[float, float, float]:
        if el.tag == "SubApp":
            ins, outs, rows = pins(el.find("SubAppInterfaceList"), "SubAppEventInputs", "SubAppEventOutputs")
            label = el.get("Name")
        else:
            ins, outs, rows = self.interface(el.get("Type"))
            label = max(el.get("Name"), el.get("Type").rpartition("::")[2], key=len)
        width = max(CHAR * (longest(ins) + longest(outs)) + 100, NAME_CHAR * len(label) + 150)
        values = [p.get("Value") or "" for p in el.findall("Parameter")]
        room = min(VALUE_ROOM[1], max(VALUE_ROOM[0], CHAR * longest(values) + 100)) if values else VALUE_ROOM[0]
        return room, width, PIN_ROW * rows + BLOCK


def pins(iface, events_in: str, events_out: str) -> tuple[list[str], list[str], int]:
    if iface is None:
        return [], [], 1
    names = lambda path: [e.get("Name") for e in iface.findall(path)]  # noqa: E731
    ei, eo = names(f"{events_in}/*"), names(f"{events_out}/*")
    di, do = names("InputVars/VarDeclaration"), names("OutputVars/VarDeclaration")
    return ei + di, eo + do, max(1, max(len(ei), len(eo)) + max(len(di), len(do)))


def longest(texts) -> int:
    return max((len(t) for t in texts), default=0)


def num(value: float) -> str:
    return str(int(round(value)))


def group_of(el) -> str | None:
    attr = el.find("Attribute[@Name='GroupName']")
    return attr.get("Value") if attr is not None else None


def header(group) -> float:
    """The height of a group's title and its comment, wrapped at the group's width: the group's
    blocks are placed relative to below it."""
    fits = max(1, int((float(group.get("width")) - 2 * PAD) // COMMENT_CHAR))
    lines, line = 0, 0
    for word in (group.get("Comment") or "").split():
        if line and line + 1 + len(word) > fits:
            lines, line = lines + 1, len(word)
        else:
            line += len(word) + (1 if line else 0)
    return HEADER + COMMENT_LINE * (lines + (1 if line else 0))


def labels(net) -> dict[str, list[float]]:
    """The room the labels of hidden connections take left (inputs) and right (outputs) of each
    block of a network. A pin with one connection is labelled with its other end, one with more
    with their number."""
    ends: dict[tuple[str, int, str], list[str]] = {}
    for group in net:
        if group.tag in CONNECTIONS:
            for conn in group:
                src, dst = conn.get("Source"), conn.get("Destination")
                for here, there, side in ((dst, src, 0), (src, dst, 1)):
                    block, _, pin = here.rpartition(".")
                    if block:
                        ends.setdefault((block, side, pin), []).append(there)
    room: dict[str, list[float]] = {}
    for (block, side, _), others in ends.items():
        text = others[0] if len(others) == 1 else str(len(others))
        if len(others) == 1 and "." not in text:
            text = "x" * OUTER + "." + text                   # a pin of the network's own interface
        r = room.setdefault(block, [0.0, 0.0])
        r[side] = max(r[side], LABEL_CHAR * min(len(text), LABEL_MOST) + LABEL_PAD)
    return room


def measure(net, size):
    """The box of a block in ``net``: (room left, width, height, room right), the room for its
    parameter values and connection labels."""
    room = labels(net)

    def box(el) -> tuple[float, float, float, float]:
        values, width, height = size(el)
        left, right = room.get(el.get("Name"), (0.0, 0.0))
        return max(values, left), width, height, right
    return box


def columns(n: int, sequence: bool = False) -> int:
    """A row for a few blocks (a sequence of steps up to six), else about square."""
    return n if n <= (6 if sequence else 3) else math.ceil(math.sqrt(n))


def grid(blocks, box, left: float, top: float, cols: int) -> tuple[float, float]:
    """Place ``blocks`` in rows of ``cols`` from (left, top); return the width and height they take."""
    sizes = [box(b) for b in blocks]
    col_w = [max((s[0] + s[1] + s[3] for s in sizes[c::cols]), default=0) for c in range(cols)]
    rows = [sizes[r:r + cols] for r in range(0, len(sizes), cols)]
    row_h = [max(s[2] for s in row) for row in rows]
    for i, (b, (room, _, _, _)) in enumerate(zip(blocks, sizes)):
        c, r = i % cols, i // cols
        b.set("x", num(left + sum(col_w[:c]) + GAP * c + room))
        b.set("y", num(top + sum(row_h[:r]) + GAP * r))
    return sum(col_w) + GAP * (cols - 1), sum(row_h) + GAP * (len(rows) - 1)


def relayout(net, size, x0: float = 1000, y0: float = 1000):
    """Lay out a network: each group's blocks in a grid inside it, the groups in rows of at most
    ``ROW_WIDTH``, blocks in no group below them (a sequence's steps in a row)."""
    blocks = [el for el in net if el.tag in ("FB", "SubApp")]
    if not blocks:
        return
    box = measure(net, size)
    groups = [g for g in net if g.tag == "Group"]
    x, y, row_h = x0, y0, 0.0
    for g in groups:
        members = [b for b in blocks if group_of(b) == g.get("Name")]
        w, h = grid(members, box, PAD, TOP, columns(len(members))) if members else (1000, 0)
        g.set("width", num(w + 2 * PAD))
        w, h = w + 2 * PAD, header(g) + TOP + h + PAD
        if x > x0 and x + w > x0 + ROW_WIDTH:
            x, y, row_h = x0, y + row_h + GROUP_GAP, 0.0
        g.set("x", num(x))
        g.set("y", num(y))
        g.set("height", num(h))
        x, row_h = x + w + GROUP_GAP, max(row_h, h)
    loose = [b for b in blocks if group_of(b) not in {g.get("Name") for g in groups}]
    if loose:
        grid(loose, box, x0, y + row_h + GROUP_GAP if groups else y0, columns(len(loose), sequence=not groups))


def networks(root):
    """Every block network: of a system, the applications' and those of the subapplications in them;
    of a composite type, its network."""
    return [n for n in root.iter() if n.tag in ("SubAppNetwork", "FBNetwork")]


def place_new(root, kept: set[int], size):
    """After a layout arranged in the IDE was kept: blocks it did not have yet go below the other
    blocks of their group (which grows to hold them), new groups below the other groups, a new block
    in no group to the right of the others."""
    for net in networks(root):
        elements = [el for el in net if el.tag in ("FB", "SubApp", "Group")]
        if not any(id(el) in kept for el in elements):
            continue                                       # a network new as a whole keeps its fresh layout
        groups = {g.get("Name"): g for g in net if g.tag == "Group"}
        bottom = max((float(g.get("y")) + float(g.get("height")) for g in groups.values() if id(g) in kept), default=1000)
        for g in groups.values():
            if id(g) not in kept:
                g.set("x", "1000")
                g.set("y", num(bottom + GROUP_GAP))
                bottom += GROUP_GAP + float(g.get("height"))
        blocks = [el for el in net if el.tag in ("FB", "SubApp")]
        box = measure(net, size)
        for b in blocks:
            if id(b) in kept or group_of(b) in groups:
                continue
            others = [o for o in blocks if id(o) in kept and group_of(o) not in groups]
            room, _, _, _ = box(b)
            right = max((float(o.get("x")) + box(o)[1] + box(o)[3] for o in others), default=1000)
            b.set("x", num(right + GAP + room))
            b.set("y", num(min((float(o.get("y")) for o in others), default=1000)))
            kept.add(id(b))
        for b in blocks:
            if id(b) in kept or group_of(b) not in groups or id(groups[group_of(b)]) not in kept:
                continue
            g = groups[group_of(b)]
            others = [o for o in blocks if group_of(o) == g.get("Name") and id(o) in kept]
            room, _, h, _ = box(b)
            top = max((float(o.get("y")) + box(o)[2] for o in others), default=TOP - GAP) + GAP
            b.set("x", num(PAD + room))
            b.set("y", num(top))
            kept.add(id(b))
            g.set("height", num(max(float(g.get("height")), header(g) + top + h + PAD)))
