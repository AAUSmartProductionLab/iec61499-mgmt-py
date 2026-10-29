"""The agents in two processes, so their messages go through the XMPP server: the manager (and SPADE's
XMPP server) in one, a product agent in another, on the AAS server of the lab's stack on this computer
(deploy/aas.py up, the example line published), the skills simulated.

    python -m pytest line-agents/tests/test_processes.py
"""
import asyncio
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

import pytest

pytest.importorskip("spade")

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "line-agents")]

from lineagents.aas import AasServer                                         # noqa: E402
from lineagents.product import ProductAgent                                  # noqa: E402
from lineagents.xmpp import free_port, run                                   # noqa: E402

AAS = os.environ.get("AAS_SERVER", "http://localhost:8081")


@pytest.fixture
def manager(tmp_path):
    try:
        urllib.request.urlopen(f"{AAS}/shells?limit=1", timeout=3).close()
    except OSError:
        pytest.skip(f"no AAS server at {AAS} (deploy/aas.py up, and the example line published)")
    port, log = free_port(), tmp_path / "manager.log"
    with open(log, "w", encoding="utf-8") as out:          # a file: a pipe nobody reads would stop it
        process = subprocess.Popen([sys.executable, "-m", "lineagents", "--aas", AAS, "--embedded", "--xmpp-port",
                                    str(port), "--executor", "simulated", "--stay"], cwd=ROOT, stdout=out,
                                   stderr=subprocess.STDOUT,
                                   env={**os.environ, "PYTHONPATH": str(ROOT / "line-agents"), "PYTHONUTF8": "1"})
    started, line = time.monotonic(), ""
    while time.monotonic() - started < 60:      # the manager says which agents run once they do
        line = next((l for l in log.read_text(encoding="utf-8").splitlines() if l.startswith("agents:")), "")
        if line or process.poll() is not None:
            break
        time.sleep(0.5)
    try:
        yield port, line or log.read_text(encoding="utf-8")
    finally:
        process.terminate()
        process.wait(10)


def test_a_product_agent_in_another_process_orders_over_xmpp(manager):
    port, started = manager
    assert "fillingmoduleaas@localhost" in started, started
    modules = [s["idShort"] for s in AasServer(AAS).shells()
               if (s.get("assetInformation", {}).get("assetType") or "").endswith("Resource/Module")]
    product = AasServer(AAS).environment(next(s for s in AasServer(AAS).shells() if s["idShort"] == "Vial2mLAAS"))

    async def order():
        agent = ProductAgent("remote-order@localhost", "secret", product,
                             lambda: [f"{m.lower()}@localhost" for m in modules], port=port)
        await agent.start(auto_register=True)
        await asyncio.wait_for(agent.finished.wait(), 120)
        await agent.stop()
        return agent.history

    history = run(order())
    assert [(d.step, d.resource, d.outcome) for d in history] == [
        ("Filling", "FillingModuleAAS", "done"), ("Stoppering", "StopperingModuleAAS", "done"),
        ("Capping", "CappingModuleAAS", "done"), ("Inspection", "InspectionModuleAAS", "done")], history
