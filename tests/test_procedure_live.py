"""Procedure (PROC) on the real filling cell: pattern FBs, online changes, read-back and boot file.

Opt-in with --forte-exe; the executable must contain the filling-cell types.
"""
import time

from conftest import free_port, launch_forte
from iec61499_mgmt import Network, NetworkPatch, boot_file, deployment, plan, verify
from iec61499_mgmt.protocol import Client, Command
from iec61499_mgmt.sysfile import load_application
from livecell import COMPLETE, FC, IDLE, SYS, Cell, CellServer, Resource, Ua, modbus_overrides, start


def call(name, skill, **params):
    """Instances and connections of one P_Call bound to ``EM_Filler.<skill>``."""
    fb = {"name": f"PROC.{name}", "type": FC + "P_Call", "parameters": {
        p: {"type": "LREAL", "value": v} for p, v in params.items()}}
    skill = f"EM_Filler.{skill}"
    edges = [(f"PROC.{name}.CALL", f"{skill}.CALL", "event"), (f"{skill}.DONE", f"PROC.{name}.DONE", "event"),
             (f"{skill}.FAILED", f"PROC.{name}.FAILED", "event"), (f"{skill}.CallError", f"PROC.{name}.CallError", "data"),
             (f"PROC.{name}.ERR", "Facade.FAILED", "event"), ("Facade.RESET", f"PROC.{name}.RESET", "event")]
    edges += [(f"PROC.{name}.CP{p[1]}", f"{skill}.{p}", "data") for p in params]
    return [fb], edges


def network(library, blocks, flow):
    """PROC network from pattern blocks and event flow edges, with type hashes from the library."""
    instances, edges = [], [(s, d, "event") for s, d in flow]
    for fbs, block_edges in blocks:
        instances += fbs
        edges += block_edges
    for fb in instances:
        fb["type_hash"] = library.types[fb["type"]].type_hash
    return Network.model_validate({"resource": "RES", "instances": instances, "connections": [
        {"source": s, "destination": d, "kind": k} for s, d, k in edges]})


def fill_once(library, volume=0.3):
    """v1: MoveDown, Dose(volume), MoveUp."""
    return network(library, [call("MoveDown", "MoveDown"), call("Dose", "Dose", P1=volume), call("MoveUp", "MoveUp")],
                   [("Facade.START", "PROC.MoveDown.EI"), ("PROC.MoveDown.EO", "PROC.Dose.EI"),
                    ("PROC.Dose.EO", "PROC.MoveUp.EI"), ("PROC.MoveUp.EO", "Facade.FINISHED")])


def fill_loop(library, count, volume=0.3):
    """v2: the Dose call inside a P_Loop whose Count is a parameter."""
    loop = ([{"name": "PROC.Loop", "type": FC + "P_Loop", "parameters": {"Count": {"type": "UINT", "value": count}}}],
            [("Facade.RESET", "PROC.Loop.RESET", "event")])
    return network(library, [call("MoveDown", "MoveDown"), call("Dose", "Dose", P1=volume), call("MoveUp", "MoveUp"), loop],
                   [("Facade.START", "PROC.MoveDown.EI"), ("PROC.MoveDown.EO", "PROC.Loop.EI"),
                    ("PROC.Loop.BODY", "PROC.Dose.EI"), ("PROC.Dose.EO", "PROC.Loop.NEXT"),
                    ("PROC.Loop.EO", "PROC.MoveUp.EI"), ("PROC.MoveUp.EO", "Facade.FINISHED")])


def apply(res, current, desired, library, expected_class):
    """Plan and execute a change, then read it back."""
    result = plan(current, desired, library)
    assert result.change_class == expected_class
    for command in result.commands:
        res.client.execute(command)
    assert verify(res.client, desired) == []
    return result


def run_procedure(ua):
    """Reset the unit in Production mode and run the procedure to Complete."""
    assert ua.call("Unit/Reset", 1, 0) == [True, 0]
    ua.expect("Unit/State", IDLE)
    assert ua.call("Unit/Start", 1) == [True, 0]
    ua.expect("Unit/State", COMPLETE, timeout=10)


def test_library_from_runtime(library):
    """Every filling-cell type has a runtime hash; fixed instances provide the boundary ports."""
    assert all(t.type_hash.startswith("v2:") for t in library.types.values())
    assert {"EI", "CALL", "DONE", "FAILED", "CP1"} <= library.types[FC + "P_Call"].ports.keys()
    assert library.boundary_ports["EM_Filler.Dose.P1"].data_type == "LREAL"
    assert "Facade.START" in library.boundary_ports


def test_fill_once_then_twice_online(request, forte_exe, tmp_path, library):
    """Run v1, change to a Dose loop online, run again, then change the loop count by WRITE only."""
    sim_port, ua_port = free_port(), free_port()
    cell = Cell(travel_s=0.2, fill_rate=0.5)  # overshoot < one 100 ms sample
    with CellServer(cell, port=sim_port), \
            launch_forte(forte_exe, tmp_path, request.config.getoption("--forte-runtime-dir"),
                         ["-op", str(ua_port)]) as port, Client("127.0.0.1", port) as client:
        res = Resource(client)
        client.execute(Command(op="create_fb", resource="", name="RES", type="iec61499::system::EMB_RES"))
        for command in load_application(SYS, "FillingCell").commands("RES", modbus_overrides(sim_port)):
            client.execute(command)
        start(res)
        empty = Network(resource="RES")
        v1 = fill_once(library)
        apply(res, empty, v1, library, "structural")
        res.write("Facade.Installed", True)
        res.fire("Facade.CONFIG")
        ua = Ua(ua_port)
        try:
            ua.expect("State/NeedleUp", True)
            assert ua.call("Occupation/Occupy", 1) == [True, 0]
            run_procedure(ua)
            assert 0.3 <= cell.filled_ml < 0.3 + 0.1
            fixed = {fb["Name"] for fb in client.execute(Command(op="query_fbs", resource="RES")).fbs
                     if not fb["Name"].startswith("PROC.")}

            v2 = fill_loop(library, count=2)
            apply(res, v1, v2, library, "structural")
            run_procedure(ua)
            assert 0.9 <= cell.filled_ml < 0.9 + 0.3
            doses = [name for _, name, on in cell.coil_trace if on]
            assert doses == ["MoveDown", "Dose", "MoveUp", "MoveDown", "Dose", "Dose", "MoveUp"]

            patch = NetworkPatch.model_validate({"base_hash": v2.digest(), "operations": [
                {"op": "set_parameter", "instance": "PROC.Loop", "parameter": "Count",
                 "value": {"type": "UINT", "value": 3}}]})
            result = apply(res, v2, patch.apply(v2), library, "parameter")
            assert [c.op for c in result.commands] == ["write"]
            after = client.execute(Command(op="query_fbs", resource="RES")).fbs
            assert fixed <= {fb["Name"] for fb in after}
            assert all(fb["Status"] == "RUNNING" for fb in after)
            assert cell.shoot_through == 0
        finally:
            ua.close()


def test_boot_file_restores_fixed_part_and_procedure(request, forte_exe, tmp_path, library):
    """A boot file of the fixed application plus PROC recreates both on a fresh runtime."""
    v1 = fill_once(library, volume=0.5)
    path = tmp_path / "forte.fboot"
    path.write_text(boot_file(deployment(load_application(SYS, "FillingCell"), procedure=v1, library=library)),
                    encoding="utf-8")
    ua_port = free_port()
    with launch_forte(forte_exe, tmp_path, request.config.getoption("--forte-runtime-dir"),
                      ["-op", str(ua_port), "-f", str(path)]) as port, Client("127.0.0.1", port) as client:
        deadline = time.monotonic() + 10
        while (problems := verify(client, v1)) and time.monotonic() < deadline:
            time.sleep(0.2)
        assert problems == []
        names = {fb["Name"] for fb in client.execute(Command(op="query_fbs", resource="RES")).fbs}
        assert {"Unit", "Occupation", "Observer", "EM_Filler.Dose", "PROC.Dose"} <= names
        ua = Ua(ua_port)
        try:
            ua.expect("Unit/State", 2)                     # safe simulated start state: Stopped
            ua.expect("State/Safe", True)
            assert ua.call("Occupation/Occupy", 1) == [True, 0]
            assert ua.call("Unit/Reset", 1, 0) == [True, 0]
            ua.expect("Unit/State", IDLE)
        finally:
            ua.close()


def test_pattern_blocks(forte):
    """Choice, fork/join, wait and loop behave as specified (event outputs counted with E_CTU)."""
    res, _ = forte
    counters = {"T": "PROC.Choice.EO_TRUE", "F": "PROC.Choice.EO_FALSE", "J": "PROC.Join.EO",
                "W": "PROC.Wait.EO", "L": "PROC.Loop.EO", "B": "PROC.Loop.BODY"}
    for name, typ in [("Choice", "P_Choice"), ("Fork", "P_Fork"), ("Join", "P_Join"), ("Wait", "P_Wait"),
                      ("Loop", "P_Loop")]:
        res.create(f"PROC.{name}", FC + typ)
    for c, source in counters.items():
        res.create(f"C{c}", "iec61499::events::E_CTU")
        res.send("connect", source=source, destination=f"C{c}.CU")
    res.send("connect", source="PROC.Fork.EO1", destination="PROC.Join.EI1")
    res.send("connect", source="PROC.Fork.EO2", destination="PROC.Join.EI2")
    start(res)

    def count(c):
        return int(res.read(f"C{c}.CV"))

    res.write("PROC.Choice.Cond", True)
    res.fire("PROC.Choice.EI")
    res.write("PROC.Choice.Cond", False)
    res.fire("PROC.Choice.EI")
    assert (count("T"), count("F")) == (1, 1)
    res.fire("PROC.Fork.EI")                     # both branches arrive: join fires once
    assert count("J") == 1
    res.fire("PROC.Join.EI1")                    # one of two branches: no output yet
    assert count("J") == 1
    res.fire("PROC.Join.EI2")
    assert count("J") == 2
    res.write("PROC.Wait.DT", "T#300ms")
    res.fire("PROC.Wait.EI")
    assert count("W") == 0
    time.sleep(0.5)
    assert count("W") == 1
    res.fire("PROC.Wait.EI")
    res.fire("PROC.Wait.RESET")                  # cancelled timer never fires
    time.sleep(0.5)
    assert count("W") == 1
    res.write("PROC.Loop.Count", 0)
    res.fire("PROC.Loop.EI")                     # zero iterations: straight to EO
    assert (count("B"), count("L")) == (0, 1)
    res.write("PROC.Loop.Count", 2)
    res.fire("PROC.Loop.EI")
    res.fire("PROC.Loop.NEXT")
    res.fire("PROC.Loop.NEXT")
    assert (count("B"), count("L")) == (2, 2)
