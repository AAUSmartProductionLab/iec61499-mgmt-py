"""An agent starts when its module's AAS is published, and stops when it is deleted: the manager
listens to the AAS server's events (MQTT) and reads the server only then (its polling every ten
minutes here). With the lab stack on this computer (deploy/aas.py up: the AAS server, Mosquitto, Prosody
with the example line published); a copy of the filling module's AAS under ids of its own is published
and deleted again.
"""
import base64
import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

pytest.importorskip("spade")
pytest.importorskip("paho.mqtt")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "line-agents"))

from lineagents.aas import AasServer                                         # noqa: E402

AAS = os.environ.get("AAS_SERVER", "http://localhost:8081")
NAME = "FillingModuleEventProbeAAS"


def b64(identifier: str) -> str:
    return base64.urlsafe_b64encode(identifier.encode()).decode().rstrip("=")


def call(method: str, path: str, body=None) -> int:
    request = urllib.request.Request(f"{AAS}/{path}", json.dumps(body).encode() if body is not None else None,
                                     method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as answer:
            return answer.status
    except urllib.error.HTTPError as e:
        return e.code


def reachable(port: int) -> bool:
    try:
        socket.create_connection(("127.0.0.1", port), timeout=2).close()
        return True
    except OSError:
        return False


def copy_of_filling() -> dict:
    """The filling module's AAS from the server, every id made its own."""
    server = AasServer(AAS)
    shell = next(s for s in server.shells() if s["idShort"] == "FillingModuleAAS")
    env = copy.deepcopy(server.environment(shell))
    old = env["assetAdministrationShells"][0]["id"]
    text = json.dumps(env).replace(old, old + "EventProbe").replace('"FillingModuleAAS"', f'"{NAME}"')
    return json.loads(text)


def test_an_agent_starts_when_its_modules_aas_is_published(tmp_path):
    try:
        urllib.request.urlopen(f"{AAS}/shells?limit=1", timeout=3).close()
    except OSError:
        pytest.skip(f"no AAS server at {AAS}")
    if not (reachable(1883) and reachable(5222)):
        pytest.skip("the lab stack's Mosquitto (1883) and Prosody (5222) are needed")
    env = copy_of_filling()
    shell = env["assetAdministrationShells"][0]
    log = tmp_path / "manager.log"
    with open(log, "w", encoding="utf-8") as out:
        manager = subprocess.Popen([sys.executable, "-m", "lineagents", "--aas", AAS, "--mqtt", "localhost:1883",
                                    "--every", "600", "--executor", "simulated", "--stay"], cwd=ROOT, stdout=out,
                                   stderr=subprocess.STDOUT,
                                   env={**os.environ, "PYTHONPATH": str(ROOT / "line-agents"), "PYTHONUTF8": "1"})

    def seen(text: str, seconds: float) -> float | None:
        started = time.monotonic()
        while time.monotonic() - started < seconds:
            if text in log.read_text(encoding="utf-8"):
                return time.monotonic() - started
            time.sleep(0.2)
        return None

    try:
        assert seen("agents:", 60) is not None, log.read_text(encoding="utf-8")
        for submodel in env["submodels"]:
            assert call("POST", "submodels", submodel) in (200, 201)
        published = time.monotonic()
        assert call("POST", "shells", shell) in (200, 201)
        assert seen(f"started {NAME.lower()}@localhost", 20) is not None, log.read_text(encoding="utf-8")
        assert time.monotonic() - published < 20                       # not the ten minutes of polling
        call("DELETE", f"shells/{b64(shell['id'])}")
        assert seen(f"stopped {NAME.lower()}@localhost", 20) is not None, log.read_text(encoding="utf-8")
    finally:
        call("DELETE", f"shells/{b64(shell['id'])}")
        for submodel in env["submodels"]:
            call("DELETE", f"submodels/{b64(submodel['id'])}")
        manager.terminate()
        manager.wait(10)
