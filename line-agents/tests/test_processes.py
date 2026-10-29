"""The agents in two processes, so their messages go through the XMPP server: the manager in one, a
product agent in another, with the lab stack on this computer (deploy/aas.py up: the AAS server with
the example line published, and Prosody, lab-xmpp), the skills simulated.

    python -m pytest line-agents/tests/test_processes.py
"""
import json
import os
import socket
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

import pytest

pytest.importorskip("spade")

ROOT = Path(__file__).resolve().parents[2]

AAS = os.environ.get("AAS_SERVER", "http://localhost:8081")


@pytest.fixture
def manager(tmp_path):
    try:
        urllib.request.urlopen(f"{AAS}/shells?limit=1", timeout=3).close()
    except OSError:
        pytest.skip(f"no AAS server at {AAS} (deploy/aas.py up, and the example line published)")
    port, log = 5222, tmp_path / "manager.log"
    try:
        socket.create_connection(("127.0.0.1", port), timeout=3).close()
    except OSError:
        pytest.skip("no XMPP server on port 5222 (the lab stack's lab-xmpp)")
    with open(log, "w", encoding="utf-8") as out:          # a file: a pipe nobody reads would stop it
        process = subprocess.Popen([sys.executable, "-m", "lineagents", "--aas", AAS, "--xmpp-port",
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


ORDER = """
import asyncio, json, sys
sys.path.insert(0, sys.argv[1])
from lineagents.aas import AasServer
from lineagents.manager import password
from lineagents.product import ProductAgent
from lineagents.xmpp import run

aas, port = sys.argv[2], int(sys.argv[3])
server = AasServer(aas)
shells = server.shells()
modules = [s["idShort"] for s in shells if (s.get("assetInformation", {}).get("assetType") or "").endswith("Resource/Module")]
product = server.environment(next(s for s in shells if s["idShort"] == "Vial2mLAAS"))

async def order():
    agent = ProductAgent("remote-order@localhost", password("remote-order@localhost"), product, lambda: [m.lower() + "@localhost" for m in modules],
                         port=port)
    await agent.start(auto_register=True)
    await asyncio.wait_for(agent.finished.wait(), 120)
    await agent.stop()
    return [[d.step, d.resource, d.outcome] for d in agent.history]

if __name__ == "__main__":
    print("HISTORY " + json.dumps(run(order())))
"""


def test_a_product_agent_in_another_process_orders_over_xmpp(manager, tmp_path):
    """The product agent in a process of its own as well: no message is handed over inside one SPADE."""
    port, started = manager
    assert "fillingmoduleaas@localhost" in started, started
    script = tmp_path / "order.py"
    script.write_text(ORDER, encoding="utf-8")
    done = subprocess.run([sys.executable, str(script), str(ROOT / "line-agents"), AAS, str(port)], cwd=ROOT,
                          capture_output=True, text=True, timeout=180, env={**os.environ, "PYTHONUTF8": "1"})
    found = next((l for l in done.stdout.splitlines() if l.startswith("HISTORY ")), None)
    assert found, done.stdout[-2000:] + done.stderr[-2000:]
    assert json.loads(found[len("HISTORY "):]) == [
        ["Filling", "FillingModuleAAS", "done"], ["Stoppering", "StopperingModuleAAS", "done"],
        ["Capping", "CappingModuleAAS", "done"], ["Inspection", "InspectionModuleAAS", "done"]]
