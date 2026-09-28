"""Skill contracts and the forward check of a compiled procedure (plan section "Contracts").

Conditions and effects reference state variables by name; there are no text formulas to parse.
The check starts from the procedure's ``Assumes``, walks the calls in order (repeating looped
calls), checks each skill's Requires and Invariant and applies its Ensures.
"""
from __future__ import annotations

import operator
from typing import Literal

from pydantic import Field

from iec61499_mgmt.models import Model

Scalar = bool | int | float | str
_OPS = {"=": operator.eq, "!=": operator.ne, "<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge}


class Condition(Model):
    """``variable operator value`` on one state variable."""
    variable: str
    operator: Literal["=", "!=", "<", "<=", ">", ">="] = "="
    value: Scalar

    def holds(self, state: dict[str, Scalar]) -> bool | None:
        """True or False on ``state``; None if the variable is unknown there."""
        if self.variable not in state:
            return None
        try:
            return _OPS[self.operator](state[self.variable], self.value)
        except TypeError:
            return False

    def text(self) -> str:
        """Readable form for violation reports."""
        return f"{self.variable} {self.operator} {self.value!r}"


class Effect(Model):
    """Assign (:=) or add (+=) a constant or a skill parameter to a state variable."""
    variable: str
    assign: Literal[":=", "+="] = ":="
    value: Scalar | None = None
    from_parameter: str | None = None


class Contract(Model):
    """Requires, Ensures and Invariant of one skill."""
    requires: list[Condition] = Field(default_factory=list)
    ensures: list[Effect] = Field(default_factory=list)
    invariant: list[Condition] = Field(default_factory=list)


class Violation(Model):
    """A condition that does not hold before a call."""
    task: str
    iteration: int
    kind: Literal["Requires", "Invariant", "Goal"]
    condition: str
    actual: Scalar | None


class CheckReport(Model):
    """Result of the forward check, as written to the Procedure submodel's Validation."""
    status: Literal["Passed", "Rejected"]
    violations: list[Violation]
    final_state: dict[str, Scalar]
    ensures: dict[str, Scalar]


def check(calls, contracts: dict[str, Contract], assumes: list[Condition],
          goals: list[Condition] = ()) -> CheckReport:
    """Forward-check ``calls`` from the ``assumes`` start state; ``goals`` must hold at the end.

    Goals come from the product (e.g. Filled = FillVolume * DosingCycles, Checked = InspectionRequired);
    they catch edits that keep every step valid but miss the product requirement.
    """
    state = {c.variable: c.value for c in assumes if c.operator == "="}
    start = dict(state)
    violations = []
    for call in calls:
        contract = contracts.get(call.skill)
        if contract is None:
            raise ValueError(f"{call.id}: no contract for skill {call.skill}")
        for iteration in range(1, (call.repeat.value if call.repeat is not None else 1) + 1):
            for kind, conditions in [("Invariant", contract.invariant), ("Requires", contract.requires)]:
                for condition in conditions:
                    if not condition.holds(state):
                        violations.append(Violation(task=call.id, iteration=iteration, kind=kind,
                                                    condition=condition.text(), actual=state.get(condition.variable)))
            for effect in contract.ensures:
                value = call.parameters[effect.from_parameter].value if effect.from_parameter else effect.value
                if effect.assign == "+=":
                    state[effect.variable] = state.get(effect.variable, 0) + value
                else:
                    state[effect.variable] = value
    for goal in goals:
        if not goal.holds(state):
            violations.append(Violation(task="End", iteration=1, kind="Goal", condition=goal.text(),
                                        actual=state.get(goal.variable)))
    changed = {k: v for k, v in state.items() if start.get(k) != v}
    return CheckReport(status="Rejected" if violations else "Passed", violations=violations,
                       final_state=state, ensures=changed)


def check_procedure(procedure, target, assumes: list[Condition], goals: list[Condition] = ()) -> CheckReport:
    """Forward-check a compiled procedure against the skill contracts of a target profile."""
    return check(procedure.calls, {k: s.contract for k, s in target.skills.items() if s.contract}, assumes, goals)


def mutations(tasks: list[str], alphabet: list[str]) -> list[tuple[str, list[str]]]:
    """Every single edit of a task order: swap neighbours, delete, duplicate, insert a skill."""
    result = []
    for i in range(len(tasks) - 1):
        result.append((f"swap {tasks[i]}/{tasks[i + 1]}", tasks[:i] + [tasks[i + 1], tasks[i]] + tasks[i + 2:]))
    for i, t in enumerate(tasks):
        result.append((f"delete {t}", tasks[:i] + tasks[i + 1:]))
        result.append((f"duplicate {t}", tasks[:i + 1] + [t] + tasks[i + 1:]))
    for i in range(len(tasks) + 1):
        for s in alphabet:
            result.append((f"insert {s} at {i}", tasks[:i] + [s] + tasks[i:]))
    return result
