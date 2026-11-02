"""Draw the documentation site's figures into aaspire.drawio, one page per figure.

    python build_figures.py                 # add the pages the file does not have yet
    python build_figures.py --force         # draw every page again (edits made in draw.io are lost)
    python build_figures.py --force modsync # draw these pages again
    python export_png.py aaspire.drawio ../docs/figures     # then the PNGs the site shows

A page edited in draw.io stays as it is unless it is named with --force: from then on the .drawio
file is its source. The kit (figlib.py) keeps the style of the figures in docs/figures.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from figlib import Page, write

HERE = Path(__file__).resolve().parent
FIGURES = {}


def figure(fn):
    FIGURES[fn.__name__.replace("_", "-")] = fn
    return fn


# -- Overview -----------------------------------------------------------------------------------------

@figure
def framework():
    p = Page("framework", 960, 660)
    # The apps on top, the AAS server in the middle, the pillars around it, the line below.
    ui = p.lane(20, 10, 920, 70, "Interfaces")
    p.text(32, 34, 160, 34, "the web UI's apps\n(basyx-aas-web-ui)", size=11, color="#41484B", parent=ui)
    for i, (name, kind) in enumerate((("Planner", "planning"), ("Skill Editor", "reconfiguration"),
                                      ("Configurator", "interfaces"), ("HMI", "execution"), ("Orders", "new"))):
        p.pill(210 + i * 144, 34, 132, name + (" *planned*" if kind == "new" else ""), kind, h=24, size=12)

    W, X1, X2, X3 = 256, 20, 352, 684           # three columns, 76 apart for the arrows' labels
    plan = p.card(X1, 104, W, 156, "Planning", icon="modplan", tag="decide", tag_color="planning")
    p.pill(X1 + 10, 140, W - 20, "**modplan**: a new skill", "outline-planning", h=22)
    p.pill(X1 + 10, 168, W - 20, "**FOND-AAS**: the line's policy", "outline-planning", h=22)
    p.text(X1 + 12, 198, W - 24, 56, "From the AASs: what the resources can do and what the product needs. "
                                     "FOND-AAS is the colleagues'", size=11, color="#41484B")

    server = p.card(X2, 104, W, 296, "The AAS server", icon="aas-model", tag="BaSyx", tag_color="aas")
    for i, (kind, name, says) in enumerate((("product", "Product AAS", "what it is and needs: the recipe"),
                                            ("process", "Process AAS", "the recipe bound to a line"),
                                            ("resource", "Resource AASs", "skills, capabilities, interface"))):
        y = 142 + i * 50
        c = p.card(X2 + 10, y, W - 20, 42, None, parent=server)
        p.shell(X2 + 20, y + 13, kind, parent=c)
        p.text(X2 + 46, y + 6, W - 66, 16, name, size=12, bold=True, parent=c)
        p.text(X2 + 46, y + 22, W - 60, 16, says, size=11, color="#41484B", parent=c)
    p.text(X2 + 12, 300, W - 24, 16, "**AAS**: the models every part reads", size=11)
    for i, name in enumerate(("aas-model", "ontologies", "skill model")):
        p.pill(X2 + 10 + i * 80, 322, 74, name, "aas", h=20, size=10)
    p.text(X2 + 12, 352, W - 24, 44, "Registered, checked against the ontology and published: one place for "
                                     "plans, changes and runs", size=11, color="#41484B")

    integ = p.card(X3, 104, W, 156, "Integration", icon="registration-service", tag="plug in",
                   tag_color="integration")
    p.pill(X3 + 10, 140, W - 20, "**registration**: build, check, publish", "outline-integration", h=22)
    p.pill(X3 + 10, 168, W - 20, "**DMP**: Operations to OPC UA", "outline-integration", h=22)
    p.pill(X3 + 10, 196, W - 20, "**modlink**: a skill run from the AAS", "outline-integration", h=22)
    p.text(X3 + 12, 226, W - 24, 28, "Discovery: a module found by mDNS", size=11, color="#41484B")

    recon = p.card(X1, 280, W, 190, "Reconfiguration", icon="modsync", tag="change", tag_color="reconfiguration")
    for i, t in enumerate(("**modsync**: the program to its AAS", "**ModLib, modgen**: the module rules",
                           "**iec61499-mgmt-py**: FORTE's protocol", "**forte-runtime**: FORTE for PC, Pi")):
        p.pill(X1 + 10, 316 + i * 28, W - 20, t, "outline-reconfiguration", h=22)
    p.text(X1 + 12, 432, W - 24, 34, "and the Skill Editor: a skill written as a flow", size=11, color="#41484B")

    exe = p.card(X3, 280, W, 190, "Execution", icon="lineagents", tag="produce", tag_color="execution")
    p.text(X3 + 12, 314, W - 24, 16, "One line, two orchestrators:", size=11)
    p.pill(X3 + 10, 334, W - 20, "**centralized**: behaviour trees", "outline-execution", h=22)
    p.pill(X3 + 10, 362, W - 20, "**multi-agent**: product, resources", "outline-execution", h=22)
    p.text(X3 + 12, 392, W - 24, 72, "Both run a skill alike: occupy the module, bring it to Execute, start "
                                     "the skill, wait for its end, release", size=11, color="#41484B")

    line = p.lane(20, 492, 920, 120, "Lines: the aseptic line")
    for i, (name, kind) in enumerate((("Filling", "plain"), ("Stoppering", "plain"), ("Capping", "new"),
                                      ("Inspection", "new"), ("Loading", "new"), ("Unloading", "new"))):
        c = p.card(32 + i * 118, 522, 108, 56, None, dashed=kind == "new", parent=line)
        p.text(40 + i * 118, 528, 92, 16, name, size=12, bold=True, parent=c)
        p.text(40 + i * 118, 546, 96, 28, "FORTE on a Pi\nOPC UA", size=10, color="#41484B", parent=c)
    tbl = p.card(744, 522, 184, 56, None, parent=line)
    p.text(752, 528, 170, 16, "Planar table, shuttles", size=12, bold=True, parent=tbl)
    p.text(752, 546, 170, 28, "planar-controller\nOPC UA, like a module", size=10, color="#41484B", parent=tbl)
    p.text(32, 586, 896, 18, "**Deployment**: the server stack by Compose (deploy-server); a Raspberry Pi becomes "
                             "a module with FORTE in Docker (deploy-module)", size=11, parent=line)

    p.edge(ui, server, "edit", "aas", exit=p.side(ui, "bottom", 480), entry=p.side(server, "top", 480))
    p.edge(plan, server, "plan", "aas", exit=p.side(plan, "right", 182), entry=p.side(server, "left", 182))
    p.edge(integ, server, "register", "aas", exit=p.side(integ, "left", 182), entry=p.side(server, "right", 182))
    p.edge(recon, server, "record", "aas", exit=p.side(recon, "right", 360), entry=p.side(server, "left", 360))
    p.edge(exe, server, "read", "aas", exit=p.side(exe, "left", 360), entry=p.side(server, "right", 360))
    p.edge(recon, line, "change online", "change", exit=p.side(recon, "bottom", 148), entry=p.side(line, "top", 148))
    p.edge(exe, line, "run skills", "operate", exit=p.side(exe, "bottom", 812), entry=p.side(line, "top", 812))
    p.legend(20, 628, ["aas", "change", "operate"], extra=[("new", "planned")])
    return p


@figure
def repository_map():
    rows = [
        ("aas-model/", "submodule", [("aas-model", "aas")]),
        ("ontology/", "", [("ontologies", "aas")]),
        ("iec61499-skill-lib/", "", [("iec61499-skill-lib", "reconfiguration"), ("skill-model: modgen.spec", "aas")]),
        ("aas61499-tools/", "", [("modsync", "reconfiguration"), ("modplan", "planning"),
                                 ("registration-service: modreg", "integration"), ("skill-model", "aas")]),
        ("iec61499-mgmt-py/", "", [("iec61499-mgmt-py", "reconfiguration")]),
        ("runtime/", "", [("forte-runtime", "reconfiguration"), ("deploy-module: install.sh, kit", "deployment")]),
        ("aas-camel-dmp/", "submodule", [("aas-camel-dmp", "integration")]),
        ("iec61499-opcua-hmi/", "submodule", [("modlink", "integration")]),
        ("line-agents/", "", [("lineagents", "execution")]),
        ("planar-controller/", "submodule", [("planar-controller", "execution")]),
        ("basyx-aas-web-ui/", "submodule", [("basyx-aas-web-ui", "interfaces")]),
        ("deploy/", "", [("deploy-server: aas/", "deployment"), ("deploy-module: pi/, pi.py", "deployment")]),
        ("cell/", "", [("aseptic-line", "lines")]),
        ("docs/", "", [("aseptic-line: the working notes", "lines"), ("aaspire: the site", "ink")]),
        ("aaspire/", "this site", [("aaspire", "ink")]),
    ]
    p = Page("repository-map", 960, 70 + 30 * len(rows) + 50)
    p.head(20, 10, 300, "Folders of this repository today")
    p.head(400, 10, 540, "Repositories of ap2030-project after the split")
    for i, (folder, note, repos) in enumerate(rows):
        y = 40 + i * 30
        f = p.pill(20, y, 250, f"**{folder}**" + (f"  *{note}*" if note else ""), "plain", h=22, size=12)
        x = 400
        first = None
        for name, kind in repos:
            w = round(len(name) * 6.4 + 26)
            r = p.pill(x, y, w, name, kind if kind != "ink" else "dark", h=22, size=11)
            first = first or r
            x += w + 8
        p.edge(f, first, "", "ref", exit=(1, 0.5), entry=(0, 0.5), dashed=False, color="#8F989D", width=1)
    y = 52 + 30 * len(rows)
    for i, (kind, name) in enumerate((("aas", "AAS"), ("planning", "Planning"), ("integration", "Integration"),
                                      ("reconfiguration", "Reconfiguration"), ("execution", "Execution"),
                                      ("interfaces", "Interfaces"), ("deployment", "Deployment"), ("lines", "Lines"))):
        p.pill(20 + i * 116, y, 108, name, kind, h=20, size=11)
    return p


# -- AAS --------------------------------------------------------------------------------------------

@figure
def aas_model():
    p = Page("aas-model", 960, 640)
    cols = (("product", "Product", "General recipe",
             "What the product is and what it needs; no equipment named",
             ["Nameplate", "Hierarchical Structures: bill of material", "Process Parameters",
              "Capability Description: required", "Production Sequence: the recipe"],
             "a product, and each part with a recipe", "the product changes", "the product designer"),
            ("process", "Process", "Master recipe",
             "The recipe bound to one line: per step the resource, the skill, its inputs",
             ["Process Information", "Bindings", "Validation: the plan check"],
             "a product on a line", "the line is reconfigured", "the line engineer"),
            ("resource", "Module, Component, ProductionSystem", "Equipment",
             "What it offers and how it is called; what its skills are made of",
             ["Nameplate", "Hierarchical Structures: its parts", "Capability Description: offered",
              "Skills (ARSO)", "Asset Interfaces Description", "Interfaces Mapping Configuration", "Variables"],
             "a line, a module, a component", "the vendor delivers; changed online", "the vendor"))
    cards = []
    for i, (kind, title, level, says, subs, per, when, owner) in enumerate(cols):
        x = 20 + i * 315
        p.head(x, 10, 290, f"ISA-88: {level}")
        c = p.card(x, 32, 290, 318, title, shell=kind)
        p.text(x + 10, 62, 270, 34, says, size=11, color="#41484B", parent=c)
        for j, s in enumerate(subs):
            p.pill(x + 10, 100 + j * 26, 270, s, "bar", h=20)
        p.text(x + 10, 296, 270, 80, f"**One per**: {per}\n**Changes when**: {when}\n**Owner**: {owner}",
               size=11, color="#41484B", parent=c)
        cards.append(c)
    p.edge(cards[1], cards[0], "binds its recipe", "ref", exit=(0.25, 1), entry=(0.75, 1),
           points=[(407, 368), (238, 368)])
    p.edge(cards[1], cards[2], "names a resource and a skill per step", "ref", exit=(0.75, 1), entry=(0.25, 1),
           points=[(552, 368), (722, 368)])

    lane = p.lane(20, 390, 920, 160, "From a template to a published AAS")
    steps = (("Templates", "IDTA's, the lab's, ARSO's: JSON with semanticIds and cardinalities", "aas"),
             ("Generator", "aas-model's: classes made from the templates", "aas"),
             ("Classes", "pydantic: Product, Process, Module, Component, ProductionSystem", "aas"),
             ("Profile", "an AAS as the pydantic dump of its type, without what the type says", "aas"),
             ("AAS", "built, checked against the ontology, on the AAS server", "aas"))
    prev = None
    for i, (title, body, _) in enumerate(steps):
        c = p.card(32 + i * 182, 422, 168, 112, title, body=body, size=11, parent=lane)
        p.num(25 + i * 182, 415, i + 1)
        if prev:
            p.edge(prev, c, "", "flow", exit=(1, 0.5), entry=(0, 0.5))
        prev = c
    p.legend(20, 568, ["flow", "ref"])
    return p


@figure
def ontologies():
    p = Page("ontologies", 960, 520)
    lane = p.lane(20, 10, 600, 460, "The ontologies (ontology/)")
    pprl = p.card(32, 44, 380, 92, "PPRL: the links", tag="0.2", tag_color="aas", size=11,
                  body="Between the three: a step requires a capability a resource offers; matching, skill "
                       "composition, bindings")
    css = p.card(428, 44, 180, 92, "CSS 2.0.2", size=11, body="Capabilities, skills, services (Plattform I4.0)")
    blue = []
    for i, (name, ver, kind, says) in enumerate((("APSO", "0.2", "product", "the product AAS"),
                                                 ("AProSO", "0.1", "process", "the process AAS"),
                                                 ("ARSO", "0.14", "resource", "the resource AAS: line, module, "
                                                                               "component"))):
        c = p.card(32 + i * 196, 162, 184, 100, name, shell=kind, tag=ver, tag_color="aas", size=11,
                   body=f"The blueprint of {says}, checkable on its own")
        blue.append(c)
    aas_o = p.card(32, 288, 576, None, "AAS v3.1 ontology", size=11,
                   body="The AAS metamodel as RDF, IDTA's, unchanged: what every blueprint is made of")
    voc = p.card(32, 372, 576, None, "Vocabulary 0.7", tag="supplemental ids", tag_color="aas", size=11,
                 body="What the AASs' elements mean: capabilities (process and auxiliary), properties, what each "
                      "kind of capability needs and does")
    p.edge(pprl, css, "", "ref", exit=(1, 0.5), entry=(0, 0.5))
    for c in blue:
        p.edge(pprl, c, "", "ref", exit=p.side(pprl, "bottom", min(p.where[c][0] + 92, 400)),
               entry=p.side(c, "top", min(p.where[c][0] + 92, 400)) if p.where[c][0] < 400 else (0.5, 0))
        p.edge(c, aas_o, "", "ref", exit=(0.5, 1), entry=p.side(aas_o, "top", p.where[c][0] + 92))
    p.text(632, 14, 300, 18, "Used by", size=12, color="#6E777B", bold=True)
    u1 = p.card(632, 44, 308, None, "modreg check", icon="registration-service", size=11,
                body="An AAS as RDF against ARSO's shapes, closed: what the ontology does not describe is a "
                     "finding. The registration service refuses what breaks a restriction")
    u2 = p.card(632, 170, 308, None, "modreg generate", icon="aas-model", size=11,
                body="ARSO's own submodels (Skills, Parameters) as templates, and aas-model's classes from them: "
                     "a test fails when they no longer match")
    u3 = p.card(632, 296, 308, None, "modplan, the planner", icon="modplan", size=11,
                body="The vocabulary says what a capability does to a product, so a skill can be planned and a "
                     "step matched")
    p.edge(blue[2], u1, "", "aas", exit=(1, 0.3), entry=(0, 0.5), points=[(620, 180), (620, 98)])
    p.edge(blue[2], u2, "", "aas", exit=(1, 0.6), entry=(0, 0.5))
    p.edge(voc, u3, "", "aas", exit=(1, 0.5), entry=(0, 0.6))
    p.legend(20, 486, ["ref", "aas"], extra=[])
    return p


# -- Planning -----------------------------------------------------------------------------------------

@figure
def modplan():
    p = Page("modplan", 960, 600)
    p.head(20, 10, 250, "The module's AAS")
    p.head(290, 10, 400, "modplan")
    p.head(710, 10, 230, "The planned skill")

    p.lane(20, 32, 250, 520)
    aas = p.card(32, 46, 226, 368, "FillingModule", shell="resource")
    p.pill(42, 80, 206, "Capability Description", "bar")
    p.pill(42, 102, 206, "Filling: FillVolume 0.5 to 10 mL", "plain")
    p.text(44, 124, 202, 30, "offered, realized by a skill; and per component what its primitives can do:",
           size=11, color="#41484B")
    for i, t in enumerate(("LinearAxis: MoveAxis, Home", "Pump: Dispense adds FillVolume", "Scale: Tare, Weigh")):
        p.pill(42, 158 + i * 22, 206, t, "aas", h=18, size=10)
    p.text(44, 226, 202, 46, "each with what it needs, does and keeps: Pre, Post, Invariant (IDTA 02020 "
                             "constraints)", size=11, color="#41484B")
    p.pill(42, 280, 206, "Skills", "bar")
    p.pill(42, 302, 206, "Dispensing *Built*", "reconfiguration")
    p.pill(42, 324, 206, "Filling *Described*", "new")
    p.text(44, 348, 202, 60, "*RestState*: what the Reset procedure leaves, where a planned skill must end",
           size=11, color="#41484B")
    p.card(32, 428, 226, 112, "Vocabulary", shell="resource", size=11,
           body="What a kind of capability needs and does wherever it is used: the planner's common ground")

    p.lane(290, 32, 400, 520)
    req = p.card(302, 46, 376, None, "The requirement", tag="from a step or an engineer", tag_color="planning",
                 size=11, body="Filling with FillVolume 2.0 mL, and the result FillWeight")
    s1 = p.card(302, 128, 184, 124, "Read", size=11,
                body="The domain: the state variables, the components' capabilities as actions, the rest state")
    s2 = p.card(494, 128, 184, 124, "Plan", tag="GTPyhop", tag_color="planning", size=11,
                body="Goals: the Post with the values, the results, the rest state; an action's Pre become goals")
    s3 = p.card(302, 268, 184, 124, "Lift", size=11,
                body="Steps ordered when they share a component or one needs what the other changes; the rest "
                     "in parallel")
    s4 = p.card(494, 268, 184, 124, "Describe", size=11,
                body="The flow in the Skills submodel, as the Skill Editor saves it: *Described*")
    for cid, n in ((s1, 1), (s2, 2), (s3, 3), (s4, 4)):
        x, y = p.where[cid][:2]
        p.num(x - 7, y - 7, n)
    also = p.card(302, 408, 376, 132, "Also", size=11)
    p.pill(312, 440, 356, "**check**: a skill's flow run through the states", "outline-planning", h=22)
    p.pill(312, 468, 356, "**discover**: what is offered after a reconfiguration", "outline-planning", h=22)
    p.pill(312, 496, 356, "**export**: PDDL and HDDL for ENHSP and Aries", "outline-planning", h=22)

    p.lane(710, 32, 230, 520)
    sk = p.card(722, 46, 206, 252, "Filling", dashed=True, tag="example", tag_color="planning")
    steps = ("MoveAxis: needle down", "Dispense 2.0 mL", "Home: needle up", "Weigh: FillWeight")
    ids = []
    for i, t in enumerate(steps):
        ids.append(p.pill(736, 84 + i * 48, 178, t, "reconfiguration", h=26))
    for a, b in zip(ids, ids[1:]):
        p.edge(a, b, "", "step", exit=(0.5, 1), entry=(0.5, 0))
    p.text(736, 276, 178, 16, "a sequence; parallel where it may", size=10, color="#6E777B")
    ms = p.card(722, 314, 206, None, "modsync reconfigure", icon="modsync", size=11,
                body="Creates the described skill online; it is verified, recorded *Built*, and runs")

    p.edge(aas, s1, "", "aas", exit=p.side(aas, "right", 190), entry=p.side(s1, "left", 190))
    p.edge(req, s2, "", "flow", exit=p.side(req, "bottom", 586), entry=p.side(s2, "top", 586))
    p.edge(s1, s2, "", "flow", exit=p.side(s1, "right", 190), entry=p.side(s2, "left", 190))
    p.edge(s2, s3, "", "flow", exit=p.side(s2, "bottom", 586), entry=p.side(s3, "top", 394),
           points=[(586, 260), (394, 260)])
    p.edge(s3, s4, "", "flow", exit=p.side(s3, "right", 330), entry=p.side(s4, "left", 330))
    p.edge(s4, aas, "", "aas", exit=p.side(s4, "bottom", 586), entry=p.side(aas, "right", 335),
           points=[(586, 400), (278, 400), (278, 335)])
    p.edge(s4, sk, "", "flow", exit=p.side(s4, "right", 300), entry=p.side(sk, "left", 270),
           points=[(698, 300), (698, 270)])
    p.edge(sk, ms, "", "flow", exit=(0.5, 1), entry=(0.5, 0))
    p.legend(20, 568, ["flow", "aas", "step"], extra=[("new", "described, not built yet")])
    return p


# -- Integration ---------------------------------------------------------------------------------------

@figure
def registration():
    p = Page("registration", 960, 600)
    p.head(20, 10, 230, "A module")
    p.head(270, 10, 420, "The registration service: modreg serve")
    p.head(710, 10, 230, "The AAS server and its readers")

    p.lane(20, 32, 230, 520)
    pi = p.card(32, 46, 206, 214, "A Raspberry Pi", tag="plugged in", tag_color="deployment")
    p.pill(42, 80, 186, "FORTE: the program", "reconfiguration")
    p.pill(42, 104, 186, "OPC UA server :4840", "execution")
    p.text(44, 128, 182, 30, "announced on the network (mDNS)", size=11, color="#41484B")
    man = p.pill(42, 160, 186, "manifest :8088", "plain")
    p.text(44, 184, 182, 70, "the profiles of the module's AAS and its components' AASs, served beside FORTE",
           size=11, color="#41484B")
    vendor = p.card(32, 276, 206, 118, "Or by hand", tag="the vendor", tag_color="lines", size=11,
                    body="A profile the vendor wrote, or made from a module spec (modreg profile), sent with "
                         "POST /profiles")
    p.card(32, 410, 206, 130, "A profile", size=11,
           body="The AAS as the pydantic dump of its aas-model type, without what the type says anyway")

    p.lane(270, 32, 420, 520)
    s = []
    for i, (title, body) in enumerate((
            ("Discover", "A new OPC UA server announced on the network"),
            ("Fetch", "GET the manifest beside it: the profiles of the module and its components"),
            ("Build", "Each profile read into its aas-model type; the AAS made from it"),
            ("Check", "Against ARSO, closed: a broken restriction refuses the module"),
            ("Publish", "To the AAS server, with the offered capabilities derived from the skills"))):
        y = 46 + i * 100
        c = p.card(282, y, 196, 88, title, body=body, size=11)
        p.num(275, y - 7, i + 1)
        s.append(c)
    p.card(494, 46, 184, 100, "Its store", size=11,
           body="Each profile, its AAS and the integrator's record, by module")
    api = p.card(494, 160, 184, 214, "Its endpoints", tag=":8090", tag_color="integration", size=11)
    for i, (path, what) in enumerate((("/profiles", "register, read, remove"), ("/check, /plan", "for the Skill Editor"),
                                      ("/process", "for the Planner: a process AAS"), ("/build", "the record"))):
        p.text(504, 192 + i * 44, 168, 40, f"**{path}**\n{what}", size=11, parent=api)
    p.text(494, 390, 184, 90, "A profile registered again unchanged is not published again; --strict also "
                              "refuses what the ontology does not describe", size=11, color="#41484B")

    p.lane(710, 32, 230, 520)
    server = p.card(722, 46, 206, 178, "AAS server", icon="aas-model", tag="BaSyx", tag_color="aas")
    p.pill(732, 80, 186, "FillingModuleAAS", "aas")
    p.pill(732, 102, 186, "LinearAxis, Pump, Scale AASs", "aas")
    p.text(734, 128, 182, 90, "Its events (a shell created, changed, deleted) go out over MQTT", size=11,
           color="#41484B")
    for i, (name, icon, body) in enumerate((
            ("agent manager", "lineagents", "starts the module's resource agent"),
            ("DMP", "aas-camel-dmp", "maps the module's interface"),
            ("Planner, Skill Editor", "Planner", "ask the service to check and plan"))):
        p.card(722, 240 + i * 102, 206, 90, name, icon=icon, body=body, size=11)

    p.edge(pi, s[0], "", "ref", exit=p.side(pi, "right", 90), entry=p.side(s[0], "left", 90))
    p.edge(s[1], man, "", "flow", exit=p.side(s[1], "left", 169), entry=p.side(man, "right", 169))
    p.edge(vendor, s[2], "", "flow", exit=p.side(vendor, "right", 290), entry=p.side(s[2], "left", 290))
    for a, b in zip(s, s[1:]):
        p.edge(a, b, "", "flow", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(s[4], server, "", "aas", exit=p.side(s[4], "right", 490), entry=p.side(server, "left", 190),
           points=[(700, 490), (700, 190)])
    p.legend(20, 568, ["flow", "aas", "ref"], extra=[])
    return p


@figure
def dmp():
    p = Page("dmp", 960, 560)
    p.head(20, 10, 250, "The AAS server")
    p.head(290, 10, 380, "The DMP: aas-camel-dmp")
    p.head(690, 10, 250, "What it connects")

    p.lane(20, 32, 250, 480)
    aas = p.card(32, 46, 226, 300, "FillingModuleAAS", shell="resource")
    for i, (bar, says) in enumerate((("Asset Interfaces Description", "the endpoint; every action and property"),
                                     ("Mapping Configuration (AIMC)", "a source to a sink, Lua between them"),
                                     ("Skills", "each command an Operation"),
                                     ("Variables", "State, Measurements, Log: time series"))):
        y = 80 + i * 64
        p.pill(42, y, 206, bar, "bar")
        p.text(44, y + 22, 202, 36, says, size=11, color="#41484B")
    caller = p.card(32, 360, 226, 140, "A client", tag="any language", tag_color="execution", size=11,
                    body="Invokes a skill's Operation at the AAS server: the agents (their DMP executor), "
                         "a behaviour tree, a script")

    p.lane(290, 32, 380, 480)
    s = []
    for i, (title, body, y, h) in enumerate((
            ("Discover", "The AIMCs by their semanticId; each submodel they reference read once", 46, 92),
            ("Compile", "Each mapping a bundle of Apache Camel routes; the Lua compiled in memory, never "
                        "read from files", 152, 104),
            ("Run", None, 270, 132),
            ("Follow", "The AAS server's events over MQTT: only what a change touches is read and compiled "
                       "again", 416, 84))):
        c = p.card(302, y, 356, h, title, body=body, size=11)
        p.num(295, y - 7, i + 1)
        s.append(c)
    p.pill(312, 304, 336, "an Operation invoked: the module's OPC UA method called", "execution", h=22)
    p.pill(312, 332, 336, "the module's values: rows in InfluxDB", "plain", h=22)
    p.pill(312, 360, 336, "every call logged in the module's Log series", "plain", h=22)

    p.lane(690, 32, 250, 480)
    mod = p.card(702, 46, 226, 150, "The module", tag="FORTE", tag_color="reconfiguration", size=11,
                 body="Its OPC UA server: the skills' methods, their State, ErrorID and results, the equipment's "
                      "values")
    db = p.card(702, 212, 226, 130, "InfluxDB", tag="time series", tag_color="deployment", size=11,
                body="One bucket of the line; each series named by the module's Variables. Read by the agents "
                     "and the HMI")
    p.card(702, 358, 226, 142, "In the lab's stack", size=11,
           body="One Java process built as an image; it starts with BaSyx, InfluxDB and Mosquitto "
                "(deploy/aas). Upstream: Tristan's; here the user's fork with the lab's modules")

    p.edge(caller, aas, "invoke", "aas", exit=p.side(caller, "top", 145), entry=p.side(aas, "bottom", 145))
    p.edge(aas, s[0], "", "aas", exit=p.side(aas, "right", 92), entry=p.side(s[0], "left", 92))
    p.edge(s[0], s[1], "", "flow", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(s[1], s[2], "", "flow", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(s[2], mod, "", "operate", exit=p.side(s[2], "right", 315), entry=p.side(mod, "left", 160),
           points=[(680, 315), (680, 160)], start="block")
    p.edge(s[2], db, "", "flow", exit=p.side(s[2], "right", 343), entry=p.side(db, "left", 290),
           points=[(686, 343), (686, 290)])
    p.edge(aas, s[3], "events", "aas", exit=p.side(aas, "right", 300), entry=p.side(s[3], "left", 458),
           points=[(280, 300), (280, 458)], label_bg="#F3F4F5")
    p.legend(20, 528, ["flow", "aas", "operate"])
    return p


@figure
def modlink():
    p = Page("modlink", 960, 600)
    p.head(20, 10, 250, "The module's AAS, by reference")
    p.head(290, 10, 380, "modlink")
    p.head(690, 10, 250, "The module's OPC UA server")

    p.lane(20, 32, 250, 520)
    chain = []
    for i, (bar, says) in enumerate((
            ("Capability Description", "Filling, 0.5 to 10 mL: realized by the skill Dispensing"),
            ("Skills", "Dispensing's commands: Start, Stop, Abort, Reset; each its InterfaceReference; "
                       "the Start's inputs are the parameters"),
            ("Asset Interfaces Description", "The endpoint and the browse path of every action and property"),
            ("Mapping Configuration, Variables", "Which property shows the skill's State, ErrorID and each "
                                                 "result"))):
        y = 46 + i * 126
        c = p.card(32, y, 226, 112, None)
        p.pill(42, y + 10, 206, bar, "bar")
        p.text(44, y + 36, 202, 70, says, size=11, color="#41484B", parent=c)
        p.num(25, y - 7, i + 1)
        chain.append(c)
    for a, b in zip(chain, chain[1:]):
        p.edge(a, b, "", "ref", exit=(0.5, 1), entry=(0.5, 0))

    p.lane(290, 32, 380, 520)
    res = p.card(302, 46, 356, None, "Resource", size=11,
                 body="What the AAS says, resolved by references and meanings, never by names: capabilities, skills "
                      "with parameters and limits, the nodes to call and to watch")
    link = p.card(302, 146, 356, None, "Link", tag="one per endpoint", tag_color="execution", size=11,
                  body="One OPC UA connection: nodes found by browse path (FORTE numbers them anew at every start), "
                       "every variable subscribed, reconnects with back-off, one call at a time")
    run = p.card(302, 264, 356, 276, "A run", tag="Module", tag_color="execution")
    for i, t in enumerate(("Occupy with a session id", "Clear, Reset, Start: the module in Execute",
                           "Listen to the skill's State", "Start(Session, values): [Accepted, ErrorID]",
                           "The first end state ends the run", "Results read; Release")):
        p.pill(314, 298 + i * 36, 332, f"{i + 1}  {t}", "outline-execution", h=26)

    p.lane(690, 32, 250, 520)
    ua = p.card(702, 46, 226, 330, "/Objects/Filling", tag="FORTE", tag_color="reconfiguration")
    for i, (node, kids) in enumerate((("Occupation", "Occupy, Release; Occupied"),
                                      ("Module", "Reset, Start, Stop, Abort, Clear; State"),
                                      ("Skills/Dispensing", "Start, Stop, Abort, Reset; State, ErrorID, "
                                                            "Parameters, Results"),
                                      ("Equipment/LinearAxis", "its values"))):
        y = 80 + i * 72
        p.pill(712, y, 206, node, "execution")
        p.text(714, y + 22, 202, 44, kids, size=11, color="#41484B")
    users = p.card(702, 390, 226, 150, "Who uses it", size=11,
                   body="The HMI (FastAPI); the agents' OPC UA executor; a script: run_capability('Filling', "
                        "FillVolume=2.0)")

    p.edge(chain[0], res, "", "aas", exit=p.side(chain[0], "right", 80), entry=p.side(res, "left", 80))
    p.edge(chain[3], res, "", "aas", exit=p.side(chain[3], "right", 460), entry=p.side(res, "left", 110),
           points=[(280, 460), (280, 110)])
    p.edge(res, link, "", "flow", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(link, run, "", "flow", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(run, ua, "", "operate", exit=p.side(run, "right", 360), entry=p.side(ua, "left", 360), start="block")
    p.legend(20, 568, ["ref", "aas", "flow", "operate"])
    return p


# -- Reconfiguration ------------------------------------------------------------------------------------

@figure
def modsync():
    p = Page("modsync", 960, 700)
    p.head(20, 10, 230, "The AAS: what is wanted")
    p.head(270, 10, 420, "modsync")
    p.head(710, 10, 230, "The module: what runs")
    L, M1, M2, R = 32, 282, 482, 722          # the cards' left edges in the three columns

    p.lane(20, 32, 230, 612)
    aas = p.card(L, 46, 206, 252, "FillingModule", shell="resource")
    p.pill(L + 10, 80, 186, "Skills", "bar")
    p.pill(L + 10, 102, 186, "Dispensing *Built*", "reconfiguration")
    p.pill(L + 10, 124, 186, "BottomUpFilling *Described*", "new")
    p.text(L + 12, 148, 182, 30, "each skill with its steps: the primitive each runs and what it is handed", size=11)
    p.pill(L + 10, 190, 186, "Capability Description", "bar")
    p.pill(L + 10, 212, 186, "Interfaces: AID, AIMC", "bar")
    p.pill(L + 10, 234, 186, "Variables", "bar")
    p.text(L + 12, 260, 182, 30, "*RuleSet*: the module rules the program follows", size=11)
    p.card(L, 312, 206, None, "LinearAxis, Pump, Scale", shell="resource", size=11,
           body="The components' AASs: their skills are the primitives a step can run")
    rec = p.card(L, 426, 206, 112, "The integrator's record", size=11,
                 body="Beside the AAS: each instance with its block type and type hash, where the module is "
                      "managed, the change log")

    p.lane(270, 32, 420, 612)
    s2 = p.card(M1, 46, 196, 106, "Describe", body="The AAS as a module spec without wiring: what is wanted. "
                                                    "Refuses what the module cannot carry out")
    s1 = p.card(M2, 46, 196, 106, "Read", tag="management", tag_color="integration",
                body="A snapshot of the program, read back by the module rules: equipment, skills, flows")
    s3 = p.card(M1, 168, 396, 108, "Compare")
    p.pill(M1 + 10, 202, 88, "create", "reconfiguration")
    p.pill(M1 + 104, 202, 88, "write", "reconfiguration")
    p.pill(M1 + 198, 202, 88, "restart", "new")
    p.pill(M1 + 292, 202, 88, "record", "new")
    p.text(M1 + 10, 228, 376, 44, "Online: a skill described but not built; a constant, a default or a limit. "
                                  "Refused: another flow or order (a restart), a record that does not match",
           size=11)
    s4 = p.card(M1, 292, 196, 118, "Guard", body="Values only while the module is Stopped, Idle or Aborted and "
                                                 "free. A block type FORTE lacks: nothing is sent")
    s5 = p.card(M2, 292, 196, 118, "Apply online", tag="management", tag_color="integration",
                body="WRITE the values; CREATE, WRITE, CONNECT and START the new skill; INIT runs once "
                     "through it")
    s6 = p.card(M1, 426, 396, 112, "Verify and record",
                body="Read back and compared with the AAS again. The commands are appended to the boot file; the "
                     "AAS marks the skill *Built* and gets its interface; the record gets every instance and hash")
    for cid, n in ((s1, 1), (s2, 2), (s3, 3), (s4, 4), (s5, 5), (s6, 6)):
        x, y = p.where[cid][:2]
        p.num(x - 7, y - 7, n)
    p.card(M1, 554, 396, None, "modsync project", tag="4diac IDE", tag_color="reconfiguration",
           body="FORTE keeps the program, not the project: read back by the rules, the program becomes a "
                "4diac project again, with the layout arranged in the IDE")

    p.lane(710, 32, 230, 612)
    forte = p.card(R, 46, 206, 364, "FORTE", tag="the module's Pi", tag_color="deployment")
    p.pill(R + 10, 80, 186, "Occupation", "plain")
    p.pill(R + 10, 102, 186, "Module: PackML states", "plain")
    p.pill(R + 10, 124, 186, "LinearAxis · Pump · Scale", "plain")
    p.pill(R + 10, 156, 186, "Dispensing", "reconfiguration")
    p.pill(R + 10, 178, 186, "BottomUpFilling *new*", "new")
    p.text(R + 12, 202, 182, 48, "a module level skill: instances of library blocks and primitives, appended "
                                 "to the INIT chain", size=11)
    p.pill(R + 10, 262, 186, "OPC UA server", "execution")
    p.text(R + 12, 288, 182, 110, "The management port (61499) changes instances, connections and values "
                                  "while the module runs; OPC UA operates it", size=11)
    boot = p.card(R, 426, 206, 112, "Boot file", tag="~/forte/boot", tag_color="deployment", size=11,
                  body="What FORTE loads when it starts: with the change appended, a restart brings the changed "
                       "program up")

    p.edge(forte, s1, "", "change", exit=p.side(forte, "left", 99), entry=p.side(s1, "right", 99))
    p.edge(aas, s2, "", "aas", exit=p.side(aas, "right", 99), entry=p.side(s2, "left", 99))
    p.edge(s1, s3, "", "flow", exit=p.side(s1, "bottom"), entry=p.side(s3, "top", 580))
    p.edge(s2, s3, "", "flow", exit=p.side(s2, "bottom"), entry=p.side(s3, "top", 380))
    p.edge(s3, s4, "", "flow", exit=p.side(s3, "bottom", 380), entry=p.side(s4, "top"))
    p.edge(s4, s5, "", "flow", exit=p.side(s4, "right"), entry=p.side(s5, "left"))
    p.edge(s5, forte, "", "change", exit=p.side(s5, "right"), entry=p.side(forte, "left", 351))
    p.edge(s5, s6, "", "flow", exit=p.side(s5, "bottom"), entry=p.side(s6, "top", 580))
    p.edge(s6, boot, "", "change", exit=p.side(s6, "right", 482), entry=p.side(boot, "left", 482))
    p.edge(s6, rec, "", "aas", exit=p.side(s6, "left", 482), entry=p.side(rec, "right", 482))
    p.edge(s6, aas, "", "aas", exit=p.side(s6, "left", 452), entry=p.side(aas, "right", 280),
           points=[(260, 452), (260, 280)])
    p.legend(20, 664, ["flow", "change", "aas"], extra=[("new", "new; or refused online")])
    return p


@figure
def skill_lib():
    p = Page("skill-lib", 960, 640)
    p.head(20, 10, 240, "The module spec (YAML)")
    p.head(280, 10, 300, "modgen writes")
    p.head(600, 10, 340, "The module's application, as FORTE runs it")

    p.lane(20, 32, 240, 560)
    spec = p.card(32, 46, 216, 360, "filling.yaml", icon="modgen")
    for i, (key, says) in enumerate((("targets", "pc: Modbus simulator; pi: GPIO and PWM"),
                                     ("equipment", "each item's IO points, an address per target; its commands"),
                                     ("skill primitives", "one command until a sensor or a time"),
                                     ("module level skills", "parameters and a flow of primitives"),
                                     ("procedures", "what Resetting and Stopping run"))):
        y = 80 + i * 64
        p.pill(42, y, 196, key, "bar")
        p.text(44, y + 22, 192, 40, says, size=11, color="#41484B")
    p.card(32, 420, 216, 160, "The rules, not the generator", size=11,
           body="A program written by hand in the 4diac IDE inside the same shell is as good: the tools rely on "
                "the module rules, which the AAS names (RuleSet)")

    p.lane(280, 32, 300, 560)
    lib = p.card(292, 46, 276, 270, "ModLib", tag="package modlib", tag_color="reconfiguration")
    for i, (name, says) in enumerate((("MOD_Occupation", "who may command the module"),
                                      ("MOD_StateManager", "the module's PackML states"),
                                      ("SKILL_Core", "a skill's state machine and OPC UA methods"),
                                      ("SKILL_Param_*", "a parameter's value and range"),
                                      ("SKILL_Join, _Condition, _Merge", "parallel blocks, decisions"),
                                      ("IO_DI, IO_DO, IO_AI, IO_AO", "an IO point from its address"))):
        y = 80 + i * 38
        p.pill(302, y, 256, f"**{name}**", "outline-reconfiguration", h=18, size=10)
        p.text(304, y + 19, 252, 16, says, size=10, color="#41484B")
    proj = p.card(292, 330, 276, 170, "The module's project", tag="cell/control", tag_color="lines")
    for i, (name, says) in enumerate((("EQ_LinearAxis, EQ_Pump, ...", "an equipment item: owns its IO"),
                                      ("SK_MoveAxis, SK_Dispense, ...", "a skill primitive: a block type"),
                                      ("FillingModule.sys", "an application per target"))):
        y = 364 + i * 42
        p.pill(302, y, 256, f"**{name}**", "outline-reconfiguration", h=18, size=10)
        p.text(304, y + 19, 252, 16, says, size=10, color="#41484B")
    p.card(292, 514, 276, 66, None, size=11,
           body="Then the 4diac IDE checks and exports the types; FORTE is built with them (forte-runtime)")

    p.lane(600, 32, 340, 560)
    start = p.pill(612, 48, 120, "START", "dark", h=24)
    p.text(740, 50, 190, 20, "the resource's own block: COLD, WARM", size=10, color="#6E777B")
    chain = []
    for i, (name, kind, says) in enumerate((("Occupation", "plain", "the module level"),
                                            ("Module", "plain", "PackML: Stopped, Idle, Execute, ..."),
                                            ("LinearAxis · Pump · Scale", "plain", "equipment: IO by address"),
                                            ("MoveAxis · Home · ...", "reconfiguration", "offered primitives"),
                                            ("Resetting · Stopping", "plain", "procedures"))):
        y = 86 + i * 42
        chain.append(p.pill(612, y, 180, name, kind, h=24))
        p.text(800, y + 4, 130, 20, says, size=10, color="#6E777B")
    sk = p.card(612, 302, 316, 210, "Dispensing", tag="a subapplication", tag_color="reconfiguration", size=11)
    p.pill(622, 336, 140, "Control: SKILL_Core", "outline-reconfiguration", h=20, size=10)
    p.pill(778, 336, 140, "UaStart: Start method", "outline-reconfiguration", h=20, size=10)
    p.pill(622, 362, 296, "Volume: SKILL_Param_LREAL", "outline-reconfiguration", h=20, size=10)
    p.text(624, 388, 290, 16, "Execute: the steps, each a primitive instance", size=10, color="#6E777B")
    steps = []
    for i, t in enumerate(("NeedleDown", "Dispense", "Home", "Weigh")):
        steps.append(p.pill(622 + i * 76, 410, 70, t, "reconfiguration", h=22, size=10))
    for a, b in zip(steps, steps[1:]):
        p.edge(a, b, "", "step", exit=(1, 0.5), entry=(0, 0.5))
    p.text(624, 440, 290, 66, "Equipment is reached over local channels (loc[Filling/LinearAxis/cmd]), so a "
                              "skill added online needs no connection to it", size=10, color="#41484B")
    p.text(612, 524, 316, 60, "One INIT chain from START; a block added online is appended to its end. "
                              "Published below /Objects/Filling", size=11, color="#41484B")
    p.edge(start, chain[0], "", "flow", exit=(0.5, 1), entry=(0.5, 0))
    for a, b in zip(chain, chain[1:]):
        p.edge(a, b, "", "flow", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(chain[-1], sk, "INIT", "flow", exit=(0.5, 1), entry=p.side(sk, "top", 702))
    p.edge(spec, lib, "", "flow", exit=p.side(spec, "right", 180), entry=p.side(lib, "left", 180))
    p.edge(spec, proj, "", "flow", exit=p.side(spec, "right", 380), entry=p.side(proj, "left", 380))
    p.edge(proj, sk, "", "ref", exit=p.side(proj, "right", 440), entry=p.side(sk, "left", 440))
    p.legend(20, 606, ["flow", "step", "ref"])
    return p


@figure
def mgmt():
    p = Page("mgmt", 960, 560)
    p.head(20, 10, 250, "What it reads")
    p.head(290, 10, 360, "iec61499_mgmt")
    p.head(670, 10, 270, "FORTE")

    p.lane(20, 32, 250, 480)
    sys_ = p.card(32, 46, 226, None, "A 4diac system", tag=".sys", tag_color="reconfiguration", size=11,
                  body="The IDE's applications, devices and mappings: what modgen writes and the IDE edits")
    types = p.card(32, 160, 226, None, "Block types", tag=".fbt", tag_color="reconfiguration", size=11,
                   body="Their interfaces; the hashes come from the running FORTE build")
    nets = p.card(32, 262, 226, None, "Networks", tag="JSON", tag_color="reconfiguration", size=11,
                  body="What runs now and what should run: instances, connections, values, versioned contracts")
    users = p.card(32, 380, 226, 120, "Used by", size=11,
                   body="modsync (read, change online), deploy/pi.py (boot files), modgen's tests, the evaluation")

    p.lane(290, 32, 360, 480)
    grid = {}
    for name, says, col, row in (
            ("sysfile", "An application flattened: subapplications as dotted names, pins resolved, START links "
                        "kept", 0, 0),
            ("bootfile", "The commands as a boot file: the resource, the blocks in the application's container, "
                         "values, connections", 1, 0),
            ("typelib", "types.json: each type's interface and the hash FORTE reports", 0, 1),
            ("cli", "python -m iec61499_mgmt plan, types, boot", 1, 1),
            ("planner", "Ordered commands from a current to a desired network; no sockets", 0, 2),
            ("verify", "A resource read back and compared with what was wanted", 1, 2)):
        grid[name] = p.card(302 + col * 172, 46 + row * 112, 164, 104, name, body=says, size=10, title_size=12)
    proto = p.card(302, 384, 336, 116, "protocol", tag="Command, Client", tag_color="integration", size=10,
                   title_size=12,
                   body="Command: one typed request (create, delete, connect, disconnect, write, read, start, stop, "
                        "kill, query). Client: one TCP connection, one request at a time, a refusal raised as "
                        "ManagementError, nothing retried")

    p.lane(670, 32, 270, 480)
    forte = p.card(682, 46, 246, 356, "Management port 61499", tag="no login", tag_color="deployment", size=11)
    p.pill(692, 80, 226, "device", "plain")
    p.pill(702, 106, 216, "resource RES: EMB_RES, START", "plain")
    p.pill(712, 132, 206, "Filling_pi: the container", "reconfiguration")
    p.pill(722, 158, 196, "Filling_pi.Dispensing.Control", "outline-reconfiguration", size=10)
    p.text(694, 190, 226, 200, "A frame: 0x50, a 16-bit length, the resource's name, the XML Request; the answer "
                               "the same way. Names inside the container carry the application's name, as the "
                               "4diac IDE deploys, so the IDE can watch the program", size=11, color="#41484B")
    boot = p.card(682, 418, 246, 82, "Boot file", tag="forte.fboot", tag_color="deployment", size=10,
                  body="<resource>;<Request .../> a line; FORTE runs it at start")

    p.edge(sys_, grid["sysfile"], "", "flow", exit=p.side(sys_, "right", 96), entry=p.side(grid["sysfile"], "left", 96))
    p.edge(types, grid["typelib"], "", "flow", exit=p.side(types, "right", 208),
           entry=p.side(grid["typelib"], "left", 208))
    p.edge(nets, grid["planner"], "", "flow", exit=p.side(nets, "right", 310),
           entry=p.side(grid["planner"], "left", 310))
    p.edge(grid["sysfile"], grid["bootfile"], "", "flow", exit=(1, 0.5), entry=(0, 0.5))
    p.edge(grid["bootfile"], boot, "", "flow", exit=p.side(grid["bootfile"], "right", 96),
           entry=p.side(boot, "left", 470), points=[(660, 96), (660, 470)])
    p.edge(grid["planner"], proto, "", "flow", exit=(0.5, 1), entry=p.side(proto, "top", 384))
    p.edge(grid["verify"], proto, "", "flow", exit=(0.5, 1), entry=p.side(proto, "top", 556))
    p.edge(proto, forte, "", "change", exit=p.side(proto, "right", 396), entry=p.side(forte, "left", 396),
           start="block")
    p.legend(20, 528, ["flow", "change"])
    return p


@figure
def runtime():
    p = Page("runtime", 960, 600)
    p.head(20, 10, 220, "From the 4diac projects")
    p.head(260, 10, 420, "To a FORTE binary")
    p.head(700, 10, 240, "Where it runs")

    p.lane(20, 32, 220, 520)
    projs = p.card(32, 46, 196, None, "The projects", icon="iec61499-skill-lib", size=11,
                   body="ModLib, FillingModule, StopperingModule and the generator's test module")
    own = p.card(32, 172, 196, None, "Your own project", tag="the kit", tag_color="deployment", size=11,
                 body="Someone else's block types, built beside the lab's (build-project.ps1)")
    p.card(32, 298, 196, None, "Types are built in", size=11,
           body="A FORTE runs only programs whose block types it was built with. A new or changed type means a "
                "new FORTE; a changed program (other instances, connections, values) is only deployed")

    p.lane(260, 32, 420, 520)
    s1 = p.card(272, 46, 396, None, "Check and export", tag="validate.ps1", tag_color="reconfiguration", size=11,
                body="The 4diac IDE 3.3, headless: every type and system checked, the types exported as C++, the "
                     "library compiled once")
    s2 = p.card(272, 148, 396, None, "Patch FORTE 3.3.0", tag="forte-patches", tag_color="reconfiguration", size=11,
                body="Fixes as a stack of patches: the IO handles, a sysfs PWM module, GPIOChip and PWMChip "
                     "stand-ins on Windows; header shims (forte-compat)")
    s3 = p.card(272, 268, 396, 122, "Build with the FBE", tag="C:\\4diac-fbe", tag_color="reconfiguration", size=11)
    p.pill(282, 300, 184, "modules-win: forte.exe", "reconfiguration", h=22)
    p.pill(474, 300, 184, "pi/modules-pi: aarch64", "reconfiguration", h=22)
    p.text(284, 330, 372, 56, "One binary with every module's types and open62541, linked statically; the cross "
                              "compiler comes with the FBE", size=11, color="#41484B")
    s4 = p.card(272, 406, 396, None, "Package", tag="build-pi.ps1", tag_color="reconfiguration", size=11,
                body="runtime/bin/forte-aarch64 and its checksum, committed: the installer takes it from there")
    for cid, n in ((s1, 1), (s2, 2), (s3, 3), (s4, 4)):
        x, y = p.where[cid][:2]
        p.num(x - 7, y - 7, n)

    p.lane(700, 32, 240, 520)
    pc = p.card(712, 46, 216, None, "This PC", tag="Windows", tag_color="execution", size=11,
                body="forte.exe with the IO simulated over Modbus: run_module.py, the live tests, the evaluation")
    pi = p.card(712, 172, 216, None, "A Raspberry Pi", tag="install.sh", tag_color="deployment", size=11,
                body="Docker, FORTE in a container with the GPIO chip and the PWM channels, fake-hwclock; again to "
                     "update, the program kept")
    p.card(712, 322, 216, None, "A running Pi", tag="update-pi.ps1", tag_color="deployment", size=11,
           body="Build, send the binary, rebuild the container, wait until FORTE answers")
    p.card(712, 436, 216, None, "Anywhere", tag="make-kit.ps1", tag_color="deployment", size=11,
           body="forte-kit.zip, without this repository: build-project.ps1, install-pi.ps1, the base images")

    p.edge(projs, s1, "", "flow", exit=p.side(projs, "right", 86), entry=p.side(s1, "left", 86))
    p.edge(own, s1, "", "flow", exit=p.side(own, "right", 214), entry=p.side(s1, "left", 112),
           points=[(250, 214), (250, 112)])
    for a, b in ((s1, s2), (s2, s3), (s3, s4)):
        p.edge(a, b, "", "flow", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(s3, pc, "", "flow", exit=p.side(s3, "right", 290), entry=p.side(pc, "left", 100),
           points=[(690, 290), (690, 100)])
    p.edge(s4, pi, "", "flow", exit=p.side(s4, "right", 440), entry=p.side(pi, "left", 240),
           points=[(694, 440), (694, 240)])
    p.legend(20, 568, ["flow"])
    return p


# -- Execution -------------------------------------------------------------------------------------------

@figure
def agents():
    p = Page("agents", 960, 600)
    top = p.lane(20, 10, 920, 92, "Orders")
    order = p.card(32, 40, 260, 52, None, parent=top)
    p.text(42, 46, 244, 40, "**POST /orders** or an XMPP message\n{product: Vial2mLAAS, quantity: 3}", size=11,
           parent=order)
    oa = p.pill(330, 52, 150, "order agent", "execution", h=28, size=12, bold=True)
    prods = [p.pill(540 + i * 132, 52, 120, f"Vial2mL-{i + 1}", "execution", h=28, size=12) for i in range(3)]
    p.text(540, 82, 380, 16, "a product agent per unit: walks the product's recipe, one step at a time", size=10,
           color="#6E777B")
    p.edge(order, oa, "", "flow", exit=(1, 0.5), entry=(0, 0.5))
    p.edge(oa, prods[0], "starts", "flow", exit=(1, 0.5), entry=(0, 0.5))

    mid = p.lane(20, 122, 920, 238, "The bidding, one step at a time (VDI/VDE 2193 over XMPP)")
    pa = p.card(32, 156, 180, 188, "Product agent", icon="lineagents", size=11,
                body="Calls for proposals with the step's required capability; takes the built skill first; has "
                     "the product carried to the module")
    msgs = []
    for i, (t, back) in enumerate((("callForProposal", False), ("proposal  |  refusal", True),
                                   ("acceptProposal  |  reject", False), ("informConfirm  |  failure", True))):
        y = 164 + i * 44
        msgs.append(p.line(232 + (300 if back else 0), y + 10, 532 - (300 if back else 0), y + 10, "message",
                           value=t, width=1.5))
    ra = p.card(552, 156, 180, 188, "Resource agents", icon="lineagents", size=11,
                body="One per module and per shuttle. Bid what their module offers, binding; refuse while busy")
    ex = p.card(752, 156, 176, 188, "On acceptance", size=11,
                body="A skill only described is created first (modsync); then the executor runs it")
    p.edge(ra, ex, "", "flow", exit=(1, 0.5), entry=(0, 0.5))

    p.lane(20, 380, 920, 168, "How a resource agent reaches its module")
    p.card(32, 412, 210, 120, "Manager", icon="lineagents", size=11,
           body="A resource agent for every module the AAS server holds, started on its MQTT events")
    execs = []
    for i, (name, says) in enumerate((("OPC UA", "straight to the module with modlink: fast, the state as it "
                                                 "changes"),
                                      ("DMP", "the Operation at the AAS server: every call in the module's log"),
                                      ("simulated", "no module: the time a skill takes"))):
        execs.append(p.card(258 + i * 170, 412, 160, 120, f"Executor: {name}", size=11, body=says))
    mods = p.card(768, 412, 160, 120, "The modules", size=11,
                  body="FORTE on their Pis, the planar table's shuttles")
    p.edge(execs[1], mods, "", "operate", exit=p.side(execs[1], "bottom", 508), entry=p.side(mods, "bottom", 848),
           points=[(508, 540), (848, 540)])
    p.edge(execs[0], mods, "", "operate", exit=p.side(execs[0], "bottom", 338), entry=p.side(mods, "bottom", 868),
           points=[(338, 544), (868, 544)])
    p.legend(20, 564, ["message", "flow", "operate"])
    return p


@figure
def planar_controller():
    p = Page("planar-controller", 960, 520)
    p.head(20, 10, 260, "The table")
    p.head(300, 10, 360, "planar-controller (Python, Docker)")
    p.head(680, 10, 260, "Its clients")

    p.lane(20, 32, 260, 440)
    tbl = p.card(32, 46, 236, 246, "Planar Motor table", tag="PMC", tag_color="execution")
    for c in range(4):
        for r in range(3):
            p.vertex(52 + c * 50, 84 + r * 50, 46, 46, "", "rounded=0;whiteSpace=wrap;html=1;fillColor=#F3F4F5;"
                                                            "strokeColor=#C9CDD0;strokeWidth=1;")
    for i, (c, r) in enumerate(((0, 0), (2, 1), (3, 2))):
        p.vertex(60 + c * 50, 92 + r * 50, 30, 30, str(i + 1), "rounded=1;absoluteArcSize=1;arcSize=8;whiteSpace="
                 "wrap;html=1;fillColor=#6C91B2;strokeColor=none;fontColor=#FFFFFF;fontStyle=1;fontFamily=Arial;")
    p.text(44, 240, 212, 46, "xbots (shuttles) levitating on flyways, Columns by Rows; the PMC's simulator "
                             "stands in for it", size=11, color="#41484B")
    p.card(32, 306, 236, 150, "Its AAS", shell="resource", size=11,
           body="modreg profile planar: the table and each shuttle as modules; the frame (Columns, Rows, "
                "FlywaySize) and the flyways' coordinates")

    p.lane(300, 32, 360, 440)
    ctl = p.card(312, 46, 336, None, "The controller", size=11,
                 body="Connects to the PMC (pmclib), takes mastership, levitates the xbots. All xbots move as one "
                      "plan, so they pass each other in narrow places; requests for one place are served in order")
    mods = p.card(312, 168, 336, 288, "Modules over OPC UA", tag=":4840", tag_color="execution")
    for i, (name, says) in enumerate((("PlanarTable", "Reset connects and levitates; Stop and Abort reach "
                                                      "every shuttle"),
                                      ("PlanarShuttle1 .. N", "one per xbot"))):
        y = 202 + i * 66
        p.pill(322, y, 316, f"**{name}**", "execution", h=22)
        p.text(324, y + 26, 312, 36, says, size=11, color="#41484B")
    p.text(324, 334, 312, 16, "each like a generated module:", size=11)
    for i, t in enumerate(("Occupation: Occupy, Release", "Module: PackML Reset, Start, Stop, Abort, Clear",
                           "Skills/MoveToPosition(X, Y, Rz)")):
        p.pill(322, 354 + i * 30, 316, t, "outline-execution", h=24)

    p.lane(680, 32, 260, 440)
    ag = p.card(692, 46, 236, 126, "The agents", icon="lineagents", size=11,
                body="Each shuttle has a resource agent: it receives a product, carries it to a module's station "
                     "and releases it (custody)")
    cf = p.card(692, 186, 236, 126, "The Configurator", icon="basyx-aas-web-ui", size=11,
                body="Lays the line out on the table's grid; the shuttle routing (lanes, turn spots, idle area) in "
                     "the line's AAS, read at Reset")
    ua = p.card(692, 326, 236, 130, "Any OPC UA client", size=11,
                body="The HMI, UaExpert, modlink: the same occupation, states and errors as the modules")

    p.edge(tbl, ctl, "", "flow", exit=p.side(tbl, "right", 100), entry=p.side(ctl, "left", 100), start="block")
    p.edge(ctl, mods, "", "flow", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(ag, mods, "", "operate", exit=p.side(ag, "left", 110), entry=p.side(mods, "right", 214),
           points=[(670, 110), (670, 214)])
    p.edge(ua, mods, "", "operate", exit=p.side(ua, "left", 390), entry=p.side(mods, "right", 390))
    p.edge(cf, mods, "routing", "aas", exit=p.side(cf, "left", 290), entry=p.side(mods, "right", 290),
           label_bg="#F3F4F5")
    p.legend(20, 488, ["flow", "operate", "aas"])
    return p


# -- Interfaces, deployment, the line -------------------------------------------------------------------

@figure
def web_ui():
    p = Page("web-ui", 960, 450)
    p.lane(20, 10, 920, 178, "basyx-aas-web-ui: the BaSyx AAS web UI, forked, with the lab's apps")
    apps = []
    for i, (name, icon, tag, kind, body) in enumerate((
            ("Planner", "Planner", "ProcessSequence", "planning",
             "A product's recipe as a graph (also in BPMN); each step's required capability matched against the "
             "resources' offers, bound to a skill and its inputs"),
            ("Skill Editor", "Skill Editor", "skills", "reconfiguration",
             "A module level skill as a flow of the components' primitives: sequences, parallel blocks, "
             "decisions; values within limits; saved as Described"),
            ("Configurator", "basyx-aas-web-ui", "Configurator", "interfaces",
             "Products assembled; a line laid out on the planar table's grid; the shuttles' routing; the "
             "process AAS written"),
            ("HMI, Orders", "HMI", "to come", "new",
             "Today the HMI is a Python app on modlink; both become apps here: modules operated from their AAS, "
             "orders sent to an orchestrator"))):
        c = p.card(32 + i * 226, 44, 214, 128, name, icon=icon, tag=tag,
                   tag_color=kind if kind != "new" else "execution", dashed=kind == "new", size=11, body=body)
        apps.append(c)

    p.lane(20, 214, 920, 170, "What they read and write")
    server = p.card(32, 246, 420, 122, "The AAS server", icon="aas-model", tag="BaSyx", tag_color="aas", size=11)
    for i, (kind, name) in enumerate((("product", "Product AASs: recipes"), ("process", "Process AASs"),
                                      ("resource", "Resource AASs: skills, layout"))):
        y = 278 + i * 28
        c = p.card(44, y, 396, 24, None, parent=server)
        p.shell(52, y + 4, kind, parent=c, w=17, h=14)
        p.text(76, y + 4, 360, 16, name, size=11, parent=c)
    reg = p.card(472, 246, 220, 122, "Registration service", icon="registration-service", size=11,
                 body="/check and /plan for the Skill Editor; /process writes a process AAS")
    ms = p.card(712, 246, 216, 122, "modsync", icon="modsync", size=11,
                body="Builds a skill saved as Described on the running module, online")

    p.edge(apps[0], server, "", "aas", exit=p.side(apps[0], "bottom", 220), entry=p.side(server, "top", 220))
    p.edge(apps[1], server, "", "aas", exit=p.side(apps[1], "bottom", 330), entry=p.side(server, "top", 330))
    p.edge(apps[1], reg, "", "flow", exit=p.side(apps[1], "bottom", 400), entry=p.side(reg, "top", 520),
           points=[(400, 200), (520, 200)])
    p.edge(apps[2], reg, "", "flow", exit=p.side(apps[2], "bottom", 600), entry=p.side(reg, "top", 600))
    p.edge(server, ms, "Described", "aas", exit=p.side(server, "bottom", 380), entry=p.side(ms, "bottom", 820),
           points=[(380, 396), (820, 396)])
    p.legend(20, 418, ["aas", "flow"], extra=[("new", "planned")])
    return p


@figure
def deploy():
    p = Page("deploy", 960, 580)
    p.head(20, 10, 470, "deploy-server: the lab's stack on one computer (deploy/aas)")
    p.head(530, 10, 410, "deploy-module: a Raspberry Pi as a module (deploy/pi)")

    left = p.lane(20, 32, 470, 486)
    stack = p.card(32, 46, 446, 320, "docker compose", tag="python deploy/aas.py up", tag_color="deployment")
    for i, (name, port, says) in enumerate((("AAS environment", ":8081", "shells and submodels, in memory"),
                                            ("registries, discovery", "", "where each AAS and submodel is"),
                                            ("web UI", ":3000", "the apps"),
                                            ("DMP", ":8085", "AAS Operations to OPC UA"),
                                            ("InfluxDB", ":8086", "the time series"),
                                            ("Mosquitto", ":1883", "the AAS server's events"),
                                            ("Prosody", ":5222", "XMPP for the agents"))):
        y = 80 + i * 40
        p.pill(42, y, 180, f"**{name}** {port}", "plain", h=26)
        p.text(232, y + 5, 236, 18, says, size=11, color="#41484B")
    beside = p.card(32, 380, 446, 124, "Beside it, as processes", size=11,
                    body="python -m modreg serve --discover: the registration service (:8090), which finds a Pi by "
                         "mDNS and registers it; python -m lineagents --mqtt localhost:1883: the agents. The "
                         "secrets in deploy/aas/.env, never committed")

    right = p.lane(530, 32, 410, 486)
    pi = p.card(542, 46, 386, 270, "Raspberry Pi 4 or 5", tag="64-bit Linux", tag_color="deployment")
    p.pill(552, 80, 366, "**forte**: a Docker container, restarts with the Pi", "reconfiguration", h=26)
    p.text(554, 110, 362, 34, "host network; /dev/gpiochip0; the PWM channels; the boot file ~/forte/boot/"
                              "forte.fboot", size=11, color="#41484B")
    p.pill(552, 152, 176, "61499 management", "integration", h=24)
    p.pill(742, 152, 176, "4840 OPC UA, mDNS", "execution", h=24)
    p.pill(552, 184, 366, "**manifest server** :8088: the module's profiles", "plain", h=24)
    p.text(554, 216, 362, 90, "One command on a fresh Pi: curl ... runtime/install.sh | bash: Docker, FORTE, the "
                              "GPIO and PWM, fake-hwclock (the Pi has no clock). Running it again updates FORTE "
                              "and keeps the program", size=11, color="#41484B")
    pc = p.card(542, 330, 386, 174, "From this PC, over SSH", tag="deploy/pi.py", tag_color="deployment", size=11)
    for i, (cmd, says) in enumerate((("install", "the FORTE binary and its container"),
                                     ("module", "the module's program as the boot file"),
                                     ("status, log, stop, start", "the container"),
                                     ("modsync push", "a spec's change, online or by restart"))):
        p.text(554, 364 + i * 34, 362, 30, f"**{cmd}**: {says}", size=11, parent=pc)

    p.edge(pc, pi, "", "flow", exit=(0.5, 0), entry=(0.5, 1))
    p.edge(pi, beside, "", "ref", exit=p.side(pi, "left", 290), entry=p.side(beside, "right", 420),
           points=[(510, 290), (510, 420)])
    p.edge(stack, pi, "", "operate", exit=p.side(stack, "right", 200), entry=p.side(pi, "left", 200), start="block")
    p.legend(20, 538, ["flow", "operate", "ref"])
    return p


@figure
def aseptic_line():
    p = Page("aseptic-line", 960, 560)
    p.head(20, 10, 920, "cell/: the AP2030 line, becoming the aseptic-line repository")
    specs = p.card(20, 34, 220, None, "modules/", icon="aseptic-line", size=11,
                   body="filling.yaml, stoppering.yaml: the module specs; planned/: capping, inspection")
    ctrl = p.card(20, 170, 220, None, "control/", icon="iec61499-skill-lib", size=11,
                  body="FillingModule, StopperingModule: the generated 4diac projects, with the layouts arranged in "
                       "the IDE")
    sim = p.card(20, 316, 220, None, "sim/", icon="forte-runtime", size=11,
                 body="module_sim.py: each module's IO simulated over Modbus (axes, steppers, a servo); "
                      "run_module.py: simulator, FORTE and the module at once")

    ex = p.card(270, 34, 400, 300, "examples/", icon="aas-model", tag="example_line.py", tag_color="lines")
    for i, (kind, name, says) in enumerate((
            ("resource", "The line", "and its planar table with the shuttles"),
            ("resource", "Four modules", "filling, stoppering, capping, inspection, with their components"),
            ("product", "Three products", "a 2 mL vial, a prefilled syringe of 1 mL, a cartridge of 3 mL"),
            ("process", "A process each", "the product's recipe bound to the line, checked (plan_check)"))):
        y = 68 + i * 50
        c = p.card(282, y, 376, 42, None, parent=ex)
        p.shell(290, y + 13, kind, parent=c)
        p.text(316, y + 5, 336, 16, name, size=12, bold=True, parent=c)
        p.text(316, y + 21, 336, 16, says, size=11, color="#41484B", parent=c)
    p.text(282, 272, 376, 56, "Every AAS built by modreg, written to aas/ and with --publish sent to an AAS "
                              "server; precedence/: the Production Sequence 4.0 examples; describe.py writes their "
                              "class diagrams", size=11, color="#41484B")
    ev = p.card(270, 368, 400, 140, "eval/", icon="docs", tag="the paper's evaluation", tag_color="lines")
    for y, t in ((402, "**scenarios.py**: plug, value, written, planned, changeover; each change made online and "
                       "by a restart, timed"),
                 (440, "**planners.py**: GTPyhop, ENHSP, Aries on the same cases"),
                 (462, "**figures.py**, **effort.py**: the charts; results/: the runs")):
        p.text(282, y, 376, 32, t, size=11, parent=ev)

    srv = p.card(700, 34, 240, None, "AAS server", icon="aas-model", tag="--publish", tag_color="aas", size=11,
                 body="The line's AASs, where the planner, the agents and the DMP find them")
    forte = p.card(700, 170, 240, None, "FORTE", tag="PC or Pi", tag_color="reconfiguration", size=11,
                   body="Runs a module's program: with the simulator on this PC, on its Pi with real IO")
    tests = p.card(700, 316, 240, None, "tests/", size=11,
                   body="The modules live on FORTE, against a Pi, with the DMP; the example line built and checked")

    p.edge(specs, ctrl, "modgen", "flow", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(specs, ex, "", "flow", exit=(1, 0.5), entry=p.side(ex, "left", p.where[specs][1] + p.where[specs][3] / 2))
    p.edge(ctrl, sim, "", "flow", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(ex, srv, "", "aas", exit=p.side(ex, "right", 80), entry=p.side(srv, "left", 80))
    p.edge(sim, forte, "", "operate", exit=p.side(sim, "right", 351), entry=p.side(forte, "left", 230),
           points=[(685, 351), (685, 230)])
    p.legend(20, 530, ["flow", "aas", "operate"])
    return p


@figure
def logo():
    p = Page("logo", 96, 96)
    p.icon("AASPIRE", 0, 0, 96)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="*", help="only these pages (default: all)")
    ap.add_argument("--force", action="store_true", help="draw the pages again even if the file has them")
    ap.add_argument("--out", default=str(HERE / "aaspire.drawio"))
    a = ap.parse_args()
    unknown = set(a.pages) - set(FIGURES)
    if unknown:
        ap.error(f"no such figure: {', '.join(sorted(unknown))} (there are: {', '.join(FIGURES)})")
    pages = [fn() for fn in FIGURES.values()]
    written = write(Path(a.out), pages, redraw=set(a.pages or FIGURES) if a.force else ())
    print("drawn:", ", ".join(written) or "nothing new")


if __name__ == "__main__":
    main()
