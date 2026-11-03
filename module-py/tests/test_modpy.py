"""modpy: a module run in Python answers as its generated program answers on FORTE (the robot
modules, cell/modules/python), and its OPC UA server is laid out as FORTE's: every node and method
argument its AAS names is there."""
import asyncio
from contextlib import contextmanager
from pathlib import Path
import sys
import threading
import uuid

import pytest

from conftest import free_port
from modgen import SPECS, load
from modgen.library import ERRORS as E, SKILL_STATES as S, STATES as M
from modpy.points import SimPoints
from modpy.run import Runtime, unsupported
from modpy.st import evaluate

ROBOTS = SPECS / "python"
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cell" / "sim"))


class Robot:
    """A robot module run on a clock of its own: ``run(seconds)`` ticks it every 10 ms."""

    def __init__(self, name: str, fails: dict | None = None):
        self.spec = load(ROBOTS / f"{name}.yaml")
        self.points = SimPoints(self.spec)
        self.points.robots["Robot"].fails = fails or {}
        self.now = 0.0
        self.rt = Runtime(self.spec, self.points, clock=lambda: self.now)
        self.module, self.skills = self.rt.module, self.rt.offered

    def run(self, seconds: float) -> None:
        end = self.now + seconds
        while self.now < end:
            self.now += 0.01
            self.rt.tick()

    @property
    def jobs(self) -> list[int]:
        return self.points.robots["Robot"].jobs

    def ready(self, session: str = "a") -> None:
        assert self.module.occupation.occupy(session) == (True, 0)
        assert self.module.command("Reset", session) == (True, 0)
        self.run(3.0)
        assert self.module.command("Start", session) == (True, 0)
        assert self.module.state == M["Execute"]


def test_structured_text_as_the_specs_write_it():
    values = {"Moving": False, "ActualPosition": 20.0, "Position": 20.0, "Done": True, "JobDone": 2.0,
              "Busy": False, "Volume": 1.0, "FlowRate": 0.5}
    assert evaluate("NOT Moving AND ABS(ActualPosition - Position) < 0.001", values) is True
    assert evaluate("Done AND JobDone = 2", values) and not evaluate("Done AND JobDone = 3", values)
    assert evaluate("Volume / FlowRate", values) == 2.0 and evaluate("-2 + 3 * 4", {}) == 10.0
    assert evaluate("NOT (Done OR Busy)", values) is False and evaluate("TRUE", {}) is True
    with pytest.raises(ValueError):
        evaluate("Done AND", values)


@pytest.mark.parametrize("name", ["loading", "unloading"])
def test_the_robot_modules_are_run_in_python(name):
    assert unsupported(load(ROBOTS / f"{name}.yaml")) == []


def test_resetting_homes_the_robot_and_a_skill_runs_its_jobs_in_order():
    robot = Robot("loading")
    robot.ready()
    assert robot.jobs == [1]                            # Resetting: nothing to wait for, then home
    robot.points.trace.clear()
    assert robot.skills["Loading"].start("a", {}) == (True, 0)
    robot.run(10.0)
    assert robot.skills["Loading"].state == S["Succeeded"] and robot.jobs == [1, 2, 3, 1]
    # Each job: its number with Start off (200 ms), then Start; Start off again when it is done.
    assert robot.points.trace == [(signal, value) for job in (2.0, 3.0, 1.0) for signal, value in
                                  [("Robot.Job", job), ("Robot.Start", True), ("Robot.Job", 0.0), ("Robot.Start", False)]]


def test_a_failing_job_fails_the_skill_and_its_reason_stays_readable():
    robot = Robot("loading", fails={3: 17})
    robot.ready()
    robot.skills["Loading"].start("a", {})
    robot.run(10.0)
    loading = robot.skills["Loading"]
    assert (loading.state, loading.error) == (S["Failed"], E["InvariantViolated"])
    assert robot.rt.skills["Skills/Loading/Execute/PlaceOnShuttle"].error == E["InvariantViolated"]
    assert robot.jobs == [1, 2, 3]                      # not home after the failure
    assert robot.points.read("Robot", "ErrorCode") == 17.0 and robot.points.read("Robot", "Error") is False
    assert robot.skills["Loading"].start("a", {}) == (True, 0)    # the next run starts afresh


def test_a_module_stopped_during_a_job_lets_the_robot_finish_it():
    robot = Robot("loading")
    robot.ready()
    robot.skills["Loading"].start("a", {})
    robot.run(1.0)                                      # PickFromTray runs
    assert robot.module.command("Stop", "a") == (True, 0)
    robot.run(0.5)
    assert robot.module.state == M["Stopping"] and robot.points.read("Robot", "Busy") is True
    robot.run(5.0)
    assert robot.module.state == M["Stopped"] and robot.jobs == [1, 2]
    assert (robot.skills["Loading"].state, robot.skills["Loading"].error) == (S["Failed"], E["Interrupted"])
    assert robot.rt.skills["Skills/Loading/Stopping/AwaitJob"].state in (S["Succeeded"], S["Idle"])


def test_a_stop_waits_for_a_long_job_as_long_as_the_module_says():
    robot = Robot("loading")
    robot.points.robots["Robot"].seconds[2] = 40.0      # a slow pick: longer than FORTE's default 10 s
    robot.ready()
    robot.skills["Loading"].start("a", {})
    robot.run(1.0)
    robot.module.command("Stop", "a")
    robot.run(30.0)
    assert robot.module.state == M["Stopping"]
    robot.run(15.0)
    assert robot.module.state == M["Stopped"] and robot.jobs == [1, 2]


def test_abort_switches_the_robot_off_and_clear_returns_to_stopped():
    robot = Robot("unloading")
    robot.ready()
    robot.skills["Unloading"].start("a", {})
    robot.run(1.0)
    assert robot.module.command("Abort", "a") == (True, 0)
    assert robot.module.state == M["Aborted"] and robot.skills["Unloading"].state == S["Aborted"]
    assert robot.points.outputs[("Robot", "Start")] is False and robot.points.outputs[("Robot", "Job")] == 0.0
    assert robot.skills["Unloading"].start("a", {}) == (False, E["NotReady"])
    assert robot.module.command("Clear", "a") == (True, 0)
    assert robot.module.state == M["Stopped"] and robot.skills["Unloading"].state == S["Idle"]


def test_commands_are_gated_as_on_a_generated_module():
    robot = Robot("loading")
    assert robot.module.command("Reset", "b") == (False, E["NotPermitted"])          # not occupied
    assert robot.module.occupation.occupy("a") == (True, 0)
    assert robot.module.occupation.occupy("b") == (False, E["NotPermitted"])
    assert robot.module.command("Abort", "b") == (False, E["NotPermitted"])           # Abort too
    assert robot.skills["Home"].start("a", {}) == (False, E["NotReady"])              # not in Execute
    assert robot.module.command("Start", "a") == (False, E["NotReady"])               # not Idle
    robot.module.occupation.release("a")
    robot.ready()
    assert robot.skills["Loading"].start("a", {}) == (True, 0)
    assert robot.skills["Loading"].start("a", {}) == (False, E["Busy"])
    assert robot.skills["PickFromTray"].start("a", {}) == (False, E["Busy"])          # the robot is held
    assert robot.skills["Home"].stop("a") == (False, E["NotReady"])                   # not running


# Over OPC UA --------------------------------------------------------------------------------------

@contextmanager
def serving(*names, speed: float = 20.0):
    """The modules ``names`` in one OPC UA server on this computer, their robots that much quicker."""
    from modpy.server import ModuleServer
    runtimes = [Runtime(spec, SimPoints(spec, speed)) for spec in (load(ROBOTS / f"{n}.yaml") for n in names)]
    port, stop, ready, held = free_port(), threading.Event(), threading.Event(), {}
    server = ModuleServer(runtimes, port, host="127.0.0.1")

    async def main():
        held["loop"], held["stop"] = asyncio.get_running_loop(), asyncio.Event()
        await server.init()
        ready.set()
        await server.serve(held["stop"])

    thread = threading.Thread(target=lambda: asyncio.run(main()), daemon=True)
    thread.start()
    for rt in runtimes:
        threading.Thread(target=rt.loop, args=(stop,), daemon=True).start()
    assert ready.wait(30)
    try:
        yield port
    finally:
        held["loop"].call_soon_threadsafe(held["stop"].set)
        thread.join(10)
        stop.set()


def test_two_robot_modules_on_one_server_run_as_generated_modules():
    pytest.importorskip("asyncua")
    from module_ua import ModuleUa
    with serving("loading", "unloading") as port:
        for module in ("Loading", "Unloading"):
            ua, a = ModuleUa(port, module), str(uuid.uuid4())
            try:
                assert ua.call("Occupation/Occupy", a) == [True, 0]
                assert ua.value("Occupation/Occupied") is True
                assert ua.call("Module/Start", a) == [False, E["NotReady"]]
                assert ua.call("Module/Reset", a) == [True, 0]
                ua.expect("Module/State", M["Idle"], timeout=5)
                assert ua.call("Module/Start", a) == [True, 0]
                ua.expect("Module/State", M["Execute"])
                assert ua.call(f"Skills/{module}/Start", a) == [True, 0]
                ua.expect(f"Skills/{module}/State", S["Succeeded"], timeout=10)
                assert ua.value("Equipment/Robot/Ready") is True
                ua.expect("Equipment/Robot/JobDone", 0.0)         # Start dropped: the robot clears it
                assert ua.call("Module/Stop", a) == [True, 0]
                ua.expect("Module/State", M["Stopped"], timeout=5)
            finally:
                ua.close()


@pytest.mark.parametrize("name", ["loading", "unloading"])
def test_its_aas_and_its_robots_follow_the_resource_ontology(name):
    """Built by the registration service's rules from the profiles modreg makes of the spec, without
    what is FORTE's (the rule set), as any module's AAS: the module and its robot, a component."""
    pytest.importorskip("aas_model")
    from modreg import model, pymodules
    from modreg.ontology import Blueprint, check
    blueprint = Blueprint(Path(__file__).resolve().parents[2] / "ontology" / "ARSO")
    built = [model.build(profile) for profile in pymodules.describe_all(load(ROBOTS / f"{name}.yaml"))]
    assert [env["assetAdministrationShells"][0]["idShort"] for env in built] == [
        f"{name.capitalize()}ModuleAAS", f"{name.capitalize()}RobotAAS"]
    for env in built:
        report = check(env, blueprint)
        assert report.ok, report.errors
    skills = next(s for s in built[0]["submodels"] if s["idShort"] == "Skills")
    assert "RuleSet" not in [e["idShort"] for e in skills["submodelElements"]]


def test_every_node_and_argument_its_aas_names_is_on_the_server():
    """The module's AAS is made by modreg's Describer, as a FORTE module's: its interface (AID) names
    each variable and method by browse path in namespace 1 and each argument as FORTE names it."""
    pytest.importorskip("aas_model")
    from asyncua.sync import Client
    from modreg import pymodules
    with serving("loading") as port:
        aid = pymodules.describe_all(load(ROBOTS / "loading.yaml"), opcua=f"opc.tcp://127.0.0.1:{port}")[0]
        meta = aid["asset_interfaces_description"]["InterfaceTemplateForOPCUA"]["interface_opcua"]["InteractionMetadata"]
        client = Client(f"opc.tcp://127.0.0.1:{port}", timeout=10)
        client.connect()
        try:
            def node(href):
                return client.nodes.root.get_child([part for part in href.split("/") if part])

            properties = meta["properties"]["property_name"]
            assert len(properties) > 20
            for name, prop in properties.items():
                node(prop["forms"]["href"]["value"]).read_value()
            for name, action in meta["actions"]["property_name"].items():
                method = node(action["forms"]["href"]["value"])
                node(action["uav_componentOf"]["value"])
                given = [a.Name for a in method.get_child("0:InputArguments").read_value()]
                answer = [a.Name for a in method.get_child("0:OutputArguments").read_value()]
                assert given == list(action["input"]["properties"]["property_name"]), name
                assert answer == list(action["output"]["properties"]["property_name"]) == ["SD_1", "SD_2"], name
        finally:
            client.disconnect()
