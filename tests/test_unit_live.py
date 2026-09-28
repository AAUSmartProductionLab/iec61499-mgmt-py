"""Iteration 1 of the generated unit (units/filler.yaml) against FORTE and the Modbus simulator.

    python -m pytest tests/test_unit_live.py --unit-forte-exe 4diac/tools/fbe/build/filler-win/output/bin/forte.exe
"""
from pathlib import Path
import time
import uuid

import pytest

from conftest import free_port, launch_forte
from iec61499_mgmt.protocol import Client, Command
from iec61499_mgmt.sysfile import load_application
from livecell import ROOT, Cell, CellServer

SYS = ROOT / "4diac" / "FillerUnit" / "FillerUnit.sys"
SKILL = "Execute/MoveNeedleDown"
STOPPED, IDLE, ABORTED, COMPLETE = 2, 4, 9, 17
SUCCEEDED, FAILED = 2, 3
NOT_READY, NOT_PERMITTED, BUSY, OUT_OF_RANGE, TIMEOUT = 4, 5, 6, 8, 3


class UnitUa:
    """OPC UA client for the unit below /Objects/Filler."""
    def __init__(self, port):
        from asyncua import ua
        from asyncua.sync import Client as UaClient
        self.ua = ua
        self.client = UaClient(f"opc.tcp://127.0.0.1:{port}", timeout=10)
        deadline = time.monotonic() + 10
        while True:
            try:
                self.client.connect()
                break
            except Exception:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.2)

    def node(self, path):
        """Node below /Objects/Filler."""
        return self.client.nodes.objects.get_child(["1:Filler"] + [f"1:{p}" for p in path.split("/")])

    def call(self, path, session, *args):
        """Call a method with a session ID and Double arguments; return [Accepted, ErrorID]."""
        parent, method = path.rsplit("/", 1)
        variants = [self.ua.Variant(session, self.ua.VariantType.String)]
        variants += [self.ua.Variant(float(a), self.ua.VariantType.Double) for a in args]
        started = time.monotonic()
        accepted, error = self.node(parent).call_method(f"1:{method}", *variants)
        assert time.monotonic() - started < 2.0          # answered synchronously
        return [accepted, error]

    def value(self, path):
        """Read a variable."""
        return self.node(path).read_value()

    def expect(self, path, value, timeout=3.0):
        """Wait until a variable has the expected value."""
        deadline = time.monotonic() + timeout
        while True:
            try:
                actual = self.value(path)
            except Exception as exc:                   # node not created yet
                actual = exc
            if actual == value:
                return
            if time.monotonic() > deadline:
                skill = [self.value(f"{SKILL}/{v}") for v in ("State", "ErrorID")]
                raise AssertionError(f"{path} = {actual!r}, expected {value!r} (skill State, ErrorID = {skill})")
            time.sleep(0.05)

    def close(self):
        """Disconnect."""
        self.client.disconnect()


@pytest.fixture
def unit(request, tmp_path):
    """Simulator (needle at 25 mm/s) + FORTE with the deployed unit; yields (cell, ua, deploy overrides)."""
    exe = request.config.getoption("--unit-forte-exe")
    if not exe:
        pytest.skip("Pass --unit-forte-exe to run the generated unit against FORTE")
    exe = Path(exe).resolve(strict=True)
    overrides = getattr(request, "param", {})
    cell = Cell(travel_s=2.0)
    modbus, ua_port = free_port(), free_port()
    app = load_application(SYS, "Filler")
    params = {k: v.replace(":1502:", f":{modbus}:") for k, v in app.parameters.items() if k.endswith("_Modbus")}
    with CellServer(cell, port=modbus), launch_forte(exe, tmp_path, None, ["-op", str(ua_port)]) as port, \
            Client("127.0.0.1", port) as client:
        client.execute(Command(op="create_fb", resource="", name="RES", type="iec61499::system::EMB_RES"))
        for command in app.commands("RES", {**params, **overrides}):
            client.execute(command)
        client.execute(Command(op="start", resource="", name="RES"))
        ua = UnitUa(ua_port)
        try:
            ua.expect("Unit/State", STOPPED)
            ua.expect(f"{SKILL}/State", 0)
            yield cell, ua
        finally:
            ua.close()


def moves(cell):
    """Coil switching sequence recorded by the simulator."""
    return [(name, on) for _, name, on in cell.coil_trace]


def run(ua, session):
    """Reset and start the unit as ``session``."""
    assert ua.call("Unit/Reset", session) == [True, 0]
    ua.expect("Unit/State", IDLE)
    assert ua.call("Unit/Start", session) == [True, 0]


def test_owner_sets_a_parameter_and_runs_the_procedure(unit):
    cell, ua = unit
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    assert ua.call("Occupation/Occupy", a) == [True, 0]
    assert ua.call("Occupation/Occupy", a) == [True, 0]                    # idempotent for the owner
    assert ua.call("Occupation/Occupy", b) == [False, NOT_PERMITTED]
    ua.expect("Occupation/Occupied", True)
    # Parameters belong to the skill instance: default first, then only the owner, only in range.
    assert ua.value(f"{SKILL}/Parameters/Distance") == 50.0
    assert ua.call(f"{SKILL}/SetParameters", b, 20.0) == [False, NOT_PERMITTED]
    assert ua.call(f"{SKILL}/SetParameters", a, 80.0) == [False, OUT_OF_RANGE]
    assert ua.call(f"{SKILL}/SetParameters", a, 20.0) == [True, 0]
    ua.expect(f"{SKILL}/Parameters/Distance", 20.0)
    # Unit commands: owner only, and only where PackML allows them.
    assert ua.call("Unit/Start", a) == [False, NOT_READY]                  # Stopped, not Idle
    assert ua.call("Unit/Reset", b) == [False, NOT_PERMITTED]
    run(ua, a)
    ua.expect("Unit/State", COMPLETE, timeout=5)
    assert ua.value(f"{SKILL}/State") == SUCCEEDED
    assert 20.0 <= cell.position_mm <= 20.8     # 10 ms Modbus poll + 20 ms simulator step at 25 mm/s
    assert moves(cell) == [("MoveDown", True), ("MoveDown", False)]
    assert cell.shoot_through == 0
    assert abs(ua.value("Equipment/NeedleAxis/Position") - cell.position_mm) < 1.0
    # Hand-over: only the owner releases; the old session loses all rights.
    assert ua.call("Occupation/Release", b) == [False, NOT_PERMITTED]
    assert ua.call("Occupation/Release", a) == [True, 0]
    ua.expect("Occupation/Occupied", False)
    assert ua.call(f"{SKILL}/SetParameters", a, 30.0) == [False, NOT_PERMITTED]
    assert ua.call("Occupation/Occupy", b) == [True, 0]
    # Already at the target depth: the skill succeeds without driving (behaviour-tree semantics).
    run(ua, b)
    ua.expect("Unit/State", COMPLETE)
    assert moves(cell) == [("MoveDown", True), ("MoveDown", False)]


def test_default_parameter_moves_all_the_way_down(unit):
    cell, ua = unit
    a = str(uuid.uuid4())
    assert ua.call("Occupation/Occupy", a) == [True, 0]
    run(ua, a)
    ua.expect("Unit/State", COMPLETE, timeout=5)
    assert cell.inputs["NeedleDown"] and cell.position_mm == 50.0
    assert ua.value("Equipment/NeedleAxis/AtBottom") is True


@pytest.mark.parametrize("unit", [{"Execute.MoveNeedleDown.Timeout": "T#1s"}], indirect=True)
def test_timeout_fails_the_skill_and_aborts_the_unit(unit):
    cell, ua = unit
    cell.physics = False                                                   # the needle never moves
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    assert ua.call("Occupation/Occupy", a) == [True, 0]
    run(ua, a)
    ua.expect(f"{SKILL}/State", 1)
    assert ua.call(f"{SKILL}/SetParameters", a, 10.0) == [False, BUSY]    # no changes while running
    ua.expect("Unit/State", ABORTED, timeout=3)
    assert ua.value(f"{SKILL}/State") == FAILED and ua.value(f"{SKILL}/ErrorID") == TIMEOUT
    assert moves(cell) == [("MoveDown", True), ("MoveDown", False)]        # drive released on failure
    assert ua.call("Unit/Clear", b) == [False, NOT_PERMITTED]
    assert ua.call("Unit/Clear", a) == [True, 0]
    ua.expect("Unit/State", STOPPED)
