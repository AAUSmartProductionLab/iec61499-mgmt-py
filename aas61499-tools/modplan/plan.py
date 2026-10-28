"""Compose a new module level skill by planning (docs/skill-planning.md, section 6).

A hybrid of HTN and goal regression, on GTPyhop (Nau, 2021): the task is a capability the module
offers with the values a requirement asks for; its goals are what its Post says (the product's
state), what the results asked for need, and then the module's rest state. A goal is reached by an
action whose Post sets the variable (to a value, to what it is given, or by adding to it), after
the action's own preconditions, which become goals in turn. Where the module states compositions
of the capability (IDTA 02020 ComposedOf), the planner first tries with their parts only: the
integrator's way. The first plan found is taken; optimality is not a goal.

The result is a sequence of steps (capability, arguments); ``lift`` makes a flow of it.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass
import io
import itertools
import math

with contextlib.redirect_stdout(io.StringIO()):     # GTPyhop greets on import
    import gtpyhop

from .domain import DIGITS, Capability, Constraint, Domain, Var, effect, holds, known, same

TIMEOUT_MS = 10_000
_count = itertools.count()


@dataclass(frozen=True)
class Planned:
    capability: str
    args: dict

    def __str__(self) -> str:
        return f"{self.capability}({', '.join(f'{k}={v}' for k, v in self.args.items())})"


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
    needs it (what its preconditions say it is)."""
    cap = domain.capabilities[capability]
    state = dict(domain.rest if start is None else start)
    for c in cap.pre:
        if c.expression.op == "=" and c.var not in state:
            state[c.var] = cap.operand(c.expression, values)
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
    for only in [*(set(parts) for parts in cap.compositions), None]:
        found = _search(domain, state, [wanted, list(domain.rest.items())], only, timeout_ms)
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


# GTPyhop --------------------------------------------------------------------------------------

def _search(domain: Domain, state: dict, goal_lists: list[list[tuple[Var, object]]],
            only: set[str] | None, timeout_ms: int) -> list[Planned] | None:
    actions = [cap for cap in domain.actions() if only is None or cap.name in only]
    meanings = sorted({c.var.meaning for cap in domain.actions() for c in (*cap.pre, *cap.post, *cap.invariant)}
                      | {var.meaning for goals_ in goal_lists for var, _ in goals_} | {var.meaning for var in state})
    planning = gtpyhop.Domain(f"{domain.module}_{next(_count)}")
    gtpyhop.declare_actions(*[_action(cap, meanings) for cap in actions])
    for meaning in meanings:
        methods = [_method(cap, c, meanings) for cap, c in _setters(domain, actions, meaning)]
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
    return [Planned(step[0], {k: v for k, v in zip(sorted(by_name[step[0]].parameters), step[1:]) if v is not None})
            for step in result.plan]


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


def _action(cap: Capability, meanings: list[str]):
    """The action of a component's capability: it runs if its preconditions hold, and leaves the
    state its Post says."""
    names = sorted(cap.parameters)

    def act(planning, *given):
        args = {**cap.defaults(), **{n: v for n, v in zip(names, given) if v is not None}}
        state = _from_state(planning, meanings)
        if any(holds(cap, c, state, args) is not True for c in cap.pre):
            return False
        _write(planning, effect(cap, state, args), meanings)
        return planning

    act.__name__ = cap.name
    return act


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
        before = [(_name(c.var.meaning), c.var.subject, cap.operand(c.expression, args))
                  for c in cap.pre if c.expression.op == "=" and known(cap.operand(c.expression, args))]
        return [*before, (cap.name, *[args.get(n) for n in names]), *again]

    method.__name__ = f"m_{cap.name}_{constraint.prop}"
    return method
