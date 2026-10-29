"""The agents with a module that runs: the filling module on FORTE with its simulator (pc target), its
resource agent running Dispensing over OPC UA (modlink) for a vial order; the other modules' agents
simulate their skills.

    python -m pytest line-agents/tests/test_agents_live.py --module-forte-exe <a FORTE with every module>
"""
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
from lineagents.execute import OpcUaExecutor, SimulatedExecutor              # noqa: E402
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
        yield module, components
    finally:
        bench.close()


def test_the_filling_modules_agent_runs_its_skill_on_the_module(filling):
    module, components = filling
    resources, products = example_line.build()
    modules = {k: v for k, v in resources.items() if is_module(v) and k != "FillingModuleAAS"}

    async def order():
        async with embedded_server(DOMAIN, port=0) as port:
            agents = [ResourceAgent(f"fillingmoduleaas@{DOMAIN}", "secret", module,
                                    lambda env: OpcUaExecutor(env, components), port=port)]
            agents += [ResourceAgent(f"{name.lower()}@{DOMAIN}", "secret", env, lambda env: SimulatedExecutor(0.05),
                                     port=port) for name, env in modules.items()]
            for agent in agents:
                await agent.start(auto_register=True)
            product = ProductAgent(f"order1@{DOMAIN}", "secret", products["Vial2mLAAS"],
                                   lambda: [str(a.jid) for a in agents], port=port)
            await product.start(auto_register=True)
            import asyncio
            await asyncio.wait_for(product.finished.wait(), 240)
            for agent in [product, *agents]:
                await agent.stop()
            return product.history

    history = run(order())
    assert [(d.step, d.resource, d.outcome) for d in history] == [
        ("Filling", "FillingModuleAAS", "done"), ("Stoppering", "StopperingModuleAAS", "done"),
        ("Capping", "CappingModuleAAS", "done"), ("Inspection", "InspectionModuleAAS", "done")], history
    assert float(history[0].results["Weight"]) == pytest.approx(2.0)          # the simulated scale's weight
