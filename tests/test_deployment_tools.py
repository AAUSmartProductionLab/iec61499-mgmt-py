"""Offline tests for the type library builder, boot files and read-back verification."""
from pathlib import Path

import pytest

from iec61499_mgmt import Network, boot_file, deployment, verify
from iec61499_mgmt.models import IECValue
from iec61499_mgmt.protocol import Response
from iec61499_mgmt.sysfile import load_application
from iec61499_mgmt.typelib import build_library, read_fbt, read_types
from iec61499_mgmt.verify import same_value, time_ms

ROOT = Path(__file__).resolve().parents[1]
TYPES = ROOT / "4diac" / "FillingCellFixed" / "Type Library"
SYS = ROOT / "4diac" / "FillingCellFixed" / "FillingCellFixed.sys"
HASH = "v2:SHA3-512:abc_-="


@pytest.fixture(scope="module")
def library():
    """Library of the generated types with a fake hash, boundary from the fixed application."""
    types = read_types(TYPES)
    names = [n for n in types if n.startswith("fillingcell::")]
    return build_library(types, {n: HASH for n in names}, "test", fixed=load_application(SYS, "FillingCell"))


def procedure(library):
    """One P_Call between the facade and the Dose skill."""
    return Network.model_validate({"resource": "RES", "instances": [
        {"name": "PROC.Dose", "type": "fillingcell::P_Call", "type_hash": HASH,
         "parameters": {"P1": {"type": "LREAL", "value": 0.5}}}], "connections": [
        {"source": "Facade.START", "destination": "PROC.Dose.EI"},
        {"source": "PROC.Dose.CALL", "destination": "EM_Filler.Dose.CALL"},
        {"source": "PROC.Dose.CP1", "destination": "EM_Filler.Dose.P1", "kind": "data"},
        {"source": "EM_Filler.Dose.DONE", "destination": "PROC.Dose.DONE"},
        {"source": "PROC.Dose.EO", "destination": "Facade.FINISHED"}]}).validate_library(library)


def test_read_fbt_ports():
    """Interface ports are read with kind, direction, type and writability."""
    name, ports = read_fbt(TYPES / "Procedure" / "P_Call.fbt")
    assert name == "fillingcell::P_Call"
    assert ports["EI"].kind == "event" and ports["EI"].direction == "input"
    assert ports["P1"].writable and ports["P1"].data_type == "LREAL"
    assert not ports["CP1"].writable and ports["CP1"].direction == "output"


def test_boundary_ports_exclude_procedure_scope(library):
    """Ports of fixed instances are boundary ports; nothing inside PROC is."""
    assert "EM_Filler.Dose.CALL" in library.boundary_ports
    assert not any(k.startswith("PROC.") for k in library.boundary_ports)


def test_boot_file_order_and_format(library):
    """Resource first, fixed part, procedure without START/STOP, resource start last."""
    commands = deployment(load_application(SYS, "FillingCell"), procedure=procedure(library), library=library)
    lines = boot_file(commands).splitlines()
    assert lines[0].startswith(';<Request ID="1" Action="CREATE"><FB Name="RES" Type="iec61499::system::EMB_RES"')
    assert lines[-1].startswith(';<Request') and 'Action="START"' in lines[-1]
    assert all(line.split(";", 1)[0] in ("", "RES") for line in lines)
    ops = [c.op for c in commands]
    assert "stop" not in ops and ops.count("start") == 1
    assert any(c.op == "create_fb" and c.type == f"fillingcell::P_Call#{HASH}" for c in commands)


def test_same_value_and_time():
    """READ results match typed values, tolerating typed literals and TIME units."""
    assert same_value(IECValue(type="LREAL", value=0.5), "LREAL#0.5")
    assert same_value(IECValue(type="UINT", value=3), "3")
    assert not same_value(IECValue(type="BOOL", value=True), "FALSE")
    assert same_value(IECValue(type="TIME", value=1500), "T#1s500ms")
    assert time_ms("T#300ms") == 300 and time_ms("garbage") is None


class FakeClient:
    """Answers QUERY and READ from canned FB, connection and value tables."""

    def __init__(self, fbs, connections, values):
        self.fbs, self.connections, self.values = fbs, connections, values

    def execute(self, command):
        fbs = [{"Name": n, "Type": t, "Status": s} for n, (t, s) in self.fbs.items()] if command.op == "query_fbs" else []
        conns = [{"Source": s, "Destination": d} for s, d in self.connections] if command.op == "query_connections" else []
        if command.op == "read":
            conns = [{"Source": command.source, "Destination": self.values[command.source]}]
        return Response(request_id="1", reason=None, fbs=fbs, connections=conns, types=[], raw="")


def test_verify_reports_drift(library):
    """Missing edges, extra instances, wrong values and stopped FBs are all reported."""
    network = procedure(library)
    edges = [(c.source, c.destination) for c in network.connections]
    good = FakeClient({"PROC.Dose": ("fillingcell::P_Call", "RUNNING"), "Unit": ("fillingcell::FC_Unit", "RUNNING")},
                      edges, {"PROC.Dose.P1": "0.5"})
    assert verify(good, network) == []
    bad = FakeClient({"PROC.Dose": ("fillingcell::P_Call", "STOPPED"), "PROC.Extra": ("fillingcell::P_Loop", "RUNNING")},
                     edges[1:], {"PROC.Dose.P1": "0.25"})
    problems = verify(bad, network)
    assert "unexpected instance PROC.Extra" in problems
    assert "missing connection Facade.START -> PROC.Dose.EI" in problems
    assert "PROC.Dose is STOPPED, expected RUNNING" in problems
    assert "PROC.Dose.P1 = 0.25, expected 0.5" in problems
