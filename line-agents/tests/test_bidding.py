"""The bidding protocol on the example line: a resource agent per module, a product agent for the vial,
over SPADE's own XMPP server in this process, the skills run by a simulated executor.

Needs the ``agents`` extra (SPADE) and the ``registration`` extra (the example line's AASs).
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
from lineagents.aas import is_module                                         # noqa: E402
from lineagents.execute import SimulatedExecutor                             # noqa: E402
from lineagents.product import ProductAgent                                  # noqa: E402
from lineagents.resource import ResourceAgent                                # noqa: E402
from lineagents.xmpp import embedded_server, run                             # noqa: E402

DOMAIN = "localhost"


@pytest.fixture(scope="module")
def line():
    resources, products = example_line.build()
    return {k: v for k, v in resources.items() if is_module(v)}, products


async def run_order(modules: dict, product: dict, fail: tuple[str, ...] = ()):
    async with embedded_server(DOMAIN, port=0) as port:
        executors = {}

        def executor_for(name):
            return lambda env: executors.setdefault(name, SimulatedExecutor(0.05, fail))

        agents = [ResourceAgent(f"{name.lower()}@{DOMAIN}", "secret", env, executor_for(name), port=port)
                  for name, env in modules.items()]
        for agent in agents:
            await agent.start(auto_register=True)
        order = ProductAgent(f"order1@{DOMAIN}", "secret", product, lambda: [str(a.jid) for a in agents],
                             answer_seconds=3, port=port)
        await order.start(auto_register=True)
        await asyncio.wait_for(order.finished.wait(), 60)
        for agent in [order, *agents]:
            await agent.stop()
        return order.history, executors


def test_each_step_of_the_vial_goes_to_the_module_that_offers_it(line):
    modules, products = line
    history, executors = run(run_order(modules, products["Vial2mLAAS"]))
    assert [(d.step, d.resource, d.skill, d.outcome) for d in history] == [
        ("Filling", "FillingModuleAAS", "Dispensing", "done"),
        ("Stoppering", "StopperingModuleAAS", "Stoppering", "done"),
        ("Capping", "CappingModuleAAS", "Capping", "done"),
        ("Inspection", "InspectionModuleAAS", "Inspection", "done")]
    assert all(d.proposals == 1 and d.refusals == 3 for d in history)
    assert executors["FillingModuleAAS"].ran == [("Dispensing", {"Volume": 2.0})]   # the vial's 2.0 mL


def test_a_step_that_fails_ends_the_order(line):
    modules, products = line
    history, _ = run(run_order(modules, products["Vial2mLAAS"], fail=("Stoppering",)))
    assert [(d.step, d.outcome) for d in history] == [("Filling", "done"), ("Stoppering", "failed")]
    assert "simulated" in history[-1].detail
