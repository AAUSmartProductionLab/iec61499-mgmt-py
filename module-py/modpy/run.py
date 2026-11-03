"""A module of a spec, run in Python as its generated program runs on FORTE: the equipment and its
commands, every skill primitive's logic, the module level skills' and the procedures' flows, under the
state machines of ``machines.py``.

What the generator writes as blocks is done here by objects of the same names:

- an item of equipment (EQ_<item>) plays a command's phases on its outputs; outputs a phase does not
  name are off, ``Arg`` is the command's argument; one holder at a time, the first command is all off;
- a primitive's logic (SL_<skill>): the precondition first (else PreconditionViolated), the item free
  within 0.5 s (else Busy), done at once if the postcondition already holds; else its command until
  the postcondition holds (or ``after`` has passed), with the invariant (InvariantViolated) and the
  timeout (Timeout) over it; at the end the stop command, after an abort the first command;
- a flow (a module level skill's execute and stop flows, a procedure): its steps one after the other,
  each a skill instance of its own, with its parameters bound to constants or to the parent's.

A module of the planar controller's kind, whose skills are not a spec's, is not run here. Neither are
items with a position (an axis that counts its steps) nor parallel and decision blocks: the robot
modules need none of them yet (``unsupported``).

Everything runs in one loop (``tick``, every 10 ms by default) under one lock; the OPC UA server
calls in with the lock held.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from modgen.spec import Equipment, ModuleSpec, Skill as SkillSpec, Step, linear, ms

from .machines import E, Ended, Module, Skill
from .points import Points
from .st import compile_st

log = logging.getLogger(__name__)

WAIT_FREE = 0.5                      # s a primitive waits for an item another holder still has


def unsupported(spec: ModuleSpec) -> list[str]:
    """What of ``spec`` this runtime cannot run (empty: all of it)."""
    found = [f"{name}: an item with a position" for name, eq in spec.equipment.items() if eq.position]
    flows = [(name, c.execute) for name, c in spec.composites.items()] + \
            [(name, c.stop) for name, c in spec.composites.items()] + list(spec.procedures.items())
    found += [f"{name}: a parallel or decision block" for name, nodes in flows if not linear(nodes)]
    return found


class Item:
    """An item of equipment: its holder, the command it plays, its inputs as the points read them."""

    def __init__(self, name: str, eq: Equipment, points: Points):
        self.name, self.eq, self.points = name, eq, points
        self.holder = ""
        self.command, self.arg, self.phase = next(iter(eq.commands)), 0.0, 0
        self._phase_ends: float | None = None
        self._play(0.0)

    @property
    def safe(self) -> str:
        return next(iter(self.eq.commands))

    def drive(self, holder: str, command: str, arg: float, now: float, release: bool = False) -> None:
        """Play ``command`` for ``holder``; with ``release`` give the item up in the same message."""
        self.holder = "" if release else holder
        self.command, self.arg, self.phase = command, arg, 0
        self._play(now)

    def switch_off(self, now: float) -> None:
        self.drive("", self.safe, 0.0, now, release=True)

    @property
    def played(self) -> bool:
        """The command's timed phases are over: it holds its last phase."""
        return self._phase_ends is None

    def inputs(self) -> dict:
        return {name: self.points.read(self.name, name) for name in self.eq.inputs}

    def tick(self, now: float) -> None:
        if self._phase_ends is not None and now >= self._phase_ends:
            self.phase += 1
            self._play(now)

    def _play(self, now: float) -> None:
        phase = self.eq.commands[self.command][self.phase]
        values = phase.values()
        for name, output in self.eq.outputs.items():
            given = values.get(name)
            if output.type == "BOOL":
                self.points.write(self.name, name, bool(given))
            else:
                self.points.write(self.name, name, float(self.arg if given == "Arg" else given or 0.0))
        self._phase_ends = now + ms(phase.duration) / 1000.0 if phase.duration else None


class Primitive:
    """The logic of a skill primitive (SL_<skill>), run by its skill instance."""

    def __init__(self, runtime: Runtime, decl: SkillSpec, holder: str, release: bool):
        self.runtime, self.decl, self.holder, self.release = runtime, decl, holder, release
        self.item = runtime.equipment[decl.equipment] if decl.equipment else None
        self.pre, self.inv = compile_st(decl.precondition), compile_st(decl.invariant)
        self.post = compile_st(decl.postcondition) if decl.postcondition is not None else None
        self.after = constant_or_st(decl.after)
        self.arg = constant_or_st(decl.arg if decl.arg is not None else 0.0)
        self.timeout = ms(decl.timeout) / 1000.0
        self.phase: str | None = None        # None, "wait" (for the item), "run", "ending"
        self.values: dict = {}
        self._ended: Ended | None = None
        self._outcome: tuple[bool, int, dict] = (False, 0, {})

    def free(self) -> bool:
        return self.item is None or self.item.holder in ("", self.holder)

    def start(self, values: dict, ended: Ended) -> None:
        self.values, self._ended = values, ended
        self._check(self.runtime.clock())

    def halt(self) -> None:
        if self.phase == "wait":                 # the item was never driven: nothing to stop
            self._end(False, E["Interrupted"], {})
        elif self.phase == "run":
            self._final(self.stop_command, (False, E["Interrupted"], {}))

    def abort(self) -> None:
        if self.phase is not None:
            self.phase, self._ended = None, None
            self.runtime.running.discard(self)
            if self.item is not None and self.item.holder in ("", self.holder):
                self.item.switch_off(self.runtime.clock())

    def stopping(self, done: Callable[[], None]) -> None:
        done()

    def tick(self, now: float) -> None:
        if self.phase == "wait":
            if self.free():
                self._check(now)
            elif now >= self._wait_until:
                self._end(False, E["Busy"], {})
        elif self.phase == "run":
            scope = self.scope()
            if self.item is None:
                if now >= self._deadline:
                    self._end(True, 0, {})
            elif not self.inv(scope):
                self._final(self.item.safe, (False, E["InvariantViolated"], {}))
            elif self.item.holder not in ("", self.holder):
                self._end(False, E["Busy"], {})                     # Lost: another holder took it
            elif self.post is not None and self.post(scope):
                self._final(self.stop_command, (True, 0, self.results(scope)))
            elif now >= self._deadline:
                if self.post is None:
                    self._final(self.stop_command, (True, 0, self.results(scope)))
                else:
                    self._final(self.item.safe, (False, E["Timeout"], {}))
        elif self.phase == "ending" and self.item.played:
            self._end(*self._outcome)

    @property
    def stop_command(self) -> str | None:
        return None if self.item is None else self.decl.stop or self.item.safe

    def scope(self) -> dict:
        return {**(self.item.inputs() if self.item is not None else {}), **self.values}

    def results(self, scope: dict) -> dict:
        return {result: scope[source] for result, source in self.decl.results.items()}

    def _check(self, now: float) -> None:
        scope = self.scope()
        if not self.pre(scope):
            return self._end(False, E["PreconditionViolated"], {})
        if self.item is not None and not self.free():
            if self.phase != "wait":
                self.phase, self._wait_until = "wait", now + WAIT_FREE
                self.runtime.running.add(self)
            return
        if self.item is not None and self.post is not None and self.post(scope):
            return self._end(True, 0, self.results(scope))           # already there: nothing to drive
        if self.item is not None:
            self.item.drive(self.holder, self.decl.command, float(self.arg(scope)), now)
        self._deadline = now + (float(self.after(scope)) if self.after is not None else self.timeout)
        self.phase = "run"
        self.runtime.running.add(self)

    def _final(self, command: str | None, outcome: tuple[bool, int, dict]) -> None:
        """The last command (it releases the item when this run is the last to use it); the run
        ends when that command has been played."""
        if self.item is None or command is None:
            return self._end(*outcome)
        self.item.drive(self.holder, command, float(self.arg(self.scope())), self.runtime.clock(), self.release)
        self.phase, self._outcome = "ending", outcome
        self.runtime.running.add(self)
        if self.item.played:
            self._end(*outcome)

    def _end(self, ok: bool, error: int, results: dict) -> None:
        self.phase = None
        self.runtime.running.discard(self)
        if self.release and self.item is not None and self.item.holder == self.holder:
            self.item.holder = ""
        ended, self._ended = self._ended, None
        if ended is not None:
            ended(ok, error, results)


class Flow:
    """Steps one after the other: a module level skill's execute flow (with its stop flow), or a
    procedure. Every step is a skill instance of its own; the items its steps drive are held for the
    whole flow and given up at its end."""

    def __init__(self, runtime: Runtime, path: str, steps: list[Step], holder: str, results: dict[str, str] | None = None,
                 stop: Flow | None = None):
        self.runtime, self.path, self.holder, self.result_map = runtime, path, holder, results or {}
        self.steps = [(step, runtime.step(f"{path}/{step.name}", step, holder)) for step in steps]
        self.stop_flow = stop
        self.at, self.values, self.collected = -1, {}, {}
        self._ended: Ended | None = None

    def free(self) -> bool:
        return all(skill.body.free() for _, skill in self.steps)

    def start(self, values: dict, ended: Ended) -> None:
        self.values, self._ended, self.at, self.collected = values, ended, -1, {}
        self._next(True, 0, {})

    def halt(self) -> None:
        if 0 <= self.at < len(self.steps):
            self.steps[self.at][1].halt()

    def abort(self) -> None:
        if 0 <= self.at < len(self.steps):
            self.steps[self.at][1].kill()
        self.at, self._ended = -1, None
        if self.stop_flow is not None:
            self.stop_flow.abort()
        self._release()

    def stopping(self, done: Callable[[], None]) -> None:
        if self.stop_flow is None:
            self._release()
            return done()
        self.stop_flow.start(self.values, lambda ok, error, results: (self._release(), done()))

    def _next(self, ok: bool, error: int, results: dict) -> None:
        if self.at >= 0:
            self.collected[self.steps[self.at][0].name] = results
        if not ok:
            return self._end(False, error)
        self.at += 1
        if self.at == len(self.steps):
            return self._end(True, 0)
        step, skill = self.steps[self.at]
        bound = {p: self.values[v] if isinstance(v, str) else v for p, v in step.bind.items()}
        skill.run(bound, self._next)

    def _end(self, ok: bool, error: int) -> None:
        self.at = -1
        self._release()
        ended, self._ended = self._ended, None
        if ended is not None:
            results = {r: self.collected.get(src.split(".")[0], {}).get(src.split(".")[1], 0.0)
                       for r, src in self.result_map.items()}
            ended(ok, error, results)

    def _release(self) -> None:
        for item in self.runtime.equipment.values():
            if item.holder == self.holder:
                item.holder = ""


class Runtime:
    """One module of a spec: its equipment, its skills (offered, steps and procedures' steps), its
    state manager; ``tick`` runs it, ``loop`` ticks it in a thread of its own."""

    def __init__(self, spec: ModuleSpec, points: Points, clock: Callable[[], float] = time.monotonic):
        if problems := unsupported(spec):
            raise ValueError(f"{spec.module}: not run in Python: {'; '.join(problems)}")
        self.spec, self.points, self.clock = spec, points, clock
        self.lock = threading.RLock()
        self.equipment = {name: Item(name, eq, points) for name, eq in spec.equipment.items()}
        self.skills: dict[str, Skill] = {}            # every instance, by its path below the module
        self.offered: dict[str, Skill] = {}           # Skills/<name>: those with OPC UA methods
        self.running: set[Primitive] = set()
        self.module = Module(self, ms(spec.stop_timeout) / 1000.0)
        for name, decl in spec.skills.items():
            if decl.offered:
                path = f"Skills/{name}"
                self.offered[name] = self._skill(path, decl.parameters, list(decl.results),
                                                 Primitive(self, decl, path, release=True))
        for name, comp in spec.composites.items():
            path = f"Skills/{name}"
            stop = Flow(self, f"{path}/Stopping", comp.stop, path) if comp.stop else None
            flow = Flow(self, f"{path}/Execute", comp.execute, path, comp.results, stop)
            skill = self._skill(path, comp.parameters, list(comp.results), flow)
            if comp.offered:
                self.offered[name] = skill
        self.procedures = {name: Flow(self, f"Procedures/{name}", steps, f"Procedures/{name}")
                           for name, steps in spec.procedures.items()}

    def step(self, path: str, step: Step, holder: str) -> Skill:
        """A step's skill instance: the primitive's logic, holding the items for ``holder``."""
        decl = self.spec.skills[step.skill]
        return self._skill(path, decl.parameters, list(decl.results), Primitive(self, decl, holder, release=False))

    def any_active(self) -> bool:
        return any(skill.active for skill in self.skills.values())

    def switch_off(self) -> None:
        """Aborting: every primitive stops where it is and every item is switched off and free."""
        for run in list(self.running):
            run.abort()
        now = self.clock()
        for item in self.equipment.values():
            item.switch_off(now)

    def tick(self) -> None:
        with self.lock:
            now = self.clock()
            self.points.tick(now)
            for item in self.equipment.values():
                item.tick(now)
            for run in list(self.running):
                run.tick(now)
            for skill in list(self.skills.values()):
                skill.tick(now)
            self.module.tick(now)

    def loop(self, stop: threading.Event, period: float = 0.01) -> None:
        while not stop.is_set():
            try:
                self.tick()
            except Exception:                    # noqa: BLE001 (the loop keeps the module served)
                log.exception("%s: tick", self.spec.module)
            stop.wait(period)

    def _skill(self, path: str, parameters, results, body) -> Skill:
        skill = Skill(self, path, parameters, results, body)
        self.skills[path] = skill
        return skill


def constant_or_st(value):
    """A number as a constant, an ST expression as its function, None as None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return lambda scope, x=float(value): x
    return compile_st(value)
