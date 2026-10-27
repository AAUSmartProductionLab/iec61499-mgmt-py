"""A module's planning domain: its state, and its capabilities with what they need, do and keep.

A **state variable** (``Var``) is a property of something: the data point of the module's
Operational Data that a capability property names with SameProperty, the product in the module, or
a component (ARSO 0.11, capabilities module). The capabilities of the module's components are the
**actions**: each is realized by a primitive and states its preconditions (Pre), effects (Post)
and invariants, each about one of its properties. An offered (process) capability is a **task**:
its Pre and Post say what it needs of the product and does to it.

A state is a dict from variable to value; a variable it does not hold is not known.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .expression import Expression, WORDS

PRODUCT = "product"
DIGITS = 9                                     # values are kept to this many decimals


@dataclass(frozen=True)
class Var:
    subject: str                               # a data point, PRODUCT, or a component
    meaning: str                               # what the property means, by local name (Position)

    def __str__(self) -> str:
        return self.meaning if self.subject == PRODUCT else f"{self.subject}.{self.meaning}"


@dataclass(frozen=True)
class Measured:
    """A value a capability measured: known once it has run, not before."""
    by: str


@dataclass(frozen=True)
class Constraint:
    prop: str                                  # the property of the capability it is about
    var: Var
    expression: Expression

    def __str__(self) -> str:
        return f"{self.prop} {self.expression}"


@dataclass(frozen=True)
class Parameter:
    """A property a capability is given when it runs (a Range in its PropertySet): a parameter of the
    skill realizing it, of the same name."""
    minimum: float | None = None
    maximum: float | None = None
    default: float | bool | str | None = None

    def admits(self, value) -> bool:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return self.minimum is None and self.maximum is None
        return ((self.minimum is None or value >= self.minimum - 10 ** -DIGITS)
                and (self.maximum is None or value <= self.maximum + 10 ** -DIGITS))


@dataclass
class Capability:
    name: str                                  # its container's idShort (Positioning)
    meaning: str                               # its class, by local name
    skill: str | None = None                   # the skill realizing it
    component: str | None = None               # the component whose set holds it; None: the module's
    parameters: dict[str, Parameter] = field(default_factory=dict)
    values: dict[str, object] = field(default_factory=dict)        # named values (FillPosition: 40.0)
    pre: list[Constraint] = field(default_factory=list)
    post: list[Constraint] = field(default_factory=list)
    invariant: list[Constraint] = field(default_factory=list)
    compositions: list[list[str]] = field(default_factory=list)    # its parts, by name (an offered one)
    results: dict[str, list[Constraint]] = field(default_factory=dict)   # a result and the state it needs

    @property
    def action(self) -> bool:
        """A component's capability, realized by a primitive."""
        return self.component is not None and self.skill is not None

    def defaults(self) -> dict:
        return {name: p.default for name, p in self.parameters.items() if p.default is not None}

    def operand(self, expression: Expression, args: dict):
        """What an expression compares with: its value, or the value of the property it names (the
        argument it was given, a named value, a parameter's default); None if not known."""
        name = expression.named
        if name is None:
            return expression.operand
        if name in args:
            return args[name]
        if name in self.values:
            return self.values[name]
        return self.defaults().get(name)


def same(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return round(a - b, DIGITS) == 0
    return a == b


def known(value) -> bool:
    return value is not None and not isinstance(value, Measured)


def holds(cap: Capability, constraint: Constraint, state: dict, args: dict) -> bool | None:
    """Whether a precondition (or an invariant's comparison) holds in ``state``; None when it cannot
    be told yet (a value not known)."""
    e = constraint.expression
    if e.op in WORDS:
        return True
    value, wanted = state.get(constraint.var), cap.operand(e, args)
    if not known(value) or not known(wanted):
        return None
    if e.op == "=":
        return same(value, wanted)
    if e.op == "!=":
        return not same(value, wanted)
    if isinstance(value, bool) or isinstance(wanted, bool):
        return None                                   # an order of Booleans says nothing
    return {"<": value < wanted, "<=": value <= wanted, ">": value > wanted, ">=": value >= wanted}[e.op]


def effect(cap: Capability, state: dict, args: dict) -> dict:
    """The state once ``cap`` has succeeded with ``args``: its Post constraints applied."""
    new = dict(state)
    for c in cap.post:
        e = c.expression
        if e.op == "=":
            new[c.var] = cap.operand(e, args)
        elif e.op == "+=":
            before, added = state.get(c.var, 0.0), cap.operand(e, args)
            new[c.var] = round(before + added, DIGITS) if known(before) and known(added) else None
        elif e.op == "given":
            new[c.var] = args.get(c.prop, cap.defaults().get(c.prop))
        elif e.op == "measured":
            new[c.var] = Measured(cap.name)
    return {var: value for var, value in new.items() if value is not None}


@dataclass
class Domain:
    module: str
    capabilities: dict[str, Capability]
    rest: dict[Var, object] = field(default_factory=dict)    # where every skill starts and ends

    def actions(self) -> list[Capability]:
        return [c for c in self.capabilities.values() if c.action]

    def tasks(self) -> list[Capability]:
        return [c for c in self.capabilities.values() if c.component is None]

    def realizing(self, skill: str) -> Capability | None:
        """The capability of a component a primitive realizes."""
        return next((c for c in self.actions() if c.skill == skill), None)

    def setting(self, var: Var) -> list[tuple[Capability, Constraint]]:
        """The actions whose Post sets ``var``: the specific ones (``= value``) first, then those set
        to what they are given or add to it."""
        found = [(cap, c) for cap in self.actions() for c in cap.post if c.var == var]
        order = {"=": 0, "given": 1, "+=": 2, "measured": 3}
        return sorted(found, key=lambda pair: order[pair[1].expression.op])

    def after(self, steps: list[tuple[str, dict]], start: dict | None = None) -> dict:
        """The state after ``steps`` (skill, arguments) from ``start``: how the rest state follows from
        the steps of the module's Reset procedure."""
        state = dict(start or {})
        for skill, args in steps:
            cap = self.realizing(skill)
            if cap is not None:
                state = effect(cap, state, {**cap.defaults(), **args})
        return state
