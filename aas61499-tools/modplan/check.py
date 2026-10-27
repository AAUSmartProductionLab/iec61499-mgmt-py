"""Check a module level skill against the module's planning domain: run its flow through the states
and report every condition that does not hold, with the steps that would make it hold.

A step's capability is the one its primitive realizes; its arguments are the step's constants and,
for a parameter of the skill it is handed, the value given (by default the parameter's default). A
precondition that cannot be told (a value not known) is not reported. Both branches of a decision
are checked; after it, a variable keeps its value only if both branches leave it the same. The
branches of a parallel block start from the same state, and a step whose invariant keeps a variable
another branch changes is reported. A skill ends at the module's rest state, or that is reported.
"""
from __future__ import annotations

from dataclasses import dataclass

from modgen.spec import Composite, Decision, Parallel, Step

from .domain import Capability, Domain, effect, holds, same


@dataclass(frozen=True)
class Finding:
    step: str                      # the step it is about ("end": the skill's end)
    what: str                      # what does not hold, in words
    fix: tuple[str, ...] = ()      # skills a step before it could run to make it hold

    def __str__(self) -> str:
        return f"{self.step}: {self.what}" + (f" (run {' or '.join(self.fix)} before it)" if self.fix else "")


def check(domain: Domain, skill: Composite, given: dict | None = None, start: dict | None = None) -> list[Finding]:
    """The findings on ``skill``'s Execute flow, from ``start`` (the rest state), with the values
    ``given`` for its parameters (else their defaults)."""
    values = {name: p.default for name, p in skill.parameters.items() if p.default is not None} | (given or {})
    checker = _Checker(domain, values)
    state = checker.run(skill.execute, dict(domain.rest if start is None else start))
    for var, value in domain.rest.items():
        if var in state and not same(state[var], value):
            checker.found.append(Finding("end", f"ends with {var} = {_text(state[var])}, not at rest ({_text(value)})",
                                         _fixes(domain, var, value)))
    return checker.found


def _text(value) -> str:
    return str(value).lower() if isinstance(value, bool) else str(value)


def _fixes(domain: Domain, var, value) -> tuple[str, ...]:
    """The skills whose capability makes ``var`` hold ``value``."""
    fixes = []
    for cap, c in domain.setting(var):
        e = c.expression
        if (e.op == "=" and same(cap.operand(e, {}), value)) or (e.op == "given" and cap.parameters.get(c.prop)
                                                               and cap.parameters[c.prop].admits(value)):
            fixes.append(f"{cap.skill}({c.prop}={_text(value)})" if e.op == "given" else cap.skill)
    return tuple(dict.fromkeys(fixes))


class _Checker:
    def __init__(self, domain: Domain, values: dict):
        self.domain, self.values, self.found = domain, values, []

    def args(self, cap: Capability, step: Step) -> dict:
        args = cap.defaults()
        for name, bound in step.bind.items():
            if isinstance(bound, str):
                if bound in self.values:
                    args[name] = self.values[bound]
                else:
                    args.pop(name, None)            # handed a value nobody knows yet
            else:
                args[name] = bound
        return args

    def run(self, nodes: list, state: dict) -> dict:
        for node in nodes:
            if isinstance(node, Step):
                state = self.step(node, state)
            elif isinstance(node, Parallel):
                ends = [self.run(branch, dict(state)) for branch in node.branches]
                self.invariants(node)
                state = _merged(state, ends, parallel=True)
            elif isinstance(node, Decision):
                state = _merged(state, [self.run(node.then, dict(state)), self.run(node.otherwise, dict(state))])
        return state

    def step(self, step: Step, state: dict) -> dict:
        cap = self.domain.realizing(step.skill)
        if cap is None:
            return state                             # a primitive no capability is realized by
        args = self.args(cap, step)
        for c in cap.pre:
            if holds(cap, c, state, args) is False:
                wanted = cap.operand(c.expression, args)
                self.found.append(Finding(step.name, f"needs {c.var} {c.expression.op} {_text(wanted)}, "
                                                     f"but it is {_text(state.get(c.var))}",
                                          _fixes(self.domain, c.var, wanted) if c.expression.op == "=" else ()))
        return effect(cap, state, args)

    def invariants(self, block: Parallel) -> None:
        """A step keeps a variable (Invariant) that a step of another branch changes."""
        def caps(branch):
            for node in branch:
                if isinstance(node, Step) and (cap := self.domain.realizing(node.skill)) is not None:
                    yield node, cap
        for i, branch in enumerate(block.branches):
            for step, cap in caps(branch):
                kept = {c.var for c in cap.invariant}
                for j, other in enumerate(block.branches):
                    for step2, cap2 in (caps(other) if j != i else ()):
                        for var in kept & {c.var for c in cap2.post}:
                            self.found.append(Finding(step.name, f"keeps {var} while {step2.name} changes it: "
                                                                 f"they cannot run at the same time"))


def _merged(before: dict, ends: list[dict], parallel: bool = False) -> dict:
    """The state after branches: a variable keeps a value all branches agree on. In a parallel block
    the branches that left a variable alone do not count: what the others changed is the change."""
    merged = {}
    for var in set(before).union(*ends):
        values = [end.get(var) for end in ends]
        if parallel:
            untouched = (lambda v: v is None) if var not in before else (lambda v: v is not None and same(v, before[var]))
            values = [v for v in values if not untouched(v)] or values
        if all(v is not None for v in values) and all(same(v, values[0]) for v in values):
            merged[var] = values[0]
    return merged
