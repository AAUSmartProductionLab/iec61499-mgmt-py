"""The planning domain for standard planners (G6; docs/skill-planning.md, section 6.5): PDDL 2.1 with
numbers and HDDL, from the same domain GTPyhop plans on.

    domain_text, problem_text = pddl(domain, "Filling", {"FillVolume": 2.0}, ("FillWeight",))
    domain_text, problem_text = hddl(domain, "Filling", {"FillVolume": 2.0}, ("FillWeight",))

PDDL (for ENHSP, say) has the module's actions and the goal; HDDL (for Aries or PANDA) has the same
actions and the tasks and methods GTPyhop uses, so a planner decomposes and inserts no actions.

**The domain** is the module's: an action per capability of a component, its preconditions what its
Pre says, its effects what its Post says. A property with truth values is a predicate, one with
numbers a function; a value measured is the predicate ``known_<property>``. An action takes the
parameters its constraints name (MoveAxis the Position it is given, Dispense the Volume it adds) as
objects of the type ``value``, each with its ``amount``, within the parameter's range.

**The problem** is the requirement's: the values a parameter may take as objects (where a property
has to be for another capability, the goals, the rest state, the doses that add up to a goal), the
state a planned skill starts from, and as the goal what the capability does, what the results asked
for need, and the module at rest again (sequential: the goal holds at the end).

**HDDL** has no numbers: a value is an object (``v_40p0``; ``unknown`` for a property not known) and a
numeric property a predicate of one value (``(linearaxis_actualposition_position v_40p0)``). An
action is given the value it replaces and deletes it; comparisons and sums are static facts of the
problem's values (``(ge_0p5 v_2p0)``, ``(sum v_0p0 v_2p0 v_2p0)``), so adding is expressed for the
values the problem holds. The tasks: a process capability, whose method reaches what its Post says;
``achieve_<property>`` (``achieve_not_<property>`` for false), whose methods are "it holds" and one
per action that sets it, the action's own preconditions reached first (goal regression, as in
``plan``); an amount is added in one dose or in several (the method calls itself). The problem's
task network: the capability, the needs of the results, the rest state.

Not expressed: invariants (``unchanged`` matters only when a plan is lifted; a comparison is a
precondition here), properties that are neither numbers nor truth values, and in HDDL the
compositions (a method for them would need actions restricted to their parts). A property not known
is false (a predicate) or undefined (a function) in PDDL, where GTPyhop does not apply an action.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import itertools
import math
import re

from .domain import DIGITS, Capability, Constraint, Domain, Measured, Var, known
from .plan import Planned, goals, start_state

COMPARE = {"=": "=", "<": "<", "<=": "<=", ">": ">", ">=": ">="}
MAX_DOSES = 10                      # how many equal doses of an added amount are offered as values


class NotExpressible(ValueError):
    """The domain says something the target language cannot."""


def ident(text: str) -> str:
    """A PDDL name: lower case, letters, digits and underscores."""
    return re.sub(r"[^a-z0-9_]", "_", str(text).lower())


def fluent(var: Var) -> str:
    return ident(f"{var.subject}_{var.meaning}")


def number(value) -> str:
    return repr(round(float(value), DIGITS))


def constraints(cap: Capability) -> list[Constraint]:
    return [*cap.pre, *cap.post, *cap.invariant, *(c for cs in cap.results.values() for c in cs)]


def kinds(domain: Domain) -> dict[Var, str]:
    """Each property's kind: ``bool``, ``number``, or ``measured`` (only whether it is known)."""
    found: dict[Var, str] = {}

    def note(var: Var, kind: str):
        if found.setdefault(var, kind) != kind:
            raise NotExpressible(f"{var} is both {found[var]} and {kind}")

    def kind_of(var: Var, value) -> str:
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, (int, float)):
            return "number"
        raise NotExpressible(f"{var} takes {value!r}: only numbers and truth values are expressed")

    for var, value in domain.rest.items():
        note(var, kind_of(var, value))
    for cap in domain.capabilities.values():
        for c in constraints(cap):
            e = c.expression
            if e.op == "measured":
                found.setdefault(c.var, "measured")
            elif e.op in ("+=", "<", "<=", ">", ">=", "given"):
                note(c.var, "number")
            elif e.op in ("=", "!="):
                value = cap.operand(e, {})
                if value is None and e.named in cap.parameters:
                    value = 0.0                        # a parameter's value: a number
                if value is not None:
                    note(c.var, kind_of(c.var, value))
    return found


def parameters(cap: Capability) -> list[str]:
    """The parameters an action takes: those its constraints name."""
    named = {c.prop for c in cap.post if c.expression.op == "given"}
    named |= {c.expression.named for c in constraints(cap) if c.expression.named in cap.parameters}
    return sorted(named)


@dataclass
class _Writer:
    domain: Domain
    kinds: dict[Var, str] = field(default_factory=dict)

    def __post_init__(self):
        # Only what the actions read or write: a property only a process capability names (that the
        # vial holds something, for Stoppering) would start undefined, which planners refuse.
        used = {c.var for cap in self.domain.actions() for c in constraints(cap)}
        self.kinds = {var: kind for var, kind in kinds(self.domain).items() if var in used}

    def operand(self, cap: Capability, c: Constraint, params: list[str]) -> str:
        e = c.expression
        if e.op == "given":
            return f"(amount ?{ident(c.prop)})"
        if e.named in params:
            return f"(amount ?{ident(e.named)})"
        value = cap.operand(e, {})
        if value is None:
            raise NotExpressible(f"{cap.name}: {c} names a value that is not known")
        return number(value)

    def truth(self, cap: Capability, c: Constraint) -> bool:
        value = cap.operand(c.expression, {})
        if not isinstance(value, bool):
            raise NotExpressible(f"{cap.name}: {c} is not a truth value")
        return value

    def condition(self, cap: Capability, c: Constraint, params: list[str]) -> str | None:
        e, f, kind = c.expression, fluent(c.var), self.kinds.get(c.var)
        if e.op in ("unchanged", "given", "measured"):
            return None
        if kind == "measured":
            raise NotExpressible(f"{cap.name}: {c} compares a value only known once measured")
        if kind == "bool":
            if e.op not in ("=", "!="):
                raise NotExpressible(f"{cap.name}: {c} orders truth values")
            positive = self.truth(cap, c) == (e.op == "=")
            return f"({f})" if positive else f"(not ({f}))"
        compared = f"(= ({f}) {self.operand(cap, c, params)})"
        return f"(not {compared})" if e.op == "!=" else f"({COMPARE[e.op]} ({f}) {self.operand(cap, c, params)})"

    def effect(self, cap: Capability, c: Constraint, params: list[str]) -> str:
        e, f, kind = c.expression, fluent(c.var), self.kinds.get(c.var)
        if e.op == "measured":
            return f"(known_{f})"
        if kind == "bool":
            return f"({f})" if self.truth(cap, c) else f"(not ({f}))"
        if e.op == "+=":
            return f"(increase ({f}) {self.operand(cap, c, params)})"
        return f"(assign ({f}) {self.operand(cap, c, params)})"

    def action(self, cap: Capability) -> str:
        params = parameters(cap)
        conditions = [self.condition(cap, c, params) for c in (*cap.pre, *cap.invariant)]
        for name in params:
            p = cap.parameters.get(name)
            if p is not None and p.minimum is not None:
                conditions.append(f"(>= (amount ?{ident(name)}) {number(p.minimum)})")
            if p is not None and p.maximum is not None:
                conditions.append(f"(<= (amount ?{ident(name)}) {number(p.maximum)})")
        effects = [self.effect(cap, c, params) for c in cap.post]
        return "\n".join([
            f"  (:action {ident(cap.name)}",
            f"    :parameters ({' '.join(f'?{ident(p)} - value' for p in params)})",
            f"    :precondition (and {' '.join(c for c in conditions if c)})",
            f"    :effect (and {' '.join(effects)}))"])

    def domain_text(self) -> str:
        predicates = sorted({f"({fluent(v)})" for v, k in self.kinds.items() if k == "bool"}
                            | {f"(known_{fluent(v)})" for v, k in self.kinds.items() if k == "measured"})
        functions = sorted(f"({fluent(v)})" for v, k in self.kinds.items() if k == "number")
        return "\n".join([
            f"; The planning domain of the {self.domain.module} module, from its AAS (modplan.export).",
            f"(define (domain {ident(self.domain.module)})",
            "  (:requirements :typing :negative-preconditions :numeric-fluents)",
            "  (:types value)",
            f"  (:predicates {' '.join(predicates)})",
            f"  (:functions {' '.join(functions)} (amount ?v - value))",
            *[self.action(cap) for cap in self.domain.actions()],
            ")", ""])

    def literal(self, var: Var, value) -> str | None:
        f, kind = fluent(var), self.kinds.get(var)
        if isinstance(value, Measured):
            return f"(known_{f})"
        if not known(value) or kind is None:
            return None
        if kind == "bool":
            return f"({f})" if value else f"(not ({f}))"
        return f"(= ({f}) {number(value)})"

    def amounts(self, state: dict, wanted: list[tuple[Var, object]], extra=()) -> list[float]:
        """The values the actions' parameters may take for this problem."""
        found = set(round(float(v), DIGITS) for v in extra)
        targets: dict[Var, set[float]] = {}
        for var, value in [*wanted, *self.domain.rest.items()]:
            if self.kinds.get(var) == "number" and known(value):
                targets.setdefault(var, set()).add(round(float(value), DIGITS))
        for cap in self.domain.actions():
            for c in cap.pre:
                value = cap.operand(c.expression, {})
                if c.expression.op == "=" and self.kinds.get(c.var) == "number" and isinstance(value, (int, float)):
                    targets.setdefault(c.var, set()).add(round(float(value), DIGITS))
        for cap in self.domain.actions():
            for c in cap.post:
                e, wanted_values = c.expression, targets.get(c.var, set())
                if e.op == "given":
                    found |= wanted_values
                elif e.op == "+=" and e.named in cap.parameters:
                    p, before = cap.parameters[e.named], state.get(c.var, 0.0)
                    for target in wanted_values:
                        need = target - (before if known(before) else 0.0)
                        for doses in range(1, MAX_DOSES + 1):
                            if need > 0 and p.admits(need / doses):
                                found.add(round(need / doses, DIGITS))
            for name in parameters(cap):
                default = cap.parameters[name].default if name in cap.parameters else None
                if isinstance(default, (int, float)) and not isinstance(default, bool):
                    found.add(round(float(default), DIGITS))
        return sorted(found)

    def problem_text(self, name: str, state: dict, wanted: list[tuple[Var, object]], amounts: list[float]) -> str:
        objects = {value: f"v{i}" for i, value in enumerate(amounts)}
        init = [f"(= (amount {o}) {number(v)})" for v, o in objects.items()]
        init += [lit for var, value in state.items() if (lit := self.literal(var, value)) and not lit.startswith("(not")]
        if unset := [str(var) for var, value in wanted if known(value) and var not in self.kinds]:
            raise NotExpressible(f"no action of {self.domain.module} sets {', '.join(unset)}")
        goal = [lit for var, value in wanted if (lit := self.literal(var, value))]
        return "\n".join([
            f"(define (problem {ident(name)}) (:domain {ident(self.domain.module)})",
            f"  (:objects {' '.join(objects.values())}{' - value' if objects else ''})",
            f"  (:init {' '.join(init)})",
            f"  (:goal (and {' '.join(dict.fromkeys(goal))})))", ""])


def pddl(domain: Domain, capability: str, values: dict, results: tuple[str, ...] = (), start: dict | None = None,
         steps: list[Planned] = ()) -> tuple[str, str]:
    """The domain and the problem of carrying out ``capability`` with ``values`` (and ``results``),
    from ``start`` (the rest state) back to rest; the arguments of ``steps`` (a plan to validate)
    are among the problem's values."""
    writer = _Writer(domain)
    state = start_state(domain, capability, values, start)
    wanted = [*goals(domain, capability, values, results), *domain.rest.items()]
    extra = [v for step in steps for v in step.args.values() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    amounts = writer.amounts(state, wanted, extra)
    return writer.domain_text(), writer.problem_text(f"{capability}_{len(amounts)}", state, wanted, amounts)


def amounts_of(problem: str) -> dict[str, float]:
    """The amount of each value object of a PDDL problem."""
    return {o: float(v) for o, v in re.findall(r"\(= \(amount (v\d+)\) ([-0-9.e]+)\)", problem)}


def plan_text(domain: Domain, steps: list[Planned], problem: str) -> list[str]:
    """``steps`` as the problem's actions: ``(dosing v3)``."""
    objects = {round(v, DIGITS): o for o, v in amounts_of(problem).items()}
    found = []
    for step in steps:
        cap = domain.capabilities[step.capability]
        args = {**cap.defaults(), **step.args}
        found.append(f"({' '.join([ident(cap.name), *(objects[round(float(args[p]), DIGITS)] for p in parameters(cap))])})")
    return found


def pddl_steps(domain: Domain, actions: list[tuple[str, list[str]]], problem: str) -> list[Planned]:
    """A plan of a PDDL planner (action names and their objects) as steps: the amounts it was given."""
    by_name, amounts = {ident(cap.name): cap for cap in domain.actions()}, amounts_of(problem)
    return [Planned(by_name[name].name, {p: amounts[o] for p, o in zip(parameters(by_name[name]), objects)})
            for name, objects in actions]


# HDDL -----------------------------------------------------------------------------------------

UNKNOWN = "unknown"
TESTS = {"<": "lt", "<=": "le", ">": "gt", ">=": "ge"}


def obj(value) -> str:
    """The object of a value: ``v_40p0``, ``v_m1p5``; ``unknown`` for none."""
    if not known(value):
        return UNKNOWN
    return "v_" + repr(round(float(value), DIGITS)).replace("-", "m").replace(".", "p")


def value_of(name: str) -> float | None:
    return None if name == UNKNOWN else float(name[2:].replace("m", "-").replace("p", "."))


def compares(op: str, a: float, b: float) -> bool:
    return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]


@dataclass
class _Hddl:
    domain: Domain
    kinds: dict[Var, str] = field(default_factory=dict)
    constants: set = field(default_factory=set)                 # values the domain names
    tests: set = field(default_factory=set)                     # (op, value) a static predicate says

    def __post_init__(self):
        self.kinds = kinds(self.domain)

    def const(self, value) -> str:
        self.constants.add(round(float(value), DIGITS))
        return obj(value)

    def test(self, op: str, value) -> str:
        self.tests.add((op, round(float(value), DIGITS)))
        return f"{TESTS[op]}_{obj(value)[2:]}"

    def task(self, var: Var, value=None) -> str:
        """The task that reaches ``var`` = ``value`` (a truth value, or an object or a variable)."""
        f = fluent(var)
        if self.kinds.get(var) == "bool":
            return f"(achieve_{f})" if value else f"(achieve_not_{f})"
        return f"(achieve_{f} {value})"

    # Actions ------------------------------------------------------------------------------------

    def head(self, cap: Capability) -> list[str]:
        """The parameters of the action of ``cap``: its values, the values it replaces, the sums it
        makes, the values it compares."""
        found = [f"?{ident(p)}" for p in parameters(cap)]
        for c in cap.post:
            if self.kinds.get(c.var) == "number":
                found.append(f"?old_{fluent(c.var)}")
                if c.expression.op == "+=":
                    found.append(f"?new_{fluent(c.var)}")
        assigned = {c.var for c in cap.post}
        for c in (*cap.pre, *cap.invariant):
            if (self.kinds.get(c.var) == "number" and c.expression.op in ("!=", *TESTS)
                    and c.var not in assigned and f"?cur_{fluent(c.var)}" not in found):
                found.append(f"?cur_{fluent(c.var)}")
        return found

    def term(self, cap: Capability, c: Constraint) -> str:
        """What a constraint compares with or sets: a parameter of the action, or a constant."""
        e, params = c.expression, parameters(cap)
        if e.op == "given":
            return f"?{ident(c.prop)}"
        if e.named in params:
            return f"?{ident(e.named)}"
        value = cap.operand(e, {})
        if value is None:
            raise NotExpressible(f"{cap.name}: {c} names a value that is not known")
        return self.const(value)

    def action(self, cap: Capability) -> str:
        head, pre, eff = self.head(cap), [], []
        current = {}                                             # var -> the parameter holding its value
        for c in cap.post:
            f, e, kind = fluent(c.var), c.expression, self.kinds.get(c.var)
            if e.op == "measured":
                eff.append(f"(known_{f})")
            elif kind == "bool":
                eff.append(f"({f})" if cap.operand(e, {}) else f"(not ({f}))")
            else:
                old = f"?old_{f}"
                current[c.var] = old
                new = f"?new_{f}" if e.op == "+=" else self.term(cap, c)
                pre.append(f"({f} {old})")
                if e.op == "+=":
                    pre.append(f"(sum {old} {self.term(cap, c)} {new})")
                eff += [f"(not ({f} {old}))", f"({f} {new})"]
        for c in (*cap.pre, *cap.invariant):
            f, e, kind = fluent(c.var), c.expression, self.kinds.get(c.var)
            if e.op in ("unchanged", "given", "measured"):
                continue
            if kind == "bool":
                value = cap.operand(e, {})
                if not isinstance(value, bool) or e.op not in ("=", "!="):
                    raise NotExpressible(f"{cap.name}: {c}")
                pre.append(f"({f})" if value == (e.op == "=") else f"(not ({f}))")
            elif e.op == "=":
                pre.append(f"({f} {self.term(cap, c)})")
            else:
                held = current.get(c.var, f"?cur_{f}")
                if c.var not in current:
                    pre.append(f"({f} {held})")
                if e.op == "!=":
                    pre.append(f"(not (= {held} {self.term(cap, c)}))")
                elif e.named is not None:
                    raise NotExpressible(f"{cap.name}: {c} compares with a parameter")
                else:
                    pre.append(f"({self.test(e.op, cap.operand(e, {}))} {held})")
        for name in parameters(cap):
            p = cap.parameters.get(name)
            if p is not None and p.minimum is not None:
                pre.append(f"({self.test('>=', p.minimum)} ?{ident(name)})")
            if p is not None and p.maximum is not None:
                pre.append(f"({self.test('<=', p.maximum)} ?{ident(name)})")
        return "\n".join([
            f"  (:action {ident(cap.name)}",
            f"    :parameters ({' '.join(head)}{' - value' if head else ''})",
            f"    :precondition (and {' '.join(pre)})",
            f"    :effect (and {' '.join(eff)}))"])

    # Methods ------------------------------------------------------------------------------------

    def regress(self, cap: Capability, binding: dict[str, str]) -> list[str]:
        """The tasks that reach the action's own preconditions (``=``), then the action."""
        found = []
        for c in cap.pre:
            if c.expression.op != "=":
                continue
            if self.kinds.get(c.var) == "bool":
                found.append(self.task(c.var, cap.operand(c.expression, {})))
            elif self.kinds.get(c.var) == "number":
                term = self.term(cap, c)
                found.append(self.task(c.var, binding.get(term, term)))
        args = [binding.get(p, p) for p in self.head(cap)]
        return [*found, f"({' '.join([ident(cap.name), *args])})"]

    def method(self, name: str, task: str, params: list[str], precondition: list[str], subtasks: list[str]) -> str:
        variables = sorted({*params, *(v for s in subtasks for v in re.findall(r"\?[a-z0-9_]+", s))},
                           key=lambda v: (v not in params, v))
        ordered = " ".join(f"(t{i} {s})" for i, s in enumerate(subtasks))
        return "\n".join([
            f"  (:method {name}",
            f"    :parameters ({' '.join(variables)}{' - value' if variables else ''})",
            f"    :task {task}",
            f"    :precondition (and {' '.join(precondition)})",
            f"    :ordered-subtasks (and {ordered}))"])

    def methods(self, var: Var) -> list[str]:
        f, kind, found = fluent(var), self.kinds.get(var), []
        setters = self.domain.setting(var)
        if kind == "bool":
            for value in (True, False):
                task = self.task(var, value)
                holds, other = (f"({f})", f"(not ({f}))") if value else (f"(not ({f}))", f"({f})")
                found.append(self.method(f"m_{task[1:-1]}_holds", task, [], [holds], []))
                for cap, c in setters:
                    if cap.operand(c.expression, {}) is value:
                        found.append(self.method(f"m_{task[1:-1]}_{ident(cap.name)}", task, [], [other],
                                                 self.regress(cap, {})))
            return found
        if kind != "number":
            return found
        task = f"(achieve_{f} ?v)"
        found.append(self.method(f"m_{f}_holds", task, ["?v"], [f"({f} ?v)"], []))
        for cap, c in setters:
            e, name, unlike = c.expression, f"m_{f}_{ident(cap.name)}", f"(not ({f} ?v))"
            if e.op == "=":
                term = self.term(cap, c)
                if term.startswith("?"):                         # the value the action is given
                    found.append(self.method(name, task, ["?v"], [unlike], self.regress(cap, {term: "?v"})))
                else:
                    found.append(self.method(name, task, ["?v"], [unlike, f"(= ?v {term})"], self.regress(cap, {})))
            elif e.op == "given":
                found.append(self.method(name, task, ["?v"], [unlike], self.regress(cap, {f"?{ident(c.prop)}": "?v"})))
            elif e.op == "+=":
                found.append(self.method(name, task, ["?v"], [unlike], self.regress(cap, {f"?new_{f}": "?v"})))
                found.append(self.method(f"{name}_more", task, ["?v"], [unlike],
                                         [*self.regress(cap, {f"?new_{f}": "?mid"}), f"(achieve_{f} ?v)"]))
        return found

    def capability(self, cap: Capability) -> tuple[str, str]:
        """The task of a process capability and its method: reach what its Post says."""
        params = sorted({c.expression.named for c in cap.post if c.expression.named in cap.parameters})
        head = [f"?{ident(p)}" for p in params]
        subtasks = []
        for c in cap.post:
            if c.expression.op != "=":
                raise NotExpressible(f"{cap.name}: {c} (a process capability's Post is what it reaches)")
            if self.kinds.get(c.var) == "bool":
                subtasks.append(self.task(c.var, cap.operand(c.expression, {})))
            else:
                named = c.expression.named
                subtasks.append(self.task(c.var, f"?{ident(named)}" if named in params else self.term(cap, c)))
        task = f"({ident(cap.name)}{''.join(' ' + h for h in head)})"
        declared = f"  (:task {ident(cap.name)} :parameters ({' '.join(head)}{' - value' if head else ''}))"
        return declared, self.method(f"m_{ident(cap.name)}", task, head, [], subtasks)

    def domain_text(self, capability: str) -> str:
        actions = [self.action(cap) for cap in self.domain.actions()]
        variables = sorted(self.kinds, key=fluent)
        methods = [m for var in variables for m in self.methods(var)]
        processes = []
        for cap in self.domain.tasks():
            try:
                processes.append(self.capability(cap))
            except NotExpressible:
                if cap.name == capability:
                    raise                            # another the module offers is left out instead
        tasks = []
        for var in variables:
            f = fluent(var)
            if self.kinds[var] == "bool":
                tasks += [f"  (:task achieve_{f} :parameters ())", f"  (:task achieve_not_{f} :parameters ())"]
            elif self.kinds[var] == "number":
                tasks.append(f"  (:task achieve_{f} :parameters (?v - value))")
        predicates = sorted({f"({fluent(v)})" for v, k in self.kinds.items() if k == "bool"}
                            | {f"({fluent(v)} ?v - value)" for v, k in self.kinds.items() if k == "number"}
                            | {f"(known_{fluent(v)})" for v, k in self.kinds.items() if k == "measured"}
                            | {f"({TESTS[op]}_{obj(value)[2:]} ?v - value)" for op, value in self.tests}
                            | {"(sum ?a ?b ?c - value)"})
        constants = sorted({obj(v) for v in self.constants} | {UNKNOWN})
        return "\n".join([
            f"; The planning domain of the {self.domain.module} module, from its AAS (modplan.export), as HDDL.",
            f"(define (domain {ident(self.domain.module)})",
            "  (:requirements :typing :hierarchy :negative-preconditions :equality)",
            "  (:types value)",
            f"  (:constants {' '.join(constants)} - value)",
            f"  (:predicates {' '.join(predicates)})",
            *tasks, *(declared for declared, _ in processes),
            *(method for _, method in processes), *methods, *actions,
            ")", ""])

    # The problem --------------------------------------------------------------------------------

    def values(self, state: dict, wanted: list[tuple[Var, object]], amounts: list[float]) -> list[float]:
        """The problem's values: the amounts, what the state and the goals hold, and the steps of
        adding a goal's amount in as few equal doses as the range allows (as ``plan`` does)."""
        found = {*amounts, *self.constants}
        found |= {round(float(v), DIGITS) for _, v in [*state.items(), *wanted]
                  if known(v) and isinstance(v, (int, float)) and not isinstance(v, bool)}
        for cap in self.domain.actions():
            for c in cap.post:
                if c.expression.op != "+=" or c.expression.named not in cap.parameters:
                    continue
                p, before = cap.parameters[c.expression.named], state.get(c.var, 0.0)
                start = float(before) if known(before) else 0.0
                for target in [v for var, v in wanted if var == c.var and known(v)]:
                    need = target - start
                    doses = max(1, math.ceil(need / p.maximum - 10 ** -DIGITS)) if p.maximum and need > 0 else 1
                    if need > 0 and p.admits(need / doses):
                        found |= {round(start + k * need / doses, DIGITS) for k in range(doses + 1)}
                        found.add(round(need / doses, DIGITS))
        return sorted(found)

    def problem_text(self, name: str, cap: Capability, values: dict, state: dict, needs: list[tuple[Var, object]],
                     amounts: list[float]) -> str:
        every = self.values(state, [*needs, *self.domain.rest.items(), *[
            (c.var, cap.operand(c.expression, values)) for c in cap.post]], amounts)
        objects = [obj(v) for v in every if round(v, DIGITS) not in self.constants]
        init = [f"({TESTS[op]}_{obj(k)[2:]} {obj(v)})" for op, k in sorted(self.tests) for v in every if compares(op, v, k)]
        init += [f"(sum {obj(a)} {obj(b)} {obj(c)})" for a, b in itertools.product(every, every) if b > 0
                 for c in [round(a + b, DIGITS)] if c in every]
        for var, kind in sorted(self.kinds.items(), key=lambda pair: fluent(pair[0])):
            value, f = state.get(var), fluent(var)
            if kind == "bool" and value is True:
                init.append(f"({f})")
            elif kind == "number":
                init.append(f"({f} {obj(value)})")
            elif kind == "measured" and isinstance(value, Measured):
                init.append(f"(known_{f})")
        params = sorted({c.expression.named for c in cap.post if c.expression.named in cap.parameters})
        network = [f"({' '.join([ident(cap.name), *(obj(values[p]) for p in params)])})"]
        for var, value in [*needs, *self.domain.rest.items()]:
            if known(value) and var in self.kinds:
                network.append(self.task(var, value if self.kinds[var] == "bool" else obj(value)))
        ordered = " ".join(f"(t{i} {s})" for i, s in enumerate(network))
        return "\n".join([
            f"(define (problem {ident(name)}) (:domain {ident(self.domain.module)})",
            f"  (:objects {' '.join(objects)}{' - value' if objects else ''})",
            f"  (:htn :parameters () :ordered-subtasks (and {ordered}))",
            f"  (:init {' '.join(init)}))", ""])


def hddl(domain: Domain, capability: str, values: dict, results: tuple[str, ...] = (),
         start: dict | None = None) -> tuple[str, str]:
    """The HDDL domain and problem of carrying out ``capability`` with ``values`` (and ``results``),
    from ``start`` (the rest state) back to rest."""
    writer, cap = _Hddl(domain), domain.capabilities[capability]
    text = writer.domain_text(capability)            # first: it collects the constants and the tests
    state = start_state(domain, capability, values, start)
    needs = [(c.var, cap.operand(c.expression, values)) for result in results for c in cap.results.get(result, [])]
    amounts = _Writer(domain).amounts(state, [*goals(domain, capability, values, results), *domain.rest.items()])
    return text, writer.problem_text(capability, cap, values, state, needs, amounts)


def hddl_steps(domain: Domain, actions: list[tuple[str, list[str]]]) -> list[Planned]:
    """A plan of an HDDL planner (action names and their objects) as steps: the values it was given."""
    by_name = {ident(cap.name): cap for cap in domain.actions()}
    return [Planned(by_name[name].name, {p: value_of(o) for p, o in zip(parameters(by_name[name]), objects)})
            for name, objects in actions]
