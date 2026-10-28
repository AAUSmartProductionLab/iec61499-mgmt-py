"""Which process capabilities a module can carry out, skill or no skill (docs/skill-planning.md,
section 6, G5): the ones a plan exists for from its components' capabilities.

A process capability of the vocabulary is defined by what it needs of the product and does to it
(``Vocabulary.constraints``). For each, the values a property of it can take are what the actions
that set the state it is about can be given (a dose's Volume for a FillVolume), and the module
offers the capability for them if a plan exists at both ends of that range. The product is taken to
arrive as the capability needs it.
"""
from __future__ import annotations

from dataclasses import dataclass

from modgen.spec import Composite
from rdflib import RDFS

from .check import simulate
from .domain import PRODUCT, Capability, Constraint, Domain, Var
from .plan import NoPlan, Planned, plan
from .vocabulary import LAB, Vocabulary, local


@dataclass
class Discovered:
    capability: str                                   # the class, by local name
    ranges: dict[str, tuple[float, float]]            # a property and the values it can be planned for
    steps: list[Planned]                              # a plan, for the lower end of each range


def task(vocabulary: Vocabulary, capability: str) -> Capability:
    """A process capability as a task: what it needs of the product and does to it."""
    cap = Capability(name=capability, meaning=capability)
    for s in vocabulary.constraints(capability):
        var = Var(PRODUCT if vocabulary.product(s.prop) else "module", s.prop)
        {"Pre": cap.pre, "Post": cap.post, "Invariant": cap.invariant}[s.kind].append(Constraint(s.prop, var, s.expression))
    for result in vocabulary.results(capability):
        cap.results[result] = [Constraint(s.prop, Var(PRODUCT, s.prop), s.expression) for s in vocabulary.needs(result)]
    return cap


def arriving(cap: Capability) -> dict:
    """The product as the capability needs it: a value for each of its preconditions."""
    state = {}
    for c in cap.pre:
        e, value = c.expression, c.expression.operand
        if e.named is None and value is not None:
            if isinstance(value, bool) or e.op in ("=", ">=", "<="):
                state[c.var] = value
            elif e.op == ">":
                state[c.var] = value + 1.0
            elif e.op == "<":
                state[c.var] = value - 1.0
    return state


def ranges(domain: Domain, cap: Capability) -> dict[str, tuple[float, float]]:
    """For each property the capability's Post compares with, the values the actions setting that
    state can be given."""
    found = {}
    for c in cap.post:
        name = c.expression.named
        if name is None:
            continue
        bounds = []
        for action, setter in domain.setting(c.var):
            given = setter.expression.named if setter.expression.op == "+=" else setter.prop if setter.expression.op == "given" else None
            parameter = action.parameters.get(given) if given else None
            if parameter is not None and parameter.minimum is not None and parameter.maximum is not None:
                bounds.append((parameter.minimum, parameter.maximum))
            elif setter.expression.op == "=" and isinstance(action.operand(setter.expression, {}), (int, float)):
                value = float(action.operand(setter.expression, {}))
                bounds.append((value, value))
        if bounds:
            found[name] = (min(b[0] for b in bounds), max(b[1] for b in bounds))
    return found


def reached(domain: Domain, skill: Composite, capability: str, vocabulary: Vocabulary | None = None) -> dict[str, tuple[float, float]]:
    """What an existing skill reaches of a process capability: for each property its Post compares
    with (a FillVolume), the values at the end of the skill run with all its parameters at their
    lower, then at their upper limits (two doses of 0.5 to 10 mL fill 1 to 20 mL)."""
    cap = task(vocabulary or Vocabulary(), capability)
    start = {**domain.rest, **arriving(cap)}
    ends = []
    for side in ("minimum", "maximum"):
        given = {name: getattr(p, side) for name, p in skill.parameters.items() if getattr(p, side) is not None}
        ends.append(simulate(domain, skill, given, start))
    found = {}
    for c in cap.post:
        values = [end.get(c.var) for end in ends]
        if c.expression.named and c.expression.op == "=" and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                                                                 for v in values):
            found[c.expression.named] = (min(values), max(values))
    return found


def discover(domain: Domain, vocabulary: Vocabulary | None = None) -> list[Discovered]:
    """The process capabilities of the vocabulary a plan exists for on this module."""
    voc = vocabulary or Vocabulary()
    found = []
    classes = sorted(local(c) for c in voc.graph.transitive_subjects(RDFS.subClassOf, LAB.ProcessCapability)
                     if c != LAB.ProcessCapability)
    for capability in classes:
        cap = task(voc, capability)
        if not cap.post:
            continue
        trial = Domain(domain.module, {**{a.name: a for a in domain.actions()}, capability: cap}, domain.rest)
        spans = ranges(trial, cap)
        if any(c.expression.named and c.expression.named not in spans for c in cap.post):
            continue                                      # nothing on the module sets what it compares with
        start = {**domain.rest, **arriving(cap)}
        try:
            low = plan(trial, capability, {k: lo for k, (lo, _) in spans.items()}, start=start)
            plan(trial, capability, {k: hi for k, (_, hi) in spans.items()}, start=start)
        except NoPlan:
            continue
        found.append(Discovered(capability, spans, low))
    return found
