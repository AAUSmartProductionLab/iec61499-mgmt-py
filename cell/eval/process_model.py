"""The oracle of Q4 (docs/cirp-evaluation.md): a process model of the filling station that runs a skill's
flow and says whether the product comes out right, from the containers and the physics alone.

It knows nothing of the AAS's capability conditions (no fill position, no rest state, no pre- or
postcondition, no invariant). It shares with the AAS only the hardware's ranges (the axis's travel,
the pump's dose and flow rate). A flow runs in time steps of 10 ms: the needle's tip at the axis's
speed, the pump at its flow rate, the scale; the branches of a parallel block at once; one holder per
equipment item.

Depths are mm down the stroke from the tip at home (100 mm above the table); volumes mL.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import math

from modgen.spec import Composite, Decision, Parallel, Step

DT = 0.01                       # s, a time step
HOME_HEIGHT = 100.0             # mm above the table, the tip at home
NEST = 30.0                     # mm above the table, a container's base in the shuttle's nest
GLASS = 1.0                     # mm, a vial's bottom


@dataclass(frozen=True)
class Container:
    name: str
    rim: float                  # depth of the rim: below it the tip is inside
    bottom: float               # depth of the inner bottom
    capacity: float             # mL to the brim
    diameter: float             # mm, inside
    from_bottom: bool = False   # filled from the bottom up (no foam: O5)

    @property
    def area(self) -> float:
        return math.pi * self.diameter ** 2 / 4

    def surface(self, content: float) -> float:
        """The depth of the liquid's surface with ``content`` mL in it."""
        return self.bottom - content * 1000.0 / self.area

    def lowered(self, by: float) -> "Container":
        return replace(self, rim=self.rim + by, bottom=self.bottom + by)


def vial(name: str, height: float, capacity: float, diameter: float) -> Container:
    return Container(name, HOME_HEIGHT - NEST - height, HOME_HEIGHT - NEST - GLASS, capacity, diameter)


CONTAINERS = {
    "vial 2R": vial("vial 2R", 35.0, 4.0, 14.0),
    "vial 10R": vial("vial 10R", 45.0, 13.5, 22.0),
    "vial 20R": vial("vial 20R", 55.0, 26.0, 28.0),
    # A prefilled syringe of 1 mL (long) stands deeper in its nest: the barrel's bottom 59 mm down.
    "syringe 1 mL": Container("syringe 1 mL", 4.0, 59.0, 1.0, 6.35, from_bottom=True),
}


@dataclass(frozen=True)
class Hardware:
    """What the station can do, the ranges of its hardware; ``lowered``: the station raised by so
    many mm, every container that much further down the stroke."""
    travel: tuple[float, float] = (0.0, 60.0)
    speed: float = 12.5                        # mm/s
    dose: tuple[float, float] = (0.5, 10.0)    # mL
    rate: tuple[float, float] = (0.1, 5.0)     # mL/s
    scale: bool = True
    lowered: float = 0.0
    tare_s: float = 2.0
    weigh_s: float = 0.2


@dataclass(frozen=True)
class Product:
    container: str
    volume: float
    weight: bool = True                        # its weight is required
    tolerance: float = 0.05                    # mL, AbsoluteFillError


ITEM = {"Home": "LinearAxis", "MoveAxis": "LinearAxis", "Dispense": "Pump", "Tare": "Scale", "Weigh": "Scale"}


class Stop(Exception):
    """The run cannot go on (O1)."""


@dataclass
class State:
    container: Container
    hw: Hardware
    z: float = 0.0                 # the tip's depth
    moving: bool = False
    pumping: bool = False
    content: float = 0.0
    spilled: float = 0.0
    tare: float = 0.0              # content when the scale was tared; tared with the empty container at the start
    tare_ok: bool = True
    doses: int = 0                 # doses begun
    weighings: list = field(default_factory=list)   # (right, content, doses) of each finished weighing
    broken: dict = field(default_factory=dict)     # rule -> first detail
    holders: dict = field(default_factory=dict)    # item -> step
    t: float = 0.0

    def breaks(self, rule: str, detail: str) -> None:
        self.broken.setdefault(rule, f"{detail} (t = {self.t:.2f} s)")

    @property
    def inside(self) -> bool:
        return self.z > self.container.rim

    @property
    def still(self) -> bool:
        return not self.moving and not self.pumping and not self.inside


@dataclass
class Outcome:
    right: bool
    broken: dict                   # rule -> detail
    content: float
    weight: float | None           # the weight the last weighing gave, as a volume (None: none right)
    seconds: float


def value(step: Step, name: str, given: dict, default: float | None = None):
    bound = step.bind.get(name, default)
    return given.get(bound) if isinstance(bound, str) else bound


def run(flow: Composite, product: Product, hw: Hardware = Hardware(), given: dict | None = None) -> Outcome:
    """``flow``'s Execute run on ``product`` by the station ``hw``, its parameters ``given`` (else their
    defaults)."""
    given = {n: p.default for n, p in flow.parameters.items() if p.default is not None} | (given or {})
    container = CONTAINERS[product.container].lowered(hw.lowered)
    s = State(container, hw)
    try:
        for _ in sequence(flow.execute, s, given):
            tick(s)
    except Stop:
        pass
    judge(s, product)
    last = s.weighings[-1] if s.weighings else None
    return Outcome(not s.broken, dict(s.broken), round(s.content, 6),
                   last[1] if last and last[0] else None, round(s.t, 2))


def tick(s: State) -> None:
    """What holds at the end of every time step."""
    s.t += DT
    if s.z > s.container.bottom - 1.0 + 1e-9:
        s.breaks("O3", f"the tip at {s.z:.1f} mm, the bottom at {s.container.bottom:.1f} mm")
        raise Stop
    if s.content > s.container.capacity + 1e-9:
        s.breaks("O4", f"{s.content:.2f} mL in a container of {s.container.capacity} mL")


def judge(s: State, p: Product) -> None:
    if s.spilled > 1e-9:
        s.breaks("O2", f"{s.spilled:.2f} mL dosed with the tip outside the container")
    if abs(s.content - p.volume) > p.tolerance + 1e-9:
        s.breaks("O6", f"{s.content:.2f} mL in it, {p.volume} required")
    if p.weight:
        last = s.weighings[-1] if s.weighings else None
        if last is None:
            s.breaks("O7", "never weighed")
        elif not last[0]:
            s.breaks("O7", "the last weighing was disturbed or the tare was not of the empty container")
        elif last[2] < s.doses or abs(last[1] - s.content) > 1e-9:
            s.breaks("O7", "weighed before the last dose")
    if s.inside:
        s.breaks("O8", f"the tip still in the container at the end ({s.z:.1f} mm)")


def sequence(nodes: list, s: State, given: dict):
    for node in nodes:
        if isinstance(node, Step):
            yield from primitive(node, s, given)
        elif isinstance(node, Parallel):
            yield from parallel(node, s, given)
        elif isinstance(node, Decision):
            raise NotImplementedError("the oracle runs no decisions (none in Q4's skills)")


def parallel(block: Parallel, s: State, given: dict):
    branches = [sequence(b, s, given) for b in block.branches]
    while branches:
        branches = [b for b in branches if next(b, StopIteration) is not StopIteration]
        if branches:
            yield


def hold(step: Step, s: State) -> str:
    item = ITEM.get(step.skill)
    if item is None or (item == "Scale" and not s.hw.scale):
        s.breaks("O1", f"{step.name}: the module has no {step.skill}")
        raise Stop
    if item in s.holders:
        s.breaks("O1", f"{step.name}: {item} is held by {s.holders[item]}")
        raise Stop
    s.holders[item] = step.name
    return item


def primitive(step: Step, s: State, given: dict):
    item = hold(step, s)
    try:
        if step.skill in ("Home", "MoveAxis"):
            target = 0.0 if step.skill == "Home" else value(step, "Position", given, 0.0)
            yield from move(step, s, target)
        elif step.skill == "Dispense":
            yield from dispense(step, s, value(step, "Volume", given, 1.0), value(step, "FlowRate", given, 1.0))
        elif step.skill == "Tare":
            yield from measure(s, s.hw.tare_s, tare=True)
        elif step.skill == "Weigh":
            yield from measure(s, s.hw.weigh_s, tare=False)
    finally:
        s.holders.pop(item, None)


def move(step: Step, s: State, target: float):
    low, high = s.hw.travel
    if target is None or not low <= target <= high:
        s.breaks("O1", f"{step.name}: {target} mm is beyond the axis's travel ({low} to {high} mm)")
        raise Stop
    while abs(s.z - target) > 1e-9:
        s.moving = True
        dz = min(s.hw.speed * DT, abs(target - s.z))
        s.z += dz if target > s.z else -dz
        yield
    s.moving = False


def dispense(step: Step, s: State, volume: float, rate: float):
    (vlow, vhigh), (rlow, rhigh) = s.hw.dose, s.hw.rate
    if volume is None or rate is None or not vlow <= volume <= vhigh or not rlow <= rate <= rhigh:
        s.breaks("O1", f"{step.name}: a dose of {volume} mL at {rate} mL/s is beyond the pump's range")
        raise Stop
    s.doses += 1
    left = volume
    while left > 1e-12:
        s.pumping = True
        dv = min(rate * DT, left)
        left -= dv
        if s.inside:
            s.content += dv
        else:
            s.spilled += dv
        if s.container.from_bottom and s.inside and s.z < s.container.surface(s.content) - 2.0:
            s.breaks("O5", f"{step.name}: the tip {s.container.surface(s.content) - s.z:.1f} mm above the liquid")
        yield
    s.pumping = False


def measure(s: State, seconds: float, tare: bool):
    right = True
    for _ in range(round(seconds / DT)):
        yield
        right = right and s.still
    if tare:
        s.tare, s.tare_ok = s.content, right
    else:
        s.weighings.append((right and s.tare_ok and s.tare == 0.0, s.content, s.doses))
