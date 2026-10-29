"""The bidding protocol on the example line: a resource agent per module, a product agent for the vial,
over SPADE's own XMPP server in this process, the skills run by a simulated executor.

Needs the ``agents`` extra (SPADE) and the ``registration`` extra (the example line's AASs).
"""
import asyncio
import json
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


async def run_order(modules: dict, product: dict, fail: tuple[str, ...] = (), failing: tuple[str, ...] | None = None):
    async with embedded_server(DOMAIN, port=0) as port:
        executors = {}

        def executor_for(name):          # the skills in ``fail`` fail on the modules in ``failing`` (all: None)
            fails = fail if failing is None or name in failing else ()
            return lambda env: executors.setdefault(name, SimulatedExecutor(0.05, fails))

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


def test_a_step_that_fails_everywhere_ends_the_order(line):
    modules, products = line
    history, _ = run(run_order(modules, products["Vial2mLAAS"], fail=("Stoppering",)))
    assert [(d.step, d.outcome) for d in history] == [("Filling", "done"), ("Stoppering", "failed"),
                                                      ("Stoppering", "nobody")]     # asked again: no other module
    assert "simulated" in history[1].detail


def second_filling_module(env: dict) -> dict:
    """The filling module's AAS again, under ids of its own: a second module that offers Filling."""
    text = json.dumps(env).replace("FillingModuleAAS", "FillingModule2AAS")
    old = env["assetAdministrationShells"][0]["id"]
    return json.loads(text.replace(old, old + "2"))


def test_a_step_that_fails_is_carried_out_by_another_module(line):
    modules, products = line
    modules = {**modules, "FillingModule2AAS": second_filling_module(modules["FillingModuleAAS"])}
    history, executors = run(run_order(modules, products["Vial2mLAAS"], fail=("Dispensing",),
                                       failing=("FillingModuleAAS",)))
    filling = [(d.resource, d.outcome, d.proposals) for d in history if d.step == "Filling"]
    assert filling in ([("FillingModuleAAS", "failed", 2), ("FillingModule2AAS", "done", 1)],
                       [("FillingModule2AAS", "done", 2)])     # whichever answered first was chosen
    assert [d.outcome for d in history if d.step != "Filling"] == ["done"] * 3
