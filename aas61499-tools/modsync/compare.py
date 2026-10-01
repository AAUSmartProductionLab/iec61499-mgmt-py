"""Compare what runs on a module with what its module spec generates for a target."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from iec61499_mgmt.sysfile import FlatApplication, flatten
from modgen.module import application, parameter_port
from modgen.spec import ModuleSpec, Parameter

from .device import Snapshot, literal


def owner(port: str) -> str:
    """The instance of ``<instance>.<port>``."""
    return port.rpartition(".")[0]


def init_link(connection: tuple[str, str]) -> bool:
    """A link of the INIT chain: it only orders the initialisation."""
    return connection[0].endswith(".INITO") and connection[1].endswith(".INIT")


def expected(spec: ModuleSpec, target: str) -> FlatApplication:
    """The application modgen generates for ``target``, flattened as FORTE names its instances."""
    return flatten(application(ET.Element("System"), spec, target).find("SubAppNetwork"))


def parameters(spec: ModuleSpec, fbs: dict[str, str]) -> dict[str, Parameter]:
    """Every skill parameter input of the program with its declaration: the values that may be
    changed online (a skill takes them over at its next start). These are the defaults of skill
    primitive instances (``<instance>.<parameter>``), the constants sequences bind for their steps,
    and the defaults of module level skills (``<skill>.<parameter>.Default``)."""
    ports = {}
    for name, typ in fbs.items():
        package, _, t = typ.rpartition("::")
        if package == spec.package and t.startswith("SK_") and t[3:] in spec.skills:
            ports.update({f"{name}.{p}": pr for p, pr in spec.skills[t[3:]].parameters.items()})
    for skill, comp in spec.composites.items():
        ports.update({parameter_port(spec, skill, p): pr for p, pr in comp.parameters.items() if f"{skill}.{p}" in fbs})
    return ports


def expected_values(spec: ModuleSpec, app: FlatApplication) -> dict[str, str]:
    """Input values of the generated program: what the deployment writes, plus the parameter
    defaults it leaves to the type. An input a data connection drives (a parameter a sequence
    binds to its parent's) holds whatever was passed last, so it has no expected value."""
    values = dict(app.parameters)
    driven = {d for _, d in app.data_connections}
    for port, pr in parameters(spec, app.fbs).items():
        if port not in driven:
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
    def additive(self) -> bool:
        """Only new instances with their connections are missing (and the INIT chain is linked
        differently): they can be created online without touching anything that runs."""
        new = set(self.missing)
        return (bool(new) and not self.unexpected and not self.retyped
                and all(map(init_link, self.unexpected_connections))
                and all(owner(s) in new or owner(d) in new or init_link((s, d)) for s, d in self.missing_connections))

    @property
    def restart(self) -> bool:
        """Only a new boot file and a restart bring the module to the spec."""
        return (self.structural and not self.additive) or any(p not in self.online for p in self.values)

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
