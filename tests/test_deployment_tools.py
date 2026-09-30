"""Offline tests for the type library builder, boot files and read-back verification, on the
generated filling module (its PC application is the fixed part; a small network added online in
the PROC scope stands for a change)."""
from pathlib import Path

import pytest

from iec61499_mgmt import Network, boot_file, deployment, verify
from iec61499_mgmt.models import IECValue
from iec61499_mgmt.protocol import Response
from iec61499_mgmt.sysfile import load_application
from iec61499_mgmt.typelib import build_library, read_fbt, read_types
from iec61499_mgmt.verify import same_value, time_ms

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "4diac" / "FillingModule"
TYPES = PROJECT / "Type Library"
SYS = PROJECT / "FillingModule.sys"
APP = "Filling"
HASH = "v2:SHA3-512:abc_-="


@pytest.fixture(scope="module")
def library():
    """Library of the module's types with a fake hash, boundary from the fixed application."""
    types = read_types(TYPES)
    names = [n for n in types if n.startswith(("filling::", "modlib::"))]
    return build_library(types, {n: HASH for n in names}, "test", fixed=load_application(SYS, APP))


def change(library):
    """A wait step added online: the module state manager's Resetting runs it."""
    return Network.model_validate({"resource": "RES", "instances": [
        {"name": "PROC.Wait", "type": "filling::SK_Dwell", "type_hash": HASH,
         "parameters": {"Duration": {"type": "LREAL", "value": 0.5}}}], "connections": [
        {"source": "Module.RUN_RESETTING", "destination": "PROC.Wait.START"},
        {"source": "PROC.Wait.SUCCESS", "destination": "Module.RESETTING_DONE"}]}).validate_library(library)


def test_read_fbt_ports():
    """Interface ports are read with kind, direction, type and writability."""
    name, ports = read_fbt(TYPES / "Skills" / "SK_Dwell.fbt")
    assert name == "filling::SK_Dwell"
    assert ports["START"].kind == "event" and ports["START"].direction == "input"
    assert ports["Duration"].writable and ports["Duration"].data_type == "LREAL"
    assert not ports["State"].writable and ports["State"].direction == "output"


def test_boundary_ports_exclude_the_owned_scope(library):
    """Ports of fixed instances are boundary ports; nothing inside PROC is."""
    assert "Module.RESETTING_DONE" in library.boundary_ports
    assert not any(k.startswith("PROC.") for k in library.boundary_ports)


def test_boot_file_order_and_format(library):
    """Resource first, fixed part, the change without START/STOP, resource start last."""
    commands = deployment(load_application(SYS, APP), procedure=change(library), library=library)
    lines = boot_file(commands).splitlines()
    assert lines[0].startswith(';<Request ID="1" Action="CREATE"><FB Name="RES" Type="iec61499::system::EMB_RES"')
    assert lines[-1].startswith(';<Request') and 'Action="START"' in lines[-1]
    assert all(line.split(";", 1)[0] in ("", "RES") for line in lines)
    ops = [c.op for c in commands]
    assert "stop" not in ops and ops.count("start") == 1
    assert any(c.op == "create_fb" and c.type == f"filling::SK_Dwell#{HASH}" for c in commands)


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
    network = change(library)
    edges = [(c.source, c.destination) for c in network.connections]
    good = FakeClient({"PROC.Wait": ("filling::SK_Dwell", "RUNNING"), "Module": ("modlib::MOD_StateManager", "RUNNING")},
                      edges, {"PROC.Wait.Duration": "0.5"})
    assert verify(good, network) == []
    bad = FakeClient({"PROC.Wait": ("filling::SK_Dwell", "STOPPED"), "PROC.Extra": ("filling::SK_Tare", "RUNNING")},
                     edges[1:], {"PROC.Wait.Duration": "0.25"})
    problems = verify(bad, network)
    assert "unexpected instance PROC.Extra" in problems
    assert "missing connection Module.RUN_RESETTING -> PROC.Wait.START" in problems
    assert "PROC.Wait is STOPPED, expected RUNNING" in problems
    assert "PROC.Wait.Duration = 0.25, expected 0.5" in problems
