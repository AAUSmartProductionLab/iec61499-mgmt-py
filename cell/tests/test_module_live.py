"""Generated modules (cell/modules/*.yaml) against FORTE and the module simulator (cell/sim/module_sim.py).

    runtime/build-modules.ps1
    python -m pytest cell/tests/test_module_live.py --module-forte-exe runtime/fbe/build/modules-win/output/bin/forte.exe

On a Raspberry Pi instead (FORTE in its container, installed with deploy/pi.py install): each
test deploys the module there as the boot file and the Pi's FORTE reaches the simulator on this
machine over Modbus TCP; no header pin is used.

    python -m pytest cell/tests/test_module_live.py --pi-host 192.168.0.191 --sim-host 192.168.0.131
"""
from contextlib import contextmanager
from pathlib import Path
import sys
import time
import uuid

import pytest

from conftest import free_port, launch_forte
from iec61499_mgmt.bootfile import deployment
from iec61499_mgmt.protocol import Client
from iec61499_mgmt.sysfile import load_application
from modgen import SPECS, load, system_file
from modgen.library import ERRORS, SKILL_STATES, STATES
from modgen.module import app_name

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cell" / "sim"))
sys.path.insert(0, str(ROOT / "deploy"))
from module_sim import ModuleSim, SimServer  # noqa: E402
from module_ua import ModuleUa  # noqa: E402,F401  (also used by other live tests through this module)

S, E, M = SKILL_STATES, ERRORS, STATES
# Looked at afterwards, a skill that succeeded may be back in Idle (it stays Succeeded for 1.5 s).
DONE = (S["Succeeded"], S["Idle"])


@contextmanager
def running(request, tmp_path, spec_name, overrides=None):
    """Simulator + FORTE with the deployed module (first target); yields (sim, ua)."""
    pi = request.config.getoption("--pi-host")
    if pi:
        with running_on_pi(request, pi, spec_name, overrides) as result:
            yield result
        return
    exe = request.config.getoption("--module-forte-exe")
    if not exe:
        pytest.skip("Pass --module-forte-exe to run the generated modules against FORTE")
    exe = Path(exe).resolve(strict=True)
    spec = load(SPECS / f"{spec_name}.yaml")
    sim = ModuleSim(spec)
    modbus, ua_port = free_port(), free_port()
    app = load_application(system_file(spec.project), app_name(spec, "pc"))
    ports = {k: v.replace(f":{spec.modbus.port}:", f":{modbus}:") for k, v in app.parameters.items()
             if k.endswith("_Modbus")}
    with SimServer(sim, port=modbus), launch_forte(exe, tmp_path, None, ["-op", str(ua_port)]) as port, \
            Client("127.0.0.1", port) as client:
        for command in deployment(app, overrides={**ports, **(overrides or {})}):
            client.execute(command)
        ua = ModuleUa(ua_port, spec.module)
        try:
            ua.expect("Module/State", M["Stopped"])
            # FORTE's Modbus client drops writes until it is connected (no Online signal yet, R6).
            time.sleep(1.0)
            yield sim, ua
        finally:
            ua.close()


@contextmanager
def running_on_pi(request, host, spec_name, overrides=None):
    """The module's PC application on the Pi's FORTE, its Modbus IO pointed at the simulator here."""
    import pi as pitool
    sim_host = request.config.getoption("--sim-host")
    if not sim_host:
        pytest.skip("Pass --sim-host (this machine's address as the Pi sees it) with --pi-host")
    spec = load(SPECS / f"{spec_name}.yaml")
    sim = ModuleSim(spec)
    modbus = free_port()
    app = load_application(system_file(spec.project), app_name(spec, "pc"))
    endpoint = f"{spec.modbus.host}:{spec.modbus.port}:"
    remote = {k: v.replace(endpoint, f"{sim_host}:{modbus}:") for k, v in app.parameters.items()
              if k.endswith("_Modbus")}
    user = request.config.getoption("--pi-user") or load(SPECS / "filling.yaml").targets["pi"].user
    args = type("Args", (), {"host": host, "user": user, "port": 61499})()
    with SimServer(sim, host="0.0.0.0", port=modbus):
        pitool.ssh(args, "cat > ~/forte/boot/forte.fboot && cd ~/forte && docker compose restart",
                   stdin=pitool.boot_file(deployment(app, overrides={**remote, **(overrides or {})})))
        pitool.wait_port(host, 61499)
        ua = ModuleUa(4840, spec.module, host)
        try:
            ua.expect("Module/State", M["Stopped"], timeout=10)
            time.sleep(1.0)                                   # Modbus clients connect (R6)
            yield sim, ua
        finally:
            ua.close()


def outputs(sim, *names):
    """Output changes recorded by the simulator: (output, value), optionally only for ``names``."""
    return [(n, v) for _, n, v in sim.trace if not names or n in names]


def ready(sim, ua, session):
    """Occupy, reset (Resetting procedure) and start the module as ``session``; then clear the
    simulator's output trace, so a test sees only what its own skills switch."""
    assert ua.call("Occupation/Occupy", session) == [True, 0]
    assert ua.call("Module/Reset", session) == [True, 0]
    ua.expect("Module/State", M["Idle"], timeout=15)
    assert ua.call("Module/Start", session) == [True, 0]
    ua.expect("Module/State", M["Execute"])
    time.sleep(0.1)
    sim.trace.clear()


# --------------------------------------------------------------------------------------------
# Filler: the generator's test module
# --------------------------------------------------------------------------------------------

@pytest.fixture
def filler(request, tmp_path):
    with running(request, tmp_path, "filler", getattr(request, "param", None)) as (sim, ua):
        yield sim, ua


def test_occupation_and_module_state_manager(filler):
    sim, ua = filler
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    assert ua.call("Occupation/Occupy", a) == [True, 0]
    assert ua.call("Occupation/Occupy", a) == [True, 0]                    # idempotent for the owner
    assert ua.call("Occupation/Occupy", b) == [False, E["NotPermitted"]]
    ua.expect("Occupation/Occupied", True)
    assert ua.call("Module/Start", a) == [False, E["NotReady"]]            # Stopped, not Idle
    assert ua.call("Module/Reset", b) == [False, E["NotPermitted"]]
    assert ua.call("Module/Reset", a) == [True, 0]
    ua.expect("Module/State", M["Idle"])
    # Skills are refused unless the module is in Execute.
    assert ua.call("Skills/MoveNeedleDown/Start", a, 20.0) == [False, E["NotReady"]]
    assert ua.call("Module/Start", a) == [True, 0]
    ua.expect("Module/State", M["Execute"])
    # Hand-over: only the owner releases; the old session loses all rights.
    assert ua.call("Occupation/Release", b) == [False, E["NotPermitted"]]
    assert ua.call("Occupation/Release", a) == [True, 0]
    assert ua.call("Skills/MoveNeedleDown/Start", a, 20.0) == [False, E["NotPermitted"]]
    assert ua.call("Occupation/Occupy", b) == [True, 0]
    assert sim.shoot_through == 0


def test_skill_primitive_with_parameters(filler):
    sim, ua = filler
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    ready(sim, ua, a)
    skill = "Skills/MoveNeedleDown"
    assert ua.value(f"{skill}/Parameters/Distance") == 50.0                 # the instance's default
    assert ua.call(f"{skill}/Start", b, 20.0) == [False, E["NotPermitted"]]
    assert ua.call(f"{skill}/Start", a, 80.0) == [False, E["OutOfRange"]]
    assert ua.call(f"{skill}/Start", a, 20.0) == [True, 0]
    ua.expect(f"{skill}/State", S["Running"], timeout=1)
    assert ua.call(f"{skill}/Start", a, 30.0) == [False, E["Busy"]]
    ua.expect(f"{skill}/State", S["Succeeded"], timeout=3)
    ua.expect(f"{skill}/Parameters/Distance", 20.0)
    assert 20.0 <= sim.position("NeedleAxis") * 50 <= 20.8                 # 10 ms poll, 10 ms simulator step
    # Start again from Succeeded without Reset; already at the target: succeeds without driving.
    assert ua.call(f"{skill}/Start", a, 20.0) == [True, 0]
    ua.expect(f"{skill}/State", S["Succeeded"])
    assert outputs(sim) == [("NeedleAxis.Down", True), ("NeedleAxis.Down", False)]
    assert ua.call("Skills/MoveNeedleUp/Start", a) == [True, 0]
    ua.expect("Skills/MoveNeedleUp/State", S["Succeeded"], timeout=3)
    assert ua.value("Equipment/NeedleAxis/AtTop") is True


def test_module_level_skill_holds_its_equipment(filler):
    sim, ua = filler
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    assert ua.call("Skills/Fill/Start", a, 30.0) == [True, 0]
    ua.expect("Skills/Fill/State", S["Running"], timeout=1)
    time.sleep(0.3)
    # The needle belongs to Fill between its children: other skills are refused.
    assert ua.call("Skills/MoveNeedleUp/Start", a) == [False, E["Busy"]]
    ua.expect("Skills/Fill/State", S["Succeeded"], timeout=6)
    assert ua.value("Skills/Fill/Parameters/Depth") == 30.0
    assert outputs(sim) == [("NeedleAxis.Down", True), ("NeedleAxis.Down", False),
                            ("NeedleAxis.Up", True), ("NeedleAxis.Up", False)]
    # Released at the end.
    assert ua.call("Skills/MoveNeedleDown/Start", a, 10.0) == [True, 0]
    ua.expect("Skills/MoveNeedleDown/State", S["Succeeded"], timeout=3)
    assert sim.shoot_through == 0


def test_stop_interrupts_a_module_level_skill_and_runs_its_stop_sequence(filler):
    sim, ua = filler
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    assert ua.call("Skills/Fill/Start", a, 50.0) == [True, 0]
    time.sleep(0.8)
    assert ua.call("Skills/Fill/Stop", a) == [True, 0]
    ua.expect("Skills/Fill/State", S["Failed"], timeout=5)
    assert ua.value("Skills/Fill/ErrorID") == E["Interrupted"]
    assert ua.value("Skills/Fill/Execute/MoveNeedleDown/ErrorID") == E["Interrupted"]
    assert ua.value("Equipment/NeedleAxis/AtTop") is True                   # the stop sequence lifted it
    assert ua.call("Skills/Fill/Stop", a) == [False, E["NotReady"]]        # nothing running


def test_module_stop_halts_running_skills_and_runs_the_stopping_procedure(filler):
    sim, ua = filler
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    assert ua.call("Skills/MoveNeedleDown/Start", a, 50.0) == [True, 0]
    time.sleep(0.8)
    assert ua.call("Module/Stop", a) == [True, 0]
    ua.expect("Module/State", M["Stopped"], timeout=6)
    assert ua.value("Skills/MoveNeedleDown/State") == S["Failed"]
    assert ua.value("Skills/MoveNeedleDown/ErrorID") == E["Interrupted"]
    assert ua.value("Procedures/Stopping/MoveNeedleUp/State") in DONE
    assert ua.value("Equipment/NeedleAxis/AtTop") is True
    assert ua.call("Skills/MoveNeedleUp/Start", a) == [False, E["NotReady"]]


@pytest.mark.parametrize("filler", [{"MoveNeedleDown.Timeout": "T#3s"}], indirect=True)
def test_timeout_fails_the_skill_and_abort_switches_everything_off(filler):
    sim, ua = filler
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    sim.axes["NeedleAxis"].travel_s = 1e9                                  # the needle never arrives
    assert ua.call("Skills/MoveNeedleDown/Start", a, 50.0) == [True, 0]
    ua.expect("Skills/MoveNeedleDown/State", S["Failed"], timeout=5)
    assert ua.value("Skills/MoveNeedleDown/ErrorID") == E["Timeout"]
    assert ua.value("Module/State") == M["Execute"]                        # a failed skill does not stop the module
    assert ua.call("Skills/MoveNeedleDown/Start", a, 50.0) == [True, 0]      # again, from Failed
    ua.expect("Skills/MoveNeedleDown/State", S["Running"], timeout=1)
    assert ua.call("Module/Abort", a) == [True, 0]
    ua.expect("Module/State", M["Aborted"])
    ua.expect("Skills/MoveNeedleDown/State", S["Aborted"])
    ua.expect("Skills/MoveNeedleUp/State", S["Aborted"])
    time.sleep(0.2)
    assert sim.outputs_on() == []
    assert ua.call("Skills/MoveNeedleUp/Start", a) == [False, E["NotReady"]]
    assert ua.call("Module/Clear", a) == [True, 0]
    ua.expect("Module/State", M["Stopped"])
    ua.expect("Skills/MoveNeedleUp/State", S["Idle"])


# --------------------------------------------------------------------------------------------
# The modules ported from the ESP32 stations
# --------------------------------------------------------------------------------------------

def test_filling_module_dispenses_and_weighs(request, tmp_path):
    with running(request, tmp_path, "filling") as (sim, ua):
        a = str(uuid.uuid4())
        ready(sim, ua, a)                                     # Resetting: needle already at the top
        assert ua.call("Skills/Dispensing/Start", a, 1.0) == [True, 0]
        ua.expect("Skills/Dispensing/State", S["Succeeded"], timeout=10)
        assert ua.value("Skills/Dispensing/Results/Weight") == pytest.approx(2.0)
        assert ua.value("Equipment/NeedleAxis/AtTop") is True
        speed = [v for n, v in outputs(sim, "NeedleAxis.Speed")]
        # Start boost then the working speed, for both moves; the brake pulses in between.
        assert speed[:2] == [190.0, 140.0] and 190.0 in speed[2:] and speed[-1] is None
        assert sim.shoot_through == 0
        assert ua.call("Skills/Tare/Start", a) == [True, 0]
        ua.expect("Skills/Tare/State", S["Succeeded"], timeout=4)


STOPPERING_FAST = {"Stoppering.Execute.ArmIn.Settle": "0.3", "Stoppering.Execute.ArmOut.Settle": "0.3",
                   "Stoppering.Execute.ExtendPlunger.Duration": "1.0",
                   "Stoppering.Execute.RetractPlunger.Duration": "1.0",
                   "Stoppering.Execute.RaisePiston.Duration": "0.5",
                   "Resetting.ArmMiddle.Settle": "0.3", "Resetting.ArmHome.Settle": "0.3",
                   "Resetting.RetractPlunger.Duration": "0.5", "Resetting.RaisePiston.Duration": "0.5"}


def test_stoppering_module_homes_and_stoppers(request, tmp_path):
    with running(request, tmp_path, "stoppering", STOPPERING_FAST) as (sim, ua):
        a = str(uuid.uuid4())
        assert ua.call("Occupation/Occupy", a) == [True, 0]
        assert ua.call("Module/Reset", a) == [True, 0]
        ua.expect("Module/State", M["Idle"], timeout=15)
        angles = [v for n, v in outputs(sim, "StopperArm.Angle")]
        assert [round(v) for v in angles if v is not None][:2] == [90, 120]   # homing: servo 90 then 120
        assert ua.call("Module/Start", a) == [True, 0]
        ua.expect("Module/State", M["Execute"])
        assert ua.call("Skills/Stoppering/Start", a) == [True, 0]
        ua.expect("Skills/Stoppering/State", S["Succeeded"], timeout=15)
        angles = [round(v) for n, v in outputs(sim, "StopperArm.Angle") if v is not None]
        assert angles[-2:] == [1, 121]
        order = [n for n, v in outputs(sim, "Piston.Down", "Piston.Up", "Plunger.Extend", "Plunger.Retract") if v]
        assert order[-4:] == ["Piston.Down", "Plunger.Extend", "Plunger.Retract", "Piston.Up"]
        assert sim.shoot_through == 0
        # A skill primitive with an argument, called directly.
        assert ua.call("Skills/MoveArm/Start", a, 45.0, 0.2) == [True, 0]
        ua.expect("Skills/MoveArm/State", S["Succeeded"], timeout=3)
        assert round([v for n, v in outputs(sim, "StopperArm.Angle") if v is not None][-1]) == 45
