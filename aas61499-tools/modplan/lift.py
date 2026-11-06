"""A plan as a flow: steps one after the other, and parallel blocks where nothing orders two steps.

Step i of a plan comes before a later step j when both use the same component (a component runs one
skill at a time), or one changes a variable the other needs, changes or keeps (its invariant). The
flow is the series-parallel form of that order: the plan is cut wherever every step before the cut
comes before every step after it; a part no cut splits becomes a parallel block with one branch per
group of steps the order connects; a part neither splits keeps the plan's order. Steps are named
after their skill (``Home``, then ``Home_2``), as a module spec names them. A step planned with others
along (the tracking's pair: the dose and the needle rising with the liquid) is a parallel block of
its own, a branch each, started together; it is ordered by what all of them touch.
"""
from __future__ import annotations

from modgen.spec import Composite

from .domain import Domain
from .plan import Planned

MAX_BRANCHES = 4                                  # what a parallel block takes (rule set 2)


def parts(step: Planned) -> list[Planned]:
    """The step and those along it."""
    return [step, *step.along]


def order(domain: Domain, steps: list[Planned]) -> list[list[bool]]:
    """``before[i][j]``: step i has to end before step j starts."""
    touched = []
    for step in steps:
        caps = [domain.capabilities[p.capability] for p in parts(step)]
        touched.append(({cap.component for cap in caps}, {c.var for cap in caps for c in cap.pre},
                        {c.var for cap in caps for c in cap.post}, {c.var for cap in caps for c in cap.invariant}))
    n = len(steps)
    before = [[False] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            (ci, ri, wi, ki), (cj, rj, wj, kj) = touched[i], touched[j]
            before[i][j] = bool(ci & cj) or bool(wi & (rj | wj | kj)) or bool(wj & (ri | ki))
    for k in range(n):                                # what comes before comes before what follows
        for i in range(n):
            if before[i][k]:
                for j in range(n):
                    before[i][j] = before[i][j] or before[k][j]
    return before


def names(domain: Domain, steps: list[Planned]) -> list[str]:
    """The name of each step (of a pair, of its first part); ``named`` has those of the parts along."""
    return [found[0] for found in named(domain, steps)]


def named(domain: Domain, steps: list[Planned]) -> list[list[str]]:
    """The names of each step's parts, the step first: ``Dispense``, then ``Dispense_2``."""
    seen: dict[str, int] = {}
    found = []
    for step in steps:
        here = []
        for part in parts(step):
            skill = domain.capabilities[part.capability].skill
            seen[skill] = seen.get(skill, 0) + 1
            here.append(skill if seen[skill] == 1 else f"{skill}_{seen[skill]}")
        found.append(here)
    return found


def flow(domain: Domain, steps: list[Planned]) -> list:
    """The plan as the Execute flow of a module level skill, in a module spec's short form."""
    before, called = order(domain, steps), named(domain, steps)
    blocks = iter(range(1, 2 * len(steps) + 1))

    def one(part: Planned, name: str):
        return {domain.capabilities[part.capability].skill: dict(part.args), "as": name}

    def item(i: int):
        if not steps[i].along:
            return one(steps[i], called[i][0])
        number = next(blocks)
        return {"parallel": [[one(part, name)] for part, name in zip(parts(steps[i]), called[i])],
                "as": "Parallel" if number == 1 else f"Parallel_{number}"}

    def nest(part: list[int]) -> list:
        if len(part) == 1:
            return [item(part[0])]
        cuts = [k for k in range(1, len(part)) if all(before[a][b] for a in part[:k] for b in part[k:])]
        if cuts:
            bounds = [0, *cuts, len(part)]
            return [node for lo, hi in zip(bounds, bounds[1:]) for node in nest(part[lo:hi])]
        groups = _connected(part, before)
        if 1 < len(groups) <= MAX_BRANCHES and not any(steps[i].along for i in part):
            number = next(blocks)
            return [{"parallel": [nest(g) for g in groups], "as": "Parallel" if number == 1 else f"Parallel_{number}"}]
        return [item(i) for i in part]

    return nest(list(range(len(steps))))


def composite(domain: Domain, steps: list[Planned], description: str, results: dict[str, str] | None = None,
              stop: list | None = None) -> Composite:
    """A module level skill that runs the plan: ``results`` (result -> ``<step>.<result>``), ``stop``
    (what a Stop runs, as the module's other skills: its Stopping procedure)."""
    return Composite(description=description, execute=flow(domain, steps), results=results or {}, stop=stop or [])


def _connected(part: list[int], before: list[list[bool]]) -> list[list[int]]:
    """The groups of ``part`` that the order connects, each in the plan's order."""
    groups: list[list[int]] = []
    for i in part:
        linked = [g for g in groups if any(before[i][j] or before[j][i] for j in g)]
        merged = sorted([i, *[j for g in linked for j in g]])
        groups = [g for g in groups if g not in linked] + [merged]
    return sorted(groups, key=lambda g: g[0])
