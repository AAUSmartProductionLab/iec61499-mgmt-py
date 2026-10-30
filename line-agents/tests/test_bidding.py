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
from lineagents.execute import SimulatedExecutor, simulated_reconfigure      # noqa: E402
from lineagents.product import ProductAgent                                  # noqa: E402
from lineagents.resource import ResourceAgent                                # noqa: E402
from lineagents.xmpp import embedded_server, run                             # noqa: E402

DOMAIN = "localhost"


@pytest.fixture(scope="module")
def line():
    resources, products = example_line.build()
    return {k: v for k, v in resources.items() if is_module(v)}, products


async def run_order(modules: dict, product: dict, fail: tuple[str, ...] = (), failing: tuple[str, ...] | None = None,
                    reconfigurer=None):
    async with embedded_server(DOMAIN, port=0) as port:
        executors = {}

        def executor_for(name):          # the skills in ``fail`` fail on the modules in ``failing`` (all: None)
            fails = fail if failing is None or name in failing else ()
            return lambda env: executors.setdefault(name, SimulatedExecutor(0.05, fails))

        agents = [ResourceAgent(f"{name.lower()}@{DOMAIN}", "secret", env, executor_for(name), port=port,
                                reconfigurer=reconfigurer) for name, env in modules.items()]
        for agent in agents:
            await agent.start(auto_register=True)
        order = ProductAgent(f"order1@{DOMAIN}", "secret", product, lambda: [str(a.jid) for a in agents],
                             answer_seconds=3, port=port)
        await order.start(auto_register=True)
        await asyncio.wait_for(order.finished.wait(), 60)
        for agent in [order, *agents]:
            await agent.stop()
        return order.history, executors, agents


def test_each_step_of_the_vial_goes_to_the_module_that_offers_it(line):
    modules, products = line
    history, executors, _ = run(run_order(modules, products["Vial2mLAAS"]))
    assert [(d.step, d.resource, d.skill, d.outcome) for d in history] == [
        ("Filling", "FillingModuleAAS", "Dispensing", "done"),
        ("Stoppering", "StopperingModuleAAS", "Stoppering", "done"),
        ("Capping", "CappingModuleAAS", "Capping", "done"),
        ("Inspection", "InspectionModuleAAS", "Inspection", "done")]
    assert all(d.proposals == 1 and d.refusals == 3 for d in history)
    assert executors["FillingModuleAAS"].ran == [("Dispensing", {"Volume": 2.0})]   # the vial's 2.0 mL


def test_a_step_that_fails_everywhere_ends_the_order(line):
    modules, products = line
    history, _, _ = run(run_order(modules, products["Vial2mLAAS"], fail=("Stoppering",)))
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
    history, executors, _ = run(run_order(modules, products["Vial2mLAAS"], fail=("Dispensing",),
                                          failing=("FillingModuleAAS",)))
    filling = [(d.resource, d.outcome, d.proposals) for d in history if d.step == "Filling"]
    assert filling in ([("FillingModuleAAS", "failed", 2), ("FillingModule2AAS", "done", 1)],
                       [("FillingModule2AAS", "done", 2)])     # whichever answered first was chosen
    assert [d.outcome for d in history if d.step != "Filling"] == ["done"] * 3


def with_bottom_up_filling(resources: dict) -> dict:
    """The filling module's AAS with BottomUpFilling described (as the skill editor saves it: not built)
    and its capabilities derived anew: it offers BottomUpFilling after a reconfiguration."""
    sys.path.insert(0, str(ROOT / "cell" / "eval"))
    from modreg.offer import capabilities
    from modsync.aasjson import parts, submodel
    from scenarios import with_written
    module = resources["FillingModuleAAS"]
    mine = {node.get("globalAssetId") for node in parts(submodel(module, "HierarchicalStructures"))}
    components = [env for env in example_line.components().values()
                  if env["assetAdministrationShells"][0]["assetInformation"].get("globalAssetId") in mine]
    return capabilities(with_written(module, components), components)


def bottom_up(product: dict) -> dict:
    """The product asking for its filling bottom-up (BottomUpFilling, a Filling) instead."""
    return json.loads(json.dumps(product).replace("/semantics/Filling\"", "/semantics/BottomUpFilling\""))


def test_a_syringe_filled_bottom_up_gets_the_skill_created_first():
    """The syringe asks for BottomUpFilling; only the filling module offers it, after a reconfiguration
    (the skill is described, not built); its agent creates the skill (simulated here) and runs it.
    A vial asks for Filling: Dispensing, built, before BottomUpFilling."""
    resources, products = example_line.build()
    modules = {k: v for k, v in resources.items() if is_module(v)}
    modules["FillingModuleAAS"] = with_bottom_up_filling(resources)
    syringe = bottom_up(products["PrefilledSyringe1mLAAS"])
    history, executors, agents = run(run_order(modules, syringe, reconfigurer=simulated_reconfigure))
    assert [(d.step, d.resource, d.skill, d.outcome, d.reconfigured) for d in history] == [
        ("Filling", "FillingModuleAAS", "BottomUpFilling", "done", True),
        ("Stoppering", "StopperingModuleAAS", "Stoppering", "done", False),
        ("Inspection", "InspectionModuleAAS", "Inspection", "done", False)], [d.detail for d in history]
    assert executors["FillingModuleAAS"].ran[0] == ("BottomUpFilling", {"Volume": 1.0})    # the syringe's 1 mL
    filling = next(a for a in agents if a.name == "FillingModuleAAS")
    assert any(line.startswith("reconfigured for BottomUpFilling: built BottomUpFilling") for line in filling.log)

    history, executors, _ = run(run_order(modules, products["Vial2mLAAS"], reconfigurer=simulated_reconfigure))
    assert history[0].skill == "Dispensing" and not history[0].reconfigured


def test_without_a_way_to_reconfigure_the_step_fails():
    resources, products = example_line.build()
    modules = {k: v for k, v in resources.items() if is_module(v)}
    modules["FillingModuleAAS"] = with_bottom_up_filling(resources)
    history, _, _ = run(run_order(modules, bottom_up(products["PrefilledSyringe1mLAAS"])))
    assert history[0].outcome == "failed" and "cannot reconfigure" in history[0].detail
