"""The planar table's AASs (H3): the table and each shuttle described as modules of the planar
controller, with the flyway layout; a shuttle run from its AAS alone on the controller's simulation."""
import asyncio
import json
from pathlib import Path
import socket
import sys
import time

import pytest

from modsync.aasjson import at, children, submodel

from modreg import model
from modreg.frames import chain, coordinates, where
from modreg.ontology import Blueprint, check
from modreg.planar import NotShown, Table, _read, describe_all

ROOT = Path(__file__).resolve().parents[2]
CONTROLLER, HMI = ROOT / "planar-controller", ROOT / "iec61499-opcua-hmi"
SIM = Table(columns=4, rows=3, holes=frozenset({(2, 1)}), shuttles=(1, 2))


def envs_of(table: Table) -> dict[str, dict]:
    return {(env := model.build(p))["assetAdministrationShells"][0]["idShort"]: env for p in describe_all(table)}


def test_the_table_lists_its_shuttles_and_its_flyways_with_where_they_are():
    envs = envs_of(SIM)
    assert list(envs) == ["PlanarTableAAS", "PlanarShuttle1AAS", "PlanarShuttle1XbotAAS",
                          "PlanarShuttle2AAS", "PlanarShuttle2XbotAAS"]
    nodes = {n["idShort"]: n for n in children(at(submodel(envs["PlanarTableAAS"], "HierarchicalStructures"), "EntryNode"))}
    assert nodes["PlanarShuttle1"]["globalAssetId"] == envs["PlanarShuttle1AAS"]["assetAdministrationShells"][0]["assetInformation"]["globalAssetId"]
    flyways = sorted(name for name in nodes if name.startswith("Flyway_"))
    assert len(flyways) == 11 and "Flyway_2_1" not in flyways                  # 4 x 3, the hole left out
    assert where(list(envs.values()), "PlanarTableAAS", "Flyway_3_2").position == (840.0, 600.0, 0.0)
    assert nodes["Flyway_0_0"]["supplementalSemanticIds"][0]["keys"][0]["value"].endswith("/semantics/Flyway")
    # The table's base is the root; a shuttle's xbot is relative to it and follows the controller's pose.
    assert chain(list(envs.values()), "PlanarShuttle1AAS", "Xbot") == [("PlanarShuttle1AAS", "Xbot"), ("PlanarTableAAS", "TableBase")]
    xbot = coordinates(envs["PlanarShuttle1AAS"])["Xbot"]
    assert {e["idShort"]: e["value"]["keys"][-1]["value"] for e in children(xbot) if e["idShort"].endswith("Source")} == {
        "XSource": "Xbot_X", "YSource": "Xbot_Y", "YawSource": "Xbot_Rz"}
    # Nothing of a FORTE program: no rule set; the controller's own errors beside the rules'.
    skills = submodel(envs["PlanarShuttle1XbotAAS"], "Skills")
    assert at(submodel(envs["PlanarShuttle1AAS"], "Skills"), "RuleSet") is None
    assert {"NotOnTable", "XbotNotDetected", "NotPermitted"} <= {e["idShort"] for e in children(at(skills, "Errors"))}
    move = at(skills, "MoveToPosition")
    assert at(move, "Conditions") is None and at(move, "Completion") is None
    start = at(move, "Start", "Start")
    assert [v["value"]["idShort"] for v in start["outputVariables"]] == ["Accepted", "ErrorID", "ReachedX", "ReachedY", "ReachedRz"]
    blueprint = Blueprint(ROOT / "ontology" / "ARSO")
    for name, env in envs.items():
        assert check(env, blueprint).ok, name


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def controllers():
    """Makes the planar controller on its simulated driver, in this process (as its own tests run it):
    ``controllers(xbots, **speeds)`` gives the controller, its OPC UA server (not started) and endpoint."""
    if not (CONTROLLER / "planar").is_dir() or not (HMI / "modlink").is_dir():
        pytest.skip("the planar-controller and iec61499-opcua-hmi submodules are needed")
    sys.path[:0] = [str(CONTROLLER), str(CONTROLLER / "tests"), str(HMI)]
    from planar.layout import Layout
    from planar.modules import PlanarController
    from planar.opcua_server import OpcUaServer
    from planar.sim_driver import SimDriver
    made = []

    def make(xbots: dict, **speeds):
        sim = SimDriver(Layout(cols=SIM.columns, rows=SIM.rows, holes=SIM.holes), xbots, **speeds)
        ctl = PlanarController(sim, sorted(xbots))
        ctl.coordinator.on_tick.insert(0, lambda: sim.advance(time.monotonic()))
        endpoint = f"opc.tcp://127.0.0.1:{free_port()}/"
        made.append(ctl)
        return ctl, OpcUaServer(ctl, endpoint), endpoint

    try:
        yield make
    finally:
        for ctl in made:
            ctl.shutdown()
        del sys.path[:3]


@pytest.fixture
def controller(controllers):
    return controllers({1: (0.06, 0.06, 0.0), 2: (0.90, 0.66, 0.0)})


def test_a_shuttle_is_moved_from_its_aas_alone(controller):
    ctl, server, endpoint = controller
    asyncio.run(_serving(ctl, server, _move(endpoint)))


def test_the_table_is_read_from_the_controller(controller):
    """Its layout once the PMC is connected, and the shuttles it offers."""
    ctl, server, endpoint = controller
    asyncio.run(_serving(ctl, server, _layout(endpoint)))


def test_the_line_runs_to_the_stations_its_aass_say(controllers):
    """H5: the planar controller's line scenario (product agents taking shuttles through Infeed,
    Filling, Stoppering, Capping, Outfeed) with each station where the AASs of the line and its
    modules put it, in the table's frame, instead of the scenario's own STATIONS."""
    import inspect
    from line_scenario import run_line, summary
    if "places" not in inspect.signature(run_line).parameters:
        pytest.skip("the planar controller in the submodule takes no stations from outside yet")
    sys.path.insert(0, str(ROOT / "cell" / "examples"))
    try:
        import example_line
        resources, _ = example_line.build()
        places = example_line.stations([example_line.table(), example_line.line(resources), *resources.values()])
    finally:
        sys.path.remove(str(ROOT / "cell" / "examples"))
    # Three xbots on the flyway centres of the left column, fast moves: as the scenario's own test.
    ctl, server, endpoint = controllers({1: (0.12, 0.12, 0.0), 2: (0.12, 0.36, 0.0), 3: (0.12, 0.60, 0.0)},
                                        speed=2.0, accel=10.0, turn_speed=20.0, turn_accel=200.0)
    found = {}

    async def line():
        found["report"] = await run_line(endpoint, agents=2, products=2, process_s=(0.1, 0.2), fail_p=0.0,
                                         sample=False, places=places)

    asyncio.run(_serving(ctl, server, line()))
    report = found["report"]
    assert not report.problems, summary(report)
    assert [p.outcome for p in report.products] == ["finished"] * 4
    assert {station for p in report.products for station, _ in p.steps} == set(places)


async def _serving(ctl, server, work):
    await server.init()
    ctl.start()
    serving = asyncio.create_task(server.run())
    try:
        await asyncio.sleep(0.5)
        await work
    finally:
        serving.cancel()
        await asyncio.gather(serving, return_exceptions=True)


def resources_of(envs: dict[str, dict]) -> dict:
    """The modules of the AASs as modlink reads them from one environment."""
    from modlink import aas
    whole = {"assetAdministrationShells": [e["assetAdministrationShells"][0] for e in envs.values()],
             "submodels": [s for e in envs.values() for s in e["submodels"]]}
    return {r.id_short: r for r in (aas.describe(e) for e in aas.environments(json.loads(json.dumps(whole))) if e.is_module)}


async def _to_execute(table) -> None:
    from modlink.module import Module
    async with table.connect() as link:
        assert await link.wait_connected(10)
        await Module(link, table.root, "agent-1", table).bring_to_execute(30)


async def _move(endpoint: str):
    from modlink.codes import ModuleState
    from modlink.module import Module
    resources = resources_of(envs_of(Table(SIM.columns, SIM.rows, SIM.shuttles, SIM.holes, endpoint)))
    assert set(resources) == {"PlanarTableAAS", "PlanarShuttle1AAS", "PlanarShuttle2AAS"}
    await _to_execute(resources["PlanarTableAAS"])
    shuttle = resources["PlanarShuttle1AAS"]
    assert shuttle.skills["MoveToPosition"].held_by == "PlanarShuttle1XbotAAS"
    async with shuttle.connect() as link:
        assert await link.wait_connected(10)
        moved = Module(link, shuttle.root, "agent-1", shuttle)
        await moved.wait_state(ModuleState.EXECUTE, timeout=30)
        await moved.occupy()
        run = await moved.run("MoveToPosition", 780.0, 660.0, 90.0, timeout=60)
        assert run.succeeded, run
        assert run.results["ReachedX"] == 780.0 and run.results["ReachedY"] == 660.0
        await moved.release()


async def _layout(endpoint: str):
    try:
        await _read(endpoint, 10)
    except NotShown as e:
        if "shows no" in str(e):
            pytest.skip("the planar controller in the submodule does not show its layout yet")
        assert "not been connected" in str(e)
    await _to_execute(resources_of(envs_of(Table(SIM.columns, SIM.rows, SIM.shuttles, SIM.holes, endpoint)))["PlanarTableAAS"])
    assert await _read(endpoint, 10) == Table(SIM.columns, SIM.rows, SIM.shuttles, SIM.holes, endpoint, 2, 240.0)
