"""The agents with a module that runs: the filling module on FORTE with its simulator (pc target), its
resource agent running Dispensing over OPC UA (modlink) for a vial order, and creating BottomUpFilling
online in the running program for a syringe filled bottom-up before it runs it; the other modules'
agents simulate their skills.

    python -m pytest line-agents/tests/test_agents_live.py --module-forte-exe <a FORTE with every module>
"""
import asyncio
import copy
from pathlib import Path
import sys
import tempfile

import pytest

pytest.importorskip("spade")
pytest.importorskip("aas_model")

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "line-agents"), str(ROOT / "cell" / "examples"), str(ROOT / "cell" / "eval"),
                str(ROOT / "aas61499-tools" / "tests")]

import example_line                                                         # noqa: E402
from lineagents.aas import is_module                                         # noqa: E402
from lineagents.execute import OpcUaExecutor, SimulatedExecutor, rebuild     # noqa: E402
from lineagents.product import ProductAgent                                  # noqa: E402
from lineagents.resource import ResourceAgent                                # noqa: E402
from lineagents.xmpp import embedded_server, run                             # noqa: E402
from modreg.plancheck import at, children                                    # noqa: E402

DOMAIN = "localhost"


@pytest.fixture
def filling(request):
    """FORTE with the filling module and its simulator; the filling module's AAS (pc target) with its
    OPC UA endpoint where that FORTE serves it."""
    exe = request.config.getoption("--module-forte-exe")
    if not exe:
        pytest.skip("Pass --module-forte-exe to run the agents against FORTE")
    import scenarios
    bench = scenarios.Bench(Path(exe).resolve(strict=True), Path(tempfile.mkdtemp(prefix="agents-")))
    try:
        bench.start(bench.boot())
        module, components = scenarios.delivered()
        module = copy.deepcopy(module)
        for interface in children(next(s for s in module["submodels"] if s["idShort"] == "AssetInterfacesDescription")):
            base = at(interface, "EndpointMetadata", "base")
            if base is not None:
                base["value"] = f"opc.tcp://127.0.0.1:{bench.ua_port}"
        yield module, components, bench
    finally:
        bench.close()


async def order(module: dict, components: list[dict], product: dict, reconfigurer=None):
    """The product's steps: the filling module's agent on FORTE, the others simulated."""
    resources, _ = example_line.build()
    modules = {k: v for k, v in resources.items() if is_module(v) and k != "FillingModuleAAS"}
    async with embedded_server(DOMAIN, port=0) as port:
        agents = [ResourceAgent(f"fillingmoduleaas@{DOMAIN}", "secret", module,
                                lambda env: OpcUaExecutor(env, components), reconfigurer=reconfigurer, port=port)]
        agents += [ResourceAgent(f"{name.lower()}@{DOMAIN}", "secret", env, lambda env: SimulatedExecutor(0.05),
                                 port=port) for name, env in modules.items()]
        for agent in agents:
            await agent.start(auto_register=True)
        ordered = ProductAgent(f"order1@{DOMAIN}", "secret", product, lambda: [str(a.jid) for a in agents], port=port)
        await ordered.start(auto_register=True)
        await asyncio.wait_for(ordered.finished.wait(), 240)
        for agent in [ordered, *agents]:
            await agent.stop()
        return ordered.history, agents[0]


def test_the_filling_modules_agent_runs_its_skill_on_the_module(filling):
    module, components, _ = filling
    _, products = example_line.build()
    history, _ = run(order(module, components, products["Vial2mLAAS"]))
    assert [(d.step, d.resource, d.outcome) for d in history] == [
        ("Filling", "FillingModuleAAS", "done"), ("Stoppering", "StopperingModuleAAS", "done"),
        ("Capping", "CappingModuleAAS", "done"), ("Inspection", "InspectionModuleAAS", "done")], history
    assert float(history[0].results["Weight"]) == pytest.approx(2.0)          # the simulated scale's weight


def test_the_filling_modules_agent_creates_bottom_up_filling_for_a_syringe(filling):
    """The syringe asks for BottomUpFilling, which the filling module offers only after a
    reconfiguration (described, as the skill editor saves it). Its agent creates the skill in the
    running program (modsync over FORTE's management port), records it (the skill Built, with its
    interface), and runs it over OPC UA with the syringe's 1 mL."""
    from scenarios import with_written
    from modreg.offer import capabilities
    from test_bidding import bottom_up
    module, components, bench = filling
    module = capabilities(with_written(module, components), components)
    _, products = example_line.build()

    async def reconfigurer(agent):
        done, agent.module = await asyncio.to_thread(rebuild, agent.module, components, "127.0.0.1", bench.port)
        agent.executor = agent.executor_for(agent.module)
        return done

    history, agent = run(order(module, components, bottom_up(products["PrefilledSyringe1mLAAS"]), reconfigurer))
    assert [(d.step, d.skill, d.outcome, d.reconfigured) for d in history] == [
        ("Filling", "BottomUpFilling", "done", True), ("Stoppering", "Stoppering", "done", False),
        ("Inspection", "Inspection", "done", False)], [d.detail for d in history]
    assert float(history[0].results["Weight"]) == pytest.approx(2.0)          # the simulated scale's weight
    assert any(line.startswith("reconfigured for BottomUpFilling: create BottomUpFilling") for line in agent.log), agent.log
    skill = at(next(s for s in agent.module["submodels"] if s["idShort"] == "Skills"), "BottomUpFilling")
    assert at(skill, "Deployment")["value"] == "Built"
