"""Transport on the example line: the planar table's shuttles bid for Transporting as the modules bid
for their steps. The product agent has the vial carried to each module's station (its transfer point
on the table, from the AASs) before it accepts the module's proposal. Custody (vocabulary 0.7): a
shuttle with room receives the vial, only the shuttle that has it transports it, and it releases it
at the end; every call goes to every agent and the shuttles' constraints decide. Three vials at once
go on three shuttles. Over SPADE's own XMPP server in this process, the skills simulated; the
constraints alone, without XMPP, first.
"""
import asyncio
from pathlib import Path
import sys

import pytest

pytest.importorskip("spade")
pytest.importorskip("aas_model")

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "line-agents"), str(ROOT / "cell" / "examples")]

import example_line                                                         # noqa: E402
from lineagents.aas import (HOLDING, OCCUPANCY, Offer, is_module, offer, request, station,      # noqa: E402
                            transport_request)
from lineagents.execute import SimulatedExecutor                             # noqa: E402
from lineagents.product import RECEIVE, RELEASE, TRANSPORT, ProductAgent     # noqa: E402
from lineagents.resource import ResourceAgent                                # noqa: E402
from lineagents.xmpp import embedded_server, run                             # noqa: E402

DOMAIN = "localhost"


@pytest.fixture(scope="module")
def line():
    resources, products = example_line.build()
    modules = {k: v for k, v in resources.items() if is_module(v)}
    placed = [*modules.values(), example_line.table(), example_line.line(resources)]
    return modules, example_line.shuttles(), {name: station(placed, name) for name in modules}, products


async def produce(line, product: str, count: int):
    modules, shuttles, stations, products = line
    async with embedded_server(DOMAIN, port=0) as port:
        executors = {name: SimulatedExecutor(0.1) for name in [*modules, *shuttles]}
        agents = []
        for name, env in [*modules.items(), *shuttles.items()]:
            agent = ResourceAgent(f"{name.lower()}@{DOMAIN}", "secret", env, lambda env, n=name: executors[n], port=port)
            agent.station = stations.get(name)
            agents.append(agent)
        for agent in agents:
            await agent.start(auto_register=True)
        made = [ProductAgent(f"{product.lower()}-{n}@{DOMAIN}", "secret", products[product],
                             lambda: [str(a.jid) for a in agents], answer_seconds=2, again_seconds=0.2, port=port)
                for n in range(1, count + 1)]
        for agent in made:
            await agent.start(auto_register=True)
        await asyncio.wait_for(asyncio.gather(*(a.finished.wait() for a in made)), 180)
        await asyncio.sleep(0.5)                       # the releases arrive
        holding = {a.name: a.holds() for a in agents}
        for agent in [*made, *agents]:
            await agent.stop()
        return made, executors, holding


def test_only_the_shuttle_that_holds_the_vial_transports_it_and_a_full_one_receives_none(line):
    modules, shuttles, _, _ = line
    shuttle, filling = shuttles["PlanarShuttle1AAS"], modules["FillingModuleAAS"]
    to_filling = transport_request(240.0, 660.0, 0.0)
    free = {HOLDING: False, OCCUPANCY: 0.0}
    refused = offer(shuttle, to_filling, free, frozenset({OCCUPANCY}))
    assert not isinstance(refused, Offer) and not refused.busy and "Holding = True" in refused[0]
    assert offer(shuttle, to_filling, {HOLDING: True, OCCUPANCY: 1.0}).skill == "MoveToPosition"
    received = offer(shuttle, request("Receiving"), free)
    assert received.skill == "" and received.effects == {HOLDING: True}
    full = offer(shuttle, request("Receiving"), {HOLDING: False, OCCUPANCY: 1.0}, frozenset({OCCUPANCY}))
    assert not isinstance(full, Offer) and full.busy and "Occupancy < 1.0" in full[0]       # for now
    assert offer(shuttle, request("Releasing"), {HOLDING: True, OCCUPANCY: 1.0}).effects == {HOLDING: False}
    assert not isinstance(offer(shuttle, request("Releasing"), free), Offer)
    assert not isinstance(offer(filling, request("Receiving"), free), Offer)                  # a module holds nothing


def test_custody_lapses_when_the_product_agent_is_not_heard_from(line):
    _, shuttles, _, _ = line
    agent = ResourceAgent(f"shuttle@{DOMAIN}", "secret", shuttles["PlanarShuttle1AAS"], lambda env: SimulatedExecutor(0.1))
    agent.custody = {"gone@localhost": 0.0, "here@localhost": 1e12}
    assert agent.holds() == {"here@localhost"}
    assert agent.state("here@localhost", {})[OCCUPANCY] == 1.0 and agent.state("other@localhost", {})[HOLDING] is False


def test_the_vial_is_carried_to_each_module_by_one_shuttle(line):
    _, _, stations, _ = line
    assert stations["FillingModuleAAS"] == (240.0, 660.0, 0.0) and stations["StopperingModuleAAS"] == (600.0, 660.0, 90.0)
    made, executors, holding = run(produce(line, "Vial2mLAAS", 1))
    history = made[0].history
    assert made[0].done, [(d.step, d.outcome, d.detail) for d in history]
    expected = [RECEIVE]
    for step in ("Filling", "Stoppering", "Capping", "Inspection"):
        if stations[f"{step}ModuleAAS"] is not None:
            expected.append(TRANSPORT)
        expected.append(step)
    assert [d.step for d in history] == expected + [RELEASE]
    carried = [d for d in history if d.step in (RECEIVE, TRANSPORT, RELEASE)]
    assert len({d.resource for d in carried}) == 1 and carried[0].resource.startswith("PlanarShuttle")
    assert all(d.outcome == "done" for d in carried)
    shuttle = executors[carried[0].resource]
    assert shuttle.ran[0] == ("MoveToPosition", {"X": 240.0, "Y": 660.0, "Rz": 0.0})       # to the filling module
    assert holding == {name: set() for name in holding} and made[0].held_by == ""          # released at the end


def test_three_vials_at_once_go_on_three_shuttles(line):
    made, executors, holding = run(produce(line, "Vial2mLAAS", 3))
    assert all(a.done for a in made), [[(d.step, d.outcome, d.detail) for d in a.history] for a in made]
    carriers = [{d.resource for d in a.history if d.step in (RECEIVE, TRANSPORT, RELEASE)} for a in made]
    assert all(len(c) == 1 for c in carriers) and len(set.union(*carriers)) == 3
    assert executors["FillingModuleAAS"].ran == [("Dispensing", {"Volume": 2.0})] * 3
    assert holding == {name: set() for name in holding}
