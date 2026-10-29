"""Builds the isometric shape pack: draw.io libraries in docs/figures/library, one per category, from the
shapes drawn for the figures (taken from their pages by cell id, so a shape and its shadow stay one group)
and the AAS shells drawn here. Also a catalogue (catalogue.drawio): every shape with its name, a page per
category.

    python build_library.py <repo>

In draw.io: File > Open Library from > Device, and pick a .xml file in docs/figures/library.
"""
import base64
import copy
import json
import sys
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
from xml.sax.saxutils import quoteattr

sys.path.insert(0, str(Path(__file__).parent))
from drawlib import (AAS, BLUE, BLUE_D, GREY, INK, PURPLE, SHELL_STYLE, SM_BAR, iso_shell, iso_shell_flat,  # noqa
                     write)

REPO = Path(sys.argv[1])
FIG = REPO / "docs" / "figures"
OUT = FIG / "library"

PAGES = {"L": ("module-tools.drawio", 6),       # Layers (illustrated)
         "C": ("module-tools.drawio", 4),       # Layers (computers)
         "T": ("slides.drawio", 12),            # 12 The tools
         "A": ("slides.drawio", 19)}            # 19 After the paper
_models = {}


def cells_of(page, ids):
    if page not in _models:
        f, i = PAGES[page]
        _models[page] = {c.get("id"): c for c in
                         ET.parse(FIG / f).getroot().findall("diagram")[i].find("mxGraphModel").iter("mxCell")}
    return [copy.deepcopy(_models[page][f"c{i}"]) for i in ids]


def compress(xml):
    data = urllib.parse.quote(xml, safe="-_.!~*'()")
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return base64.b64encode(c.compress(data.encode()) + c.flush()).decode()


def entry(title, cells):
    """One library shape: the cells moved to the origin, grouped when there are several."""
    boxes = []
    for c in cells:
        g = c.find("mxGeometry")
        boxes.append((float(g.get("x", 0)), float(g.get("y", 0)), float(g.get("width")), float(g.get("height"))))
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    w, h = max(b[0] + b[2] for b in boxes) - x0, max(b[1] + b[3] for b in boxes) - y0
    out = []
    parent = "1"
    if len(cells) > 1:
        out.append(f'<mxCell id="g" value="" style="group;tooltip={title.replace(";", ",")};" vertex="1" '
                   f'connectable="0" parent="1"><mxGeometry width="{w:g}" height="{h:g}" as="geometry"/></mxCell>')
        parent = "g"
    for k, c in enumerate(cells):
        c.set("id", f"s{k}"), c.set("parent", parent)
        g = c.find("mxGeometry")
        g.set("x", f"{float(g.get('x', 0)) - x0:g}"), g.set("y", f"{float(g.get('y', 0)) - y0:g}")
        out.append(ET.tostring(c, encoding="unicode"))
    xml = '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(out) + '</root></mxGraphModel>'
    return {"xml": compress(xml), "w": round(w, 1), "h": round(h, 1), "aspect": "fixed", "title": title,
            "_cells": out, "_w": w, "_h": h}


def from_page(page, title, *ids):
    return entry(title, cells_of(page, ids))


def made(title, style, w, h):
    c = ET.Element("mxCell", id="x", value="", style=style, vertex="1", parent="1")
    ET.SubElement(c, "mxGeometry", x="0", y="0", width=f"{w:g}", height=f"{h:g}", **{"as": "geometry"})
    return entry(title, [c])


def made_cells(title, parts):
    """Several drawn cells: [(style, x, y, w, h, value)]."""
    cells = []
    for i, (style, x, y, w, h, value) in enumerate(parts):
        c = ET.Element("mxCell", id=f"x{i}", value=value, style=style, vertex="1", parent="1")
        ET.SubElement(c, "mxGeometry", x=f"{x:g}", y=f"{y:g}", width=f"{w:g}", height=f"{h:g}", **{"as": "geometry"})
        cells.append(c)
    return entry(title, cells)


# ==== The categories ================================================================================
LINE = [
    from_page("L", "Floor slab", 4),
    from_page("L", "Maglev table", 11),
    from_page("L", "Station", 5),
    from_page("C", "Station · filling", 5),
    from_page("C", "Station · stoppering", 7),
    from_page("C", "Station · capping", 9),
    from_page("C", "Station · inspection", 11),
    from_page("L", "Station arm · filling, with a vial", 28),
    from_page("L", "Station arm · stoppering", 29),
    from_page("L", "Station arm · capping", 30),
    from_page("L", "Station arm · inspection camera", 31),
    from_page("L", "Robot, facing right", 10),
    from_page("L", "Robot, facing left", 32),
    from_page("L", "Robot, small", 50, 51),
    from_page("L", "Tray of empty vials", 9),
    from_page("L", "Tray of finished vials", 33),
    from_page("L", "Shuttle, empty", 23),
    from_page("L", "Shuttle with an empty vial", 12),
    from_page("L", "Shuttle with a filled vial", 14),
    from_page("L", "Shuttle with a stoppered vial", 15),
    from_page("L", "Shuttle with a capped vial", 16),
    from_page("C", "Puck, empty", 27),
    from_page("C", "Puck with an empty vial", 16),
    from_page("C", "Puck with a filled vial", 18),
    from_page("C", "Puck with a stoppered vial", 19),
    from_page("C", "Puck with a capped vial", 21),
    from_page("C", "Puck under the camera", 20),
    from_page("L", "Name tag · Filling", 36, 37),
    from_page("L", "Name tag · Stoppering", 38, 39),
    from_page("L", "Name tag · Capping", 40, 41),
    from_page("L", "Name tag · Inspection", 42, 43),
    from_page("L", "Shadow, small", 53),
    from_page("L", "Shadow, wide", 59),
    from_page("L", "Shadow, robot", 50),
]
PARTS = [
    from_page("L", "Raspberry Pi 5", 59, 60),
    from_page("L", "Linear axis (stepper)", 53, 54),
    from_page("L", "Pump", 55, 56),
    from_page("L", "Scale", 57, 58),
    from_page("L", "Piston", 64, 65),
    from_page("L", "Gripper", 71, 72),
    from_page("L", "Camera", 76, 77),
    from_page("L", "Camera, second", 78, 79),
    from_page("L", "Maglev segment with two xbots", 83),
    from_page("L", "Module tile · Filling", 52),
    from_page("L", "Module tile · Stoppering", 61),
    from_page("L", "Module tile · Capping", 68),
    from_page("L", "Module tile · Inspection", 75),
    from_page("L", "Tile · Loading", 49),
    from_page("L", "Tile · Transport", 82),
    from_page("L", "Tile · Unloading", 86),
]
COMPUTERS = [
    from_page("L", "Computer, dark, small", 84),
    from_page("C", "Computer, dark", 84),
    from_page("C", "Computer, grey", 105),
    from_page("C", "Computer, green (FORTE)", 64),
    from_page("C", "Computer, green", 117),
    from_page("C", "Computer, blue", 90),
    from_page("C", "Computer, purple", 111),
    from_page("C", "Computer, gold", 87),
    from_page("L", "Server rack", 141, 142),
    from_page("C", "Database", 93),
    from_page("C", "Database, small, purple", 99),
    from_page("C", "Database, small, blue", 100),
    from_page("L", "Monitor, dark", 131),
    from_page("L", "Monitor, grey", 170),
    from_page("L", "Window · FORTE", 104, 105),
    from_page("L", "Window · AAS server", 131, 132),
    from_page("L", "Window · modsync", 133, 134),
    from_page("L", "Window · modreg", 135, 136),
    from_page("L", "Window · Time series", 137, 138),
    from_page("L", "Window · Orchestrator", 139, 140),
    from_page("L", "Window · Scheduling", 170, 171),
    from_page("L", "Window · Skill editor", 172, 173),
    from_page("L", "Window · Planner", 174, 175),
    from_page("L", "Window · MES", 176, 177),
    from_page("L", "Window · ERP", 178, 179),
    from_page("L", "Window · HMI", 180, 181),
    from_page("L", "Person · planner", 186),
    from_page("L", "Person · operator", 188),
]
SHELLS = []
for lab in ["", "Product", "Process", "Resource", "Module", "Component", "Line"]:
    st, w, h, _ = iso_shell(lab)
    SHELLS.append(made(f"AAS shell, standing{' · ' + lab if lab else ''}", st, w, h))
for lab in ["", "Product", "Process", "Resource", "Module"]:
    st, w, h, _ = iso_shell_flat(lab)
    SHELLS.append(made(f"AAS shell, lying flat{' · ' + lab if lab else ''}", st, w, h))
SHELLS += [from_page("L", "AASs as documents · product", 145),
           from_page("L", "AASs as documents · process", 148),
           from_page("L", "AASs as documents · resource", 151)]
PLANES = [
    from_page("L", "Plane · beige (digital assets)", 48),
    from_page("L", "Plane · green (behaviour)", 94),
    from_page("L", "Plane · blue (AAS models)", 115),
    from_page("L", "Plane · purple (HMI, planning)", 158),
    from_page("L", "Plane label · Digital assets", 89),
    from_page("L", "Plane label · Behaviour · IEC 61499", 112),
    from_page("L", "Plane label · AAS models and orchestration", 154),
    from_page("L", "Plane label · HMI, MES, planning and scheduling", 190),
    from_page("L", "Sketch · a skill's function block network", 101),
    from_page("L", "Sketch · PackML, the module's state", 102),
    from_page("L", "Sketch · a skill's state machine", 103),
    from_page("L", "Sketch · a module's AAS", 123),
    from_page("L", "Sketch · product and process AAS", 124),
    from_page("L", "Sketch · agents", 125),
    from_page("L", "Sketch · schedule", 168),
    from_page("L", "Sketch · HMI, the line at a glance", 169),
]
B = 30 / 86 * 103                                # a flat shell's band, 120 × 103
FLAT = [
    made("AAS shell", SHELL_STYLE, 120, 103),
    *[made_cells(f"AAS shell · {lab}", [(SHELL_STYLE, 0, 0, 120, 103, ""),
                                        ("text;html=1;align=center;verticalAlign=middle;fontFamily=Arial;fontSize=15;"
                                         "fontStyle=1;fontColor=#FFFFFF;strokeColor=none;fillColor=none;",
                                         4, 0, 112, B, lab)]) for lab in ["Product", "Process", "Resource", "Module"]],
    made_cells("Submodel bar", [(f"rounded=1;arcSize=14;whiteSpace=wrap;html=1;fillColor={SM_BAR};strokeColor=none;"
                                 "fontFamily=Arial;fontSize=16;fontColor=#FFFFFF;fontStyle=1;", 0, 0, 260, 34,
                                 "Submodel")]),
    *[made_cells(f"Agent badge · {name}", [(f"ellipse;whiteSpace=wrap;html=1;fillColor={fill};strokeColor=#FFFFFF;"
                                            "strokeWidth=3;fontFamily=Arial;fontSize=22;fontColor=#FFFFFF;fontStyle=1;",
                                            0, 0, 44, 44, mark)])
      for name, mark, fill in [("product", "P", PURPLE), ("resource", "R", BLUE), ("transport", "T", BLUE_D)]],
    from_page("L", "Icon · application", 192),
    from_page("L", "Icon · database", 196),
    from_page("L", "Icon · program, hierarchy", 200),
    from_page("L", "Icon · terminal", 204),
    from_page("L", "Icon · vial", 208),
    from_page("T", "Icon · person", 21),
    from_page("A", "Icon · process steps", 14),
]
CATEGORIES = [("iso-line", "Isometric · the line", LINE), ("iso-parts", "Isometric · parts", PARTS),
              ("iso-computers", "Isometric · computers and software", COMPUTERS),
              ("iso-aas", "Isometric · AAS", SHELLS), ("iso-planes", "Isometric · planes and sketches", PLANES),
              ("flat", "Flat · AAS, agents, icons", FLAT)]

# ==== Write the libraries and the catalogue ===========================================================
OUT.mkdir(parents=True, exist_ok=True)
pages = []
for key, name, items in CATEGORIES:
    lib = [{k: v for k, v in e.items() if not k.startswith("_")} for e in items]
    (OUT / f"{key}.xml").write_text("<mxlibrary>" + json.dumps(lib, ensure_ascii=False) + "</mxlibrary>",
                                    encoding="utf-8")
    # the catalogue page: the shapes in rows, each with its name below
    cells, x, y, row_h, W = [], 40, 40, 0, 1800
    for i, e in enumerate(items):
        s = min(1.0, 260 / e["_w"], 220 / e["_h"])          # big shapes shown smaller
        w, h = e["_w"] * s, e["_h"] * s
        if x + max(w, 200) > W:
            x, y, row_h = 40, y + row_h + 70, 0
        gid = f"e{i}"
        cells.append(f'<mxCell id="{gid}" value="" style="group;tooltip={e["title"].replace(";", ",")};" vertex="1" '
                     f'connectable="0" parent="1"><mxGeometry x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" '
                     f'as="geometry"/></mxCell>')
        for c in e["_cells"]:
            el = ET.fromstring(c)
            if el.get("id") == "g":                     # the entry's own group: its cells go straight in ours
                continue
            el.set("id", f"{gid}{el.get('id')}"), el.set("parent", gid)
            g = el.find("mxGeometry")
            for a in ("x", "y", "width", "height"):     # draw.io does not scale a group's cells with it
                if g.get(a) is not None:
                    g.set(a, f"{float(g.get(a)) * s:g}")
            if "fontSize=" in (el.get("style") or ""):
                import re
                el.set("style", re.sub(r"fontSize=([\d.]+)", lambda m: f"fontSize={float(m.group(1)) * s:g}",
                                       el.get("style")))
            cells.append(ET.tostring(el, encoding="unicode"))
        cells.append(f'<mxCell id="{gid}t" value={quoteattr(e["title"])} style="text;html=1;align=center;'
                     f'verticalAlign=top;whiteSpace=wrap;fontFamily=Arial;fontSize=13;fontColor={GREY};" vertex="1" '
                     f'parent="1"><mxGeometry x="{x + w / 2 - 110:g}" y="{y + h + 6:g}" width="220" height="40" '
                     f'as="geometry"/></mxCell>')
        x += max(w, 200) + 50
        row_h = max(row_h, h)
    pages.append((name, W, int(y + row_h + 120), ['<mxCell id="1" parent="0"/>' + "\n".join(cells)]))
write(OUT / "catalogue.drawio", pages)
for key, name, items in CATEGORIES:
    print(f"{key}.xml  {len(items):3d} shapes  {name}")
