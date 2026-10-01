"""4diac XML builders for type files, systems and project files.

A :class:`Project` owns one generated 4diac project folder: it qualifies type names, records
every written type in a manifest (read by validate.ps1) and declares the generic comm FBs
(``SERVER_x_y``, ``PUBLISH_n``, ``SUBSCRIBE_n``) that FORTE instantiates at runtime.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

STD = {
    "E_DELAY": "iec61499::events::E_DELAY",
    "E_CYCLE": "iec61499::events::E_CYCLE",
    "E_RESTART": "iec61499::events::E_RESTART",
    "IX": "eclipse4diac::io::IX",
    "QX": "eclipse4diac::io::QX",
    "IW": "eclipse4diac::io::IW",
    "QW": "eclipse4diac::io::QW",
    "GPIOChip": "eclipse4diac::io::gpiochip::GPIOChip",
    "PWMChip": "eclipse4diac::io::pwmsysfs::PWMChip",
    "CLIENT_1_0": "iec61499::net::CLIENT_1_0",
    "CLIENT_0_1": "iec61499::net::CLIENT_0_1",
    "EMB_RES": "iec61499::system::EMB_RES",
    "FORTE_PC": "iec61499::system::FORTE_PC",
}
# Interface declarations of standard types, vendored from the 4diac IDE 3.3 type libraries.
STDTYPES = Path(__file__).resolve().parents[1] / "stdtypes"
NET = "iec61499::net"


GENERIC = re.compile(rf"{NET}::(SERVER|PUBLISH|SUBSCRIBE)_(\d+)(?:_(\d+))?")


def server(sds: int, rds: int) -> str:
    """SERVER_sds_rds: an OPC UA method with rds arguments in and sds results out."""
    return f"{NET}::SERVER_{sds}_{rds}"


def publish(n: int) -> str:
    return f"{NET}::PUBLISH_{n}"


def subscribe(n: int) -> str:
    return f"{NET}::SUBSCRIBE_{n}"


def elem(parent, tag, **attrs):
    """Append an XML child with stringified attributes."""
    return ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()})


LAYOUT = ("x", "y", "dx1", "dx2", "dy")


def keep_layout(root, path):
    """Copy positions and connection routing from the file being replaced, so a layout arranged
    in the IDE survives regeneration. Blocks match by name path, connections by their ends."""
    try:
        old = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return

    def placed(tree):
        found = {}

        def walk(node, prefix):
            for child in node:
                name = child.get("Name")
                if child.tag in ("FB", "SubApp", "ECState", "Group") and name:
                    found[(child.tag, prefix + name)] = child
                    walk(child, prefix + name + ".")
                elif child.tag == "Connection":
                    found[("Connection", prefix + child.get("Source", "") + ">" + child.get("Destination", ""))] = child
                else:
                    walk(child, prefix)
        walk(tree, "")
        return found

    def group(node):
        attr = node.find("Attribute[@Name='GroupName']")
        return attr.get("Value") if attr is not None else None

    before = placed(old)
    for key, node in placed(root).items():
        # A block's position is relative to its group: only kept while it stays in that group.
        if key in before and group(before[key]) == group(node):
            for attr in LAYOUT:
                if attr in before[key].attrib:
                    node.set(attr, before[key].get(attr))


LEFT, TOP, GAP = 2800, 900, 1200     # room for parameter values left of a block, the group title, between groups


def arrange(net, groups, x=1000, y=1000):
    """Arrange a network's blocks in titled groups stacked from top to bottom.

    ``groups``: (name, comment, members, columns, dx, dy) with the grid pitch of the group; members
    not in the network are skipped, empty groups left out. The IDE 3.2 has no group colours.
    """
    blocks = {el.get("Name"): el for el in net if el.tag in ("FB", "SubApp")}
    made = []
    for name, comment, members, cols, dx, dy in groups:
        names = [n for n in members if n in blocks]
        if not names:
            continue
        rows = (len(names) + cols - 1) // cols
        width, height = LEFT + min(cols, len(names)) * dx, TOP + rows * dy
        made.append(ET.Element("Group", Name=name, Comment=comment, x=str(x), y=str(y), width=str(width),
                               height=str(height), locked="false"))
        for i, n in enumerate(names):
            el = blocks[n]
            # A grouped block's position is relative to its group.
            el.set("x", str(LEFT + (i % cols) * dx))
            el.set("y", str(TOP + (i // cols) * dy))
            elem(el, "Attribute", Name="GroupName", Type="STRING", Value=name)
        y += height + GAP
    for i, g in enumerate(made):
        net.insert(i, g)


def save(root, path):
    """Indent and write an XML tree, creating folders; keeps the layout of an existing file."""
    if path.exists():
        keep_layout(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def spec(v):
    """Split a variable spec into (type, initial value)."""
    return v if isinstance(v, tuple) else (v, None)


def wstr(text):
    """Quote text as a WSTRING literal."""
    return '"' + text + '"'


def declare(group, variables):
    """Add VarDeclarations from {name: type or (type, initial)}."""
    for name, value in variables.items():
        typ, initial = spec(value)
        attrs = dict(Name=name, Type=typ)
        if initial is not None:
            attrs["InitialValue"] = initial
        elem(group, "VarDeclaration", **attrs)


def interface(root, inputs, outputs, iv=None, ov=None, sub=False):
    """inputs/outputs: {event: [vars]} or {event: ([vars], "EInit")}.

    ``sub``: the interface of an untyped subapplication, which the IDE's system loader only
    accepts as ``SubAppInterfaceList`` with ``SubAppEventInputs``/``SubAppEventOutputs``.
    """
    prefix = "SubApp" if sub else ""
    iface = elem(root, prefix + "InterfaceList")
    for tag, events in [(prefix + "EventInputs", inputs), (prefix + "EventOutputs", outputs)]:
        group = elem(iface, tag)
        for name, variables in events.items():
            variables, etype = variables if isinstance(variables, tuple) else (variables, "Event")
            event = elem(group, prefix + "Event", Name=name, Type=etype)
            for var in [] if sub else variables:          # the IDE keeps no With on a subapp's events
                elem(event, "With", Var=var)
    for tag, variables in [("InputVars", iv or {}), ("OutputVars", ov or {})]:
        if variables or not sub:                          # nor empty variable lists
            declare(elem(iface, tag), variables)
    return iface


def connections(net, events, data):
    """Add event and data connection lists to a network."""
    for tag, pairs in [("EventConnections", events), ("DataConnections", data)]:
        if pairs:                                         # as the IDE saves it: no empty lists
            group = elem(net, tag)
            for s, d in pairs:
                elem(group, "Connection", Source=s, Destination=d)


def fb(net, name, typ, x, y, **params):
    """Add an FB instance with parameters to a network."""
    f = elem(net, "FB", Name=name, Type=typ, x=x, y=y)
    for p, v in params.items():
        elem(f, "Parameter", Name=p, Value=v)
    return f


def subapp(net, name, x, y, comment, ei, eo, iv=None, ov=None):
    """Add an untyped subapplication; return it and its inner network."""
    sa = elem(net, "SubApp", Name=name, x=x, y=y, Comment=comment)
    interface(sa, ei, eo, iv, ov, sub=True)
    return sa, elem(sa, "SubAppNetwork")


class Project:
    """One generated 4diac project: type library, system and manifest."""

    def __init__(self, root: Path, name: str, symbolic: str, comment: str, date: str = "2026-09-28",
                 external: frozenset[str] = frozenset()):
        self.root, self.name, self.symbolic, self.comment, self.date = Path(root), name, symbolic, comment, date
        # Packages whose types are declared here but compiled in another project's export (the library).
        self.external = external
        self.types = self.root / "Type Library"
        self.manifest: list[tuple[str, str, str, bool]] = []  # (qualified name, kind, file, exported to C++)
        self.generic: set[tuple[str, int, int]] = set()      # (kind, sds, rds)

    def clean(self):
        """Remember the existing type files; :meth:`prune` later removes those not written again.

        Files are overwritten in place instead of deleting the folder first: an IDE with the
        project open loses its index entries when files disappear ("Could not load system").
        """
        self.stale = {p for p in self.types.rglob("*") if p.is_file()
                      and not any(part.endswith(".assets") for part in p.parts)} if self.types.exists() else set()

    def prune(self):
        """Delete type files from a previous generation that this one did not write."""
        written = {self.types / rel for _, _, rel, _ in self.manifest}
        for path in self.stale - written:
            path.unlink()
        for folder in sorted({p for p in self.types.rglob("*") if p.is_dir()}, reverse=True):
            if not any(folder.iterdir()):
                folder.rmdir()

    # Generic comm FBs: declared once per size, instantiated by FORTE from GEN_*.
    def server(self, sds: int, rds: int) -> str:
        return self.use(server(sds, rds))

    def publish(self, n: int) -> str:
        return self.use(publish(n))

    def subscribe(self, n: int) -> str:
        return self.use(subscribe(n))

    def use(self, typ: str) -> str:
        """Declare ``typ`` in the project if it is a generic comm FB; return it."""
        if m := GENERIC.fullmatch(typ):
            kind, a, b = m[1], int(m[2]), int(m[3] or 0)
            self.generic.add({"SERVER": (kind, a, b), "PUBLISH": (kind, a, 0), "SUBSCRIBE": (kind, 0, a)}[kind])
        return typ

    def record(self, name, kind, rel, exported):
        """Record a written file in the manifest."""
        self.manifest.append((name, kind, rel.as_posix(), exported))

    def write_generic(self):
        """Write interface-only declarations of every generic comm FB used."""
        for kind, sds, rds in sorted(self.generic):
            name = {"SERVER": f"SERVER_{sds}_{rds}", "PUBLISH": f"PUBLISH_{sds}", "SUBSCRIBE": f"SUBSCRIBE_{rds}"}[kind]
            sd = {f"SD_{i}": "ANY" for i in range(1, sds + 1)}
            rd = {f"RD_{i}": "ANY" for i in range(1, rds + 1)}
            if kind == "SERVER":
                ei = {"INIT": (["QI", "ID"], "EInit"), "RSP": ["QI", *sd]}
                eo = {"INITO": (["QO", "STATUS"], "EInit"), "IND": ["QO", "STATUS", *rd]}
            elif kind == "PUBLISH":
                ei = {"INIT": (["QI", "ID"], "EInit"), "REQ": ["QI", *sd]}
                eo = {"INITO": (["QO", "STATUS"], "EInit"), "CNF": ["QO", "STATUS"]}
            else:
                ei = {"INIT": (["QI", "ID"], "EInit"), "RSP": ["QI"]}
                eo = {"INITO": (["QO", "STATUS"], "EInit"), "IND": ["QO", "STATUS", *rd]}
            t = FB(self, name, f"Generic {kind.lower()} ({sds} SD, {rds} RD); instantiated from GEN_{kind}",
                   ei, eo, {"QI": "BOOL", "ID": "WSTRING", **sd}, {"QO": "BOOL", "STATUS": "WSTRING", **rd},
                   folder="Generic", package=NET)
            t.kind, t.exported = "GenericComm", False
            elem(t.root, "Attribute", Name="eclipse4diac::core::GenericClassName", Value=f"'GEN_{kind}'")
            t.write()

    def copy_std_types(self, skip=("net/PUBLISH_",)):
        """Copy the vendored standard type declarations (generic comm FBs are generated instead)."""
        for src in sorted(STDTYPES.glob("*/*.*")):
            rel = Path("Std") / src.parent.name / src.name
            if any(rel.as_posix().startswith("Std/" + s) for s in skip):
                continue
            (self.types / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, self.types / rel)
            pkg = ET.parse(src).getroot().find("CompilerInfo")
            self.record((pkg.get("packageName") + "::" if pkg is not None else "") + src.stem, "Standard", rel, False)

    def write_project_files(self):
        """Write .project, settings and MANIFEST.MF."""
        root = ET.Element("projectDescription")
        elem(root, "name").text = self.name
        elem(root, "comment").text = self.comment
        elem(root, "projects")
        build = elem(root, "buildSpec")
        for builder in ["org.eclipse.fordiac.ide.library.builder", "org.eclipse.xtext.ui.shared.xtextBuilder",
                        "org.eclipse.fordiac.ide.export.builder"]:
            command = elem(build, "buildCommand")
            elem(command, "name").text = builder
            elem(command, "arguments")
        natures = elem(root, "natures")
        for nature in ["org.eclipse.fordiac.ide.systemmanagement.FordiacNature", "org.eclipse.xtext.ui.shared.xtextNature"]:
            elem(natures, "nature").text = nature
        save(root, self.root / ".project")
        # No .buildpath: one naming only "Type Library" as source folder keeps the root .sys out of
        # the IDE's type library, so the system editor finds no entry ("Could not load system").
        (self.root / ".buildpath").unlink(missing_ok=True)
        # The IDE's library manager walks these folders; they stay empty (standard types are vendored).
        for folder in ["Standard Libraries", "External Libraries"]:
            (self.root / folder).mkdir(parents=True, exist_ok=True)
            (self.root / folder / ".gitkeep").write_text("", encoding="utf-8")
        settings = self.root / ".settings"
        settings.mkdir(exist_ok=True)
        (settings / "org.eclipse.core.resources.prefs").write_text(
            "eclipse.preferences.version=1\nencoding/<project>=UTF-8\n", encoding="utf-8")
        manifest = ET.Element("Manifest", {
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:noNamespaceSchemaLocation": "platform:/resource/org.eclipse.fordiac.ide.library.model/model/library.xsd",
            "Scope": "Project"})
        elem(manifest, "Dependencies")
        product = elem(manifest, "Product", Name=self.name, SymbolicName=self.symbolic, Comment=self.comment)
        elem(product, "VersionInfo", Version="0.1.0", Author="Project contributors", Date=self.date)
        save(manifest, self.root / "MANIFEST.MF")

    def write_manifest(self, path: Path):
        """Write the type manifest read by validate.ps1 and the tests."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([{"type": n, "kind": k, "file": f, "exported": e} for n, k, f, e in self.manifest],
                                   indent=2) + "\n", encoding="utf-8")


class TypeFile:
    """Header and writing shared by all 4diac type files."""
    ext = ".fbt"
    exported = True
    kind = ""

    def header(self, project, tag, name, comment, package, folder):
        """Create the root element with identification, version and package."""
        self.project, self.name, self.package, self.folder = project, name, package, folder
        self.root = ET.Element(tag, Name=name, Comment=comment)
        elem(self.root, "Identification", Standard="61499-2")
        elem(self.root, "VersionInfo", Organization="AAU Smart Production Lab", Version="0.1",
             Author="Project contributors", Date=project.date)
        elem(self.root, "CompilerInfo", packageName=package)

    @property
    def qualified(self):
        """Package-qualified type name."""
        return f"{self.package}::{self.name}"

    def write(self):
        """Write the file and record it in the manifest; return the qualified name."""
        rel = Path(self.folder) / (self.name + self.ext)
        save(self.root, self.project.types / rel)
        self.project.record(self.qualified, self.kind, rel, self.exported and self.package not in self.project.external)
        return self.qualified


class Struct(TypeFile):
    """Structured data type (.dtp)."""
    ext = ".dtp"
    kind = "Struct"

    def __init__(self, project, package, name, comment, members, folder):
        self.header(project, "DataType", name, comment, package, folder)
        declare(elem(self.root, "StructuredType"), members)


class FB(TypeFile):
    """FB type with an interface list."""

    def __init__(self, project, name, comment, ei, eo, iv=None, ov=None, folder="", package=""):
        self.header(project, "FBType", name, comment, package, folder)
        interface(self.root, ei, eo, iv, ov)


class Basic(FB):
    """Basic FB built from ECC states, transitions and ST algorithms; the first state is initial."""
    kind = "BasicFB"

    def __init__(self, project, package, name, comment, ei, eo, iv=None, ov=None, internal=None, folder=""):
        super().__init__(project, name, comment, ei, eo, iv, ov, folder, package)
        self.body = elem(self.root, "BasicFB")
        if internal:
            declare(elem(self.body, "InternalVars"), internal)
        self.ecc = elem(self.body, "ECC")
        self.transitions = []
        self.algorithms = {}

    def state(self, name, code=None, output=None, extra=()):
        """Add an ECC state with an optional algorithm and output events."""
        n = len(self.ecc)
        state = elem(self.ecc, "ECState", Name=name, x=150 + (n % 4) * 420, y=100 + (n // 4) * 230)
        outputs = ([output] if output else []) + list(extra)
        if code is not None:
            self.algorithms[name] = code
            attrs = {"Algorithm": "Alg_" + name}
            if outputs:
                attrs["Output"] = outputs.pop(0)
            elem(state, "ECAction", **attrs)
        for out in outputs:
            elem(state, "ECAction", Output=out)

    def trans(self, source, target, condition):
        """Add an ECC transition; earlier transitions have priority."""
        self.transitions.append((source, target, condition))

    def write(self):
        """Emit transitions and algorithms, then write the file."""
        for source, target, condition in self.transitions:
            elem(self.ecc, "ECTransition", Source=source, Destination=target, Condition=condition, x=0, y=0)
        for name, code in self.algorithms.items():
            alg = elem(self.body, "Algorithm", Name="Alg_" + name)
            elem(alg, "ST").text = code  # element text, as the IDE writes it
        return super().write()


class Simple(FB):
    """SimpleFB: one algorithm per input event, each confirmed by one output event."""
    kind = "SimpleFB"

    def __init__(self, project, package, name, comment, ei, eo, iv, ov, algorithms, internal=None, folder=""):
        super().__init__(project, name, comment, ei, eo, iv, ov, folder, package)
        body = elem(self.root, "SimpleFB")
        if internal:
            declare(elem(body, "InternalVars"), internal)
        for event, (code, output) in algorithms.items():
            state = elem(body, "ECState", Name=event)
            elem(state, "ECAction", Algorithm=event, Output=output)
        for event, (code, _) in algorithms.items():
            alg = elem(body, "Algorithm", Name=event)
            elem(alg, "ST").text = code  # element text, as the IDE writes it


class Wiring:
    """FB instances and connections collected for one network (a composite type's or a subapp's)."""

    def __init__(self):
        self.fbs, self.events, self.data, self.groups = [], [], [], []

    def group(self, name, comment, members, cols=8, dx=4600, dy=3400):
        """Show ``members`` together in a titled group (see :func:`arrange`); groups stack in the order given."""
        self.groups.append((name, comment, list(members), cols, dx, dy))

    def fb(self, name, typ, **params):
        """Add an FB instance with parameter values."""
        self.fbs.append((name, typ, params))
        return name

    def ev(self, source, *destinations):
        """Add event connections from ``source`` to each destination."""
        self.events += [(source, d) for d in destinations]

    def da(self, source, *destinations):
        """Add data connections from ``source`` to each destination."""
        self.data += [(source, d) for d in destinations]

    def chain(self, event, names, last):
        """Chain INIT through ``names`` (INITO -> INIT), starting at ``event`` and ending at ``last``."""
        self.ev(event, names[0] + ".INIT")
        for a, z in zip(names, names[1:]):
            self.ev(a + ".INITO", z + ".INIT")
        self.ev(names[-1] + ".INITO", *([last] if isinstance(last, str) else last))

    def emit(self, net, x, y, dx):
        """Write the instances in one row (no overlapping blocks) and the connections, then the groups."""
        for i, (name, typ, params) in enumerate(self.fbs):
            fb(net, name, typ, x + i * dx, y, **params)
        connections(net, self.events, self.data)
        order = {"FB": 0, "SubApp": 1}                  # FBs ahead of subapps already in the network
        net[:] = sorted(net, key=lambda e: order.get(e.tag, 2))
        arrange(net, self.groups)


class SubNet(Wiring):
    """The network of an untyped subapplication; ``write`` emits it into ``net``."""

    def __init__(self, net):
        super().__init__()
        self.net = net

    def write(self):
        self.emit(self.net, 1000, 1000, 4000)


class Composite(FB, Wiring):
    """Composite FB with an internal FB network."""
    kind = "CompositeFB"

    def __init__(self, project, package, name, comment, ei, eo, iv=None, ov=None, folder=""):
        FB.__init__(self, project, name, comment, ei, eo, iv, ov, folder, package)
        Wiring.__init__(self)
        self.net = elem(self.root, "FBNetwork")

    def write(self):
        """Emit the network (declaring the generic comm FBs it uses), then write the file."""
        for _, typ, _ in self.fbs:
            self.project.use(typ)
        self.emit(self.net, 400, 200, 3600)
        return super().write()
