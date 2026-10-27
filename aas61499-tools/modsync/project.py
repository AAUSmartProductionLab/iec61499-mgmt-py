"""A 4diac IDE project of what runs on a module (``python -m modsync project --host <module>``).

FORTE keeps the program, not the project: its blocks with their types, its connections and its
values, but no layout, comments or type sources, and the IDE cannot load a project from it. A
program built by the module rules says what it is made of, though (``structure``), so together
with the module spec it was generated from, the spec of exactly what runs can be written: the
spec's equipment, skill primitives and wiring, with the module level skills, procedures, offered
primitives and parameter values read from the program, a skill added online among them. modgen
makes the project from that. Its layout comes from the module's project in the repository, so
blocks keep the places they were given in the IDE (taken anew each time: the repository's layout
wins), a block only this project has (a skill added online) keeps its place here, new ones get
free places, and the layout is spread where it is too tight.

The project is checked: the program it deploys must be the one that runs. Only what the module
rules describe can be read back; anything else the program has is reported, not guessed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from iec61499_mgmt.protocol import Client
from modgen import generate, project_dir
from modgen.fbxml import keep_layout
from modgen.spec import Composite, Modbus, ModuleSpec, Parameter

from .compare import Candidate
from .device import literal, read_values
from .structure import read_primitives, structure, nodes_of
from .sync import Status, inspect


@dataclass
class Project:
    """The project of a running module: where it was written, what it differs in from the module
    spec, and what of the program it does not reproduce (empty: all of it)."""
    path: Path
    spec: ModuleSpec
    target: str
    changes: list[str] = field(default_factory=list)
    unreproduced: list[str] = field(default_factory=list)


def running_spec(client: Client, status: Status) -> tuple[ModuleSpec, list[str]]:
    """The module spec of the program that runs, and how it differs from the spec it was made from."""
    cand, snap = status.candidate, status.snapshot
    spec = cand.spec

    def value(port: str) -> str | None:
        if port not in snap.values:
            read_values(client, snap, [port])
        return snap.values.get(port)

    found = structure(snap.fbs, snap.connections, value, read_primitives(project_dir(spec.project) / "Type Library"))
    changes = []

    def parameters(read: dict, before: dict[str, Parameter]) -> dict[str, Parameter]:
        made = {}
        for name, p in read.items():
            old = before.get(name)
            made[name] = Parameter(type=p["type"], default=typed(p["default"], p["type"]),
                                   minimum=typed(p["minimum"], p["type"]), maximum=typed(p["maximum"], p["type"]),
                                   unit=old.unit if old else None, description=old.description if old else "")
        return made

    steps = nodes_of

    composites = {}
    for name, c in found["composites"].items():
        old = spec.composites.get(name)
        if old is None:
            changes.append(f"{name}: a module level skill the spec does not have (added online)")
        composites[name] = Composite(description=old.description if old else "",
                                     parameters=parameters(c["parameters"], old.parameters if old else {}),
                                     execute=steps(c["execute"]), stop=steps(c["stop"]), results=c["results"],
                                     offered=c["offered"])
    changes += [f"{name}: in the spec, not in the program" for name in spec.composites if name not in composites]

    skills = {}
    for name, skill in spec.skills.items():
        offered = found["skills"].get(name, {}).get("offered", skill.offered)
        params = dict(skill.parameters)
        if offered:                                      # an offered primitive holds its defaults itself
            for p, decl in skill.parameters.items():
                written = value(f"{name}.{p}")
                if written is not None:
                    params[p] = decl.model_copy(update={"default": typed(literal(written), decl.type)})
        if offered != skill.offered or params != skill.parameters:
            changes.append(f"{name}: {'offered' if offered else 'not offered'}" if offered != skill.offered
                           else f"{name}: other parameter values than the spec's")
        skills[name] = skill.model_copy(update={"offered": offered, "parameters": params})

    target = spec.targets[cand.target].model_copy(update={"host": snap.host, "port": snap.port})
    if (server := modbus_server(spec, cand.target, value)) is not None:
        changes.append(f"Modbus server: {server.host}:{server.port} unit {server.unit} (the spec's: "
                       f"{(target.modbus or spec.modbus).host}:{(target.modbus or spec.modbus).port})")
        target = target.model_copy(update={"modbus": server})
    made = spec.model_copy(update={"composites": composites, "skills": skills,
                                   "procedures": {n: steps(s) for n, s in found["procedures"].items()},
                                   "targets": {**spec.targets, cand.target: target}})
    if found["equipment"] != list(spec.equipment):
        changes.append(f"equipment: the program has {found['equipment']}, the spec {list(spec.equipment)}")
    return made, changes


def modbus_server(spec: ModuleSpec, target: str, value) -> Modbus | None:
    """The Modbus server the program's IO points use, if it is another than the spec's (a simulator
    on another port): read from the first IO point's address, ``modbus[<host>:<port>:<unit>:...]``."""
    stated = spec.targets[target].modbus or spec.modbus
    for item, eq in spec.equipment.items():
        for point, io in [*eq.inputs.items(), *eq.outputs.items()]:
            if getattr(io, "computed", False) or spec.backend(target, io) != "modbus":
                continue
            address = literal(value(f"{item}.{point}_Address") or "") or ""
            if not str(address).startswith("modbus["):
                return None
            host, port, unit = str(address)[len("modbus["):].split(":")[:3]
            running = stated.model_copy(update={"host": host, "port": int(port), "unit": int(unit)})
            return None if running == stated else running
    return None


def typed(value, typ: str):
    """A value read back (a float for any number) as its parameter type holds it."""
    if value is None or typ == "LREAL":
        return value
    return bool(value) if typ == "BOOL" else int(value)


def write_project(client: Client, host: str, port: int, status: Status, out: Path) -> Project:
    """Write the IDE project of the module ``status`` read into ``out/<project>`` and check it
    against what runs."""
    spec, changes = running_spec(client, status)
    path = Path(out) / spec.project
    system = path / f"{spec.project}.sys"
    arranged = project_dir(spec.project) / f"{spec.project}.sys"
    if arranged.exists():                                   # the layout arranged in the IDE comes along
        if system.exists():
            tree = ET.parse(system)                         # what only this project has keeps its place
            keep_layout(tree.getroot(), arranged)
            tree.write(system, encoding="utf-8", xml_declaration=True)
        else:
            system.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(arranged, system)
    generate(spec, path)
    target = status.candidate.target
    check = inspect(client, host, port, [Candidate(None, spec, target)], status.snapshot.resource)
    return Project(path, spec, target, changes, check.drift.lines())
