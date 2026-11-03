"""Where an item's points are: its inputs read and its outputs written, by name, as a generated module
reaches its IO points (Modbus, a GPIO line, a PWM channel) by name.

``SimPoints`` simulates every item in the process. An item with ``sim: {robot: ...}`` in its spec
answers the robot program's contract (docs/demo-modules.md, section 3.1); any other input reads its
``sim`` value. A driver for a robot controller (Ethernet KRL, OPC UA, KukaVarProxy) is a ``Points``
too, once the controllers' options are known (step M0 there).
"""
from __future__ import annotations

from modgen.spec import ModuleSpec


class Points:
    """The points of a module's items."""

    def read(self, item: str, name: str):
        raise NotImplementedError

    def write(self, item: str, name: str, value) -> None:
        raise NotImplementedError

    def tick(self, now: float) -> None:
        """Advance what is simulated; the module calls it before it samples its inputs."""

    def close(self) -> None:
        """Let go of the device."""


class SimRobot:
    """The robot program as the contract has it. On Start's rising edge with a Job: Busy for the
    job's time, then Done with JobDone, the job's number (or Error with ErrorCode, for a job made to
    fail). While Start is off and no job runs, Done, JobDone and Error are cleared: a job started
    and then left (Start off) is finished all the same. ErrorCode says why the last job failed until
    the next one starts. Ready while the program runs.

    ``sim: {robot: {seconds: {<job>: <s>}, default: <s>, fails: {<job>: <ErrorCode>}}}``"""

    def __init__(self, cfg: dict, speed: float = 1.0):
        self.seconds = {int(job): float(s) / speed for job, s in (cfg.get("seconds") or {}).items()}
        self.default = float(cfg.get("default", 2.0)) / speed
        self.fails = {int(job): float(code) for job, code in (cfg.get("fails") or {}).items()}
        self.inputs = {"Ready": True, "Busy": False, "Done": False, "JobDone": 0.0, "Error": False, "ErrorCode": 0.0}
        self.outputs = {"Job": 0.0, "Start": False}
        self.jobs: list[int] = []            # the jobs started, in order
        self._start, self._job, self._ends = False, 0, 0.0

    def tick(self, now: float) -> None:
        start = bool(self.outputs["Start"])
        if start and not self._start and not self.inputs["Busy"] and int(self.outputs["Job"]) > 0:
            self._job = int(self.outputs["Job"])
            self._ends = now + self.seconds.get(self._job, self.default)
            self.jobs.append(self._job)
            self.inputs.update(Busy=True, Done=False, JobDone=0.0, Error=False, ErrorCode=0.0)
        if self.inputs["Busy"] and now >= self._ends:
            self.inputs["Busy"] = False
            if self._job in self.fails:
                self.inputs.update(Error=True, ErrorCode=self.fails[self._job])
            else:
                self.inputs.update(Done=True, JobDone=float(self._job))
        if not start and not self.inputs["Busy"]:
            self.inputs.update(Done=False, JobDone=0.0, Error=False)
        self._start = start


class SimPoints(Points):
    """Every item simulated in the process; ``speed`` makes the robots' jobs that much quicker."""

    def __init__(self, spec: ModuleSpec, speed: float = 1.0):
        self.robots = {name: SimRobot(eq.sim["robot"], speed) for name, eq in spec.equipment.items()
                       if "robot" in eq.sim}
        self.values = {(name, i): bool(inp.sim) if inp.type == "BOOL" else float(inp.sim)
                       for name, eq in spec.equipment.items() for i, inp in eq.inputs.items()}
        self.outputs: dict[tuple[str, str], object] = {}
        self.trace: list[tuple[str, object]] = []    # ("<item>.<output>", value) of every change

    def read(self, item: str, name: str):
        robot = self.robots.get(item)
        return robot.inputs[name] if robot is not None and name in robot.inputs else self.values[(item, name)]

    def write(self, item: str, name: str, value) -> None:
        if self.outputs.get((item, name)) != value:
            self.trace.append((f"{item}.{name}", value))
        self.outputs[(item, name)] = value
        robot = self.robots.get(item)
        if robot is not None and name in robot.outputs:
            robot.outputs[name] = value

    def tick(self, now: float) -> None:
        for robot in self.robots.values():
            robot.tick(now)
