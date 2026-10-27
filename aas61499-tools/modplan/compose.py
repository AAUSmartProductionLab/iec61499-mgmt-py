"""A new module level skill, planned and described in the module's AAS (docs/skill-planning.md, G4).

Read the module's planning domain from its AAS, plan the capability a requirement asks for, lift the
plan to a flow and describe it as the skill editor saves a skill (Deployment Described). Then
``modsync reconfigure`` creates it online, as any described skill. The new skill stops as the
module's other skills do: by the steps of the module's Stop procedure. A result asked for comes from
the step that measured it: the last one that made the state hold the result is known by.
"""
from __future__ import annotations

from dataclasses import dataclass

from modgen.spec import Composite
from modsync.described import described

from .domain import Domain
from .lift import flow, names
from .plan import Planned, plan
from .read import read

STOP = "Stopping"


@dataclass
class Composed:
    module: dict                # the module's AAS with the new skill described
    name: str
    skill: Composite
    steps: list[Planned]
    domain: Domain


def compose(module: dict, components: list[dict], capability: str, values: dict, results: tuple[str, ...] = (),
            name: str | None = None) -> Composed:
    """Plan ``capability`` with ``values`` (and ``results``) on the module and describe the skill that
    carries it out as ``name`` (default: Planned<capability>). NoPlan if the module cannot."""
    from modreg.offer import described_skill           # modreg writes AASs; it reads the vocabulary from here
    domain = read(module, components)
    steps = plan(domain, capability, values, results)
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
    skill = Composite(description=f"{capability} ({told}{', giving ' + ', '.join(results) if results else ''}), planned",
                      execute=flow(domain, steps), stop=list(spec.procedures.get(STOP, [])), results=sources)
    name = name or f"Planned{capability}"
    return Composed(described_skill(module, components, name, skill), name, skill, steps, domain)
