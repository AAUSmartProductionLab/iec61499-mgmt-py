"""The filling and stoppering modules against FORTE and the module simulator: module states, every
skill, the IO they drive, and what happens on stop, abort and a fault. All over OPC UA.

    python -m pytest cell/tests/test_filling_stoppering_live.py --module-forte-exe runtime/fbe/build/modules-win/output/bin/forte.exe

Also with --pi-host and --sim-host, as cell/tests/test_module_live.py.
"""
import time
import uuid

import pytest

from test_module_live import E, M, S, STOPPERING_FAST, outputs, ready, running


def in_order(history, *values, timeout=1.0) -> bool:
    """``values`` appear in the recorded ``history`` in this order (other values may lie between);
    waits a moment for the last notifications of the subscription."""
    deadline = time.monotonic() + timeout
    while True:
        it = iter(list(history))
        if all(v in it for v in values):
            return True
        if time.monotonic() > deadline:
            return False
        time.sleep(0.05)


def on_time(sim, name) -> float:
    """Seconds the BOOL output ``name`` was on, the last time it was switched on and off."""
    edges = [(t, v) for t, n, v in sim.trace if n == name]
    on = max(i for i, (_, v) in enumerate(edges) if v)
    return edges[on + 1][0] - edges[on][0]


def settled(sim, wait=0.3):
    """The outputs that are on after the equipment had time to switch off."""
    time.sleep(wait)
    return sim.outputs_on()


# --------------------------------------------------------------------------------------------
# Module states (both modules)
# --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name, overrides", [("filling", None), ("stoppering", STOPPERING_FAST)])
def test_module_states_follow_the_commands_of_its_occupant(request, tmp_path, name, overrides):
    with running(request, tmp_path, name, overrides) as (sim, ua):
        a, b = str(uuid.uuid4()), str(uuid.uuid4())

        def refused(error, *commands, session=a):
            for command in commands:
                assert ua.call(f"Module/{command}", session) == [False, error], command

        refused(E["NotPermitted"], "Reset", "Abort")                        # nobody occupies the module
        assert ua.call("Occupation/Occupy", a) == [True, 0]
        refused(E["NotReady"], "Start", "Stop", "Clear")                    # Stopped
        assert ua.call("Module/Reset", a) == [True, 0]
        ua.expect("Module/State", M["Idle"], timeout=15)
        refused(E["NotReady"], "Reset", "Clear")                            # Idle
        assert ua.call("Module/Start", a) == [True, 0]
        ua.expect("Module/State", M["Execute"])
        refused(E["NotReady"], "Reset", "Start", "Clear")                   # Execute
        refused(E["NotPermitted"], "Stop", "Abort", session=b)              # not the occupant
        assert ua.call("Module/Stop", a) == [True, 0]
        ua.expect("Module/State", M["Stopped"], timeout=10)
        assert ua.call("Module/Reset", a) == [True, 0]
        ua.expect("Module/State", M["Idle"], timeout=15)
        assert ua.call("Module/Start", a) == [True, 0]
        ua.expect("Module/State", M["Execute"])
        assert ua.call("Module/Abort", a) == [True, 0]
        ua.expect("Module/State", M["Aborted"])
        refused(E["NotReady"], "Reset", "Start", "Stop", "Abort")           # Aborted
        assert settled(sim) == []
        assert ua.call("Module/Clear", a) == [True, 0]
        ua.expect("Module/State", M["Stopped"])
        assert sim.shoot_through == 0


# --------------------------------------------------------------------------------------------
# Filling module
# --------------------------------------------------------------------------------------------

@pytest.fixture
def filling(request, tmp_path):
    with running(request, tmp_path, "filling", getattr(request, "param", None)) as (sim, ua):
        yield sim, ua


def test_filling_resetting_and_stopping_bring_the_needle_to_the_top(filling):
    sim, ua = filling
    a = str(uuid.uuid4())
    sim.axes["NeedleAxis"].position = 0.6                                    # left somewhere in between
    ua.expect("Equipment/NeedleAxis/AtTop", False)
    states = ua.record("Module/State")
    assert ua.call("Occupation/Occupy", a) == [True, 0]
    assert ua.call("Module/Reset", a) == [True, 0]
    ua.expect("Module/State", M["Idle"], timeout=8)
    assert ua.value("Equipment/NeedleAxis/AtTop") is True
    assert ua.value("Procedures/Resetting/MoveNeedleUp/State") == S["Succeeded"]
    assert ua.call("Module/Start", a) == [True, 0]
    assert ua.call("Skills/MoveNeedleDown/Start", a) == [True, 0]
    ua.expect("Skills/MoveNeedleDown/State", S["Succeeded"], timeout=6)
    assert ua.call("Module/Stop", a) == [True, 0]                            # the Stopping procedure lifts it
    ua.expect("Module/State", M["Stopped"], timeout=8)
    assert ua.value("Equipment/NeedleAxis/AtTop") is True
    assert in_order(states, M["Resetting"], M["Idle"], M["Execute"], M["Stopping"], M["Stopped"]), states
    assert settled(sim) == [] and sim.shoot_through == 0


def test_filling_needle_skills_drive_boost_brake_and_end_switches(filling):
    sim, ua = filling
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    # Already at the top: succeeds without driving.
    assert ua.call("Skills/MoveNeedleUp/Start", a) == [True, 0]
    ua.expect("Skills/MoveNeedleUp/State", S["Succeeded"])
    assert outputs(sim) == []
    # Down: boost 190, then 140 until the bottom switch, then a short reverse (brake) pulse, then off.
    states = ua.record("Skills/MoveNeedleDown/State")
    assert ua.call("Skills/MoveNeedleDown/Start", a) == [True, 0]
    ua.expect("Skills/MoveNeedleDown/State", S["Succeeded"], timeout=6)
    assert in_order(states, S["Running"], S["Succeeded"]), states
    assert ua.value("Equipment/NeedleAxis/AtBottom") is True and ua.value("Equipment/NeedleAxis/AtTop") is False
    assert sim.position("NeedleAxis") == 1.0
    assert [v for n, v in outputs(sim, "NeedleAxis.Speed")] == [190.0, 140.0, None]
    assert outputs(sim, "NeedleAxis.Down", "NeedleAxis.Up") == [
        ("NeedleAxis.Down", True), ("NeedleAxis.Down", False), ("NeedleAxis.Up", True), ("NeedleAxis.Up", False)]
    assert 0.05 <= on_time(sim, "NeedleAxis.Up") <= 0.3                      # the 100 ms brake pulse
    assert settled(sim) == []
    # Up again, then down without boost (AttachNeedle).
    assert ua.call("Skills/MoveNeedleUp/Start", a) == [True, 0]
    ua.expect("Skills/MoveNeedleUp/State", S["Succeeded"], timeout=6)
    assert ua.value("Equipment/NeedleAxis/AtTop") is True
    sim.trace.clear()
    assert ua.call("Skills/AttachNeedle/Start", a) == [True, 0]
    ua.expect("Skills/AttachNeedle/State", S["Succeeded"], timeout=6)
    assert 190.0 not in [v for n, v in outputs(sim, "NeedleAxis.Speed")]
    assert ua.value("Equipment/NeedleAxis/AtBottom") is True
    assert settled(sim) == [] and sim.shoot_through == 0


def test_filling_scale_skills(filling):
    sim, ua = filling
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    started = time.monotonic()
    assert ua.call("Skills/Tare/Start", a) == [True, 0]
    ua.expect("Skills/Tare/State", S["Running"], timeout=1)
    assert ua.call("Skills/Weigh/Start", a) == [False, E["Busy"]]            # the scale is taken
    ua.expect("Skills/Tare/State", S["Succeeded"], timeout=4)
    assert 1.8 <= time.monotonic() - started <= 3.0                          # tares for 2 s
    sim.values["Scale.Weight"] = 3.25
    assert ua.call("Skills/Weigh/Start", a) == [True, 0]
    ua.expect("Skills/Weigh/State", S["Succeeded"], timeout=2)
    assert ua.value("Skills/Weigh/Results/Weight") == pytest.approx(3.25)
    assert ua.value("Equipment/Scale/Weight") == pytest.approx(3.25)
    assert outputs(sim) == []                                                # the scale has no outputs


def test_filling_dispensing_runs_its_steps_in_order_and_holds_the_needle(filling):
    sim, ua = filling
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    steps = {s: ua.record(f"Skills/Dispensing/Execute/{s}/State") for s in ["MoveNeedleDown", "Dwell", "MoveNeedleUp", "Weigh"]}
    assert ua.call("Skills/Dispensing/Start", a) == [True, 0]
    ua.expect("Skills/Dispensing/Execute/Dwell/State", S["Running"], timeout=6)
    assert ua.value("Equipment/NeedleAxis/AtBottom") is True                # dwelling at the bottom
    assert ua.value("Skills/Dispensing/Execute/MoveNeedleDown/State") == S["Succeeded"]
    assert ua.value("Skills/Dispensing/Execute/MoveNeedleUp/State") == S["Idle"]
    assert ua.call("Skills/MoveNeedleUp/Start", a) == [False, E["Busy"]]    # Dispensing holds the needle
    assert ua.call("Skills/Dispensing/Start", a) == [False, E["Busy"]]
    ua.expect("Skills/Dispensing/State", S["Succeeded"], timeout=8)
    assert all(in_order(h, S["Running"], S["Succeeded"]) for h in steps.values()), steps
    assert ua.value("Skills/Dispensing/Results/Weight") == pytest.approx(2.0)
    assert ua.value("Module/State") == M["Execute"]                         # the module stays in Execute
    # The needle is free again, and the skill runs a second time.
    assert ua.call("Skills/Dispensing/Start", a) == [True, 0]
    ua.expect("Skills/Dispensing/State", S["Succeeded"], timeout=10)
    assert settled(sim) == [] and sim.shoot_through == 0


def test_filling_stop_of_dispensing_lifts_the_needle(filling):
    sim, ua = filling
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    states = ua.record("Skills/Dispensing/State")
    assert ua.call("Skills/Dispensing/Start", a) == [True, 0]
    ua.expect("Skills/Dispensing/Execute/Dwell/State", S["Running"], timeout=6)
    assert ua.call("Skills/Dispensing/Stop", a) == [True, 0]
    ua.expect("Skills/Dispensing/State", S["Failed"], timeout=6)
    assert ua.value("Skills/Dispensing/ErrorID") == E["Interrupted"]
    assert in_order(states, S["Running"], S["Stopping"], S["Failed"]), states
    assert ua.value("Skills/Dispensing/Execute/Dwell/ErrorID") == E["Interrupted"]
    assert ua.value("Skills/Dispensing/Stopping/MoveNeedleUp/State") == S["Succeeded"]
    assert ua.value("Equipment/NeedleAxis/AtTop") is True
    assert ua.value("Module/State") == M["Execute"]
    assert ua.call("Skills/MoveNeedleDown/Start", a) == [True, 0]            # the needle was released
    ua.expect("Skills/MoveNeedleDown/State", S["Succeeded"], timeout=6)


def test_filling_abort_switches_off_and_the_module_recovers(filling):
    sim, ua = filling
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    assert ua.call("Skills/Dispensing/Start", a) == [True, 0]
    ua.expect("Skills/Dispensing/State", S["Running"], timeout=1)
    time.sleep(0.8)                                                          # the needle is on its way down
    assert sim.outputs_on() != []
    assert ua.call("Module/Abort", a) == [True, 0]
    ua.expect("Module/State", M["Aborted"])
    ua.expect("Skills/Dispensing/State", S["Aborted"])
    ua.expect("Skills/Dispensing/Execute/MoveNeedleDown/State", S["Aborted"])
    assert settled(sim) == []
    assert 0.0 < sim.position("NeedleAxis") < 1.0                            # stopped where it was
    assert ua.call("Skills/Dispensing/Start", a) == [False, E["NotReady"]]
    # Clear, reset (the needle goes back up) and run again.
    assert ua.call("Module/Clear", a) == [True, 0]
    ua.expect("Module/State", M["Stopped"])
    ua.expect("Skills/Dispensing/State", S["Idle"])
    assert ua.call("Module/Reset", a) == [True, 0]
    ua.expect("Module/State", M["Idle"], timeout=8)
    assert ua.value("Equipment/NeedleAxis/AtTop") is True
    assert ua.call("Module/Start", a) == [True, 0]
    ua.expect("Module/State", M["Execute"])
    assert ua.call("Skills/Dispensing/Start", a) == [True, 0]
    ua.expect("Skills/Dispensing/State", S["Succeeded"], timeout=10)
    assert sim.shoot_through == 0


@pytest.mark.parametrize("filling", [{"MoveNeedleDown.Timeout": "T#3s", "Dispensing.Execute.MoveNeedleDown.Timeout": "T#3s"}],
                         indirect=True)
def test_filling_a_needle_that_never_arrives_fails_the_skill_and_frees_the_needle(filling):
    sim, ua = filling
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    sim.axes["NeedleAxis"].travel_s = 1e9                                    # e.g. a blocked axis
    assert ua.call("Skills/MoveNeedleDown/Start", a) == [True, 0]
    ua.expect("Skills/MoveNeedleDown/State", S["Failed"], timeout=5)
    assert ua.value("Skills/MoveNeedleDown/ErrorID") == E["Timeout"]
    assert settled(sim) == []
    # Inside the module level skill: it fails with the step's error and gives the needle up.
    assert ua.call("Skills/Dispensing/Start", a) == [True, 0]
    ua.expect("Skills/Dispensing/State", S["Failed"], timeout=5)
    assert ua.value("Skills/Dispensing/ErrorID") == E["Timeout"]
    assert ua.value("Skills/Dispensing/Execute/Dwell/State") == S["Idle"]   # the later steps did not run
    assert settled(sim) == []
    assert ua.value("Module/State") == M["Execute"]
    sim.axes["NeedleAxis"].travel_s = 2.0
    assert ua.call("Skills/MoveNeedleDown/Start", a) == [True, 0]            # free again
    ua.expect("Skills/MoveNeedleDown/State", S["Succeeded"], timeout=6)


# --------------------------------------------------------------------------------------------
# Stoppering module
# --------------------------------------------------------------------------------------------

@pytest.fixture
def stoppering(request, tmp_path):
    overrides = {**STOPPERING_FAST, **getattr(request, "param", {})}
    with running(request, tmp_path, "stoppering", overrides) as (sim, ua):
        a = str(uuid.uuid4())
        assert ua.call("Occupation/Occupy", a) == [True, 0]
        assert ua.call("Module/Reset", a) == [True, 0]
        ua.expect("Module/State", M["Idle"], timeout=15)
        yield sim, ua, a


def start(sim, ua, a):
    assert ua.call("Module/Start", a) == [True, 0]
    ua.expect("Module/State", M["Execute"])
    time.sleep(0.1)
    sim.trace.clear()


def test_stoppering_resetting_homes_the_equipment(stoppering):
    sim, ua, a = stoppering
    for step in ["ArmMiddle", "ArmHome", "RetractPlunger", "LowerPiston", "RaisePiston"]:
        assert ua.value(f"Procedures/Resetting/{step}/State") == S["Succeeded"], step
    angles = [round(v) for n, v in outputs(sim, "StopperArm.Angle") if v is not None]
    assert angles == [90, 120]
    order = [n for n, v in outputs(sim, "Plunger.Retract", "Piston.Down", "Piston.Up") if v]
    assert order == ["Plunger.Retract", "Piston.Down", "Piston.Up"]
    assert 0.3 <= on_time(sim, "Piston.Up") <= 0.9                           # raised for 0.5 s (clearance)
    assert 0.5 < sim.position("Piston") < 1.0
    assert settled(sim) == [] and sim.shoot_through == 0
    # Skills are refused until the module is started.
    assert ua.call("Skills/LowerPiston/Start", a) == [False, E["NotReady"]]


def test_stoppering_piston_skills(stoppering):
    sim, ua, a = stoppering
    start(sim, ua, a)
    assert ua.value("Equipment/Piston/AtLimit") is False
    assert ua.call("Skills/LowerPiston/Start", a) == [True, 0]
    ua.expect("Skills/LowerPiston/State", S["Running"], timeout=1)
    assert ua.call("Skills/RaisePiston/Start", a, 1.0) == [False, E["Busy"]]   # the piston is taken
    ua.expect("Skills/LowerPiston/State", S["Succeeded"], timeout=5)
    assert ua.value("Equipment/Piston/AtLimit") is True and sim.position("Piston") == 1.0
    assert outputs(sim) == [("Piston.Down", True), ("Piston.Speed", 200.0), ("Piston.Down", False), ("Piston.Speed", None)]
    # Up for a given time, with its range checked.
    assert ua.value("Skills/RaisePiston/Parameters/Duration") == 2.0
    assert ua.call("Skills/RaisePiston/Start", a, 11.0) == [False, E["OutOfRange"]]
    assert ua.call("Skills/RaisePiston/Start", a, -1.0) == [False, E["OutOfRange"]]
    assert ua.call("Skills/RaisePiston/Start", a, 0.6) == [True, 0]
    ua.expect("Skills/RaisePiston/State", S["Succeeded"], timeout=3)
    assert ua.value("Skills/RaisePiston/Parameters/Duration") == 0.6
    assert 0.5 <= on_time(sim, "Piston.Up") <= 0.9
    assert sim.position("Piston") == pytest.approx(1.0 - 0.6 / 3.0, abs=0.08)
    ua.expect("Equipment/Piston/AtLimit", False)
    assert settled(sim) == [] and sim.shoot_through == 0


def test_stoppering_plunger_and_arm_run_at_the_same_time(stoppering):
    sim, ua, a = stoppering
    start(sim, ua, a)
    assert ua.call("Skills/ExtendPlunger/Start", a, 1.0) == [True, 0]
    assert ua.call("Skills/MoveArm/Start", a, 45.0, 0.5) == [True, 0]       # other equipment: not refused
    ua.expect("Skills/ExtendPlunger/State", S["Running"], timeout=1)
    assert ua.value("Skills/MoveArm/State") == S["Running"]
    assert ua.call("Skills/RetractPlunger/Start", a, 1.0) == [False, E["Busy"]]
    ua.expect("Skills/MoveArm/State", S["Succeeded"], timeout=2)
    ua.expect("Skills/ExtendPlunger/State", S["Succeeded"], timeout=2)
    assert [v if v is None else round(v) for n, v in outputs(sim, "StopperArm.Angle")] == [45, None]   # then detached
    assert 0.8 <= on_time(sim, "Plunger.Extend") <= 1.3
    assert sim.position("Plunger") == pytest.approx(1.0 / 8.0, abs=0.03)
    assert ua.call("Skills/MoveArm/Start", a, 181.0, 0.5) == [False, E["OutOfRange"]]
    assert ua.call("Skills/RetractPlunger/Start", a, 1.5) == [True, 0]
    ua.expect("Skills/RetractPlunger/State", S["Succeeded"], timeout=3)
    assert sim.position("Plunger") == 0.0
    assert sim.shoot_through == 0


def test_stoppering_stop_and_abort_in_the_middle_of_the_cycle(stoppering):
    sim, ua, a = stoppering
    start(sim, ua, a)
    states = ua.record("Skills/Stoppering/State")
    assert ua.call("Skills/Stoppering/Start", a) == [True, 0]
    ua.expect("Skills/Stoppering/Execute/ExtendPlunger/State", S["Running"], timeout=8)
    assert ua.value("Skills/Stoppering/Execute/ArmOut/State") == S["Succeeded"]
    assert ua.call("Skills/Stoppering/Stop", a) == [True, 0]
    ua.expect("Skills/Stoppering/State", S["Failed"], timeout=3)
    assert ua.value("Skills/Stoppering/ErrorID") == E["Interrupted"]
    assert in_order(states, S["Running"], S["Failed"]), states             # no stop sequence: Stopping is instant
    assert ua.value("Skills/Stoppering/Execute/RetractPlunger/State") == S["Idle"]
    assert "Plunger.Extend" not in settled(sim)
    assert ua.value("Module/State") == M["Execute"]
    # Again, and this time the module aborts: everything off, the servo without pulses.
    assert ua.call("Skills/Stoppering/Start", a) == [True, 0]
    ua.expect("Skills/Stoppering/Execute/ArmIn/State", S["Running"], timeout=8)
    assert sim.angle("StopperArm") is not None
    assert ua.call("Module/Abort", a) == [True, 0]
    ua.expect("Module/State", M["Aborted"])
    ua.expect("Skills/Stoppering/State", S["Aborted"])
    assert settled(sim) == [] and sim.angle("StopperArm") is None
    assert ua.call("Module/Clear", a) == [True, 0]
    ua.expect("Skills/Stoppering/State", S["Idle"])
    assert sim.shoot_through == 0


@pytest.mark.parametrize("stoppering", [{"LowerPiston.Timeout": "T#2s"}], indirect=True)
def test_stoppering_a_piston_that_never_reaches_its_switch_times_out(stoppering):
    sim, ua, a = stoppering
    start(sim, ua, a)
    assert ua.call("Skills/RaisePiston/Start", a, 0.5) == [True, 0]
    ua.expect("Skills/RaisePiston/State", S["Succeeded"], timeout=3)
    sim.axes["Piston"].travel_s = 1e9
    assert ua.call("Skills/LowerPiston/Start", a) == [True, 0]
    ua.expect("Skills/LowerPiston/State", S["Failed"], timeout=4)
    assert ua.value("Skills/LowerPiston/ErrorID") == E["Timeout"]
    assert settled(sim) == []
    assert ua.value("Module/State") == M["Execute"]
    assert ua.call("Skills/RaisePiston/Start", a, 0.5) == [True, 0]          # the piston is free again
    ua.expect("Skills/RaisePiston/State", S["Succeeded"], timeout=3)
