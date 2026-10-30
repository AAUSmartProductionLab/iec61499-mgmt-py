"""The agents in two processes, so their messages go through the XMPP server: the manager in one, a
product agent or whoever orders in another, with the lab stack on this computer (deploy/aas.py up: the
AAS server with the example line published, and Prosody, lab-xmpp), the skills simulated. Orders over
HTTP as well. The example line's shuttles carry the vial between the modules (their transports are in
the history beside the steps).

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
sys.path.insert(0, str(ROOT / "line-agents"))

from lineagents.xmpp import free_port                                      # noqa: E402

AAS = os.environ.get("AAS_SERVER", "http://localhost:8081")
HANDLING = ("Receiving", "Transporting", "Releasing")          # what carries the vial, not a step of it


@pytest.fixture
def manager(tmp_path):
    try:
        urllib.request.urlopen(f"{AAS}/shells?limit=1", timeout=3).close()
    except OSError:
        pytest.skip(f"no AAS server at {AAS} (deploy/aas.py up, and the example line published)")
    port, log, http = 5222, tmp_path / "manager.log", free_port()
    try:
        socket.create_connection(("127.0.0.1", port), timeout=3).close()
    except OSError:
        pytest.skip("no XMPP server on port 5222 (the lab stack's lab-xmpp)")
    with open(log, "w", encoding="utf-8") as out:          # a file: a pipe nobody reads would stop it
        process = subprocess.Popen([sys.executable, "-m", "lineagents", "--aas", AAS, "--xmpp-port",
                                    str(port), "--executor", "simulated", "--http", str(http), "--stay"], cwd=ROOT, stdout=out,
                                   stderr=subprocess.STDOUT,
                                   env={**os.environ, "PYTHONPATH": str(ROOT / "line-agents"), "PYTHONUTF8": "1"})
    started, line = time.monotonic(), ""
    while time.monotonic() - started < 60:      # the manager says which agents run once they do
        line = next((l for l in log.read_text(encoding="utf-8").splitlines() if l.startswith("agents:")), "")
        if line or process.poll() is not None:
            break
        time.sleep(0.5)
    try:
        yield port, line or log.read_text(encoding="utf-8"), http
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
    port, started, _ = manager
    assert "fillingmoduleaas@localhost" in started, started
    script = tmp_path / "order.py"
    script.write_text(ORDER, encoding="utf-8")
    done = subprocess.run([sys.executable, str(script), str(ROOT / "line-agents"), AAS, str(port)], cwd=ROOT,
                          capture_output=True, text=True, timeout=180, env={**os.environ, "PYTHONUTF8": "1"})
    found = next((l for l in done.stdout.splitlines() if l.startswith("HISTORY ")), None)
    assert found, done.stdout[-2000:] + done.stderr[-2000:]
    history = json.loads(found[len("HISTORY "):])
    assert [h for h in history if h[0] not in HANDLING] == [
        ["Filling", "FillingModuleAAS", "done"], ["Stoppering", "StopperingModuleAAS", "done"],
        ["Capping", "CappingModuleAAS", "done"], ["Inspection", "InspectionModuleAAS", "done"]], history
    carried = [h for h in history if h[0] in HANDLING]
    assert carried and all(h[2] == "done" for h in carried) and len({h[1] for h in carried}) == 1, history


CUSTOMER = """
import asyncio, json, sys
sys.path.insert(0, sys.argv[1])
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
from lineagents import i40
from lineagents.manager import password
from lineagents.orders import order_message
from lineagents.xmpp import run

port = int(sys.argv[2])
received = []

class Order(OneShotBehaviour):
    async def run(self):
        await self.send(order_message(str(self.agent.jid), "orders@localhost", "Vial2mLAAS", 2).to_spade())
        while len(received) < 3:                     # the confirmation, then one report per vial
            message = await self.receive(timeout=120)
            if message is None:
                return
            m = i40.I40Message.from_spade(message)
            received.append([m.type, m.sender, [e["idShort"] for e in m.elements]])

async def order():
    jid = "customer@localhost"
    agent = Agent(jid, password(jid), port=port)
    await agent.start(auto_register=True)
    behaviour = Order()
    agent.add_behaviour(behaviour)
    await behaviour.join()
    await agent.stop()
    return received

if __name__ == "__main__":
    print("RECEIVED " + json.dumps(run(order())))
"""


def test_an_order_from_another_process_gets_a_product_agent_per_vial(manager, tmp_path):
    port, started, _ = manager
    assert "orders@localhost" in started, started
    script = tmp_path / "customer.py"
    script.write_text(CUSTOMER, encoding="utf-8")
    done = subprocess.run([sys.executable, str(script), str(ROOT / "line-agents"), str(port)], cwd=ROOT,
                          capture_output=True, text=True, timeout=240, env={**os.environ, "PYTHONUTF8": "1"})
    found = next((l for l in done.stdout.splitlines() if l.startswith("RECEIVED ")), None)
    assert found, done.stdout[-2000:] + done.stderr[-2000:]
    received = json.loads(found[len("RECEIVED "):])
    assert received[0][0] == "orderConfirm" and received[0][2] == ["Agents"]
    assert sorted(m[0] for m in received[1:]) == ["informConfirm", "informConfirm"], received
    assert all(m[1].startswith("vial2mlaas-") for m in received[1:])


def test_an_order_over_http(manager):
    _, _, http = manager
    request = urllib.request.Request(f"http://localhost:{http}/orders", json.dumps({"product": "Vial2mLAAS"}).encode(),
                                     method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as answer:
        assert answer.status == 201
        agents = json.loads(answer.read())["agents"]
    assert len(agents) == 1
    ended = time.monotonic() + 120
    while time.monotonic() < ended:
        with urllib.request.urlopen(f"http://localhost:{http}/orders", timeout=10) as answer:
            mine = next(o for o in json.loads(answer.read()) if o["agent"] == agents[0])
        if mine["finished"]:
            break
        time.sleep(1)
    assert mine["done"], mine
    assert [s["resource"] for s in mine["steps"] if s["step"] not in HANDLING] == [
        "FillingModuleAAS", "StopperingModuleAAS", "CappingModuleAAS", "InspectionModuleAAS"]
    assert {s["resource"] for s in mine["steps"] if s["step"] in HANDLING} <= {
        "PlanarShuttle1AAS", "PlanarShuttle2AAS", "PlanarShuttle3AAS"}
    request = urllib.request.Request(f"http://localhost:{http}/orders", json.dumps({"product": "NoSuchProduct"}).encode(),
                                     method="POST", headers={"Content-Type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as refused:
        urllib.request.urlopen(request, timeout=10)
    assert refused.value.code == 404
