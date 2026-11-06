"""A new module level skill, planned and described in the module's AAS (docs/skill-planning.md, G4).

Read the module's planning domain from its AAS, plan the capability a requirement asks for, lift the
plan to a flow and describe it as the skill editor saves a skill (Deployment Described). Then
``modsync reconfigure`` creates it online, as any described skill. The new skill stops as the
module's other skills do: by the steps of the module's Stop procedure. A result asked for comes from
the step that measured it: the last one that made the state hold the result is known by.

A capability the module does not offer yet is planned as the vocabulary defines it (``requiring``): a
narrower one too (BottomUpFilling, a Filling that keeps the needle near the liquid's surface), with
the bounds and the container's geometry the requirement gives. Every plan is run through the checker
in time against the requirement before it is described (``planned``): what does not hold is NoPlan.
A skill planned for a capability narrower than what its steps contribute says what it was written for
(``pprl:writtenFor``), so that it offers that one.
"""
from __future__ import annotations

from dataclasses import dataclass

from modgen.spec import Composite
from modsync.described import described

from .check import check
from .domain import Domain
from .lift import flow, names
from .plan import NoPlan, Planned, plan, start_state
from .read import read
from .vocabulary import Vocabulary

STOP = "Stopping"


@dataclass
class Composed:
    module: dict                # the module's AAS with the new skill described
    name: str
    skill: Composite
    steps: list[Planned]
    domain: Domain


def requiring(domain: Domain, capability: str, vocabulary: Vocabulary | None = None) -> Domain:
    """The domain with ``capability`` as a task: the module's own, else the vocabulary's process
    capability of that name, with all it needs, does and keeps (a narrower one included)."""
    if capability in domain.capabilities:
        return domain
    voc = vocabulary or Vocabulary()
    if not voc.process(capability):
        raise NoPlan(f"{capability} is no process capability of the vocabulary")
    from .discover import task
    return Domain(domain.module, {**domain.capabilities, capability: task(voc, capability)}, domain.rest)


def planned(domain: Domain, capability: str, values: dict, results: tuple[str, ...] = ()) -> tuple[Domain, list[Planned]]:
    """Plan ``capability`` with ``values`` and run the plan through the checker in time against the
    requirement (its invariants, the product's geometry): the domain planned on and the steps; NoPlan
    if there is none, or it does not hold."""
    domain = requiring(domain, capability)
    steps = plan(domain, capability, values, results)
    found = check(domain, Composite(execute=flow(domain, steps)), start=start_state(domain, capability, values),
                  task=domain.capabilities[capability], values=values)
    if found:
        raise NoPlan(f"the plan for {capability} does not hold: {'; '.join(str(f) for f in found)}")
    return domain, steps


def compose(module: dict, components: list[dict], capability: str, values: dict, results: tuple[str, ...] = (),
            name: str | None = None) -> Composed:
    """Plan ``capability`` with ``values`` (and ``results``) on the module and describe the skill that
    carries it out as ``name`` (default: Planned<capability>). NoPlan if the module cannot."""
    from modreg.offer import described_skill           # modreg writes AASs; it reads the vocabulary from here
    domain, steps = planned(read(module, components), capability, values, results)
    spec = described(module, components)
    named = names(domain, steps)
    sources = {}
    for result in results:
        needed = {c.var for c in domain.capabilities[capability].results[result]}
        for i in reversed(range(len(steps))):
            cap = domain.capabilities[steps[i].capability]
            if needed & {c.var for c in cap.post}:
                outputs = spec.skills[cap.skill].results if cap.skill in spec.skills else {}
                measured = [c.prop for c in cap.post if c.expression.op == "measured" and c.prop in outputs]
                if measured:
                    sources[result] = f"{named[i]}.{measured[0]}"
                break
    told = ", ".join(f"{k} {v}" for k, v in values.items())
    narrower = Vocabulary().specializes(capability) is not None
    skill = Composite(description=f"{capability} ({told}{', giving ' + ', '.join(results) if results else ''}), planned",
                      execute=flow(domain, steps), stop=list(spec.procedures.get(STOP, [])), results=sources,
                      capability=capability if narrower else None)
    name = name or f"Planned{capability}"
    return Composed(described_skill(module, components, name, skill), name, skill, steps, domain)
