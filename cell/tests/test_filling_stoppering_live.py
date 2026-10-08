"""The filling and stoppering modules against FORTE and the module simulator: module states, every
skill, the IO they drive, and what happens on stop, abort and a fault. All over OPC UA.

    python -m pytest cell/tests/test_filling_stoppering_live.py --module-forte-exe runtime/fbe/build/modules-win/output/bin/forte.exe

Also with --pi-host and --sim-host, as cell/tests/test_module_live.py.
"""
import time
import uuid

import pytest

from test_module_live import DONE, E, M, S, outputs, ready, running


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

@pytest.mark.parametrize("name", ["filling", "stoppering"])
def test_module_states_follow_the_commands_of_its_occupant(request, tmp_path, name):
    with running(request, tmp_path, name) as (sim, ua):
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


AXIS = "Equipment/LinearAxis"


def at(sim, ua, position, tolerance=1.5):
    """The axis says it is at ``position``, and the simulated one is there too (it is not measured:
    the difference is what starting and stopping late costs at 20 mm/s)."""
    return (ua.value(f"{AXIS}/ActualPosition") == pytest.approx(position, abs=0.001)
            and sim.position("LinearAxis") == pytest.approx(position, abs=tolerance))


def test_filling_resetting_finds_home_and_stopping_returns_there(filling):
    sim, ua = filling
    a = str(uuid.uuid4())
    assert sim.position("LinearAxis") == 15.0                                # left somewhere in between
    ua.expect(f"{AXIS}/AtHome", False)
    assert ua.value(f"{AXIS}/Homed") is False                                # the controller does not know where
    states = ua.record("Module/State")
    assert ua.call("Occupation/Occupy", a) == [True, 0]
    assert ua.call("Module/Reset", a) == [True, 0]
    ua.expect("Module/State", M["Idle"], timeout=10)
    assert ua.value(f"{AXIS}/AtHome") is True and ua.value(f"{AXIS}/Homed") is True
    assert ua.value(f"{AXIS}/ActualPosition") == 0.0 and sim.position("LinearAxis") == 0.0
    assert ua.value("Procedures/Resetting/Home/State") in DONE
    assert ua.value("Procedures/Resetting/Tare/State") in DONE               # the scale is tared with it
    assert ua.call("Module/Start", a) == [True, 0]
    assert ua.call("Skills/MoveAxis/Start", a, 30.0) == [True, 0]
    ua.expect("Skills/MoveAxis/State", S["Succeeded"], timeout=6)
    assert at(sim, ua, 30.0)
    assert ua.call("Module/Stop", a) == [True, 0]                            # the Stopping procedure homes it
    ua.expect("Module/State", M["Stopped"], timeout=8)
    assert ua.value(f"{AXIS}/AtHome") is True and sim.position("LinearAxis") == 0.0
    assert in_order(states, M["Resetting"], M["Idle"], M["Execute"], M["Stopping"], M["Stopped"]), states
    assert settled(sim) == []


def test_filling_the_axis_moves_to_a_position_from_either_side(filling):
    """A stepper with a limit switch: the controller knows the position from the time it has stepped."""
    sim, ua = filling
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    # Already there: succeeds without driving.
    assert ua.call("Skills/MoveAxis/Start", a, 0.0) == [True, 0]
    ua.expect("Skills/MoveAxis/State", S["Succeeded"])
    assert outputs(sim) == []
    assert ua.call("Skills/MoveAxis/Start", a, 80.0) == [False, E["OutOfRange"]]       # beyond its travel
    # Down to 40 mm: enabled, direction down, stepping; then everything off.
    states, moving = ua.record("Skills/MoveAxis/State"), ua.record(f"{AXIS}/Moving")
    started = time.monotonic()
    assert ua.call("Skills/MoveAxis/Start", a, 40.0) == [True, 0]
    ua.expect("Skills/MoveAxis/State", S["Succeeded"], timeout=6)
    assert 1.7 <= time.monotonic() - started <= 2.8                          # 40 mm at 20 mm/s
    assert in_order(states, S["Running"], S["Succeeded"]) and in_order(moving, True, False)
    assert at(sim, ua, 40.0)
    assert ua.value("Skills/MoveAxis/Parameters/Position") == 40.0
    assert outputs(sim, "LinearAxis.Down") == [("LinearAxis.Down", True), ("LinearAxis.Down", False)]
    assert [v for n, v in outputs(sim, "LinearAxis.Step")] == [50.0, None]
    assert settled(sim) == []
    # Back up to 10 mm: the same skill, the other direction.
    sim.trace.clear()
    assert ua.call("Skills/MoveAxis/Start", a, 10.0) == [True, 0]
    ua.expect("Skills/MoveAxis/State", S["Succeeded"], timeout=6)
    assert at(sim, ua, 10.0)
    assert outputs(sim, "LinearAxis.Down") == [] and [v for n, v in outputs(sim, "LinearAxis.Step")] == [50.0, None]
    # While it moves, the position on the way is published.
    seen = ua.record(f"{AXIS}/ActualPosition")
    assert ua.call("Skills/MoveAxis/Start", a, 50.0) == [True, 0]
    ua.expect("Skills/MoveAxis/State", S["Succeeded"], timeout=6)
    between = [v for v in seen if 10.0 < v < 50.0]
    assert len(between) >= 3 and between == sorted(between), seen
    assert settled(sim) == []


def test_filling_a_move_cut_short_leaves_the_axis_where_the_time_puts_it(filling):
    sim, ua = filling
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    assert ua.call("Skills/MoveAxis/Start", a, 50.0) == [True, 0]
    ua.expect("Skills/MoveAxis/State", S["Running"], timeout=1)
    time.sleep(1.0)
    assert ua.call("Skills/MoveAxis/Stop", a) == [True, 0]
    ua.expect("Skills/MoveAxis/State", S["Failed"], timeout=3)
    assert ua.value("Skills/MoveAxis/ErrorID") == E["Interrupted"]
    assert settled(sim) == []
    stopped = sim.position("LinearAxis")
    assert 12.0 < stopped < 35.0
    ua.expect(f"{AXIS}/Moving", False)
    assert ua.value(f"{AXIS}/ActualPosition") == pytest.approx(stopped, abs=2.0)        # by time, not measured
    assert ua.value(f"{AXIS}/Homed") is True
    # From there on to a position, as from any other.
    assert ua.call("Skills/MoveAxis/Start", a, 5.0) == [True, 0]
    ua.expect("Skills/MoveAxis/State", S["Succeeded"], timeout=6)
    assert at(sim, ua, 5.0, tolerance=3.0)


def test_filling_an_axis_that_lost_its_reference_has_to_home_first(filling):
    sim, ua = filling
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    assert ua.call("Skills/MoveAxis/Start", a, 40.0) == [True, 0]
    ua.expect("Skills/MoveAxis/State", S["Succeeded"], timeout=6)
    # Homing cut short: it was driven without counting, so where it is is no longer known.
    assert ua.call("Skills/Home/Start", a) == [True, 0]
    ua.expect("Skills/Home/State", S["Running"], timeout=1)
    time.sleep(0.5)
    assert ua.call("Skills/Home/Stop", a) == [True, 0]
    ua.expect("Skills/Home/State", S["Failed"], timeout=3)
    ua.expect(f"{AXIS}/Homed", False)
    assert ua.call("Skills/MoveAxis/Start", a, 10.0) == [True, 0]
    ua.expect("Skills/MoveAxis/State", S["Failed"], timeout=3)
    assert ua.value("Skills/MoveAxis/ErrorID") == E["PreconditionViolated"]
    assert settled(sim) == [] and sim.position("LinearAxis") > 20.0          # it did not move
    assert ua.call("Skills/Home/Start", a) == [True, 0]
    ua.expect("Skills/Home/State", S["Succeeded"], timeout=6)
    assert ua.value(f"{AXIS}/Homed") is True and ua.value(f"{AXIS}/ActualPosition") == 0.0
    assert ua.call("Skills/MoveAxis/Start", a, 10.0) == [True, 0]
    ua.expect("Skills/MoveAxis/State", S["Succeeded"], timeout=6)
    assert at(sim, ua, 10.0)


def test_a_skill_shows_succeeded_for_a_moment_then_is_idle_again(filling):
    sim, ua = filling
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    states = ua.record("Skills/Weigh/State")
    assert ua.call("Skills/Weigh/Start", a) == [True, 0]
    ua.expect("Skills/Weigh/State", S["Succeeded"], timeout=2)
    succeeded = time.monotonic()
    ua.expect("Skills/Weigh/State", S["Idle"], timeout=3)
    assert 1.2 <= time.monotonic() - succeeded <= 2.2                        # Succeeded for 1.5 s
    assert in_order(states, S["Running"], S["Succeeded"], S["Idle"]), states
    assert ua.value("Skills/Weigh/ErrorID") == 0
    # Started again while it shows Succeeded: the earlier success no longer sends it to Idle.
    assert ua.call("Skills/Tare/Start", a) == [True, 0]
    ua.expect("Skills/Tare/State", S["Succeeded"], timeout=4)
    assert ua.call("Skills/Tare/Start", a) == [True, 0]                      # tares for 2 s
    ua.expect("Skills/Tare/State", S["Running"], timeout=1)
    time.sleep(1.7)                                                          # past the first success's 1.5 s
    assert ua.value("Skills/Tare/State") == S["Running"]
    ua.expect("Skills/Tare/State", S["Succeeded"], timeout=2)
    ua.expect("Skills/Tare/State", S["Idle"], timeout=3)
    # A failure stays until the next start.
    assert ua.call("Skills/MoveAxis/Start", a, 50.0) == [True, 0]
    ua.expect("Skills/MoveAxis/State", S["Running"], timeout=1)
    assert ua.call("Skills/MoveAxis/Stop", a) == [True, 0]
    ua.expect("Skills/MoveAxis/State", S["Failed"], timeout=3)
    time.sleep(2.0)
    assert ua.value("Skills/MoveAxis/State") == S["Failed"]


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


def test_filling_the_pump_dispenses_on_its_own_and_for_the_volume(filling):
    """Dispense is a skill like any other. No pump is wired yet: the volume is a time at the flow rate."""
    sim, ua = filling
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    assert ua.call("Skills/Dispense/Start", a, 20.0, 1.0) == [False, E["OutOfRange"]]
    started = time.monotonic()
    assert ua.call("Skills/Dispense/Start", a, 3.0, 2.0) == [True, 0]        # 3 mL at 2 mL/s
    ua.expect("Skills/Dispense/State", S["Running"], timeout=1)
    assert ua.call("Skills/Dispensing/Start", a, 1.0) == [True, 0]           # its needle goes down meanwhile
    ua.expect("Skills/Dispense/State", S["Succeeded"], timeout=4)
    assert 1.2 <= time.monotonic() - started <= 2.2
    assert (ua.value("Skills/Dispense/Parameters/Volume"), ua.value("Skills/Dispense/Parameters/FlowRate")) == (3.0, 2.0)
    assert outputs(sim, "LinearAxis.Step") != []                             # only the needle moved meanwhile


def test_filling_the_volume_decides_how_long_it_dispenses(filling):
    sim, ua = filling
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    assert ua.call("Skills/Dispensing/Start", a, 20.0) == [False, E["OutOfRange"]]      # offers 0.5 to 10 mL
    assert ua.call("Skills/Dispensing/Start", a, 0.1) == [False, E["OutOfRange"]]
    took = {}
    for volume in (1.0, 2.5):
        assert ua.call("Skills/Dispensing/Start", a, volume) == [True, 0]
        ua.expect("Skills/Dispensing/Execute/Dispense/State", S["Running"], timeout=6)
        started = time.monotonic()
        assert ua.value("Skills/Dispensing/Parameters/Volume") == volume
        assert ua.value("Skills/Dispensing/Execute/Dispense/Parameters/Volume") == volume
        ua.expect("Skills/Dispensing/Execute/Home/State", S["Running"], timeout=6)
        took[volume] = time.monotonic() - started
        ua.expect("Skills/Dispensing/State", S["Succeeded"], timeout=8)
    assert 0.7 <= took[1.0] <= 1.5 and 2.2 <= took[2.5] <= 3.0, took
    assert settled(sim) == []


def test_filling_dispensing_runs_its_steps_in_order_and_holds_the_needle(filling):
    sim, ua = filling
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    steps = {s: ua.record(f"Skills/Dispensing/Execute/{s}/State") for s in ["NeedleDown", "Dispense", "Home", "Weigh"]}
    assert ua.call("Skills/Dispensing/Start", a, 1.0) == [True, 0]
    ua.expect("Skills/Dispensing/Execute/Dispense/State", S["Running"], timeout=6)
    assert at(sim, ua, 40.0)                                                # dispensing at the filling position
    assert ua.value("Skills/Dispensing/Execute/NeedleDown/Parameters/Position") == 40.0
    assert ua.value("Skills/Dispensing/Execute/NeedleDown/State") in DONE
    assert ua.value("Skills/Dispensing/Execute/Home/State") == S["Idle"]
    assert ua.call("Skills/MoveAxis/Start", a, 0.0) == [False, E["Busy"]]   # Dispensing holds the needle
    assert ua.call("Skills/Dispensing/Start", a, 1.0) == [False, E["Busy"]]
    ua.expect("Skills/Dispensing/State", S["Succeeded"], timeout=8)
    assert all(in_order(h, S["Running"], S["Succeeded"]) for h in steps.values()), steps
    assert ua.value("Skills/Dispensing/Results/Weight") == pytest.approx(2.0)
    assert at(sim, ua, 0.0)
    assert ua.value("Module/State") == M["Execute"]                         # the module stays in Execute
    # The needle is free again, and the skill runs a second time.
    assert ua.call("Skills/Dispensing/Start", a, 1.0) == [True, 0]
    ua.expect("Skills/Dispensing/State", S["Succeeded"], timeout=10)
    assert settled(sim) == []


def test_filling_stop_of_dispensing_homes_the_needle(filling):
    sim, ua = filling
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    states = ua.record("Skills/Dispensing/State")
    assert ua.call("Skills/Dispensing/Start", a, 1.0) == [True, 0]
    ua.expect("Skills/Dispensing/Execute/Dispense/State", S["Running"], timeout=6)
    assert ua.call("Skills/Dispensing/Stop", a) == [True, 0]
    ua.expect("Skills/Dispensing/State", S["Failed"], timeout=6)
    assert ua.value("Skills/Dispensing/ErrorID") == E["Interrupted"]
    assert in_order(states, S["Running"], S["Stopping"], S["Failed"]), states
    assert ua.value("Skills/Dispensing/Execute/Dispense/ErrorID") == E["Interrupted"]
    assert ua.value("Skills/Dispensing/Stopping/Home/State") in DONE
    assert ua.value(f"{AXIS}/AtHome") is True and sim.position("LinearAxis") == 0.0
    assert ua.value("Module/State") == M["Execute"]
    assert ua.call("Skills/MoveAxis/Start", a, 20.0) == [True, 0]           # the needle was released
    ua.expect("Skills/MoveAxis/State", S["Succeeded"], timeout=6)
    assert at(sim, ua, 20.0)


def test_filling_abort_switches_off_and_the_module_recovers(filling):
    sim, ua = filling
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    assert ua.call("Skills/Dispensing/Start", a, 1.0) == [True, 0]
    ua.expect("Skills/Dispensing/State", S["Running"], timeout=1)
    time.sleep(0.8)                                                          # the needle is on its way down
    assert sim.outputs_on() != []
    assert ua.call("Module/Abort", a) == [True, 0]
    ua.expect("Module/State", M["Aborted"])
    ua.expect("Skills/Dispensing/State", S["Aborted"])
    ua.expect("Skills/Dispensing/Execute/NeedleDown/State", S["Aborted"])
    assert settled(sim) == []
    stopped = sim.position("LinearAxis")
    assert 5.0 < stopped < 35.0                                              # stopped where it was
    ua.expect(f"{AXIS}/Moving", False)
    assert ua.value(f"{AXIS}/ActualPosition") == pytest.approx(stopped, abs=2.0)
    assert ua.call("Skills/Dispensing/Start", a, 1.0) == [False, E["NotReady"]]
    # Clear, reset (the needle goes home) and run again.
    assert ua.call("Module/Clear", a) == [True, 0]
    ua.expect("Module/State", M["Stopped"])
    ua.expect("Skills/Dispensing/State", S["Idle"])
    assert ua.call("Module/Reset", a) == [True, 0]
    ua.expect("Module/State", M["Idle"], timeout=10)
    assert ua.value(f"{AXIS}/AtHome") is True
    assert ua.call("Module/Start", a) == [True, 0]
    ua.expect("Module/State", M["Execute"])
    assert ua.call("Skills/Dispensing/Start", a, 1.0) == [True, 0]
    ua.expect("Skills/Dispensing/State", S["Succeeded"], timeout=10)


@pytest.mark.parametrize("filling", [{"Home.Timeout": "T#3s"}], indirect=True)
def test_filling_an_axis_that_never_reaches_its_switch_fails_homing_and_is_freed(filling):
    """Only the limit switch is a sensor: a blocked axis shows when it is to find it. A move to a
    position is not measured, so a blocked axis is not noticed there."""
    sim, ua = filling
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    assert ua.call("Skills/MoveAxis/Start", a, 30.0) == [True, 0]
    ua.expect("Skills/MoveAxis/State", S["Succeeded"], timeout=6)
    sim.axes["LinearAxis"].speed = 0.0                                       # blocked
    assert ua.call("Skills/Home/Start", a) == [True, 0]
    ua.expect("Skills/Home/State", S["Failed"], timeout=5)
    assert ua.value("Skills/Home/ErrorID") == E["Timeout"]
    assert settled(sim) == [] and ua.value(f"{AXIS}/Homed") is False
    assert ua.value("Module/State") == M["Execute"]
    sim.axes["LinearAxis"].speed = 20.0
    assert ua.call("Skills/Home/Start", a) == [True, 0]                      # free again
    ua.expect("Skills/Home/State", S["Succeeded"], timeout=6)
    assert ua.value(f"{AXIS}/Homed") is True


# --------------------------------------------------------------------------------------------
# Stoppering module
# --------------------------------------------------------------------------------------------

@pytest.fixture
def stoppering(request, tmp_path):
    with running(request, tmp_path, "stoppering", getattr(request, "param", None)) as (sim, ua):
        yield sim, ua


def test_stoppering_resetting_draws_the_piston_in_and_homes_the_head(stoppering):
    sim, ua = stoppering
    a = str(uuid.uuid4())
    sim.axes["Piston"].position = 0.5                                        # left out, e.g. by an abort
    assert ua.call("Occupation/Occupy", a) == [True, 0]
    assert ua.call("Module/Reset", a) == [True, 0]
    ua.expect("Module/State", M["Idle"], timeout=12)
    assert sim.position("Piston") == 0.0 and sim.position("LinearAxis") == 0.0
    assert ua.value("Equipment/LinearAxis/AtHome") is True and ua.value("Equipment/LinearAxis/Homed") is True
    assert ua.value("Procedures/Resetting/RetractPiston/State") in DONE
    assert ua.value("Procedures/Resetting/Home/State") in DONE
    assert settled(sim) == [] and sim.shoot_through == 0


def test_stoppering_has_the_same_axis_skills_as_the_filling_module(stoppering):
    """One kind of component, the same two skills in every module that has one."""
    sim, ua = stoppering
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    assert ua.call("Skills/MoveAxis/Start", a, 80.0) == [False, E["OutOfRange"]]
    assert ua.call("Skills/MoveAxis/Start", a, 25.0) == [True, 0]
    ua.expect("Skills/MoveAxis/State", S["Succeeded"], timeout=6)
    assert ua.value("Equipment/LinearAxis/ActualPosition") == 25.0
    assert sim.position("LinearAxis") == pytest.approx(25.0, abs=1.5)
    assert ua.call("Skills/Home/Start", a) == [True, 0]
    ua.expect("Skills/Home/State", S["Succeeded"], timeout=6)
    assert ua.value("Equipment/LinearAxis/AtHome") is True and sim.position("LinearAxis") == 0.0
    assert settled(sim) == []


def test_stoppering_a_press_goes_out_for_the_stroke_and_back_in(stoppering):
    sim, ua = stoppering
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    states = ua.record("Skills/PressStopper/State")
    started = time.monotonic()
    assert ua.call("Skills/PressStopper/Start", a) == [True, 0]
    ua.expect("Skills/PressStopper/State", S["Running"], timeout=1)
    time.sleep(2.0)
    assert sim.position("Piston") > 0.5                                      # on its way out
    ua.expect("Skills/PressStopper/State", S["Succeeded"], timeout=8)
    assert 5.5 <= time.monotonic() - started <= 7.5                          # 3 s out, 3 s back
    assert in_order(states, S["Running"], S["Succeeded"]), states
    assert outputs(sim, "Piston.Extend", "Piston.Retract") == [
        ("Piston.Extend", True), ("Piston.Extend", False), ("Piston.Retract", True), ("Piston.Retract", False)]
    assert 2.6 <= on_time(sim, "Piston.Extend") <= 3.4 and 2.6 <= on_time(sim, "Piston.Retract") <= 3.4
    assert sim.position("Piston") == pytest.approx(0.0, abs=0.1)
    assert settled(sim) == [] and sim.shoot_through == 0


def test_stoppering_a_press_that_is_stopped_still_draws_the_piston_in(stoppering):
    sim, ua = stoppering
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    assert ua.call("Skills/PressStopper/Start", a) == [True, 0]
    ua.expect("Skills/PressStopper/State", S["Running"], timeout=1)
    time.sleep(1.0)
    assert ua.call("Skills/PressStopper/Stop", a) == [True, 0]
    ua.expect("Skills/PressStopper/State", S["Failed"], timeout=6)
    assert ua.value("Skills/PressStopper/ErrorID") == E["Interrupted"]
    assert sim.position("Piston") == 0.0 and settled(sim) == []
    assert sim.shoot_through == 0


def test_stoppering_runs_its_steps_in_order_and_holds_its_equipment(stoppering):
    sim, ua = stoppering
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    steps = {s: ua.record(f"Skills/Stoppering/Execute/{s}/State") for s in ["HeadDown", "PressStopper", "Home"]}
    assert ua.call("Skills/Stoppering/Start", a) == [True, 0]
    ua.expect("Skills/Stoppering/Execute/PressStopper/State", S["Running"], timeout=6)
    assert ua.value("Equipment/LinearAxis/ActualPosition") == 40.0           # pressing at the working position
    assert sim.position("LinearAxis") == pytest.approx(40.0, abs=1.5)
    assert ua.call("Skills/MoveAxis/Start", a, 0.0) == [False, E["Busy"]]    # Stoppering holds the head
    assert ua.call("Skills/RetractPiston/Start", a) == [False, E["Busy"]]    # and the piston
    ua.expect("Skills/Stoppering/State", S["Succeeded"], timeout=12)
    assert all(in_order(h, S["Running"], S["Succeeded"]) for h in steps.values()), steps
    assert ua.value("Equipment/LinearAxis/ActualPosition") == 0.0 and sim.position("Piston") == pytest.approx(0.0, abs=0.1)
    assert ua.value("Module/State") == M["Execute"]
    assert settled(sim) == [] and sim.shoot_through == 0


def test_stoppering_stop_draws_the_piston_in_and_homes_the_head(stoppering):
    sim, ua = stoppering
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    states = ua.record("Skills/Stoppering/State")
    assert ua.call("Skills/Stoppering/Start", a) == [True, 0]
    ua.expect("Skills/Stoppering/Execute/PressStopper/State", S["Running"], timeout=6)
    time.sleep(1.0)
    assert ua.call("Skills/Stoppering/Stop", a) == [True, 0]
    ua.expect("Skills/Stoppering/State", S["Failed"], timeout=12)
    assert ua.value("Skills/Stoppering/ErrorID") == E["Interrupted"]
    assert in_order(states, S["Running"], S["Stopping"], S["Failed"]), states
    assert ua.value("Skills/Stoppering/Stopping/Home/State") in DONE
    assert sim.position("Piston") == 0.0 and sim.position("LinearAxis") == 0.0
    # The piston came in before the head went up.
    last = {n: max(t for t, m, v in sim.trace if m == n and v) for n in ("Piston.Retract", "LinearAxis.Step")}
    assert last["Piston.Retract"] < last["LinearAxis.Step"]
    assert settled(sim) == [] and sim.shoot_through == 0


def test_stoppering_abort_switches_off_and_the_module_recovers(stoppering):
    sim, ua = stoppering
    a = str(uuid.uuid4())
    ready(sim, ua, a)
    assert ua.call("Skills/Stoppering/Start", a) == [True, 0]
    ua.expect("Skills/Stoppering/Execute/PressStopper/State", S["Running"], timeout=6)
    time.sleep(1.0)
    assert ua.call("Module/Abort", a) == [True, 0]
    ua.expect("Module/State", M["Aborted"])
    ua.expect("Skills/Stoppering/State", S["Aborted"])
    assert settled(sim) == []
    assert 0.1 < sim.position("Piston") < 0.9                                # left where it was, the head down
    assert sim.position("LinearAxis") == pytest.approx(40.0, abs=1.5)
    assert ua.call("Module/Clear", a) == [True, 0]
    ua.expect("Module/State", M["Stopped"])
    assert ua.call("Module/Reset", a) == [True, 0]                           # the piston in, then the head home
    ua.expect("Module/State", M["Idle"], timeout=12)
    assert sim.position("Piston") == 0.0 and sim.position("LinearAxis") == 0.0
    assert ua.call("Module/Start", a) == [True, 0]
    ua.expect("Module/State", M["Execute"])
    assert ua.call("Skills/Stoppering/Start", a) == [True, 0]
    ua.expect("Skills/Stoppering/State", S["Succeeded"], timeout=15)
    assert sim.shoot_through == 0
