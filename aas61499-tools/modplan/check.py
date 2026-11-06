"""Check a module level skill against the module's planning domain: run its flow through the states
and report every condition that does not hold, with the steps that would make it hold.

A step's capability is the one its primitive realizes; its arguments are the step's constants and,
for a parameter of the skill it is handed, the value given (by default the parameter's default). A
precondition that cannot be told (a value not known) is not reported, nor is an argument beyond the
range of its parameter (6 Nov: a dose the pump cannot give). Both branches of a decision
are checked; after it, a variable keeps its value only if both branches leave it the same. A skill
ends at the module's rest state, or that is reported.

**In time** (6 Nov). A step keeps its invariants from its start to its end: they are checked at both,
and a linear one that holds at both holds in between, as everything it changes changes steadily. An
Invariant ``=`` a formula about a property nothing else sets defines it while the step runs (how deep
the needle is in the liquid); a requirement's invariants (``task``: BottomUpFilling's bounds on it)
are checked wherever what they are about is defined.

A parallel block whose steps all say how long they take (a rate, a Completion) is **run in time**:
each branch starts its next step when the one before has ended, every state a step changes moves at
its rate, and at every event (a step starting or ending) every running step's invariants and the
requirement's are checked, with what the others have done by then. Between two events every rate is
constant, so a linear invariant that holds at both holds all along: the check is exact without time
steps. A block with a step whose duration is not known, or with a decision in it, is checked as
before: the branches start from the same state, and a step whose invariant keeps a variable another
branch changes is reported unless it holds at every state that branch passes through.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from modgen.spec import Composite, Decision, Parallel, Step

from .domain import DIGITS, Capability, Domain, Var, effect, holds, known, same
from .expression import Formula

EPS = 1e-9                         # s: events this close are at the same time


@dataclass(frozen=True)
class Finding:
    step: str                      # the step it is about ("end": the skill's end)
    what: str                      # what does not hold, in words
    fix: tuple[str, ...] = ()      # skills a step before it could run to make it hold

    def __str__(self) -> str:
        return f"{self.step}: {self.what}" + (f" (run {' or '.join(self.fix)} before it)" if self.fix else "")


def check(domain: Domain, skill: Composite, given: dict | None = None, start: dict | None = None,
          task: Capability | None = None, values: dict | None = None) -> list[Finding]:
    """The findings on ``skill``'s Execute flow, from ``start`` (the rest state), with the values
    ``given`` for its parameters (else their defaults); ``task``: a capability whose invariants the
    run has to keep, with the requirement's ``values`` (a BottomUpFilling's bounds)."""
    checker = _Checker(domain, _values(skill, given), task, values)
    state = checker.run(skill.execute, dict(domain.rest if start is None else start))
    for var, value in domain.rest.items():
        if var in state and not same(state[var], value):
            checker.report(Finding("end", f"ends with {var} = {_text(state[var])}, not at rest ({_text(value)})",
                                   _fixes(domain, var, value)))
    return checker.found


def simulate(domain: Domain, skill: Composite, given: dict | None = None, start: dict | None = None) -> dict:
    """The state after ``skill``'s Execute flow, run with the values ``given`` for its parameters (else
    their defaults) from ``start`` (the rest state)."""
    return timed(domain, skill, given, start)[0]


def timed(domain: Domain, skill: Composite, given: dict | None = None, start: dict | None = None) -> tuple[dict, float | None]:
    """The state after ``skill``'s Execute flow and how long it takes, in seconds (None if a step does
    not say)."""
    checker = _Checker(domain, _values(skill, given))
    state = checker.run(skill.execute, dict(domain.rest if start is None else start))
    return state, checker.time


def _values(skill: Composite, given: dict | None) -> dict:
    return {name: p.default for name, p in skill.parameters.items() if p.default is not None} | (given or {})


def _text(value) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return str(round(value, 3))
    return str(value)


def _fixes(domain: Domain, var, value) -> tuple[str, ...]:
    """The skills whose capability makes ``var`` hold ``value``."""
    fixes = []
    for cap, c in domain.setting(var):
        e = c.expression
        if (e.op == "=" and same(cap.operand(e, {}), value)) or (e.op == "given" and cap.parameters.get(c.prop)
                                                               and cap.parameters[c.prop].admits(value)):
            fixes.append(f"{cap.skill}({c.prop}={_text(value)})" if e.op == "given" else cap.skill)
    return tuple(dict.fromkeys(fixes))


def _add(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a + b


class _Untimed(Exception):
    """A parallel block that cannot be run in time."""


@dataclass
class _Running:
    """A step of a parallel block run in time."""
    name: str
    cap: Capability
    args: dict
    end: float
    rates: dict[Var, float]                # per second
    final: dict[Var, object]               # what its Post leaves of what it does not change at a rate
    branch: "_Branch"


@dataclass
class _Branch:
    nodes: list
    parent: "_Branch | None" = None
    at: int = 0
    step: _Running | None = None
    children: list["_Branch"] = field(default_factory=list)

    @property
    def done(self) -> bool:
        return self.at >= len(self.nodes) and self.step is None and not self.children


class _Checker:
    def __init__(self, domain: Domain, values: dict, task: Capability | None = None, task_values: dict | None = None):
        self.domain, self.values, self.found = domain, values, []
        self.task, self.task_values = task, dict(task_values or {})
        self.time: float | None = 0.0
        self.defined = {c.var for cap in domain.capabilities.values() for c in cap.invariant
                        if c.expression.op == "=" and isinstance(c.expression.operand, Formula)} - domain.changed()

    def report(self, finding: Finding, into: list | None = None) -> None:
        found = self.found if into is None else into
        if all((f.step, f.what) != (finding.step, finding.what) for f in found):
            found.append(finding)

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

    # What holds at a moment --------------------------------------------------------------------

    def derived(self, running: list[tuple[Capability, dict]], state: dict) -> dict:
        """``state`` with what the running steps define (an Invariant ``=`` a formula about a property
        nothing else sets)."""
        seen = dict(state)
        for cap, args in running:
            for c in cap.invariant:
                if c.var in self.defined and c.expression.op == "=":
                    value = cap.operand(c.expression, args, state)
                    if value is not None:
                        seen[c.var] = round(value, DIGITS)
        return seen

    def ranges(self, name: str, cap: Capability, args: dict, into: list | None = None) -> None:
        """Report an argument beyond the range of its parameter (a dose the pump cannot give)."""
        for given, p in cap.parameters.items():
            if given in args and isinstance(args[given], (int, float)) and not isinstance(args[given], bool) and not p.admits(args[given]):
                self.report(Finding(name, f"{given} = {_text(args[given])} is beyond its range ({_text(p.minimum)} to {_text(p.maximum)})"), into)

    def pre(self, name: str, cap: Capability, args: dict, state: dict, into: list | None = None) -> set[Var]:
        """Report the preconditions that do not hold; the variables they are about."""
        broken = set()
        for c in cap.pre:
            if holds(cap, c, state, args) is False:
                wanted = cap.operand(c.expression, args, state)
                broken.add(c.var)
                self.report(Finding(name, f"needs {c.var} {c.expression.op} {_text(wanted)}, but it is {_text(state.get(c.var))}",
                                    _fixes(self.domain, c.var, wanted) if c.expression.op in ("=", "<=", ">=") else ()), into)
        return broken

    def keeps(self, running: list[tuple[str, Capability, dict]], state: dict, changers: dict[Var, str] | None = None,
              into: list | None = None, skip: dict[str, set[Var]] | None = None) -> None:
        """Report the invariants of the running steps, and the requirement's, that do not hold in
        ``state``; ``changers``: which step changes a variable (named in the finding)."""
        seen = self.derived([(cap, args) for _, cap, args in running], state)

        def changer(own: str, c, cap) -> str | None:
            names = [c.var, *(cap.variables.get(n) for n in c.expression.names)]
            return next((changers[v] for v in names if v is not None and v in (changers or {}) and changers[v] != own), None)
        for name, cap, args in running:
            for c in cap.invariant:
                if c.expression.op == "unchanged" or (c.var in self.defined and c.expression.op == "="):
                    continue
                if c.var in (skip or {}).get(name, ()):
                    continue
                if holds(cap, c, seen, args) is False:
                    wanted, by = cap.operand(c.expression, args, seen), changer(name, c, cap)
                    what = (f"keeps {c.var} {c.expression.op} {_text(wanted)} while {by} changes it" if by else
                            f"keeps {c.var} {c.expression.op} {_text(wanted)}, but it comes to {_text(seen.get(c.var))}")
                    self.report(Finding(name, what), into)
        if self.task is not None:
            for c in self.task.invariant:
                if not known(seen.get(c.var)) or holds(self.task, c, seen, self.task_values) is not False:
                    continue
                wanted = self.task.operand(c.expression, self.task_values, seen)
                during = next((name for name, cap, _ in running if any(d.var == c.var for d in cap.invariant)), "task")
                self.report(Finding(during, f"{self.task.name} keeps {c.var} {c.expression.op} {_text(wanted)}, "
                                            f"but it comes to {_text(seen[c.var])}"), into)

    # The flow ------------------------------------------------------------------------------------

    def run(self, nodes: list, state: dict) -> dict:
        for node in nodes:
            if isinstance(node, Step):
                state = self.step(node, state)
            elif isinstance(node, Parallel):
                state = self.parallel(node, state)
            elif isinstance(node, Decision):
                before = self.time
                then = self.run(node.then, dict(state))
                took, self.time = self.time, before
                otherwise = self.run(node.otherwise, dict(state))
                self.time = None if took is None or self.time is None else max(took, self.time)
                state = _merged(state, [then, otherwise])
        return state

    def step(self, step: Step, state: dict) -> dict:
        cap = self.domain.realizing(step.skill)
        if cap is None:
            return state                             # a primitive no capability is realized by
        args = self.args(cap, step)
        alone = [(step.name, cap, args)]
        self.ranges(step.name, cap, args)
        broken = self.pre(step.name, cap, args, state)
        self.keeps(alone, state, skip={step.name: broken})
        end = effect(cap, state, args)
        self.keeps(alone, end, skip={step.name: broken})
        self.time = _add(self.time, cap.duration(state, args))
        return end

    def parallel(self, block: Parallel, state: dict) -> dict:
        found: list[Finding] = []
        try:
            end, took = self.in_time(block, dict(state), found)
        except _Untimed:
            ends = [self.run(branch, dict(state)) for branch in block.branches]
            self.invariants(block, state)
            self.time = None
            return _merged(state, ends, parallel=True)
        for finding in found:
            self.report(finding)
        self.time = _add(self.time, took)
        return end

    def in_time(self, block: Parallel, state: dict, found: list) -> tuple[dict, float]:
        """Run the block's branches at once, event by event (see the module's text); _Untimed if a step
        does not say how long it takes, or a decision is in it."""
        now, running = 0.0, []

        def start(step: Step, branch: _Branch) -> bool:
            cap = self.domain.realizing(step.skill)
            if cap is None:
                return False
            args = self.args(cap, step)
            took = cap.duration(state, args)
            if took is None:
                raise _Untimed
            for c in cap.post:                                    # what is added to starts from nothing
                if c.expression.op == "+=" and c.var not in state:
                    state[c.var] = 0.0
            here = [(r.name, r.cap, r.args) for r in running] + [(step.name, cap, args)]
            seen = self.derived([(c, a) for _, c, a in here], state)
            self.ranges(step.name, cap, args, found)
            broken = self.pre(step.name, cap, args, seen, found)
            end = effect(cap, state, args)
            rates = {var: (end[var] - state[var]) / took for var in cap.rates
                     if took > 0 and isinstance(end.get(var), (int, float)) and isinstance(state.get(var), (int, float))}
            final = {var: value for var, value in end.items() if var not in rates and not (var in state and same(state[var], value))}
            final.update({var: end[var] for var in cap.rates if var not in rates and var in end       # done at once
                          and not (var in state and same(state[var], end[var]))})
            running.append(_Running(step.name, cap, args, now + took, rates, final, branch))
            branch.step = running[-1]
            self.keeps(here, state, self.changers(running), found, skip={step.name: broken})
            return True

        def advance(branch: _Branch) -> bool:
            """Start what the branch can start; True once it has run all of its nodes."""
            while branch.at < len(branch.nodes):
                node = branch.nodes[branch.at]
                if isinstance(node, Step):
                    if start(node, branch):
                        return False
                    branch.at += 1
                elif isinstance(node, Parallel):
                    branch.children = [_Branch(list(b), branch) for b in node.branches]
                    if all([advance(child) for child in branch.children]):
                        branch.children = []
                        branch.at += 1
                        continue
                    return False
                else:
                    raise _Untimed
            return True

        def ended(step: _Running) -> None:
            branch = step.branch
            branch.step, branch.at = None, branch.at + 1
            while advance(branch) and branch.parent is not None and all(c.done for c in branch.parent.children):
                branch = branch.parent
                branch.children, branch.at = [], branch.at + 1

        root = _Branch([block])
        advance(root)
        while running:
            then = min(r.end for r in running)
            for r in running:                                     # every rate runs until then
                for var, rate in r.rates.items():
                    state[var] = state[var] + rate * (then - now)
            if then - now > EPS:
                self.unchanged(running, found)
            now = then
            here = [(r.name, r.cap, r.args) for r in running]
            self.keeps(here, state, self.changers(running), found)
            ending = [r for r in running if r.end <= now + EPS]
            for r in ending:
                running.remove(r)
                for var in r.rates:
                    state[var] = round(state[var], DIGITS)
                state.update(r.final)
                for other in running:                             # a step that keeps it unchanged sees it change
                    for c in other.cap.invariant:
                        if c.expression.op == "unchanged" and c.var in r.final:
                            self.report(Finding(other.name, f"keeps {c.var} while {r.name} changes it: "
                                                            f"they cannot run at the same time"), found)
            if ending and running:
                self.keeps([(r.name, r.cap, r.args) for r in running], state,
                           {var: r.name for r in ending for var in r.final}, found)
            for r in ending:
                ended(r)
        return state, now

    @staticmethod
    def changers(running: list[_Running]) -> dict[Var, str]:
        return {var: r.name for r in running for var in r.rates}

    def unchanged(self, running: list[_Running], found: list) -> None:
        """A step that keeps a variable unchanged while another changes it at a rate."""
        for r in running:
            for c in r.cap.invariant:
                if c.expression.op != "unchanged":
                    continue
                for other in running:
                    if other is not r and other.rates.get(c.var, 0.0) != 0.0:
                        self.report(Finding(r.name, f"keeps {c.var} while {other.name} changes it: they cannot run at the same time"),
                                    found)

    def invariants(self, block: Parallel, state: dict) -> None:
        """Without time: a step keeps a variable (Invariant) that a step of another branch changes:
        unchanged, or a comparison that does not hold at each state the other branch passes through (a
        move goes straight from one value to the next, so its ends are enough)."""
        def caps(branch):
            for node in branch:
                if isinstance(node, Step) and (cap := self.domain.realizing(node.skill)) is not None:
                    yield node, cap

        def passes(branch):
            states = [dict(state)]
            for step, cap in caps(branch):
                states.append(effect(cap, states[-1], self.args(cap, step)))
            return states
        for i, branch in enumerate(block.branches):
            for step, cap in caps(branch):
                args = self.args(cap, step)
                for j, other in enumerate(block.branches):
                    for step2, cap2 in (caps(other) if j != i else ()):
                        for c in (c for c in cap.invariant if c.var in {c2.var for c2 in cap2.post}):
                            if c.expression.op == "unchanged":
                                self.report(Finding(step.name, f"keeps {c.var} while {step2.name} changes it: "
                                                               f"they cannot run at the same time"))
                            elif c.var not in self.defined and (broken := next(
                                    (s for s in passes(other) if holds(cap, c, s, args) is False), None)):
                                wanted = cap.operand(c.expression, args, broken)
                                self.report(Finding(step.name, f"keeps {c.var} {c.expression.op} {_text(wanted)} "
                                                               f"while {step2.name} changes it"))


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
