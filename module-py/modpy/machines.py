"""The module rules' state machines in Python, answering as ModLib's blocks answer in the generated
modules (modgen/library.py): the occupation (MOD_OccupationLogic), the module's PackML state manager
(MOD_StateLogic) and the state machine every skill shares (SKILL_Control).

After the planar controller's ``planar/statemachines.py`` (MIT, Aalborg University Smart Lab). What
differs is ModLib's: every command needs the occupation, Abort too; a module has no Hold; a Resetting
or Stopping procedure that fails aborts the module; Stopping gives up after the module's
``stop_timeout``; a skill's Abort is taken in every state but Aborted, and a skill that a parent
started (a step) does not stop by itself when the module stops: its parent stops it.

Everything of a module is guarded by its runtime's lock; whatever a skill runs reports back through
the callbacks it was handed, with that lock held (``run.py``).
"""
from __future__ import annotations

import logging
from typing import Callable, Protocol

from modgen.library import ERRORS, SKILL_STATES, STATES
from modgen.spec import Parameter

log = logging.getLogger(__name__)

E, S, M = ERRORS, SKILL_STATES, STATES
SUCCEEDED_FOR = 1.5                  # s a skill shows Succeeded before it is Idle again (SUCCEEDED_FOR)
READY = (S["Idle"], S["Succeeded"], S["Failed"])
ACTIVE = (S["Running"], S["Stopping"])

Answer = tuple[bool, int]
OK: Answer = (True, 0)
Ended = Callable[[bool, int, dict], None]       # (succeeded, ErrorID, results)


def refuse(error: str) -> Answer:
    return (False, E[error])


class Body(Protocol):
    """What a skill runs: a primitive's logic or a flow of steps (run.py)."""

    def start(self, values: dict, ended: Ended) -> None:
        """Begin a run; ``ended`` is called once when it is over (not after an abort)."""

    def halt(self) -> None:
        """End the run in order: ``ended`` follows, with Interrupted."""

    def abort(self) -> None:
        """Switch off at once; ``ended`` does not follow."""

    def stopping(self, done: Callable[[], None]) -> None:
        """After a halt, the skill's stop flow; ``done`` at its end."""

    def free(self) -> bool:
        """Whether what the run needs is free (EquipmentFree, checked by Start)."""


class Occupation:
    """Occupy when free or again by the owner; Release only by the owner. Published: Occupied."""

    def __init__(self, changed: Callable[[], None]):
        self.owner = ""
        self._changed = changed

    @property
    def occupied(self) -> bool:
        return self.owner != ""

    def owns(self, session: str) -> bool:
        return self.owner != "" and session == self.owner

    def occupy(self, session: str) -> Answer:
        if not session or self.owner not in ("", session):
            return refuse("NotPermitted")
        self.owner = session
        self._changed()
        return OK

    def release(self, session: str) -> Answer:
        if not self.owns(session):
            return refuse("NotPermitted")
        self.owner = ""
        self._changed()
        return OK


class Skill:
    """One skill instance: an offered skill (with OPC UA methods), or a step of a module level skill
    or of a procedure (started by its parent). Idle 0, Running 1, Stopping 2, Succeeded 3, Failed 4,
    Aborted 5; ErrorID why it failed."""

    def __init__(self, runtime, path: str, parameters: dict[str, Parameter], results: list[str], body: Body):
        self.runtime, self.path, self.parameters, self.body = runtime, path, parameters, body
        self.state, self.error = S["Idle"], 0
        self.values = {p: pr.default for p, pr in parameters.items()}
        self.result_names = list(results)
        self.results: dict = {r: 0.0 for r in results}
        self.called_by_client = False
        self._ended: Ended | None = None
        self._succeeded_at = 0.0
        self._run = 0

    @property
    def active(self) -> bool:
        return self.state in ACTIVE

    # OPC UA ---------------------------------------------------------------------------------

    def start(self, session: str, values: dict) -> Answer:
        if not self.runtime.module.occupation.owns(session):
            return refuse("NotPermitted")
        if self.runtime.module.state != M["Execute"]:
            return refuse("NotReady")
        if self.active:
            return refuse("Busy")
        if self.state == S["Aborted"]:
            return refuse("NotReady")
        merged = {**self.values, **values}
        if not all(in_range(pr, merged[p]) for p, pr in self.parameters.items()):
            return refuse("OutOfRange")
        if not self.body.free():
            return refuse("Busy")
        self._begin(merged, None, client=True)
        return OK

    def stop(self, session: str) -> Answer:
        if not self.runtime.module.occupation.owns(session):
            return refuse("NotPermitted")
        if self.state != S["Running"]:
            return refuse("NotReady")
        self.halt()
        return OK

    def abort(self, session: str) -> Answer:
        if not self.runtime.module.occupation.owns(session):
            return refuse("NotPermitted")
        if self.state == S["Aborted"]:
            return refuse("NotReady")
        self.kill()
        return OK

    def reset(self, session: str) -> Answer:
        if not self.runtime.module.occupation.owns(session):
            return refuse("NotPermitted")
        if self.state != S["Aborted"]:
            return refuse("NotReady")
        self.clear()
        return OK

    # From a parent or the module (not gated) --------------------------------------------------

    def run(self, values: dict, ended: Ended) -> None:
        """START from a parent: from Idle, Succeeded or Failed; an aborted skill refuses (NotReady)."""
        if self.state == S["Aborted"]:
            ended(False, E["NotReady"], {})
        elif self.state in READY:
            self._begin({**self.values, **values}, ended, client=False)

    def halt(self) -> None:
        if self.state == S["Running"]:
            self._set(S["Stopping"])
            self.body.halt()

    def kill(self) -> None:
        if self.state == S["Aborted"]:
            return
        self._run += 1                           # what the aborted run still reports is ignored
        was_active = self.active
        self._set(S["Aborted"], E["Interrupted"] if was_active else None)
        if was_active:
            self.body.abort()

    def clear(self) -> None:
        if self.state == S["Aborted"]:
            self._set(S["Idle"])

    def module_changed(self, state: int) -> None:
        """MOD_CHG: a skill the occupant started stops when the module stops; every skill aborts
        when the module aborts, and an aborted one is reset when the module is cleared."""
        if state == M["Stopping"] and self.called_by_client and self.state == S["Running"]:
            self.halt()
        elif state in (M["Aborting"], M["Aborted"]):
            self.kill()
        elif state in (M["Clearing"], M["Stopped"]):
            self.clear()

    def tick(self, now: float) -> None:
        if self.state == S["Succeeded"] and now - self._succeeded_at >= SUCCEEDED_FOR:
            self._set(S["Idle"])

    # Internals ------------------------------------------------------------------------------

    def _begin(self, values: dict, ended: Ended | None, client: bool) -> None:
        self._run += 1
        run = self._run
        self.values, self._ended, self.called_by_client = values, ended, client
        self.results = {r: 0.0 for r in self.result_names}
        self._set(S["Running"], 0)
        self.body.start(values, lambda ok, error, results: self._finished(run, ok, error, results))

    def _finished(self, run: int, ok: bool, error: int, results: dict) -> None:
        if run != self._run or not self.active:
            return
        if self.state == S["Stopping"]:          # halted: the stop flow, then Failed with Interrupted
            self.body.stopping(lambda: self._interrupted(run))
            return
        if ok:
            self.results.update(results or {})
            self._succeeded_at = self.runtime.clock()
            self._set(S["Succeeded"], 0)
        else:
            self._set(S["Failed"], error)
        self._tell(ok, error)

    def _interrupted(self, run: int) -> None:
        if run == self._run and self.state == S["Stopping"]:
            self._set(S["Failed"], E["Interrupted"])
            self._tell(False, E["Interrupted"])

    def _tell(self, ok: bool, error: int) -> None:
        ended, self._ended = self._ended, None
        if ended is not None:
            ended(ok, error, dict(self.results))

    def _set(self, state: int, error: int | None = None) -> None:
        if error is not None:
            self.error = error
        if state != self.state:
            log.info("%s/%s: %s -> %s%s", self.runtime.spec.module, self.path, name_of(S, self.state),
                     name_of(S, state), f" ({name_of(E, self.error)})" if self.error else "")
        self.state = state


class Module:
    """The PackML state manager: Stopped -Reset-> Resetting {Resetting} -> Idle -Start-> Starting ->
    Execute; Stop -> Stopping (the skills the occupant started stop; when none is active the
    Stopping procedure runs, unless stop_timeout passes first) -> Stopped; Abort -> Aborting (skills
    and equipment off) -> Aborted -Clear-> Clearing -> Stopped. Commands only from the occupant, and
    only where PackML has them."""

    VALID = {"Reset": ("Stopped",), "Start": ("Idle",), "Stop": ("Resetting", "Idle", "Execute"),
             "Abort": ("Stopped", "Resetting", "Idle", "Execute", "Stopping"), "Clear": ("Aborted",)}

    def __init__(self, runtime, stop_timeout: float):
        self.runtime, self.stop_timeout = runtime, stop_timeout
        self.state = M["Stopped"]
        self.occupation = Occupation(lambda: None)
        self._procedure = 0                  # the run of the procedure running now
        self._stop_by = None                 # Stopping: when it gives up waiting for the skills
        self._stopping_procedure = False

    def command(self, name: str, session: str) -> Answer:
        if not self.occupation.owns(session):
            return refuse("NotPermitted")
        if self.state not in (M[s] for s in self.VALID[name]):
            return refuse("NotReady")
        getattr(self, f"_{name.lower()}")()
        return OK

    def tick(self, now: float) -> None:
        if self.state != M["Stopping"] or self._stopping_procedure:
            return
        if not self.runtime.any_active():
            self._stopping_procedure = True
            self._run_procedure("Stopping", self._stopped)
        elif now >= self._stop_by:
            self._aborting()

    # Commands -------------------------------------------------------------------------------

    def _reset(self) -> None:
        self._set(M["Resetting"])
        self._run_procedure("Resetting", self._reset_done)

    def _start(self) -> None:
        self._set(M["Starting"])
        self._set(M["Execute"])

    def _stop(self) -> None:
        self._procedure += 1                 # a Resetting still running ends unheard (its steps run on)
        self._stop_by = self.runtime.clock() + self.stop_timeout
        self._stopping_procedure = False
        self._set(M["Stopping"])
        self.tick(self.runtime.clock())

    def _abort(self) -> None:
        self._aborting()

    def _clear(self) -> None:
        self._set(M["Clearing"])
        self._set(M["Stopped"])

    # Internals ------------------------------------------------------------------------------

    def _run_procedure(self, name: str, then: Callable[[bool], None]) -> None:
        self._procedure += 1
        run = self._procedure
        flow = self.runtime.procedures.get(name)
        if flow is None:
            then(True)
        else:
            flow.start({}, lambda ok, error, results: run == self._procedure and then(ok))

    def _reset_done(self, ok: bool) -> None:
        if self.state == M["Resetting"]:
            self._set(M["Idle"]) if ok else self._aborting()

    def _stopped(self, ok: bool) -> None:
        if self.state == M["Stopping"]:
            self._set(M["Stopped"]) if ok else self._aborting()

    def _aborting(self) -> None:
        self._procedure += 1
        self._set(M["Aborting"])
        for flow in self.runtime.procedures.values():
            flow.abort()
        self.runtime.switch_off()
        self._set(M["Aborted"])

    def _set(self, state: int) -> None:
        if state == self.state:
            return
        log.info("%s: %s -> %s", self.runtime.spec.module, name_of(M, self.state), name_of(M, state))
        self.state = state
        for skill in list(self.runtime.skills.values()):
            skill.module_changed(state)


def in_range(parameter: Parameter, value) -> bool:
    return ((parameter.minimum is None or value >= parameter.minimum)
            and (parameter.maximum is None or value <= parameter.maximum))


def name_of(table: dict[str, int], code: int) -> str:
    return next((name for name, c in table.items() if c == code), str(code))
