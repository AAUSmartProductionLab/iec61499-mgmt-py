"""Compose a new module level skill by planning (docs/skill-planning.md, section 6).

A hybrid of HTN and goal regression, on GTPyhop (Nau, 2021): the task is a capability the module
offers with the values a requirement asks for; its goals are what its Post says (the product's
state), what the results asked for need, and then the module's rest state. A goal is reached by an
action whose Post sets the variable (to a value, to what it is given, or by adding to it), after
the action's own preconditions, which become goals in turn. Where the module states compositions
of the capability (IDTA 02020 ComposedOf), the planner first tries with their parts only: the
integrator's way. The first plan found is taken; optimality is not a goal.

The result is a sequence of steps (capability, arguments); ``lift`` makes a flow of it.

**Invariants and time** (6 Nov). An action keeps its own invariants (the needle above the container's
bottom) and the requirement's (``task``: BottomUpFilling's bounds on how deep the needle is in the
liquid) from its start to its end; one that would break them is not applied. Where an action changes
a state at a rate and so would break a bound on a quantity a formula defines (the liquid rises, the
needle stays: it ends deep in it), a second method **tracks** it: it pairs the action with one that
changes another state in the same formula at a rate (the axis moves the needle), sets the rate it can
set (the pump's flow rate, as the axis's speed is fixed) so that the quantity stays as it is, and
first brings that other state to where every bound of both holds at the start and at the end (the
middle of what is left, or where it is if that will do). The pair runs as one step with the second in
parallel (``Planned.along``). It is generic: nothing in it is about filling.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass
import io
import itertools
import math

with contextlib.redirect_stdout(io.StringIO()):     # GTPyhop greets on import
    import gtpyhop

from .domain import DIGITS, PRODUCT, Capability, Constraint, Domain, Var, effect, holds, known, same
from .expression import Formula

TIMEOUT_MS = 10_000
_count = itertools.count()


ROUND = 3                        # decimals of a rate or target the tracking sets


@dataclass(frozen=True)
class Planned:
    capability: str
    args: dict
    along: tuple["Planned", ...] = ()          # steps that run at the same time, started with it

    def __str__(self) -> str:
        said = f"{self.capability}({', '.join(f'{k}={v}' for k, v in self.args.items())})"
        return said + "".join(f" with {other}" for other in self.along)


class NoPlan(Exception):
    pass


def goals(domain: Domain, capability: str, values: dict, results: tuple[str, ...] = ()) -> list[tuple[Var, object]]:
    """What carrying out ``capability`` with ``values`` has to reach: its Post, then what the results
    asked for need."""
    cap = domain.capabilities[capability]
    found = [(c.var, cap.operand(c.expression, values)) for c in cap.post if c.expression.op == "="]
    for result in results:
        if result not in cap.results:
            raise NoPlan(f"{capability} has no result {result}")
        found += [(c.var, cap.operand(c.expression, values)) for c in cap.results[result]]
    return found


def start_state(domain: Domain, capability: str, values: dict, start: dict | None = None) -> dict:
    """The state a planned skill starts from: the module at rest, the product as the capability
    needs it (what its preconditions say it is) and as the requirement states it (its container's
    geometry: a value of a property of the product a capability names)."""
    cap = domain.capabilities[capability]
    state = dict(domain.rest if start is None else start)
    for c in cap.pre:
        if c.expression.op == "=" and c.var not in state:
            state[c.var] = cap.operand(c.expression, values)
    for var in {v for c in domain.capabilities.values() for v in c.variables.values() if v.subject == PRODUCT}:
        if var not in state and isinstance(values.get(var.meaning), (int, float, bool)):
            state[var] = values[var.meaning]
    return state


def plan(domain: Domain, capability: str, values: dict, results: tuple[str, ...] = (),
         start: dict | None = None, timeout_ms: int = TIMEOUT_MS) -> list[Planned]:
    """The steps that carry out ``capability`` with ``values`` (its properties, as a requirement
    states them) and the ``results`` asked for, from ``start`` (the rest state) back to rest.
    NoPlan if the module cannot."""
    cap = domain.capabilities[capability]
    state = start_state(domain, capability, values, start)
    for c in cap.pre:
        if holds(cap, c, state, values) is False:
            raise NoPlan(f"{capability} needs {c.var} {c.expression}, and it is {state.get(c.var)}")
    wanted = goals(domain, capability, values, results)
    keeping = _Keeping(domain, cap, values)
    for only in [*(set(parts) for parts in cap.compositions), None]:
        found = _search(domain, state, [wanted, list(domain.rest.items())], only, timeout_ms, keeping)
        if found is not None:
            return found
    raise NoPlan(f"{domain.module} has no way to {capability} with {values}" + (f" and {', '.join(results)}" if results else ""))


def reach(domain: Domain, wanted: list[tuple[Var, object]], start: dict | None = None,
          timeout_ms: int = TIMEOUT_MS) -> list[Planned]:
    """The steps that reach ``wanted`` from ``start`` (nothing known): how the module gets to rest."""
    found = _search(domain, dict(start or {}), [wanted], None, timeout_ms)
    if found is None:
        raise NoPlan(f"{domain.module} cannot reach {', '.join(f'{v} = {x}' for v, x in wanted)}")
    return found


# Invariants -----------------------------------------------------------------------------------

class _Keeping:
    """What a plan keeps: each action's own invariants and those of the requirement (``task``)."""

    def __init__(self, domain: Domain, task: Capability | None = None, values: dict | None = None):
        self.domain, self.task, self.values = domain, task, dict(values or {})
        self.defined = {c.var for cap in domain.capabilities.values() for c in cap.invariant
                        if c.expression.op == "=" and isinstance(c.expression.operand, Formula)} - domain.changed()

    def seen(self, parts: list[tuple[Capability, dict]], state: dict) -> dict:
        """``state`` with what the running ``parts`` define."""
        found = dict(state)
        for cap, args in parts:
            for c in cap.invariant:
                if c.var in self.defined and c.expression.op == "=":
                    value = cap.operand(c.expression, args, state)
                    if value is not None:
                        found[c.var] = value
        return found

    def broken(self, parts: list[tuple[Capability, dict]], state: dict) -> bool:
        """Whether an invariant of the parts, or of the requirement, does not hold in ``state``."""
        seen = self.seen(parts, state)
        for cap, args in parts:
            for c in cap.invariant:
                if c.expression.op == "unchanged" or c.var in self.defined:
                    continue
                if holds(cap, c, seen, args) is False:
                    return True
        if self.task is not None:
            return any(known(seen.get(c.var)) and holds(self.task, c, seen, self.values) is False for c in self.task.invariant)
        return False

    def slack(self, cap: Capability, c: Constraint, args: dict, state: dict) -> float | None:
        """How far a comparison is from breaking (at least 0: it holds); None if it cannot be told."""
        value, wanted = state.get(c.var), cap.operand(c.expression, args, state)
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (value, wanted)):
            return None
        return {"<": wanted - value, "<=": wanted - value, ">": value - wanted, ">=": value - wanted}.get(c.expression.op)


def _bounds(keeping: _Keeping, checks, y: Var, state_at) -> tuple[float, float]:
    """The values of ``y`` (where it starts) for which every check holds: each is linear in it, so its
    slack at 0 and at 1 says where it breaks. ``checks``: (capability, constraint, args, parts, when)."""
    low, high = -math.inf, math.inf
    for cap, c, args, parts, when in checks:
        at = [keeping.seen(parts, state_at(v, when)) for v in (0.0, 1.0)]
        slacks = [keeping.slack(cap, c, args, s) for s in at]
        if any(s is None for s in slacks):
            continue
        a, b = slacks[1] - slacks[0], slacks[0]
        if abs(a) < 10 ** -DIGITS:
            if b < -10 ** -DIGITS:
                return math.inf, -math.inf                  # it breaks wherever y starts
            continue
        if a > 0:
            low = max(low, -b / a)
        else:
            high = min(high, -b / a)
    return low, high


def _trackers(domain: Domain, actions: list[Capability], keeping: _Keeping) -> list[tuple[Capability, Capability, Var, Var]]:
    """(S, A, x, y): S changes x at a rate, a quantity a formula of S defines depends on x and on y, and
    A sets y (to what it is given) at a rate: A can keep the quantity as it is while S runs."""
    if keeping.task is None or not keeping.task.invariant:
        return []
    found = []
    for s in actions:
        for d in (d for d in s.invariant if d.var in keeping.defined and isinstance(d.expression.operand, Formula)):
            if d.var not in {c.var for c in keeping.task.invariant}:
                continue
            named = {s.variables[n] for n in d.expression.names if n in s.variables}
            for x in (x for x in s.rates if x in named):
                for a in actions:
                    for c in a.post:
                        if a is not s and c.expression.op == "given" and c.var in a.rates and c.var in named and c.var != x:
                            found.append((s, a, x, c.var))
    return found


# GTPyhop --------------------------------------------------------------------------------------

def _search(domain: Domain, state: dict, goal_lists: list[list[tuple[Var, object]]],
            only: set[str] | None, timeout_ms: int, keeping: _Keeping | None = None) -> list[Planned] | None:
    keeping = keeping or _Keeping(domain)
    actions = [cap for cap in domain.actions() if only is None or cap.name in only]
    meanings = sorted({c.var.meaning for cap in domain.actions() for c in (*cap.pre, *cap.post, *cap.invariant)}
                      | {var.meaning for goals_ in goal_lists for var, _ in goals_} | {var.meaning for var in state}
                      | {var.meaning for cap in domain.actions() for var in cap.variables.values()})
    trackers = _trackers(domain, actions, keeping)
    planning = gtpyhop.Domain(f"{domain.module}_{next(_count)}")
    gtpyhop.declare_actions(*[_action(cap, meanings, keeping) for cap in actions],
                            *[_paired(s, a, meanings, keeping) for s, a, _, _ in trackers])
    for meaning in meanings:
        methods = [_method(cap, c, meanings) for cap, c in _setters(domain, actions, meaning)]
        methods += [_tracking(s, a, x, y, c, meanings, keeping) for s, a, x, y in trackers
                    for c in s.post if x.meaning == meaning and c.var == x and c.expression.op == "+="]
        if methods:
            gtpyhop.declare_unigoal_methods(_name(meaning), *methods)
    gtpyhop.declare_multigoal_methods(gtpyhop.m_split_multigoal)

    todo = []
    for i, goals_ in enumerate(goal_lists):
        multigoal = gtpyhop.Multigoal(f"goals{i}")
        for var, value in goals_:
            if known(value):
                vars(multigoal).setdefault(_name(var.meaning), {})[var.subject] = value
        todo.append(multigoal)
    # A session sets GTPyhop's verbosity and says so on standard output, then sets it back.
    with contextlib.redirect_stdout(io.StringIO()), \
            gtpyhop.PlannerSession(domain=planning, verbose=0, strategy="iterative_dfs_backtracking") as session:
        result = session.find_plan(_to_state(state, meanings), todo, timeout_ms=timeout_ms)
    if not result.success:
        return None
    by_name = {cap.name: cap for cap in actions}
    found = []
    for step in result.plan:
        if step[0] in by_name:
            found.append(Planned(step[0], {k: v for k, v in zip(sorted(by_name[step[0]].parameters), step[1:]) if v is not None}))
            continue
        first, second = step[0].split("+")                 # a pair (_paired): the second runs along
        names = sorted(by_name[first].parameters)
        found.append(Planned(first, {k: v for k, v in zip(names, step[1:]) if v is not None},
                             (Planned(second, {k: v for k, v in zip(sorted(by_name[second].parameters), step[1 + len(names):])
                                               if v is not None}),)))
    return found


def _setters(domain: Domain, actions: list[Capability], meaning: str):
    names = {cap.name for cap in actions}
    seen = set()
    for var in {c.var for cap in actions for c in cap.post if c.var.meaning == meaning}:
        for cap, c in domain.setting(var):
            if cap.name in names and (cap.name, c.prop, var) not in seen:
                seen.add((cap.name, c.prop, var))
                yield cap, c


def _name(meaning: str) -> str:
    return f"v_{meaning}"


def _to_state(state: dict, meanings: list[str]) -> gtpyhop.State:
    planning = gtpyhop.State("start", **{_name(m): {} for m in meanings})
    for var, value in state.items():
        getattr(planning, _name(var.meaning))[var.subject] = value
    return planning


def _from_state(planning: gtpyhop.State, meanings: list[str]) -> dict:
    return {Var(subject, meaning): value for meaning in meanings
            for subject, value in getattr(planning, _name(meaning), {}).items()}


def _write(planning: gtpyhop.State, state: dict, meanings: list[str]) -> None:
    for meaning in meanings:
        setattr(planning, _name(meaning), {})
    for var, value in state.items():
        getattr(planning, _name(var.meaning))[var.subject] = value


def _action(cap: Capability, meanings: list[str], keeping: _Keeping):
    """The action of a component's capability: it runs if its preconditions hold, and leaves the
    state its Post says; not if it breaks an invariant, its own or the requirement's, at its start or
    its end (a linear one that holds at both holds in between)."""
    names = sorted(cap.parameters)

    def act(planning, *given):
        args = {**cap.defaults(), **{n: v for n, v in zip(names, given) if v is not None}}
        state = _from_state(planning, meanings)
        if any(holds(cap, c, state, args) is not True for c in cap.pre):
            return False
        end = effect(cap, state, args)
        if keeping.broken([(cap, args)], state) or keeping.broken([(cap, args)], end):
            return False
        _write(planning, end, meanings)
        return planning

    act.__name__ = cap.name
    return act


def _paired(s: Capability, a: Capability, meanings: list[str], keeping: _Keeping):
    """``s`` and ``a`` started together and ending together (the tracking sets them so): both
    preconditions at the start, both Posts at the end, every invariant at both."""
    s_names, a_names = sorted(s.parameters), sorted(a.parameters)

    def act(planning, *given):
        s_args = {**s.defaults(), **{n: v for n, v in zip(s_names, given[:len(s_names)]) if v is not None}}
        a_args = {**a.defaults(), **{n: v for n, v in zip(a_names, given[len(s_names):]) if v is not None}}
        state = _from_state(planning, meanings)
        if any(holds(cap, c, state, args) is not True for cap, args in ((s, s_args), (a, a_args)) for c in cap.pre):
            return False
        if not all(p.admits(args[n]) for cap, args in ((s, s_args), (a, a_args)) for n, p in cap.parameters.items() if n in args):
            return False
        end = effect(a, effect(s, state, s_args), a_args)
        parts = [(s, s_args), (a, a_args)]
        if keeping.broken(parts, state) or keeping.broken(parts, end):
            return False
        _write(planning, end, meanings)
        return planning

    act.__name__ = f"{s.name}+{a.name}"
    return act


def _tracking(s: Capability, a: Capability, x: Var, y: Var, adding: Constraint, meanings: list[str], keeping: _Keeping):
    """A way to reach ``x = value`` by ``s`` (it adds to x at a rate) with ``a`` moving y alongside, so
    that what a formula of ``s`` defines from x and y stays as it is (see the module's text)."""
    s_names, a_names = sorted(s.parameters), sorted(a.parameters)
    amount = adding.expression.named
    target = next(c.prop for c in a.post if c.var == y and c.expression.op == "given")

    def method(planning, subject, value):
        if subject != x.subject:
            return False
        state = _from_state(planning, meanings)
        before = state.get(x, 0.0)
        parameter = s.parameters.get(amount)
        need = round(value - before, DIGITS) if known(before) and isinstance(value, (int, float)) else None
        if parameter is None or need is None or need <= 0 or not known(state.get(y)):
            return False
        doses = max(1, math.ceil(need / parameter.maximum - 10 ** -DIGITS)) if parameter.maximum else 1
        s_args = {**s.defaults(), amount: round(need / doses, DIGITS)}
        a_args = a.defaults()
        if not parameter.admits(s_args[amount]):
            return False                                   # the pump cannot dose so little
        # How the defined quantity moves with x and with y (the formula is linear in both).
        quantity = next(d for d in s.invariant if d.var in keeping.defined and d.var in {c.var for c in keeping.task.invariant})
        g = lambda st: s.operand(quantity.expression, s_args, st)                       # noqa: E731
        base = g(state)
        if base is None:
            return False
        gx, gy = g({**state, x: before + 1.0}) - base, g({**state, y: state[y] + 1.0}) - base
        if abs(gx) < 10 ** -DIGITS or abs(gy) < 10 ** -DIGITS:
            return False
        # The rates: x at s's, y at a's; one of them is set so that gx * rate_x + gy * rate_y = 0.
        x_rate, y_rate = s.rates[x], a.rates[y]
        fixed_x, fixed_y = x_rate not in s.parameters, y_rate not in a.parameters
        rx, ry = s.lookup(x_rate, s_args, state), a.lookup(y_rate, a_args, state)
        if fixed_y and not fixed_x and ry:
            rx = round(abs(ry * gy / gx), ROUND)
            if not s.parameters[x_rate].admits(rx):
                return False
            s_args[x_rate] = rx
        elif fixed_x and not fixed_y and rx:
            ry = round(abs(rx * gx / gy), ROUND)
            if not a.parameters[y_rate].admits(ry):
                return False
            a_args[y_rate] = ry
        elif not (rx and ry and math.isclose(abs(rx * gx), abs(ry * gy), rel_tol=1e-6)):
            return False
        took = s_args[amount] / rx
        way = -math.copysign(1.0, gx * gy) * abs(ry) * took                             # where y goes meanwhile
        # Where y has to start: every bound of s, of a and of the requirement, at the start and at the end.
        added = s_args[amount]

        def state_at(v: float, when: str) -> dict:
            return {**state, y: v} if when == "start" else {**state, y: v + way, x: before + added}

        def checks():
            for when in ("start", "end"):
                for cap, args in ((s, s_args), (a, {**a_args, target: 0.0})):
                    for c in (*(cap.pre if when == "start" else ()), *cap.invariant):
                        if c.expression.op in ("<", "<=", ">", ">=") and c.var not in keeping.defined:
                            yield cap, c, args, [(s, s_args)], when
                for c in keeping.task.invariant:
                    if c.expression.op in ("<", "<=", ">", ">="):
                        yield keeping.task, c, keeping.values, [(s, s_args)], when
        low, high = _bounds(keeping, list(checks()), y, state_at)
        p = a.parameters.get(target)
        if p is not None:                                       # a can be told to go where y starts and ends
            least = p.minimum if p.minimum is not None else -math.inf
            most = p.maximum if p.maximum is not None else math.inf
            low, high = max(low, least, least - way), min(high, most, most - way)
        if not low <= high:
            return False
        here = state[y]
        if low - 10 ** -DIGITS <= here <= high + 10 ** -DIGITS:
            begin = here                                        # where it is will do
        elif math.isinf(low) or math.isinf(high):
            begin = round(low if math.isinf(high) else high, ROUND)
        else:
            begin = round((low + high) / 2, ROUND)
        a_args[target] = round(begin + way, ROUND)
        again = [(_name(x.meaning), subject, value)] if doses > 1 else []
        return [(_name(y.meaning), y.subject, begin),
                (f"{s.name}+{a.name}", *[s_args.get(n) for n in s_names], *[a_args.get(n) for n in a_names]), *again]

    method.__name__ = f"m_{s.name}_{a.name}_{x.meaning}"
    return method


def _method(cap: Capability, constraint: Constraint, meanings: list[str]):
    """A way to reach ``(meaning, subject) = value``: ``cap``, whose Post sets the variable, after its
    own preconditions. Adding (``+=``) takes as few equal doses as its parameter's range allows."""
    names, e = sorted(cap.parameters), constraint.expression

    def method(planning, subject, value):
        if subject != constraint.var.subject:
            return False
        args = cap.defaults()
        again = []
        if e.op == "=":
            if not same(cap.operand(e, args), value):
                return False
        elif e.op == "given":
            parameter = cap.parameters.get(constraint.prop)
            if parameter is None or not parameter.admits(value):
                return False
            args[constraint.prop] = value
        elif e.op == "+=":
            parameter = cap.parameters.get(e.named)
            before = _from_state(planning, meanings).get(constraint.var, 0.0)
            need = round(value - before, DIGITS) if known(before) and isinstance(value, (int, float)) else None
            if parameter is None or need is None or need <= 0:
                return False
            doses = max(1, math.ceil(need / parameter.maximum - 10 ** -DIGITS)) if parameter.maximum else 1
            args[e.named] = round(need / doses, DIGITS)
            if not parameter.admits(args[e.named]):
                return False
            again = [(_name(constraint.var.meaning), subject, value)] if doses > 1 else []
        else:
            return False
        # A precondition "=" is a goal before it; a comparison that does not hold yet, its bound.
        now = _from_state(planning, meanings)
        before = [(_name(c.var.meaning), c.var.subject, cap.operand(c.expression, args))
                  for c in cap.pre if known(cap.operand(c.expression, args))
                  and (c.expression.op == "=" or (c.expression.op in ("<=", ">=") and holds(cap, c, now, args) is not True))]
        return [*before, (cap.name, *[args.get(n) for n in names]), *again]

    method.__name__ = f"m_{cap.name}_{constraint.prop}"
    return method
