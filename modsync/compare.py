"""Compare what runs on a module with what its module spec generates for a target."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from iec61499_mgmt.sysfile import FlatApplication, flatten
from modgen.module import application
from modgen.spec import ModuleSpec, Parameter

from .device import Snapshot, literal


def expected(spec: ModuleSpec, target: str) -> FlatApplication:
    """The application modgen generates for ``target``, flattened as FORTE names its instances."""
    return flatten(application(ET.Element("System"), spec, target).find("SubAppNetwork"))


def skill_of(spec: ModuleSpec, typ: str) -> tuple[str, str] | None:
    """(``SK`` or ``SC``, skill name) of an instance type of the module's own package, else None."""
    package, _, name = typ.rpartition("::")
    kind, _, skill = name.partition("_")
    if package != spec.package or (kind, skill in spec.skills, skill in spec.composites) not in (
            ("SK", True, False), ("SC", False, True)):
        return None
    return kind, skill


def parameters(spec: ModuleSpec, fbs: dict[str, str]) -> dict[str, Parameter]:
    """Every skill parameter input of the program (``<instance>.<parameter>``) with its declaration.

    These are the values that may be changed online: the defaults of offered skills and the
    constants a module level skill or procedure binds for its steps.
    """
    ports = {}
    for name, typ in fbs.items():
        found = skill_of(spec, typ)
        if found:
            kind, skill = found
            params = spec.skills[skill].parameters if kind == "SK" else spec.composites[skill].parameters
            ports.update({f"{name}.{p}": pr for p, pr in params.items()})
    return ports


def expected_values(spec: ModuleSpec, app: FlatApplication) -> dict[str, str]:
    """Input values of the generated program: what the deployment writes, plus the parameter
    defaults it leaves to the type."""
    values = dict(app.parameters)
    for port, pr in parameters(spec, app.fbs).items():
        values.setdefault(port, pr.literal())
    return values


def same(a: str | None, b: str | None) -> bool:
    """Equal as IEC values (see device.literal)."""
    x, y = literal(a), literal(b)
    if isinstance(x, float) and isinstance(y, float):
        return math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-12)
    return x == y


@dataclass
class Drift:
    """Differences of the running program from the generated one; empty means in sync."""
    missing: list[str] = field(default_factory=list)                    # instances
    unexpected: list[str] = field(default_factory=list)
    retyped: list[tuple[str, str, str]] = field(default_factory=list)   # instance, expected, running
    missing_connections: list[tuple[str, str]] = field(default_factory=list)
    unexpected_connections: list[tuple[str, str]] = field(default_factory=list)
    values: dict[str, tuple[str, str | None]] = field(default_factory=dict)   # port -> (expected, running)
    # Ports FORTE takes over at the next start of their skill (skill parameters): writable online.
    # Every other input is only read at INIT (OPC UA paths, IO and Modbus ids): changing it needs a restart.
    online: set[str] = field(default_factory=set)

    @property
    def structural(self) -> bool:
        """Instances, types or connections differ."""
        return bool(self.missing or self.unexpected or self.retyped or self.missing_connections
                    or self.unexpected_connections)

    @property
    def restart(self) -> bool:
        """Only a new boot file and a restart bring the module to the spec."""
        return self.structural or any(p not in self.online for p in self.values)

    @property
    def empty(self) -> bool:
        return not (self.structural or self.values)

    def size(self) -> int:
        return (len(self.missing) + len(self.unexpected) + len(self.retyped) + len(self.missing_connections)
                + len(self.unexpected_connections) + len(self.values))

    def lines(self) -> list[str]:
        """One line per difference, for reports and the AAS."""
        out = [f"missing instance {n}" for n in self.missing]
        out += [f"unexpected instance {n}" for n in self.unexpected]
        out += [f"{n} is {r}, expected {e}" for n, e, r in self.retyped]
        out += [f"missing connection {s} -> {d}" for s, d in self.missing_connections]
        out += [f"unexpected connection {s} -> {d}" for s, d in self.unexpected_connections]
        out += [f"{p} = {r}, spec {e}" for p, (e, r) in self.values.items()]
        return out


def compare(app: FlatApplication, values: dict[str, str], snap: Snapshot, online: set[str] = frozenset()) -> Drift:
    """Drift of ``snap`` from the generated ``app`` with its ``values``; values are compared where read;
    ``online``: the ports that may be written online (see Drift.online)."""
    wanted = set(app.event_connections + app.data_connections)
    return Drift(
        missing=sorted(app.fbs.keys() - snap.fbs.keys()),
        unexpected=sorted(snap.fbs.keys() - app.fbs.keys()),
        retyped=[(n, app.fbs[n], snap.fbs[n]) for n in sorted(app.fbs.keys() & snap.fbs.keys())
                 if app.fbs[n] != snap.fbs[n]],
        missing_connections=sorted(wanted - snap.connections),
        unexpected_connections=sorted(snap.connections - wanted),
        values={p: (v, snap.values[p]) for p, v in sorted(values.items())
                if p in snap.values and not same(v, snap.values[p])},
        online=set(online))


def distance(app: FlatApplication, snap: Snapshot) -> int:
    """How far the running structure is from ``app`` (instances with type, connections)."""
    wanted = set(app.event_connections + app.data_connections)
    return len(set(app.fbs.items()) ^ set(snap.fbs.items())) + len(wanted ^ snap.connections)


@dataclass
class Candidate:
    """A module spec and one of its targets: a program the module may be running."""
    path: Path | None
    spec: ModuleSpec
    target: str

    @cached_property
    def app(self) -> FlatApplication:
        return expected(self.spec, self.target)


def closest(snap: Snapshot, candidates: list[Candidate]) -> tuple[Candidate, int]:
    """The candidate whose generated program is structurally closest to ``snap``, and its distance."""
    scored = [(distance(c.app, snap), i, c) for i, c in enumerate(candidates)]
    d, _, best = min(scored, key=lambda s: s[:2])
    return best, d
