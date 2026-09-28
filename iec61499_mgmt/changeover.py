"""Guarded changeover: occupy, check, apply, verify, release (steps 4 to 6 of the plan's cycle).

The unit is accessed through a small protocol so the same cycle works with the OPC UA facade
(`opcua_unit.OpcUaUnit`) or a test double. A failed or unverified apply keeps the unit occupied:
the runtime state is uncertain and must be reconciled before production continues.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Callable, Literal, Protocol

from .models import Network, TypeLibrary
from .planner import plan
from .protocol import Client, ManagementError
from .verify import verify


class Unit(Protocol):
    """What the changeover needs from the unit coordinator."""

    def occupy(self) -> bool:
        """Occupy the unit for the manager; False if refused."""

    def release(self) -> bool:
        """Release the manager's occupation; False if refused."""

    def quiescent(self) -> list[str]:
        """Reasons the unit or a skill is not in a quiescent state (empty = quiescent)."""


@dataclass
class ChangeRecord:
    """Outcome of one changeover, as written to the control-configuration change log."""
    result: Literal["Applied", "Rejected", "Failed"]
    change_class: str | None = None
    commands: int = 0
    duration_ms: float = 0.0
    problems: list[str] = field(default_factory=list)
    released: bool = False


def changeover(client: Client, unit: Unit, current: Network, desired: Network, library: TypeLibrary,
               guards: list[Callable[[], list[str]]] = ()) -> ChangeRecord:
    """Apply ``current`` -> ``desired`` only while the unit is occupied and quiescent, then verify."""
    started = time.perf_counter()

    def done(record):
        record.duration_ms = (time.perf_counter() - started) * 1000
        return record

    try:
        result = plan(current, desired, library)
    except ValueError as exc:
        return done(ChangeRecord("Rejected", problems=[str(exc)]))
    if result.change_class == "none":
        return done(ChangeRecord("Applied", "none"))
    if not unit.occupy():
        return done(ChangeRecord("Rejected", result.change_class, problems=["unit occupation refused"]))
    problems = unit.quiescent()
    for guard in guards:
        problems += guard()
    problems += [f"drift: {p}" for p in verify(client, current)]
    if problems:
        return done(ChangeRecord("Rejected", result.change_class, problems=problems, released=unit.release()))
    record = ChangeRecord("Applied", result.change_class)
    try:
        for command in result.commands:
            client.execute(command)
            record.commands += 1
    except (ManagementError, OSError) as exc:
        record.result, record.problems = "Failed", [f"command {record.commands + 1}: {exc}"]
        return done(record)
    record.problems = verify(client, desired)
    if record.problems:
        record.result = "Failed"
        return done(record)
    record.released = unit.release()
    return done(record)
