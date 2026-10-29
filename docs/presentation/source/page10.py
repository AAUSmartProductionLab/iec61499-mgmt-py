"""Page 10: the filling module's AAS through modsync into the function block network of Dispensing, drawn
like "What the rules draw" (docs/figures/skill-blocks.drawio, page 2)."""
import xml.etree.ElementTree as ET

from drawlib import *  # noqa

EV_AAS = ("#5B963B", 2.2)      # an event connection the AAS gives (the order)
DATA_AAS = ("#788791", 2.2)    # a data connection the AAS gives (a binding)
EV_RULE = ("#B5CFA5", 1.1)     # drawn by the rules
DATA_RULE = ("#C3CBD0", 1.1)
CHIP = "rounded=1;absoluteArcSize=1;arcSize=2;fillColor=#D8E6F3;strokeColor=#6C91B2;strokeWidth=0.8;html=1;" \
       "whiteSpace=wrap;fontFamily=Arial;fontSize=10;fontColor=#6C91B2;align=center;verticalAlign=middle;"


def label(node, x, y, w, value, size=10.5, color=INK, align="left", bold=False, italic=False):
    box(node, x, y, w, 14, f"text;html=1;align={align};verticalAlign=middle;spacing=0;fontFamily=Arial;"
        f"fontSize={size};fontColor={color};fontStyle={(1 if bold else 0) + (2 if italic else 0)};"
        "strokeColor=none;fillColor=none;", value)


def tri(node, x, y, color):
    box(node, x, y, 8, 8, f"triangle;direction=east;fillColor={color};strokeColor=none;")


def wire(node, pts, kind):
    color, width = kind
    line(node, pts, f"edgeStyle=none;rounded=0;html=1;strokeColor={color};strokeWidth={width};endArrow=none;")


def fb(node, x, y, name, typ, ev_in, ev_out, d_in=(), d_out=(), w=140, faded=False):
    """A function block as the reference draws it; returns its pins: ("in"|"out", name) -> (x, y)."""
    g = node.group(f"Block {name} ({typ})")
    n_ev, n_d = max(len(ev_in), len(ev_out), 1), max(len(d_in), len(d_out), 1)
    eh, dh = 6 + 17 * n_ev, 6 + 17 * n_d
    yn, yd = y + eh, y + eh + 26
    ink, ev_c, d_c = ("#A9B3B9", "#B5CFA5", "#C3CBD0") if faded else (INK, "#5B963B", "#788791")
    outline = "#C3CBD0" if faded else "#41484B"
    for (rx, ry, rw, rh) in [(x, y, w, eh), (x + 12, yn, w - 24, 26), (x, yd, w, dh)]:
        rect(g, rx, ry, rw, rh, "#F4F9FC")
    pts = [(x, y), (x + w, y), (x + w, yn), (x + w - 12, yn), (x + w - 12, yd), (x + w, yd), (x + w, yd + dh),
           (x, yd + dh), (x, yd), (x + 12, yd), (x + 12, yn), (x, yn), (x, y)]
    line(g, pts, f"edgeStyle=none;rounded=0;html=1;strokeColor={outline};strokeWidth=1.3;endArrow=none;")
    label(g, x - 20, y - 19, w + 40, name, 13, ink, "center", True)
    box(g, x + 18, yn + 5, 30, 16, CHIP.replace("#6C91B2", "#A9B9C9") if faded else CHIP, "FB")
    label(g, x + 52, yn + 6, w - 60, typ, 10.5, "#A9B9C9" if faded else "#4D7392", "left", italic=True)
    pins = {}
    for i, e in enumerate(ev_in):
        cy = y + 10 + 17 * i
        tri(g, x + 1, cy - 4, ev_c), label(g, x + 12, cy - 7, w / 2, e, 10.5, ev_c)
        pins[("in", e)] = (x, cy)
    for i, e in enumerate(ev_out):
        cy = y + 10 + 17 * i
        label(g, x + w / 2 - 12, cy - 7, w / 2, e, 10.5, ev_c, "right"), tri(g, x + w - 9, cy - 4, ev_c)
        pins[("out", e)] = (x + w, cy)
    for i, d in enumerate(d_in):
        cy = yd + 10 + 17 * i
        tri(g, x + 1, cy - 4, d_c), label(g, x + 12, cy - 7, w / 2, d, 10.5, d_c)
        pins[("in", d)] = (x, cy)
    for i, d in enumerate(d_out):
        cy = yd + 10 + 17 * i
        label(g, x + w / 2 - 12, cy - 7, w / 2, d, 10.5, d_c, "right"), tri(g, x + w - 9, cy - 4, d_c)
        pins[("out", d)] = (x + w, cy)
    pins["bottom"] = yd + dh
    return pins


def iface(node, x, y, name, side, data=False):
    """A pin of a subapplication's interface, on its frame: side "in" (left edge) or "out" (right edge)."""
    c = "#788791" if data else "#5B963B"
    if side == "in":
        tri(node, x + 2, y - 4, c), label(node, x + 13, y - 7, 70, name, 10.5, c)
        return (x + 13 + 6 * len(name) + 4, y)
    label(node, x - 83, y - 7, 70, name, 10.5, c, "right"), tri(node, x - 10, y - 4, c)
    return (x - 83 + 70 - 6 * len(name) - 4, y)


def manhattan(a, b, via_y, da=8, db=8):
    """From an output (a, leaving right) to an input (b, entering from the left) through the level via_y."""
    return [a, (a[0] + da, a[1]), (a[0] + da, via_y), (b[0] - db, via_y), (b[0] - db, b[1]), b]


def build(make_panel):
    """make_panel(layer_id) -> (raw cells of the FillingModuleAAS panel, rows: row name -> (x_right, y))."""
    L = {}

    def layer(key, name, visible=True):
        L[key] = Node(name, visible)
        return L[key]

    aas = layer("aas", "AAS: FillingModuleAAS (from the hierarchy page)")
    aas_panel_xml, rows = make_panel(aas.id)
    leg = layer("legend", "legend")
    g = leg.group("Legend")
    for i, (kind, txt) in enumerate([(EV_AAS, "event, from the AAS (the order)"),
                                     (DATA_AAS, "data, from the AAS (a binding)"),
                                     (EV_RULE, "event, drawn by the rules"), (DATA_RULE, "data, drawn by the rules")]):
        y = 812 + i * 20
        wire(g, [(30, y), (70, y)], kind)
        label(g, 80, y - 7, 300, txt, 12, GREY)

    # ---- The subapplication Dispensing -------------------------------------------------------------
    fr = layer("frame", "FORTE: the subapplication Dispensing")
    g = fr.group("Dispensing frame")
    box(g, 680, 18, 905, 862, "rounded=1;absoluteArcSize=1;arcSize=8;fillColor=#FFFFFF;strokeColor=#41484B;"
        "strokeWidth=1.2;html=1;")
    label(g, 696, 30, 120, "Dispensing", 15, INK, bold=True)
    box(g, 790, 29, 50, 16, CHIP, "SubApp")
    label(g, 848, 30, 520, "a module level skill, as modsync creates it on FORTE while the module runs", 12, GREY)

    # Execute, a sequence: frame and interface (part of the skill: created with it)
    EX0, EX1, EY0, EY1 = 700, 1570, 300, 800
    BY = 404                                   # top of the step blocks
    rows_ev = [BY + 10 + 17 * i for i in range(5)]
    created1 = layer("c1", "created 1 · the skill: Control, Execute")
    g1 = created1.group("Dispensing: Control and the frame of Execute")
    ex = g1.group("Execute frame and interface")
    box(ex, EX0, EY0, EX1 - EX0, EY1 - EY0, "rounded=1;absoluteArcSize=1;arcSize=8;fillColor=none;"
        "strokeColor=#41484B;strokeWidth=1.2;html=1;")
    label(ex, EX0 + 14, EY0 + 10, 70, "Execute", 14, INK, bold=True)
    box(ex, EX0 + 80, EY0 + 9, 50, 16, CHIP, "SubApp")
    label(ex, EX0 + 138, EY0 + 10, 300, "a sequence", 11.5, GREY)
    xin = {n: iface(ex, EX0, y, n, "in") for n, y in zip(["INIT", "START", "HALT", "ABORT", "RESET"], rows_ev)}
    xin["Volume"] = iface(ex, EX0, 600, "Volume", "in", True)
    xout = {n: iface(ex, EX1, y, n, "out") for n, y in zip(["INITO", "DONE", "FAILED"], rows_ev)}
    xout["Weight"] = iface(ex, EX1, 600, "Weight", "out", True)
    xout["ErrorID"] = iface(ex, EX1, 770, "ErrorID", "out", True)
    ctl = fb(g1, 1150, 96, "Control", "SKILL_Core", ["START_REQ", "EXECUTE_DONE", "EXECUTE_FAILED"],
             ["START_RSP", "RUN", "HALT_SEQ", "ABORT_SEQ", "RESET_SEQ"], ["ParamsInRange"], ["State", "ErrorID"],
             w=170, faded=False)
    # Control and Execute, drawn by the rules
    for k, (o, i) in enumerate([("HALT_SEQ", "HALT"), ("ABORT_SEQ", "ABORT"), ("RESET_SEQ", "RESET")]):
        a = ctl[("out", o)]
        b = (EX0, rows_ev[2 + k])
        wire(g1, [a, (a[0] + 10 + 6 * k, a[1]), (a[0] + 10 + 6 * k, 268 + 6 * k), (684 + 4 * k, 268 + 6 * k),
                  (684 + 4 * k, b[1]), b], EV_RULE)
    for k, (o, i) in enumerate([("DONE", "EXECUTE_DONE"), ("FAILED", "EXECUTE_FAILED")]):
        a = (EX1, rows_ev[1 + k])
        b = ctl[("in", i)]
        wire(g1, [a, (1574 + 4 * k, a[1]), (1574 + 4 * k, 286 + 6 * k), (1128 - 6 * k, 286 + 6 * k),
                  (1128 - 6 * k, b[1]), b], EV_RULE)

    # The Start Operation: UaStart and the parameter latch
    created2 = layer("c2", "created 2 · the Start Operation: UaStart, the latch Volume")
    g2 = created2.group("UaStart and Volume")
    ua = fb(g2, 720, 96, "UaStart", "SERVER_2_2", ["RSP"], ["IND"], ["SD_1", "SD_2"], ["RD_1", "RD_2"], w=150)
    vol = fb(g2, 935, 96, "Volume", "SKILL_Param_LREAL", ["CHECK", "LATCH"], ["CHECKED", "LATCHED"],
             ["Requested", "Lower", "Upper"], ["Value"], w=150)
    wire(g2, manhattan(ua[("out", "IND")], vol[("in", "CHECK")], ua[("out", "IND")][1]), EV_RULE)
    wire(g2, manhattan(ua[("out", "RD_2")], vol[("in", "Requested")], vol[("in", "Requested")][1], 10, 14), DATA_RULE)
    wire(g2, manhattan(vol[("out", "CHECKED")], ctl[("in", "START_REQ")], ctl[("in", "START_REQ")][1]), EV_RULE)
    a, b = ctl[("out", "START_RSP")], ua[("in", "RSP")]
    wire(g2, [a, (a[0] + 30, a[1]), (a[0] + 30, 66), (b[0] - 10, 66), (b[0] - 10, b[1]), b], EV_RULE)
    a, b = ctl[("out", "RUN")], vol[("in", "LATCH")]
    wire(g2, [a, (a[0] + 36, a[1]), (a[0] + 36, 60), (b[0] - 14, 60), (b[0] - 14, b[1]), b], EV_RULE)
    a, b = vol[("out", "LATCHED")], (EX0, rows_ev[1])
    wire(g2, [a, (a[0] + 12, a[1]), (a[0] + 12, 262), (680 - 4, 262), (680 - 4, b[1]), b], EV_RULE)
    for pin, value in [("Lower", "0.5"), ("Upper", "10.0")]:     # the Start variable's limits, as values
        px, py = vol[("in", pin)]
        label(g2, px - 34, py - 7, 30, value, 11, INK, "right", True)

    # The steps: one instance each, the order and the bindings from the AAS
    STEPS = [("NeedleDown", "SK_MoveAxis", ["Position"], ["ErrorID"]),
             ("Dispense", "SK_Dispense", ["Volume", "FlowRate"], ["ErrorID"]),
             ("Home", "SK_Home", [], ["ErrorID"]),
             ("Weigh", "SK_Weigh", [], ["ErrorID", "Weight"])]
    EVI, EVO = ["INIT", "START", "HALT", "ABORT", "RESET"], ["INITO", "SUCCESS", "FAILURE"]
    BX = [800, 985, 1170, 1355]
    blocks = []
    for i, ((name, typ, din, dout), bx) in enumerate(zip(STEPS, BX)):
        Lk = layer(f"s{i}", f"created 3.{i + 1} · step {name}: an instance of {typ}")
        g = Lk.group(f"Step {name}: block and its connections")
        p = fb(g, bx, BY, name, typ, EVI, EVO, din, dout)
        blocks.append(p)
        prev_init = xin["INIT"] if i == 0 else blocks[i - 1][("out", "INITO")]
        prev_ok = xin["START"] if i == 0 else blocks[i - 1][("out", "SUCCESS")]
        wire(g, [prev_init, p[("in", "INIT")]], EV_RULE)
        wire(g, [prev_ok, p[("in", "START")]], EV_AAS)
        for k, e in enumerate(["HALT", "ABORT", "RESET"]):
            src, dst = xin[e], p[("in", e)]
            if i == 0:
                wire(g, [src, dst], EV_RULE)
            else:
                bus_x, bus_y, drop = 770 + 7 * k, 370 - 6 * k, bx - 34 + 7 * k
                wire(g, [(bus_x, src[1]), (bus_x, bus_y), (drop, bus_y), (drop, dst[1]), dst], EV_RULE)
        if name == "NeedleDown":
            label(g, bx - 46, p[("in", "Position")][1] - 7, 42, "40.0", 11, INK, "right", True)
        if name == "Dispense":
            label(g, bx - 26, p[("in", "FlowRate")][1] - 7, 24, "1.0", 11, INK, "right", True)
            v = p[("in", "Volume")]
            wire(g, [xin["Volume"], (bx - 30, xin["Volume"][1]), (bx - 30, v[1]), v], DATA_AAS)
        if i == 3:
            wire(g, [p[("out", "INITO")], xout["INITO"]], EV_RULE)
            wire(g, [p[("out", "SUCCESS")], xout["DONE"]], EV_AAS)
    # The binding of Dispense's Volume reaches Execute from the latch: from the AAS too
    a, b = vol[("out", "Value")], (EX0, 600)
    wire(L["s1"].items[0], [a, (a[0] + 18, a[1]), (a[0] + 18, 256), (672, 256), (672, b[1]), b], DATA_AAS)

    # What the rules add: the failures merged pairwise, the error codes with them
    rl = layer("rules", "created 4 · drawn by the rules: failures and errors merged")
    g = rl.group("Fail merges")
    FX, FY = [890, 1075, 1260], 650
    fails = [fb(g, fx, FY, f"Fail{j + 1}", "SKILL_FailMerge", ["FAIL_1", "FAIL_2"], ["FAIL"], ["Error1", "Error2"],
                ["Error"], w=120, faded=True) for j, fx in enumerate(FX)]
    for j in range(3):
        left = blocks[0][("out", "FAILURE")] if j == 0 else fails[j - 1][("out", "FAIL")]
        lerr = blocks[0][("out", "ErrorID")] if j == 0 else fails[j - 1][("out", "Error")]
        right, rerr = blocks[j + 1][("out", "FAILURE")], blocks[j + 1][("out", "ErrorID")]
        f = fails[j]
        if j == 0:
            wire(g, manhattan(left, f[("in", "FAIL_1")], 600, 8, 10), EV_RULE)
            wire(g, manhattan(lerr, f[("in", "Error1")], 624, 6, 22), DATA_RULE)
        else:
            wire(g, [left, f[("in", "FAIL_1")]], EV_RULE)
            wire(g, [lerr, f[("in", "Error1")]], DATA_RULE)
        wire(g, manhattan(right, f[("in", "FAIL_2")], 606 + 6 * j, 8, 16), EV_RULE)
        wire(g, manhattan(rerr, f[("in", "Error2")], 630 + 6 * j, 14, 28), DATA_RULE)
    a = fails[2][("out", "FAIL")]
    wire(g, [a, (1536, a[1]), (1536, xout["FAILED"][1]), xout["FAILED"]], EV_RULE)
    a = fails[2][("out", "Error")]
    wire(g, [a, (1542, a[1]), (1542, xout["ErrorID"][1]), xout["ErrorID"]], DATA_RULE)

    # The result: Weigh's Weight published
    rs = layer("result", "created 5 · the result: Weight published")
    g = rs.group("PubResults and the Weight")
    pub = fb(g, 1405, 96, "PubResults", "PUBLISH_1", ["REQ"], ["CNF"], ["SD_1"], [], w=140)
    w8 = blocks[3][("out", "Weight")]
    wire(g, [w8, (1520, w8[1]), (1520, 600), (EX1, 600)], DATA_AAS)
    a, b = (EX1, 600), pub[("in", "SD_1")]
    wire(g, [a, (1580, 600), (1580, 280), (1390, 280), (1390, b[1]), b], DATA_AAS)

    # ---- modsync, and the arrows from the AAS through it -----------------------------------------------
    ms = layer("modsync", "modsync")
    g = ms.group("modsync reconfigure")
    rect(g, 498, 18, 160, 862, "#FBF5E6", GOLD, 2.5, 3)
    text(g, 506, 26, 146, 30, "modsync", 20, INK, True, "center")
    text(g, 506, 54, 146, 22, "reconfigure", 14, GREY, False, "center")
    for i, s in enumerate(["Read the AAS", "Compare with the program", "Compile by the rules",
                           "Create online", "Read back, verify", "Record: Built"]):
        y = 96 + i * 128
        st = g.group(f"Stage {i + 1}")
        rect(st, 510, y, 136, 84, "#FFFFFF", GOLD, 2, 10, "", f"<b>{i + 1}</b><br>{s}", 14, INK)
        if i:
            arrow(st, [(578, y - 44), (578, y)], GOLD, 2.5)

    arrows = []

    def through(n, title, row, targets):
        A = Node(f"arrow {n} · {title}", False)
        g = A.group(f"{title}: from the AAS through modsync")
        x0, y0 = rows[row]
        for j, t in enumerate(targets):
            xv = 664 + 3 * n
            if len(t) == 3:
                tx, ty, above = t
                pts = [(x0, y0), (xv, y0), (xv, above), (tx, above), (tx, ty)]
            else:
                tx, ty = t
                pts = [(x0, y0), (xv, y0), (xv, ty), (tx, ty)]
            arrow(g, pts, GOLD, 2.5)
        ring(g, 22, y0 - 10, x0 - 24, 20, GOLD, 30, 2.5)
        arrows.append(A)

    through(1, "the skill → Control and Execute", "Dispensing", [(1235, 76, 49)])
    through(2, "the Start Operation → UaStart and the latch", "Start", [(795, 76, 54), (1010, 76, 54)])
    for i, (name, *_), bx in zip(range(4), STEPS, BX):
        through(3 + i, f"step {name} → its instance", f"Step_000{i}", [(bx + 70, BY - 22, 330 + 4 * i)])

    order = ["aas", "legend", "frame", "c1", "c2", "s0", "s1", "s2", "s3", "rules", "result"]
    out = [L[k] for k in order] + arrows + [ms]
    out.insert(1, aas_panel_xml)               # the copied cells, right after their layer cell
    return out
