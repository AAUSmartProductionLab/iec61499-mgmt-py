"""Behaviour of the filling-cell building blocks on a real FORTE build (opt-in: --forte-exe).

The executable must contain the exported filling-cell types (4diac/tools/build-runtime.ps1).
Events are fired through management WRITE of ``$e``, so the type-level tests need no OPC UA;
the cell-level tests use the OPC UA facade exactly as a higher-level controller would.
"""
import json

import pytest

from conftest import free_port
from iec61499_mgmt.sysfile import load_application
from livecell import (ABORTED, CELL_OK, COMPLETE, EXECUTE, FC, HELD, IDLE, MANIFEST, STOPPED, SYS, Cell,
                      CellServer, Ua, deploy_cell, start)


def test_exported_types_present_with_hash(forte):
    """Every exported type exists in the runtime with a hash."""
    res, _ = forte
    for entry in json.loads(MANIFEST.read_text()):
        if not entry["exported"] or not entry["type"].startswith(FC) or entry["kind"] == "Struct":
            continue
        response = res.send("query_type", type=entry["type"])
        name, _, digest = response.types[0]["Name"].partition("#")
        assert name == entry["type"] and digest, response.raw


def test_packml_transition_table(forte):
    """SKILL_PackML follows the reduced PackML transitions."""
    res, _ = forte
    res.create("P", FC + "SKILL_PackML")
    start(res)

    def cmd(code, requires=True):
        res.write("P.Command", code)
        res.write("P.RequiresOK", requires)
        res.fire("P.CMD")

    def cond(ensures, invariant):
        res.write("P.EnsuresOK", ensures)
        res.write("P.InvariantOK", invariant)
        res.fire("P.COND")

    res.expect("P.State", IDLE)
    cmd(2, requires=False)                      # start guard: Requires false -> refused
    res.expect("P.State", IDLE)
    res.expect("P.ErrorID", 1)
    cmd(2)
    res.expect("P.State", EXECUTE)
    res.expect("P.Active", True)
    cond(False, True)
    res.expect("P.State", EXECUTE)
    cond(True, True)                            # completion only by Ensures
    res.expect("P.State", COMPLETE)
    res.expect("P.Active", False)
    cmd(1)
    res.expect("P.State", IDLE)
    cmd(2)
    cmd(3)
    res.expect("P.State", HELD)
    res.expect("P.Active", False)
    cmd(4)
    res.expect("P.State", EXECUTE)
    cond(False, False)                          # invariant violation -> abort
    res.expect("P.State", ABORTED)
    res.expect("P.ErrorID", 2)
    cmd(7)
    res.expect("P.State", STOPPED)
    cmd(1)
    cmd(2)
    res.fire("P.TIMEOUT")                       # watchdog -> abort
    res.expect("P.State", ABORTED)
    res.expect("P.ErrorID", 3)
    cmd(2)                                      # commands invalid in Aborted are ignored
    res.expect("P.State", ABORTED)


def test_gate_authority(forte):
    """SKILL_Gate enforces occupation, mode, state and call rules."""
    res, _ = forte
    res.create("G", FC + "SKILL_Gate")
    start(res)

    def manual(code, requester=1, owner=1, remote=True, mode=1, quiescent=True, state=IDLE):
        for port, value in [("Owner", owner), ("RemoteAllowed", remote), ("Mode", mode),
                            ("UnitQuiescent", quiescent), ("UnitState", IDLE)]:
            res.write("G." + port, value)
        res.fire("G.UNIT_STAT")
        res.write("G.State", state)
        res.fire("G.TRACK")
        res.write("G.Requester", requester)
        res.write("G.MCode", code)
        res.fire("G.MCMD")
        return int(res.read("G.MErr"))

    assert manual(3, remote=False) == 5          # unit not occupied
    assert manual(3, requester=2) == 5           # not the occupation owner
    assert manual(3, mode=0) == 5                # Production: only the procedure commands skills
    assert manual(3) == 4                        # Hold is invalid in Idle
    assert manual(2, quiescent=False) == 5       # manual start needs a quiescent unit
    assert manual(1, state=COMPLETE) == 0        # Reset from Complete
    assert int(res.read("G.Command")) == 1
    assert manual(2) == 0                        # start pending until the skill reports Starting
    assert manual(1) == 5                        # busy with the pending start
    res.write("G.State", EXECUTE)
    res.fire("G.TRACK")
    assert manual(3, state=EXECUTE) == 0

    # Procedure call port.
    res.write("G.UnitRunning", False)
    res.fire("G.UNIT_STAT")
    res.fire("G.CALL")
    assert int(res.read("G.CallError")) == 5     # only while the unit runs
    res.write("G.UnitRunning", True)
    res.fire("G.UNIT_STAT")
    res.write("G.State", IDLE)
    res.fire("G.TRACK")
    res.fire("G.CALL")
    assert int(res.read("G.CallError")) == 0
    res.fire("G.CALL")
    assert int(res.read("G.CallError")) == 6     # one call at a time


def make_dose(res, timeout="T#1s"):
    """Create and initialise an SK_Dose with simulated IO."""
    res.create("D", FC + "SK_Dose")
    for port, value in [("UaEnable", False), ("IoBackend", 0), ("Timeout", timeout), ("UnitRunning", True)]:
        res.write("D." + port, value)
    start(res)
    res.fire("D.INIT")
    res.fire("D.UNIT_STAT")


def sample(res, fb, **cell):
    """Send a cell sample, overriding some state variables."""
    res.write(fb + ".Cell", {**CELL_OK, **cell})
    res.fire(fb + ".SAMPLE")


def call(res, fb, p1):
    """Call a skill with P1 through its CALL port."""
    res.write(fb + ".P1", p1)
    res.fire(fb + ".CALL")


def test_skill_composite_contract(forte):
    """SK_Dose honours its contract, watchdog and unit control."""
    res, _ = forte
    make_dose(res)
    sample(res, "D")
    call(res, "D", 5.0)                          # outside 0.1..2.0 mL: Requires false
    res.expect("D.CallError", 1)
    res.expect("D.State", IDLE)
    call(res, "D", 0.5)
    res.expect("D.State", EXECUTE)
    res.expect("D.Drive", True)
    sample(res, "D", FilledMl=0.3)
    res.expect("D.State", EXECUTE)
    sample(res, "D", FilledMl=0.5)               # Ensures: FilledMl >= latched target
    res.expect("D.State", COMPLETE)
    res.expect("D.Drive", False)
    call(res, "D", 0.5)                          # gate resets from Complete, then starts
    res.expect("D.State", EXECUTE)
    sample(res, "D", FilledMl=0.7, NeedleDown=False)  # Invariant violated -> abort
    res.expect("D.State", ABORTED)
    res.expect("D.SkillError", 2)
    res.expect("D.CallError", 2)
    res.expect("D.Drive", False)
    for code, state in [(7, STOPPED), (1, IDLE)]:     # unit Clear, Reset
        res.write("D.ControlCode", code)
        res.fire("D.UNIT_CTL")
        res.expect("D.State", state)
    sample(res, "D", FilledMl=0.7)
    call(res, "D", 0.5)
    res.expect("D.State", EXECUTE)
    res.expect("D.State", ABORTED, timeout=3)    # watchdog
    res.expect("D.SkillError", 3)


# ------------------------------------------------------------------------------------------
# Whole cell over OPC UA
# ------------------------------------------------------------------------------------------
@pytest.fixture
def ua_cell(forte):
    """Deployed cell with simulated sensors and a connected OPC UA client."""
    pytest.importorskip("asyncua")
    res, ua_port = forte
    deploy_cell(res)
    sim = {"Observer.Sim_" + k: v for k, v in CELL_OK.items() if k not in ("Valid", "Safe")}
    sim.update({"Observer.Sim_NeedleUp": True, "Observer.Sim_NeedleDown": False})
    for port, value in sim.items():
        res.write(port, value)
    ua = Ua(ua_port)
    try:
        yield res, ua
    finally:
        ua.close()


def test_cell_over_opcua(ua_cell):
    """Drive the whole cell through its OPC UA methods."""
    res, ua = ua_cell
    ua.expect("State/NeedleUp", True)
    assert ua.call("Occupation/Occupy", 1) == [True, 0]
    ua.expect("Occupation/Owner", 1)
    assert ua.call("Unit/Reset", 1, 1) == [True, 0]            # Maintenance mode
    ua.expect("Unit/State", IDLE)
    assert ua.call("Skills/MoveDown/Start", 2, 0.0, 0.0, 0.0, 0.0) == [False, 5]   # not the owner
    assert ua.call("Skills/Dose/Start", 1, 0.5, 0.0, 0.0, 0.0) == [False, 1]       # needle not down
    assert ua.call("Skills/MoveDown/Hold", 1) == [False, 4]    # invalid in Idle
    assert ua.call("Skills/MoveDown/Start", 1, 0.0, 0.0, 0.0, 0.0) == [True, 0]
    ua.expect("Skills/MoveDown/State", EXECUTE)
    res.expect("EM_Filler.MoveDown.Drive", True)
    res.write("Observer.Sim_NeedleUp", False)
    res.write("Observer.Sim_NeedleDown", True)
    ua.expect("Skills/MoveDown/State", COMPLETE)
    assert ua.call("Skills/Dose/Start", 1, 0.5, 0.0, 0.0, 0.0) == [True, 0]
    ua.expect("Skills/Dose/P1", 0.5)
    res.write("Observer.Sim_FilledMl", 0.5)
    ua.expect("Skills/Dose/State", COMPLETE)
    assert ua.call("Unit/Start", 1) == [False, 4]               # Start needs Production mode
    res.write("Observer.Sim_DoorClosed", False)                 # unsafe -> unit aborts
    ua.expect("Unit/State", ABORTED)
    res.write("Observer.Sim_DoorClosed", True)
    assert ua.call("Unit/Clear", 1) in ([True, 0], [False, 4])  # refused until the next sample is Safe
    ua.expect("State/Safe", True)
    if ua.value("Unit/State") != STOPPED:
        assert ua.call("Unit/Clear", 1) == [True, 0]
    ua.expect("Unit/State", STOPPED)
    assert ua.call("Occupation/Release", 1) == [True, 0]
    ua.expect("Occupation/Owner", 0)


def test_equipment_module_changed_online(ua_cell):
    """Add a second inspection skill to EM_Filler while the fixed part keeps running."""
    res, ua = ua_cell
    before = {fb["Name"]: fb["Type"] for fb in res.send("query_fbs").fbs}
    new = "EM_Filler.Inspect2"
    res.create(new, FC + "SK_Inspect")
    for port, value in [("UaRoot", '"/Objects/FillingCell/Filler/Skills/Inspect2"'), ("UaEnable", "TRUE"),
                        ("IoBackend", "0")]:
        res.send("write", destination=f"{new}.{port}", value=value)
    for event in ["UNIT_CTL", "UNIT_STAT", "SAMPLE"]:
        src = {"UNIT_CTL": ["Unit.CONTROL"], "UNIT_STAT": ["Unit.CNF", "Occupation.CNF"],
               "SAMPLE": ["Observer.SAMPLE"]}[event]
        for s in src:
            res.send("connect", source=s, destination=f"{new}.{event}")
    for s, d in [("Unit.ControlCode", "ControlCode"), ("Observer.Cell", "Cell"), ("Unit.Running", "UnitRunning"),
                 ("Unit.Quiescent", "UnitQuiescent"), ("Unit.State", "UnitState"), ("Unit.Mode", "Mode"),
                 ("Occupation.Owner", "Owner"), ("Occupation.RemoteAllowed", "RemoteAllowed")]:
        res.send("connect", source=s, destination=f"{new}.{d}")
    # Splice the status chain: Inspect -> Inspect2 -> Unit.
    last = "EM_Filler.Inspect"
    for s, d in [("STAT_OUT", "STATUS"), ("BusyOut", "Busy"), ("HeldOut", "HeldAll"), ("RunOut", "RunAll")]:
        res.send("disconnect", source=f"{last}.{s}", destination=f"Unit.{d}")
        res.send("connect", source=f"{new}.{s}", destination=f"Unit.{d}")
    for s, d in [("STAT_OUT", "STAT_IN"), ("BusyOut", "BusyIn"), ("HeldOut", "HeldIn"), ("RunOut", "RunIn")]:
        res.send("connect", source=f"{last}.{s}", destination=f"{new}.{d}")
    res.send("start", name=new)
    res.fire(new + ".INIT", settle=0.5)
    after = {fb["Name"]: fb for fb in res.send("query_fbs").fbs}
    assert set(after) == set(before) | {new}
    assert all(fb["Status"] == "RUNNING" for fb in after.values())
    assert ua.call("Occupation/Occupy", 1) == [True, 0]
    assert ua.call("Unit/Reset", 1, 1) == [True, 0]
    ua.expect("Unit/State", IDLE)                                 # chain end reaches the unit
    ua.expect("Skills/Inspect2/State", IDLE)
    assert ua.call("Skills/Inspect2/Start", 1, 0.0, 0.0, 0.0, 0.0) == [False, 1]   # not stoppered


def test_cell_with_modbus_simulator(forte):
    """IoBackend 2: the same types drive the Modbus simulator's coils; its physics closes the loop."""
    pytest.importorskip("asyncua")
    res, ua_port = forte
    port = free_port()
    backend = {}
    app = load_application(SYS, "FillingCell")
    for name, value in app.parameters.items():
        if name.endswith("Modbus"):
            backend[name] = value.replace(":1502:", f":{port}:")
        elif name.endswith("IoBackend"):
            backend[name] = "2"
    cell = Cell(travel_s=0.2, actuation_s=0.2, fill_rate=2.0)
    with CellServer(cell, port=port):
        deploy_cell(res, backend)
        ua = Ua(ua_port)
        try:
            ua.expect("State/NeedleUp", True)
            assert ua.call("Occupation/Occupy", 1) == [True, 0]
            assert ua.call("Unit/Reset", 1, 1) == [True, 0]
            ua.expect("Unit/State", IDLE)
            for skill, args in [("MoveDown", ()), ("Dose", (0.4,)), ("MoveUp", ()), ("Stopper", ()), ("Inspect", ())]:
                params = [float(a) for a in args] + [0.0] * (4 - len(args))
                assert ua.call(f"Skills/{skill}/Start", 1, *params) == [True, 0], skill
                ua.expect(f"Skills/{skill}/State", COMPLETE, timeout=5)
            assert cell.filled_ml >= 0.4
            assert cell.inputs["Checked"] and cell.inputs["Stoppered"] and cell.inputs["NeedleUp"]
            assert cell.shoot_through == 0
            assert not any(cell.coils.values())
            order = [name for _, name, on in cell.coil_trace if on]
            assert order == ["MoveDown", "Dose", "MoveUp", "Stopper", "Inspect"]
        finally:
            ua.close()
