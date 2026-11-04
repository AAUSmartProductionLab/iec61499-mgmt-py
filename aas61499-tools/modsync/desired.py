"""The AAS as the desired state of a module: what it describes, how the running program differs
from that, and the program brought to it online.

A module is delivered with its program and its AAS (the module's own and one per component).
What the AAS describes is read here without the module spec the program may have been generated
from:

- the components (Hierarchical Structures) are the equipment;
- a component's skills are the skill primitives, each with its parameters, limits and results;
- a skill of the module of the kind Composite is a module level skill: its parameters, the
  primitives it runs in order (or, rule set 2, in parallel blocks and decisions), what each step is
  handed (a constant, or a parameter of the skill) and which step gives a result;
- the steps of the module's own Reset and Stop (skills of the kind ModuleControl) are the procedures;
- a skill's Deployment says whether the program carries it out (Built) or it is only described.

What was built in detail (instance, block type and type hash of every skill and step, the change
log, where the module is managed) is the integrator's record, kept outside the AAS (ARSO 0.10): a
Control Configuration submodel in a folder or at the registration service (``load_record``).

``described`` gives that as a module spec without wiring, ``differences`` compares it with the
program FORTE reports (read by the module rules, ``structure``), and ``reconfigure`` applies what
the rules allow online: a constant, a parameter's default or limits, and a module level skill
that is described but not in the program. A reconfiguration is therefore a change to the AAS;
this module carries it into the program. ``record`` writes what was built: Deployment and the
interface of a built skill into the AAS, the rest into the record.

The AASs are read as plain JSON (an environment: shells and submodels), as an AAS server gives
them.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import html
import re
import time
import xml.etree.ElementTree as ET

from iec61499_mgmt.protocol import Client, Command
from iec61499_mgmt.sysfile import FlatApplication, flatten
from modgen.fbxml import connections as wire, fb
from modgen.module import module_skill
from modgen.spec import ModuleSpec, Parameter

from .compare import Drift, expected, expected_values, init_link, owner
from .device import BOOT, Snapshot, literal, outside, read_structure, read_values
from .structure import driven_by, shape, stated, structure, walk
# What the AAS says, where it is, and what it describes: re-exported, so ``desired`` stays the one
# name a caller needs.
from .aasjson import also, at, children, meaning, qualifier, skill_path, skills_in, submodel, target, variables  # noqa: F401
from .described import COMPOSITE, CONTROL, PRIMITIVE, NotDescribed, deployment, described  # noqa: F401
from .sources import (endpoint, instances, is_server, load, load_record, new_record, record_url,  # noqa: F401
                      store, store_record)
from .sync import Refused, guard, lacking, online, summary

# What a module's program says about itself (rule 1): its name and where its OPC UA nodes are.
MODULE_NAME, MODULE_ROOT = "Occupation.Module", "Occupation.UaRoot"


# The program against the description -------------------------------------------------------------

@dataclass
class Differences:
    """How a running program differs from what its AAS describes; empty: the AAS holds."""
    create: list[str] = field(default_factory=list)                         # described skills the program lacks
    values: dict[str, tuple[str, str | None]] = field(default_factory=dict)  # port -> (described, running)
    restart: list[str] = field(default_factory=list)                        # differences no online change removes
    built: list[str] = field(default_factory=list)                          # the record of what was built is wrong
    partial: dict[str, str] = field(default_factory=dict)                  # of ``create``: what the program has of it

    @property
    def empty(self) -> bool:
        return not (self.create or self.values or self.restart or self.built)

    @property
    def online(self) -> bool:
        """Something differs, and all of it can be brought in line without a restart."""
        return bool(self.create or self.values) and not self.restart

    def lines(self) -> list[str]:
        return ([self.partial.get(n) or f"described, not in the program: {n}" for n in self.create]
                + [f"{p} = {r}, the AAS describes {w}" for p, (w, r) in self.values.items()]
                + self.restart + self.built)


@dataclass
class Reading:
    """A module read against its AAS."""
    spec: ModuleSpec                 # what the AAS describes (``described``)
    snapshot: Snapshot
    running: dict                    # the structure of the program (``structure``)
    differences: Differences


def read(client: Client, host: str, port: int, module: dict, components: list[dict], resource: str = "RES",
         record_: dict | None = None, stats: dict | None = None, audit: bool = False,
         boot: str | None = None) -> Reading:
    """Read the running program and compare it with what the AASs describe and, if there is one, with
    what the record says was built: as skills (their steps, bindings and parameters), and block by
    block against the program the generator builds from the AAS (instances, types, connections,
    instances running; with ``audit``, also every value it writes, one request each, the IO addresses
    against the deployed ``boot`` file). ``stats``, if
    given, gets the seconds of reading the program (``program_s``), of interpreting the AAS
    (``aas_s``) and of comparing the two (``compare_s``)."""
    mark = time.perf_counter()
    snap = read_structure(client, host, port, resource)
    if snap.empty:
        raise NotDescribed(f"{host}:{port} runs no program")

    def value(port_: str) -> str | None:
        if port_ not in snap.values:
            read_values(client, snap, [port_])
        return snap.values.get(port_)

    package = next((t.partition("::")[0] for t in snap.fbs.values() if "::EQ_" in t or "::SK_" in t), None)
    if package is None or value(MODULE_NAME) is None:
        raise NotDescribed(f"{host}:{port} does not run a module built by the module rules")
    name, root = literal(value(MODULE_NAME)), literal(value(MODULE_ROOT))
    if boot:
        # The module's name and OPC UA root are not in the AAS: as the deployed boot file has them, so
        # that one of them changed in the program is found, not taken for what the AAS describes.
        deployed = written(boot, snap.container)
        name = literal(deployed.get(MODULE_NAME)) or name
        root = literal(deployed.get(MODULE_ROOT)) or root
    if stats is not None:
        stats["program_s"] = time.perf_counter() - mark
        mark = time.perf_counter()
    spec = described(module, components, name, package, root)
    wanted = stated(spec)
    if stats is not None:
        stats["aas_s"] = time.perf_counter() - mark
        mark = time.perf_counter()
    primitives = {n: {"package": package, **{k: v for k, v in s.items() if k != "offered"}}
                  for n, s in wanted["skills"].items()}
    # A described skill the program has only part of (a change that was cut) is read as one it lacks,
    # and so created, that is completed; the rest of the program is read without it.
    partial = {s: why for s in spec.composites if (why := partly(spec, snap, s, value))}
    running = structure(*without(snap.fbs, snap.connections, partial), value, primitives)
    found = differences(wanted, running, spec)
    # A skill the program has all of, running, that the skills were not read from is not to be
    # created: the INIT chain does not reach it, or its blocks do not make a skill (a restart).
    for s in [s for s in found.create if s not in partial and any(n.startswith(s + ".") for n in snap.fbs)]:
        found.create.remove(s)
        found.restart.append(f"{s}: in the program, but not reached by the INIT chain from START or not read as a skill")
    found.partial = {s: why for s, why in partial.items() if s in found.create}
    blockwise(spec, snap, value, found, audit, boot)
    for path, typ, digest in instances(record_):
        if path.split(".")[0] in found.create:
            continue                                      # of a skill that is still to be built
        if path not in snap.fbs:
            found.built.append(f"{path}: recorded as built, not in the program")
        elif snap.fbs[path] != typ:
            found.built.append(f"{path} is {snap.fbs[path]}, recorded as {typ}")
        elif digest and snap.hashes.get(typ) != digest:
            found.built.append(f"{path}: {typ} has another hash than the one recorded")
    if stats is not None:
        stats["compare_s"] = time.perf_counter() - mark
    return Reading(spec, snap, running, found)


_GENERATED: dict[str, FlatApplication] = {}


def generated(spec: ModuleSpec) -> FlatApplication:
    """The program the generator builds from ``spec`` for the target the AAS was made for (its one
    target); kept for the next reading of the same AAS (the one after a change, its verification)."""
    target = next(iter(spec.targets))
    key = hashlib.sha256(f"{target}\n{spec!r}".encode()).hexdigest()
    if key not in _GENERATED:
        if len(_GENERATED) >= 8:
            _GENERATED.clear()
        _GENERATED[key] = expected(spec, target)
    return _GENERATED[key]


def blockwise(spec: ModuleSpec, snap: Snapshot, value, found: Differences, audit: bool, boot: str | None = None) -> None:
    """The program against the one the generator builds from the AAS, block by block: an instance more
    or missing or of another type, one not running, a connection more or missing (a restart; one line
    for each top-level part), and with ``audit`` every value the generator writes (written online),
    the equipment's IO addresses as the deployed ``boot`` file writes them (the AAS does not describe
    them; left out without it). What the skills as read do not hold is found so too: a stray instance,
    wiring outside the flow, a value outside the skills. Skills to be created or completed are left
    to that."""
    app = generated(spec)
    skip = set(found.create)
    inside = lambda n: any(n == s or n.startswith(s + ".") for s in skip)          # noqa: E731
    top = lambda n: n.partition(".")[0]                                             # noqa: E731
    want = {n: t for n, t in app.fbs.items() if not inside(n)}
    have = {n: t for n, t in snap.fbs.items() if not inside(n)}
    lines: dict[str, list[str]] = {}

    def note(name: str, line: str) -> None:
        lines.setdefault(top(name), []).append(line)

    for n in sorted(have.keys() - want.keys()):
        note(n, f"{n} ({have[n]}) is not described")
    for n in sorted(want.keys() - have.keys()):
        note(n, f"{n} ({want[n]}) is missing")
    for n in sorted(want.keys() & have.keys()):
        if want[n] != have[n]:
            note(n, f"{n} is {have[n]}, described as {want[n]}")
        elif snap.status.get(n, "RUNNING") != "RUNNING":
            note(n, f"{n} is {snap.status[n]}")
    links = {(s, d) for s, d in app.event_connections + app.data_connections if not inside(owner(s)) and not inside(owner(d))}
    running = {(s, d) for s, d in snap.connections if not inside(owner(s)) and not inside(owner(d))}
    for s, d in sorted(running - links):
        note(owner(s), f"{s} -> {d} is not described")
    for s, d in sorted(links - running):
        note(owner(s), f"{s} -> {d} is missing")
    for part, found_ in sorted(lines.items()):
        found.restart.append(f"{part}: block by block, {len(found_)} "
                             f"difference{'s' if len(found_) > 1 else ''}: {'; '.join(found_[:4])}"
                             + ("; ..." if len(found_) > 4 else ""))
    if audit:
        deployed = written(boot, snap.container) if boot else {}
        values = expected_values(spec, app)
        # Every IO address the boot file writes, also where the program built from the AAS has none.
        values.update({p: v for p, v in deployed.items() if p not in values and wiring(p, app)})
        for port, want_value in values.items():
            if inside(owner(port)) or port in found.values or owner(port) not in have:
                continue
            if wiring(port, app):                  # not in the AAS: as the deployed boot file has it, if given
                if port not in deployed:
                    continue
                want_value = deployed[port]
            if literal(value(port)) != literal(want_value):
                found.values[port] = (want_value, value(port))


def wiring(port: str, app: FlatApplication) -> bool:
    """An equipment item's IO address (``<item>.<signal>_Address``: a pin, a PWM channel, a Modbus
    register): the target's wiring, which the AAS does not describe."""
    return port.endswith("_Address") and app.fbs.get(owner(port), "").partition("::")[2].startswith("EQ_")


def written(boot: str, container: str) -> dict[str, str]:
    """The values a boot file writes, by port as read from FORTE (without the application's container)."""
    found = {}
    for line in boot.splitlines():
        if 'Action="WRITE"' in line and (m := re.search(r'<Connection Source="([^"]*)" Destination="([^"]*)"', line)):
            found[outside(m.group(2), container)] = html.unescape(m.group(1))
    return found


def differences(wanted: dict, running: dict, spec: ModuleSpec) -> Differences:
    """What of ``wanted`` (the AAS, ``stated``) the ``running`` program (``structure``) does not show."""
    found = Differences()
    if wanted["equipment"] != running["equipment"]:
        found.restart.append(f"equipment: the AAS describes {wanted['equipment']}, the program has {running['equipment']}")
    for name, skill in wanted["skills"].items():
        if skill["offered"] != running["skills"].get(name, {}).get("offered"):
            found.restart.append(f"{name}: {'offered' if skill['offered'] else 'not offered'} in the AAS, the program differs")

    def text(value, typ: str) -> str:
        return Parameter(type=typ, default=value).literal()

    def sequence(prefix: str, described_: list[dict], have: list[dict]):
        if shape(described_) != shape(have):
            found.restart.append(f"{prefix}: the AAS describes the steps {[s['name'] for s in walk(described_)]}, "
                                 f"the program runs {[s['name'] for s in walk(have)]}"
                                 + ("" if [s["name"] for s in walk(described_)] != [s["name"] for s in walk(have)]
                                    else " (in another flow)"))
            return
        for a, b in zip(walk(described_), walk(have)):
            for p, v in a["bind"].items():
                r = b["bind"].get(p)
                if v == r:
                    continue
                if isinstance(v, str) or isinstance(r, str):
                    found.restart.append(f"{prefix}.{a['name']}.{p}: handed {v} in the AAS, {r} in the program")
                else:
                    typ = spec.skills[a["skill"]].parameters[p].type
                    found.values[f"{prefix}.{a['name']}.{p}"] = (text(v, typ), text(r, typ))

    for name, why in running.get("unreadable", {}).items():
        found.restart.append(f"{name}: in the program, but it cannot be read as a skill ({why})")
    for name, comp in wanted["composites"].items():
        have = running["composites"].get(name)
        if have is None:
            if name not in running.get("unreadable", {}):
                found.create.append(name)
            continue
        sequence(f"{name}.Execute", comp["execute"], have["execute"])
        sequence(f"{name}.Stop", comp["stop"], have["stop"])
        if (list(comp["parameters"]), comp["results"], comp["offered"]) != (list(have["parameters"]), have["results"], have["offered"]):
            found.restart.append(f"{name}: parameters, results or whether it is offered differ from the AAS")
            continue
        for p, decl in comp["parameters"].items():
            if decl["type"] != have["parameters"][p]["type"]:
                found.restart.append(f"{name}.{p}: {decl['type']} in the AAS, {have['parameters'][p]['type']} in the program")
                continue
            for key, pin in (("default", "Default"), ("minimum", "Lower"), ("maximum", "Upper")):
                if decl[key] != have["parameters"][p][key]:
                    if decl[key] is None:
                        found.restart.append(f"{name}.{p}: the AAS states no {key}, the program has {have['parameters'][p][key]}")
                    else:
                        r = have["parameters"][p][key]
                        found.values[f"{name}.{p}.{pin}"] = (text(decl[key], decl["type"]),
                                                             None if r is None else text(r, decl["type"]))
    for name in running["composites"]:
        if name not in wanted["composites"]:
            found.restart.append(f"{name}: a skill of the program the AAS does not describe")
    for name in sorted(set(wanted["procedures"]) | set(running["procedures"])):
        sequence(name, wanted["procedures"].get(name, []), running["procedures"].get(name, []))
    return found


# Bringing the program to the description -----------------------------------------------------------

def init_tail(connections) -> str:
    """Where the INIT chain of the running program ends (rule 1.5): a new skill is added there."""
    at_, last = driven_by(connections, BOOT), None
    while at_:
        last, at_ = at_, driven_by(connections, at_[:-len(".INIT")] + ".INITO", ".INIT")
    if last is None:
        raise NotDescribed(f"the program has no INIT chain from {BOOT}")
    return last[:-len(".INIT")] + ".INITO"


def fragment(spec: ModuleSpec, names: list[str], tail: str) -> tuple[FlatApplication, list[tuple[str, str]]]:
    """The instances, values and connections of the module level skills ``names`` as the module
    rules build them (the generator's own pattern), and their connections, the first being the
    link from ``tail``, the end of the program's INIT chain."""
    net = ET.Element("SubAppNetwork")
    fb(net, "Tail__", "", 0, 0)
    for i, name in enumerate(names):
        module_skill(net, spec, name, 2000 + i * 5000, 9000)
    chain = ["Tail__", *names]
    wire(net, [(a + ".INITO", z + ".INIT") for a, z in zip(chain, chain[1:])], [])
    flat = flatten(net)
    del flat.fbs["Tail__"]
    links = [(tail if s == "Tail__.INITO" else s, d) for s, d in flat.event_connections + flat.data_connections]
    return flat, links


TAIL = "Tail__.INITO"                       # where ``fragment`` links a skill into the INIT chain


def partly(spec: ModuleSpec, snap: Snapshot, name: str, value) -> str | None:
    """What the program has of the described skill ``name`` when it has some of it but not all of it
    running and initialised, as a reconfiguration leaves it that was cut (it creates, writes, connects,
    starts, and fires INIT last): an instance never started (IDLE), or its OPC UA method not opened
    (``UaStart.QO`` FALSE, set by INIT). None when the program has none of it, or all of it running."""
    have = [n for n in snap.fbs if n.startswith(name + ".")]
    if not have:
        return None
    idle = [n for n in have if snap.status.get(n) == "IDLE"]
    uninitialised = literal(value(f"{name}.UaStart.QO")) is False
    if not idle and not uninitialised:
        return None
    app, links = fragment(spec, [name], TAIL)
    inner = [c for c in links if c[0] != TAIL]
    entry = next(d for s, d in links if s == TAIL)
    lacking_ = [n for n in app.fbs if n not in snap.fbs]
    unlinked = [c for c in inner if c not in snap.connections]
    entered = any(d == entry and not s.startswith(name + ".") for s, d in snap.connections)
    return (f"{name}: part of it in the program, to be completed ({len(app.fbs) - len(lacking_)} of "
            f"{len(app.fbs)} instances, {len(inner) - len(unlinked)} of {len(inner)} connections, "
            f"{len(idle)} never started{'' if entered else ', not in the INIT chain'}"
            f"{', not initialised' if uninitialised or idle else ''})")


def without(fbs: dict[str, str], connections, names) -> tuple[dict[str, str], set[tuple[str, str]]]:
    """The program without the instances of the skills ``names`` and the connections to and from them."""
    inside = lambda instance: any(instance.startswith(n + ".") for n in names)          # noqa: E731
    return ({i: t for i, t in fbs.items() if not inside(i)},
            {(s, d) for s, d in connections if not inside(owner(s)) and not inside(owner(d))})


def completing(app: FlatApplication, links: list[tuple[str, str]], snap: Snapshot,
               values: dict[str, tuple[str, str | None]], resource: str) -> list[Command]:
    """The commands that complete skills the program has part of: the instances it lacks created, the
    values of all their instances written, the connections it lacks made, what has not run started,
    and the INIT chain fired once where it enters them (a cut change stopped before that, its last
    command). Refused where completing is not enough: an instance of another type, or one the skill
    does not have (they would have to be deleted)."""
    names = {n.partition(".")[0] for n in app.fbs}
    wrong = [n for n in app.fbs if n in snap.fbs and snap.fbs[n] != app.fbs[n]]
    stray = [n for n in snap.fbs if n.partition(".")[0] in names and n not in app.fbs]
    if wrong or stray:
        raise Refused("a skill the program has part of cannot be completed online: "
                      + "; ".join(([f"{n} is {snap.fbs[n]}, the skill needs {app.fbs[n]}" for n in wrong]
                                   + [f"{n} is not one of the skill's instances" for n in stray])[:10]))
    cmd = lambda op, **kw: Command(op=op, resource=resource, **kw).inside(snap.container)  # noqa: E731
    entries = [d for s, d in links if init_link((s, d)) and owner(s) not in app.fbs and owner(d) in app.fbs]
    return [*[cmd("write", destination=p, value=e) for p, (e, _) in values.items()],
            *[cmd("create_fb", name=n, type=app.fbs[n]) for n in app.fbs if n not in snap.fbs],
            *[cmd("write", destination=p, value=v) for p, v in app.parameters.items() if owner(p) in app.fbs],
            *[cmd("connect", source=s, destination=d) for s, d in links if (s, d) not in snap.connections],
            *[cmd("start", name=n) for n in app.fbs if snap.status.get(n) != "RUNNING"],
            *[cmd("write", destination=d, value="$e") for d in entries]]


def initialised(client: Client, snap: Snapshot, names, timeout: float = 5.0) -> None:
    """Until the skills ``names`` have opened their OPC UA method (``UaStart.QO``, set when the INIT
    fired at their entry has reached it), or ``timeout``: the INIT chain runs after its trigger."""
    deadline = time.monotonic() + timeout
    waiting = set(names)
    while waiting and time.monotonic() < deadline:
        found = Snapshot(snap.host, snap.port, snap.resource, snap.container, fbs={f"{n}.UaStart": "" for n in waiting})
        read_values(client, found, [f"{n}.UaStart.QO" for n in waiting])
        waiting = {n for n in waiting if literal(found.values.get(f"{n}.UaStart.QO")) is False}
        if waiting:
            time.sleep(0.005)


def amended(boot: str, commands: list[Command]) -> str:
    """The boot file ``boot`` with an online change added, so a restart brings up the changed
    program: what was created and connected goes in before the resource is started, and a value
    written takes the place of the boot file's own write of it (so the boot file is the one the
    generator makes of the changed program, not the old one with the change behind it). Starting
    single instances and firing INIT are left out (a boot does both for everything)."""
    lines = boot.splitlines()
    if not lines or 'Action="START"' not in lines[-1]:
        raise ValueError("not a boot file that ends by starting its resource")
    writes = {}
    for i, line in enumerate(lines):
        if 'Action="WRITE"' in line and (found := re.search(r'Destination="([^"]*)"', line)):
            writes[(line.split(";", 1)[0], found.group(1))] = i
    added = []
    for c in (c for c in commands if c.op in ("create_fb", "write", "connect") and c.value != "$e"):
        at_ = writes.get((c.resource, c.destination)) if c.op == "write" else None
        if at_ is None:
            added.append(c)
        else:
            request = int(re.search(r'ID="(\d+)"', lines[at_]).group(1))
            lines[at_] = f"{c.resource};{c.xml(request)}"
    new = [f"{c.resource};{c.xml(i)}" for i, c in enumerate(added, len(lines))]
    last = lines[-1].replace(f'ID="{len(lines)}"', f'ID="{len(lines) + len(added)}"')
    return "\n".join([*lines[:-1], *new, last]) + "\n"


def reconfigure(client: Client, host: str, port: int, module: dict, components: list[dict], deployer=None,
                force: bool = False, dry_run: bool = False, resource: str = "RES",
                record_: dict | None = None, stats: dict | None = None, audit: bool = False) -> tuple[list[str], Reading]:
    """Bring the running module to what its AAS describes, online; returns what was done (or would
    be, with ``dry_run``) and the module as read afterwards.

    Refused when a difference needs a restart, when FORTE lacks a block type, or (unless ``force``)
    when values are to be written while the module runs or is occupied. A new skill touches
    nothing that runs and is created in any state. The change is verified by reading the program
    back against the AAS, then added to the module's boot file (``deployer``: where that file is).

    ``stats``, if given, gets the time of each phase in seconds (``read_s``: the program read and
    compared with the AAS; ``compile_s``: the commands from the rules and the types asked of FORTE;
    ``guard_s``; ``apply_s``: the commands sent; ``verify_s``: read and compared again; ``persist_s``:
    the boot file amended), the number of ``commands`` and the ``bytes`` of their requests.
    """
    stats = {} if stats is None else stats
    mark = time.perf_counter()
    boot = deployer.load() if audit and deployer is not None else None

    def phase(name: str) -> None:
        nonlocal mark
        now = time.perf_counter()
        stats[name] = now - mark
        mark = now

    before = read(client, host, port, module, components, resource, record_, stats.setdefault("read", {}), audit, boot)
    phase("read_s")
    found = before.differences
    if found.empty:
        return ["the program is what the AAS describes, nothing to do"], before
    if found.restart or found.built:
        raise Refused("not possible online: " + "; ".join((found.restart + found.built)[:10]))
    snap = before.snapshot
    # The INIT chain's end without the skills to create: a skill the program has part of may be in it.
    app, links = fragment(before.spec, found.create, init_tail(without(snap.fbs, snap.connections, found.create)[1])) \
        if found.create else (FlatApplication(), [])
    if missing := lacking(client, app.fbs.values(), snap.hashes):
        raise Refused(f"FORTE lacks the block types {missing}")
    skills = sorted({n.partition(".")[0] for n in app.fbs})
    if any(n in snap.fbs for n in app.fbs):        # skills the program has part of: completed
        commands = completing(app, links, snap, found.values, resource)
        count = lambda op: sum(c.op == op for c in commands)                      # noqa: E731
        done = [f"write {p} := {e} (was {r})" for p, (e, r) in found.values.items()]
        done.append(f"complete {', '.join(skills)}: {count('create_fb')} instances created, "
                    f"{count('connect')} connections made, {count('start')} started")
        done += [f"initialise from {c.destination}" for c in commands if c.value == "$e"]
        done.append(f"{len(commands)} management commands")
    else:
        drift = Drift(missing=list(app.fbs), missing_connections=links, values=found.values)
        commands = online(app, drift, resource, container=snap.container)
        done = summary(drift, commands)
    stats["commands"] = len(commands)
    stats["bytes"] = sum(len(c.xml(i).encode()) for i, c in enumerate(commands, 1))
    phase("compile_s")
    if dry_run:
        return done, before
    if found.values and not force:
        guard(client, before.snapshot)
    phase("guard_s")
    for command in commands:
        client.execute(command)
    if skills:
        initialised(client, snap, skills)          # their INIT chain runs after its trigger
    phase("apply_s")
    after = read(client, host, port, module, components, resource, record_, stats.setdefault("verify", {}), audit, boot)
    lacks = [n for n in app.fbs if n not in after.snapshot.fbs]
    if not after.differences.empty or lacks:
        raise RuntimeError("The module differs from its AAS after the change: "
                           + "; ".join([*after.differences.lines(), *lacks][:10]))
    done.append("verified by reading the program back against the AAS")
    phase("verify_s")
    if deployer is not None:
        deployer.save(amended(deployer.load(), commands))
        done.append("added to the boot file")
    else:
        done.append("not in the boot file (no deployer): a FORTE restart loses the change")
    phase("persist_s")
    return done, after


# The record of what was built ----------------------------------------------------------------------

def prop(id_short: str, value: str) -> dict:
    return {"idShort": id_short, "modelType": "Property", "valueType": "xs:string", "value": value}


def record(module: dict, reading: Reading, done: list[str] | None = None, trigger: str = "",
           components: list[dict] | None = None, record_: dict | None = None) -> tuple[dict, dict]:
    """What runs, written down: the module's AAS with every module level skill the program carries
    out marked Built, and the record (``record_``, or a new one) with every described skill and step,
    its instance, block type and the hash FORTE reports, where the module is managed, when it was
    read, and (with ``done``, what a reconfiguration did) one more entry in the change log.

    A skill that was built and has no action of the interface yet (it was described, then created
    online) also gets its interface: actions, properties, data points and mappings, written by the
    rules a module's AAS is written by (``modreg.offer``; without the registration extra the AAS
    stays without them). With the AASs of the ``components``, the capabilities the module offers
    are derived anew from its skills (``modreg.offer.capabilities``)."""
    module = copy.deepcopy(module)
    config = copy.deepcopy(record_) if record_ is not None else new_record(module)
    skills_ = submodel(module, "Skills")
    snap, spec = reading.snapshot, reading.spec
    elements = config.setdefault("submodelElements", [])

    def element(id_short: str, empty: dict) -> dict:
        found = at(config, id_short)
        if found is None:
            found = {"idShort": id_short, **empty}
            elements.append(found)
        return found

    listed = element("Instances", {"modelType": "SubmodelElementCollection", "value": []})
    known = {(at(i, "InstancePath") or {}).get("value"): i for i in children(listed)}

    def note(path: str, keys: list[str]):
        """A skill or step that is built and not recorded yet."""
        if path in known or path not in snap.fbs:
            return
        known[path] = {"idShort": path.replace(".", "_"), "modelType": "SubmodelElementCollection", "value": [
            prop("InstancePath", path),
            {"idShort": "Skill", "modelType": "ReferenceElement", "value": {"type": "ModelReference", "keys": [
                {"type": "Submodel", "value": skills_["id"]},
                *[{"type": "SubmodelElementCollection", "value": k} for k in keys]]}}]}
        listed.setdefault("value", []).append(known[path])

    def steps_at(steps_: dict | None, keys: list[str]) -> dict[str, list[str]]:
        """Where each step of a flow is in the AAS, by its NodeId: Steps/Step_<k>, inside a parallel
        block or a decision below its Branches/Branch_<j>, inside a conditional below its own Steps."""
        found = {}
        for step in children(steps_):
            here_ = [*keys, "Steps", step["idShort"]]
            found[(at(step, "NodeId") or {}).get("value") or step["idShort"]] = here_
            for b in children(at(step, "Branches")):
                found.update(steps_at(at(b, "Steps"), [*here_, "Branches", b["idShort"]]))
            found.update(steps_at(at(step, "Steps"), here_))
        return found

    for name, comp in spec.composites.items():
        note(f"{name}.Control", skill_path(skills_, name))
        for command, branch in (("Start", "Execute"), ("Stop", "Stop")):
            held_ = at(skills_, *skill_path(skills_, name), command)
            for node, keys in steps_at(at(held_, "Steps"), [*skill_path(skills_, name), command]).items():
                note(f"{name}.{branch}.{node}", keys)
                # The conditions of a decision are part of it.
                for path_ in [p_ for p_ in snap.fbs if p_.startswith(f"{name}.{branch}.{node}_C")]:
                    note(path_, keys)
        # The program carries it out: the AAS says so.
        if f"{name}.Control" in snap.fbs:
            held = at(skills_, *skill_path(skills_, name))
            stated_ = at(held, "Deployment")
            if stated_ is None:
                held.setdefault("value", []).insert(0, prop("Deployment", "Built"))
            else:
                stated_["value"] = "Built"
    for path, entry in known.items():                     # every recorded instance: what runs there now
        if (typ := snap.fbs.get(path)) is not None:
            entry["value"] = [e for e in entry["value"] if e["idShort"] not in ("FBType", "TypeHash")]
            entry["value"][1:1] = [prop("FBType", typ), *([prop("TypeHash", snap.hashes[typ])] if snap.hashes.get(typ) else [])]
    runtime = element("Runtime", {"modelType": "SubmodelElementCollection", "value": []})
    managed = at(runtime, "ManagementEndpoint")
    if managed is None:
        runtime.setdefault("value", []).append(prop("ManagementEndpoint", f"{snap.host}:{snap.port}"))
    else:
        managed["value"] = f"{snap.host}:{snap.port}"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for id_short, value in (("ReadAt", snap.read_at or now), ("SyncState", "InSync" if reading.differences.empty else "Drift")):
        element(id_short, prop(id_short, value))["value"] = value
    if done:
        log = element("ChangeLog", {"modelType": "SubmodelElementList", "orderRelevant": True,
                                    "typeValueListElement": "SubmodelElementCollection", "value": []})
        log["value"].append({"modelType": "SubmodelElementCollection", "value": [
            prop("Time", now), prop("Trigger", trigger or "the AAS describes what the program did not have"),
            prop("Result", "; ".join(done))]})
    reachable = [name for name, comp in spec.composites.items() if comp.offered and f"{name}.Control" in snap.fbs
                 and at(skills_, *skill_path(skills_, name), "Start", "InterfaceReference") is None]
    try:
        from modreg.offer import capabilities, offered      # needs the registration extra (aas-model, rdflib)
    except ImportError:
        return module, config
    if reachable:
        module = offered(module, spec, reachable)
    if components is not None:
        # What the module offers follows from its skills: one that is built now is offered now.
        module = capabilities(module, components)
    return module, config
