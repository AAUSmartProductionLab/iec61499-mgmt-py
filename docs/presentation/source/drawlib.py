"""Drawing helpers for draw.io pages: layers and nested groups in page coordinates, the AAS shell."""
import base64
import urllib.parse
import zlib
from xml.sax.saxutils import quoteattr

INK, GREY = "#252B2D", "#6E777B"
ORANGE, ORANGE_D = "#F07D2E", "#C9621F"
GREEN, GREEN_D = "#5B963B", "#3F7A2A"          # IEC 61499 events, a Pi running its program
BLUE, BLUE_D = "#6C91B2", "#4D7392"            # resources, OPC UA
PURPLE, PURPLE_D = "#9080B7", "#6F5E99"        # the product
GOLD = "#B88A1C"                               # the management protocol
AAS = "#2A918B"                                # every AAS shell
SM_BAR = "#A7ACB6"                             # a submodel bar
RUN_FILL, OPC_FILL, STEP_FILL, PROD_FILL = "#E3F1DA", "#E1EAF2", "#FCE3D0", "#EEEAF5"
FB_FILL, FB_STROKE = "#EEF3F7", "#7D93A6"     # a function block

_ids = [0]


def nid(prefix="c"):
    _ids[0] += 1
    return f"{prefix}{_ids[0]}"


class Node:
    """A layer or a group: holds cells in page coordinates, written relative to the group."""

    def __init__(self, name, visible=True, layer=True):
        self.id, self.name, self.visible, self.layer, self.items = nid("n"), name, visible, layer, []

    def group(self, name):
        g = Node(name, layer=False)
        self.items.append(g)
        return g

    def bounds(self):
        xs, ys, xe, ye = [], [], [], []
        for it in self.items:
            b = it.bounds() if isinstance(it, Node) else it["box"]
            xs.append(b[0]), ys.append(b[1]), xe.append(b[0] + b[2]), ye.append(b[1] + b[3])
        return min(xs), min(ys), max(xe) - min(xs), max(ye) - min(ys)

    def emit(self, out, parent="0", ox=0, oy=0):
        if self.layer:
            out.append(f'<mxCell id="{self.id}" value={quoteattr(self.name)} parent="0"'
                       + ('' if self.visible else ' visible="0"') + '/>')
            gx, gy = 0, 0
        else:
            gx, gy, w, h = self.bounds()
            # The group's name is kept as a tooltip, so it shows in draw.io and survives a save.
            out.append(f'<mxCell id="{self.id}" value="" style="group;tooltip={_esc(self.name)};" vertex="1" '
                       f'connectable="0" parent="{parent}">'
                       f'<mxGeometry x="{gx - ox:g}" y="{gy - oy:g}" width="{w:g}" height="{h:g}" as="geometry"/>'
                       f'</mxCell>')
        for it in self.items:
            if isinstance(it, Node):
                it.emit(out, self.id, gx, gy)
            else:
                out.append(it["xml"](self.id, gx, gy))


def _esc(s):
    return s.replace(";", ",").replace("=", ":")


def box(node, x, y, w, h, style, value=""):
    cid = nid()
    node.items.append({"box": (x, y, w, h), "xml": lambda p, ox, oy: (
        f'<mxCell id="{cid}" value={quoteattr(value)} style={quoteattr(style)} vertex="1" parent="{p}">'
        f'<mxGeometry x="{x - ox:g}" y="{y - oy:g}" width="{w:g}" height="{h:g}" as="geometry"/></mxCell>')})


def line(node, pts, style, value=""):
    cid = nid()
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]

    def xml(p, ox, oy):
        (x0, y0), (x1, y1), mid = pts[0], pts[-1], pts[1:-1]
        way = "".join(f'<mxPoint x="{x - ox:g}" y="{y - oy:g}"/>' for x, y in mid)
        return (f'<mxCell id="{cid}" value={quoteattr(value)} style={quoteattr(style)} edge="1" parent="{p}">'
                f'<mxGeometry relative="1" as="geometry"><mxPoint x="{x0 - ox:g}" y="{y0 - oy:g}" as="sourcePoint"/>'
                f'<mxPoint x="{x1 - ox:g}" y="{y1 - oy:g}" as="targetPoint"/>'
                + (f'<Array as="points">{way}</Array>' if mid else "") + '</mxGeometry></mxCell>')
    node.items.append({"box": (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)), "xml": xml})


def text(node, x, y, w, h, value, size=16, color=GREY, bold=False, align="left", font="Arial", valign="middle"):
    box(node, x, y, w, h, f"text;html=1;whiteSpace=wrap;fontFamily={font};fontSize={size};fontColor={color};"
        f"align={align};verticalAlign={valign};strokeColor=none;fillColor=none;" + ("fontStyle=1;" if bold else ""),
        value)


def rect(node, x, y, w, h, fill, stroke="none", sw=1, rounded=0, extra="", value="", size=16, color=INK,
         bold=False, align="center"):
    box(node, x, y, w, h, f"rounded={1 if rounded else 0};arcSize={rounded or 10};whiteSpace=wrap;html=1;"
        f"fillColor={fill};strokeColor={stroke};strokeWidth={sw};fontFamily=Arial;fontSize={size};"
        f"fontColor={color};align={align};spacingLeft=8;spacingRight=8;" + ("fontStyle=1;" if bold else "") + extra, value)


def pill(node, x, y, w, h, value, fill="#FFFFFF", stroke=INK, sw=1.5, size=18, color=INK, bold=False, dashed=False):
    box(node, x, y, w, h, f"rounded=1;arcSize=50;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
        f"strokeWidth={sw};fontFamily=Arial;fontSize={size};fontColor={color};" + ("fontStyle=1;" if bold else "")
        + ("dashed=1;" if dashed else ""), value)


def ring(node, x, y, w, h, color, arc=12, sw=3):
    box(node, x, y, w, h, f"rounded=1;arcSize={arc};html=1;fillColor=none;strokeColor={color};strokeWidth={sw};")


def arrow(node, pts, color=INK, sw=2, dashed=False, label="", size=13, end="block", start=None, label_color=None,
          above=False):
    style = (f"html=1;rounded=1;strokeColor={color};strokeWidth={sw};endArrow={end};endFill=1;endSize=7;"
             + ("verticalAlign=bottom;spacingBottom=4;" if above else "")
             + (f"startArrow={start};startFill=1;startSize=7;" if start else "")
             + ("dashed=1;" if dashed else "")
             + f"fontFamily=Arial;fontSize={size};fontColor={label_color or color};labelBackgroundColor=#FFFFFF;")
    line(node, pts, style, label)


def image(node, x, y, w, h, uri):
    box(node, x, y, w, h, f"shape=image;aspect=fixed;imageAspect=0;image={uri};")


def png_uri(path):
    return "data:image/png," + base64.b64encode(open(path, "rb").read()).decode()


# ---- The AAS shell ---------------------------------------------------------------------------------
# An arch with rounded corners, like the AAS logo, without an asset inside. A stencil, so its colour is
# the shape's fill colour (Format panel in draw.io) and it scales to any size.
SHELL_W, SHELL_H, BAND, LEG = 100, 86, 30, 17


def _shell_path():
    R, r, f = 10, 8, 5          # outer corners, the inner top corners, a leg's foot
    W, H, L, B = SHELL_W, SHELL_H, LEG, BAND
    arc = lambda rr, x, y, sweep: (f'<arc rx="{rr}" ry="{rr}" x-axis-rotation="0" large-arc-flag="0" '
                                   f'sweep-flag="{sweep}" x="{x}" y="{y}"/>')
    ln = lambda x, y: f'<line x="{x}" y="{y}"/>'
    return (f'<move x="{R}" y="0"/>' + ln(W - R, 0) + arc(R, W, R, 1) + ln(W, H - f) + arc(f, W - f, H, 1)
            + ln(W - L + f, H) + arc(f, W - L, H - f, 1) + ln(W - L, B + r) + arc(r, W - L - r, B, 0)
            + ln(L + r, B) + arc(r, L, B + r, 0) + ln(L, H - f) + arc(f, L - f, H, 1) + ln(f, H) + arc(f, 0, H - f, 1)
            + ln(0, R) + arc(R, R, 0, 1) + '<close/>')


def _stencil(xml):
    data = urllib.parse.quote(xml, safe="-_.!~*'()")
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return base64.b64encode(c.compress(data.encode()) + c.flush()).decode()


SHELL_STYLE = ("shape=stencil(" + _stencil(
    f'<shape name="AAS shell" w="{SHELL_W}" h="{SHELL_H}" aspect="variable" strokewidth="inherit">'
    f'<foreground><path>{_shell_path()}</path><fillstroke/></foreground></shape>')
    + f");whiteSpace=wrap;html=1;fillColor={AAS};strokeColor=none;")


def shell(node, x, y, w, h, label="", size=None, fill=AAS, picture=None, pic_size=None, name=None):
    """An AAS: the shell with its name on the band, optionally a picture inside; returns its group."""
    g = node.group(name or (label.replace("<br>", " ") or "AAS shell"))
    box(g, x, y, w, h, SHELL_STYLE.replace(AAS, fill))
    band = h * BAND / SHELL_H
    if label:
        text(g, x + 4, y, w - 8, band, label, size or max(9, int(band * 0.42)), "#FFFFFF", True, "center")
    if picture:
        leg = w * LEG / SHELL_W
        iw, ih = pic_size
        aw, ah = w - 2 * leg - 16, h - band - 12
        s = min(aw / iw, ah / ih)
        image(g, x + (w - iw * s) / 2, y + band + 6 + (ah - ih * s) / 2, iw * s, ih * s, picture)
    return g


def polygon(node, pts, fill, stroke, sw=2, extra=""):
    """A closed polygon in page coordinates, as a stencil in its bounding box (so it stays one shape)."""
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0, w, h = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    path = (f'<move x="{pts[0][0] - x0:g}" y="{pts[0][1] - y0:g}"/>'
            + "".join(f'<line x="{x - x0:g}" y="{y - y0:g}"/>' for x, y in pts[1:]) + '<close/>')
    st = _stencil(f'<shape name="polygon" w="{w:g}" h="{h:g}" aspect="variable" strokewidth="inherit">'
                  f'<foreground><path>{path}</path><fillstroke/></foreground></shape>')
    box(node, x0, y0, w, h, f"shape=stencil({st});html=1;fillColor={fill};strokeColor={stroke};strokeWidth={sw};"
        + extra)


def iso_shell(label="", W=130, H=110, D=30, fill=AAS):
    """The AAS shell as an isometric solid: its outline (with the logo's rounded corners) extruded by D,
    drawn on the isometric axes (x down to the right, y down to the left, z up) and shaded like the
    figures' boxes; the name on the front of the band. Returns (style, width, height, top), where top is the
    point of the image where the middle of the shell's top face is, to stand it under a line's end."""
    import math
    s = H / SHELL_H                                      # the logo's proportions, scaled to height H
    w0, band, leg, R, r, f = SHELL_W, BAND, LEG, 10, 8, 5
    def arc(cx, cy, rad, a0, a1, n=6):
        return [(cx + rad * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                 cy + rad * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
    # The outline in the logo's own units (y down), clockwise from the top left
    pts = (arc(R, R, R, 180, 270) + arc(w0 - R, R, R, 270, 360) + arc(w0 - f, SHELL_H - f, f, 0, 90)
           + arc(w0 - leg + f, SHELL_H - f, f, 90, 180) + arc(w0 - leg - r, band + r, r, 0, -90)
           + arc(leg + r, band + r, r, 270, 180) + arc(leg - f, SHELL_H - f, f, 0, 90)
           + arc(f, SHELL_H - f, f, 90, 180))
    prof = [(px * W / w0, (SHELL_H - py) * s) for px, py in pts]        # (x along the front, z up)
    proj = lambda x, y, z: (0.866 * (x - y), 0.5 * (x + y) - z)
    front = [proj(x, D, z) for x, z in prof]
    back = [proj(x, 0, z) for x, z in prof]
    faces = []
    n = len(prof)
    for i in range(n):
        (x1, z1), (x2, z2) = prof[i], prof[(i + 1) % n]
        nx, nz = -(z2 - z1), x2 - x1                     # the outward normal
        if nx + nz <= 1e-9:
            continue                                     # faces away from the viewer
        shade = "#45B8B0" if nz > abs(nx) else "#1F6F6A"  # tops lighter, the sides darker
        quad = [back[i], back[(i + 1) % n], front[(i + 1) % n], front[i]]
        depth = (x1 + x2) / 2 + D / 2 + (z1 + z2) / 2
        faces.append((depth, quad, shade))
    xs = [p[0] for p in front + back]
    ys = [p[1] for p in front + back]
    x0, y0 = min(xs) - 2, min(ys) - 2
    w, h = max(xs) - x0 + 2, max(ys) - y0 + 2
    poly = lambda q, c: (f'<polygon points="{" ".join(f"{x - x0:.1f},{y - y0:.1f}" for x, y in q)}" fill="{c}" '
                         f'stroke="{c}" stroke-width="0.6" stroke-linejoin="round"/>')
    body = [poly(back, "#1F6F6A")] + [poly(q, c) for _, q, c in sorted(faces)] + [poly(front, fill)]
    if label:
        bx, by = proj(W / 2, D, H - band * s / 2)
        size = band * s * 0.46
        body.append(f'<text transform="matrix(0.866,0.5,0,1,{bx - x0:.1f},{by - y0:.1f})" text-anchor="middle" '
                    f'dominant-baseline="central" font-family="Arial" font-weight="bold" font-size="{size:.1f}" '
                    f'fill="#FFFFFF">{label}</text>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.1f}" height="{h:.1f}" '
           f'viewBox="0 0 {w:.1f} {h:.1f}">' + "".join(body) + '</svg>')
    tx, ty = proj(W / 2, D / 2, H)
    style = ("shape=image;aspect=fixed;imageAspect=0;image=data:image/svg+xml,"
             + base64.b64encode(svg.encode()).decode() + ";")
    return style, w, h, (tx - x0, ty - y0)


def iso_shell_flat(label="", W=130, H=110, T=10, fill=AAS):
    """The AAS shell lying flat on an isometric plane, T thick, its band at the back, its legs towards the
    viewer, the name on the band's top. Returns (style, width, height, centre): centre is where the middle
    of the shell's top face is in the image."""
    import math
    s = H / SHELL_H
    w0, band, leg, R, r, f = SHELL_W, BAND, LEG, 10, 8, 5
    def arc(cx, cy, rad, a0, a1, n=6):
        return [(cx + rad * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                 cy + rad * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
    pts = (arc(R, R, R, 180, 270) + arc(w0 - R, R, R, 270, 360) + arc(w0 - f, SHELL_H - f, f, 0, 90)
           + arc(w0 - leg + f, SHELL_H - f, f, 90, 180) + arc(w0 - leg - r, band + r, r, 0, -90)
           + arc(leg + r, band + r, r, 270, 180) + arc(leg - f, SHELL_H - f, f, 0, 90)
           + arc(f, SHELL_H - f, f, 90, 180))
    prof = [(px * W / w0, py * s) for px, py in pts]     # (x along the plane, y across it, towards the viewer)
    proj = lambda x, y, z: (0.866 * (x - y), 0.5 * (x + y) - z)
    top = [proj(x, y, T) for x, y in prof]
    bottom = [proj(x, y, 0) for x, y in prof]
    sides = []
    n = len(prof)
    for i in range(n):
        (x1, y1), (x2, y2) = prof[i], prof[(i + 1) % n]
        if (y2 - y1) - (x2 - x1) <= 1e-9:                # the outward normal (dy, -dx) faces away
            continue
        quad = [bottom[i], bottom[(i + 1) % n], top[(i + 1) % n], top[i]]
        sides.append(((x1 + x2 + y1 + y2) / 2, quad))
    xs = [p[0] for p in top + bottom]
    ys = [p[1] for p in top + bottom]
    x0, y0 = min(xs) - 2, min(ys) - 2
    w, h = max(xs) - x0 + 2, max(ys) - y0 + 2
    poly = lambda q, c: (f'<polygon points="{" ".join(f"{x - x0:.1f},{y - y0:.1f}" for x, y in q)}" fill="{c}" '
                         f'stroke="{c}" stroke-width="0.6" stroke-linejoin="round"/>')
    body = [poly(q, "#1F6F6A") for _, q in sorted(sides)] + [poly(top, fill)]
    if label:
        bx, by = proj(W / 2, band * s / 2, T)
        size = band * s * 0.5
        body.append(f'<text transform="matrix(0.866,0.5,-0.866,0.5,{bx - x0:.1f},{by - y0:.1f})" '
                    f'text-anchor="middle" dominant-baseline="central" font-family="Arial" font-weight="bold" '
                    f'font-size="{size:.1f}" fill="#FFFFFF">{label}</text>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.1f}" height="{h:.1f}" '
           f'viewBox="0 0 {w:.1f} {h:.1f}">' + "".join(body) + '</svg>')
    cx, cy = proj(W / 2, H / 2, T)
    style = ("shape=image;aspect=fixed;imageAspect=0;image=data:image/svg+xml,"
             + base64.b64encode(svg.encode()).decode() + ";")
    return style, w, h, (cx - x0, cy - y0)


def sm_bar(node, x, y, w, h, label, size=18, fill=SM_BAR, dashed=False):
    rect(node, x, y, w, h, fill, "none" if not dashed else GREY, 1.5, 14, "dashed=1;" if dashed else "",
         label, size, "#FFFFFF", True)


def write(path, pages):
    """pages: [(name, width, height, [layers])]"""
    out = ['<mxfile host="drawio" type="device">']
    for i, (name, w, h, layers) in enumerate(pages):
        out.append(f'<diagram id="p{i}" name={quoteattr(name)}>')
        out.append(f'<mxGraphModel dx="{w}" dy="{h}" grid="0" gridSize="10" guides="1" tooltips="1" connect="1" '
                   f'arrows="1" fold="1" page="1" pageScale="1" pageWidth="{w}" pageHeight="{h}" '
                   f'background="#FFFFFF" math="0" shadow="0"><root><mxCell id="0"/>')
        for node in layers:
            if isinstance(node, str):
                out.append(node)                      # raw cells of a copied page
            else:
                node.emit(out)
        out.append('</root></mxGraphModel></diagram>')
    out.append('</mxfile>')
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
