"""The filling module through the lab's AAS stack (deploy/aas): an Operation of its AAS, invoked at
the AAS environment, calls the module's OPC UA method through the DMP, and the module's values
arrive in InfluxDB as the rows of the time series its Variables name.

    python deploy/aas.py up
    python -m pytest cell/tests/test_dmp_live.py --module-forte-exe runtime/fbe/build/modules-win/output/bin/forte.exe

The module runs simulated on this computer (FORTE and cell/sim/module_sim.py, as in
test_module_live.py); the DMP, in its container, reaches it as host.docker.internal. Skipped
without the stack. The AASs it publishes stay in the AAS environment afterwards.
"""
from contextlib import contextmanager
import base64
import csv
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import pytest

pytest.importorskip("aas_model")

from conftest import free_port, launch_forte  # noqa: E402
from iec61499_mgmt.bootfile import deployment  # noqa: E402
from iec61499_mgmt.protocol import Client  # noqa: E402
from iec61499_mgmt.sysfile import load_application  # noqa: E402
from modgen import load, spec_file, system_file  # noqa: E402
from modgen.library import SKILL_STATES, STATES  # noqa: E402
from modgen.module import app_name  # noqa: E402
from modreg import model, profile as profiles  # noqa: E402
from modreg.service import AasServer, mapped_last  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cell" / "sim"))
from module_sim import ModuleSim, SimServer  # noqa: E402
from module_ua import ModuleUa  # noqa: E402

REPOSITORY = "http://localhost:8081"
DMP = "http://localhost:8085"
INFLUX = "http://localhost:8086"
SECRETS = ROOT / "deploy" / "aas" / ".env"
# The module's OPC UA port, the same in every run: a module that restarts keeps its address, the
# DMP reconnects to it, and the same AASs published again leave its routes as they are.
UA_PORT = 4841


def get(url: str, body: dict | None = None, headers: dict | None = None, timeout: float = 70):
    request = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json", **(headers or {})},
                                     method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as answer:
            return answer.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise AssertionError(f"{request.method} {url}: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:2000]}") from e


@pytest.fixture(scope="module")
def stack():
    try:
        get(f"{REPOSITORY}/shells", timeout=3)
    except (OSError, AssertionError) as e:
        pytest.skip(f"The AAS stack is not running (python deploy/aas.py up): {e}")
    # Ready once it has read the repository; for a moment after a change it reads it again.
    until(lambda: get(f"{DMP}/health", timeout=3), timeout=60)


@contextmanager
def filling(request, tmp_path, ua_port):
    """The filling module's PC application on FORTE, its OPC UA server on ``ua_port``, its IO the simulator."""
    exe = request.config.getoption("--module-forte-exe")
    if not exe:
        pytest.skip("Pass --module-forte-exe to run the filling module on FORTE")
    spec = load(spec_file("filling"))
    sim, modbus = ModuleSim(spec), free_port()
    app = load_application(system_file(spec.project), app_name(spec, "pc"))
    ports = {k: v.replace(f":{spec.modbus.port}:", f":{modbus}:") for k, v in app.parameters.items() if v.startswith("'modbus[")}
    with SimServer(sim, port=modbus), launch_forte(Path(exe).resolve(strict=True), tmp_path, None, ["-op", str(ua_port)]) as port, \
            Client("127.0.0.1", port) as client:
        for command in deployment(app, overrides=ports, container=app_name(spec, "pc")):
            client.execute(command)
        ua = ModuleUa(ua_port, spec.module)
        try:
            ua.expect("Module/State", STATES["Stopped"])
            time.sleep(1.0)                               # FORTE's Modbus client connects (R6)
            yield spec, ua
        finally:
            ua.close()


def published(spec, ua_port: int) -> dict[str, dict]:
    """The AASs of the module and its components, its interface at this computer as the DMP's
    container sees it, put into the AAS environment (created, or replaced)."""
    envs = [model.build(p) for p in profiles.describe_all(spec, "pc", opcua=f"opc.tcp://host.docker.internal:{ua_port}")]
    server = AasServer(REPOSITORY)
    for env in mapped_last(envs):
        server.publish(env)
    return {env["assetAdministrationShells"][0]["idShort"]: env for env in envs}


def installed(env: dict, timeout: float = 90) -> list[dict]:
    """The mappings of an AAS's AIMC once the DMP runs every one of them; why not, if it does not."""
    aimc = next(sm["id"] for sm in env["submodels"] if sm["idShort"] == "AssetInterfacesMappingConfiguration")
    deadline, found = time.monotonic() + timeout, []
    while time.monotonic() < deadline:
        found = json.loads(get(f"{DMP}/management/mappings?aimc={urllib.parse.quote(aimc, safe='')}", timeout=5))["mappings"]
        if found and all(m["state"] == "installed" for m in found):
            return found
        time.sleep(1)
    stuck = [{k: m[k] for k in ("listIndex", "state", "category", "diagnostics")} for m in found if m["state"] != "installed"]
    raise AssertionError(f"{len(stuck)} of {len(found)} mappings do not run: {json.dumps(stuck, indent=1)[:3000]}")


def invoke(env: dict, path: str, **inputs) -> dict:
    """Invoke an Operation of the module's Skills at the AAS environment; its outputs by idShort."""
    skills = next(sm for sm in env["submodels"] if sm["idShort"] == "Skills")
    operation = skills
    for step in path.split("."):
        operation = next(e for e in (operation.get("submodelElements") or operation.get("value")) if e.get("idShort") == step)
    types = {v["value"]["idShort"]: v["value"]["valueType"] for v in operation["inputVariables"]}
    body = {"inputArguments": [{"value": {"modelType": "Property", "idShort": k, "valueType": types[k], "value": str(v)}}
                               for k, v in inputs.items()],
            "inoutputArguments": [], "clientTimeoutDuration": "PT60S"}
    sm_id = base64.urlsafe_b64encode(skills["id"].encode()).decode().rstrip("=")
    result = json.loads(get(f"{REPOSITORY}/submodels/{sm_id}/submodel-elements/{path}/invoke", body))
    assert result.get("success", True) and result.get("executionState", "Completed") == "Completed", result
    return {v["value"]["idShort"]: v["value"].get("value") for v in result.get("outputArguments") or []}


def number(text: str):
    try:
        return float(text)
    except ValueError:
        return text


def latest(asset: str, measurement: str, since: str = "-10m") -> dict:
    """The latest value of each field of a series in InfluxDB, written since ``since`` (a Flux time)."""
    token = next(line.partition("=")[2] for line in SECRETS.read_text(encoding="utf-8").splitlines() if line.startswith("INFLUX_TOKEN="))
    flux = (f'from(bucket: "ap2030") |> range(start: {since}) |> filter(fn: (r) => r["_measurement"] == "{measurement}"'
            f' and r["asset"] == "{asset}") |> last()')
    table = [row for row in csv.reader(get(f"{INFLUX}/api/v2/query?org=ap2030", {"query": flux},
                                           {"Authorization": f"Token {token}", "Accept": "application/csv"}).splitlines()) if row]
    header = next((row for row in table if "_field" in row), [])
    return {r[header.index("_field")]: number(r[header.index("_value")]) for r in table if r != header and len(r) == len(header)}


def until(check, timeout: float = 15):
    deadline = time.monotonic() + timeout
    while True:
        try:
            return check()
        except AssertionError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.5)


def test_a_skill_of_the_aas_runs_on_the_module_and_its_values_reach_the_database(stack, request, tmp_path):
    session, started = f"dmp-{uuid.uuid4()}", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with filling(request, tmp_path, UA_PORT) as (spec, ua):
        env = published(spec, UA_PORT)["FillingModuleAAS"]
        mappings = installed(env)
        assert len(mappings) == len(next(sm for sm in env["submodels"] if sm["idShort"] == "AssetInterfacesMappingConfiguration")
                                    ["submodelElements"][0]["value"])
        # The DMP reads this module: a row of its state, written since the module started, Stopped and free.
        until(lambda: _check(latest("FillingModuleAAS", "state_module", started), PackMLState=STATES["Stopped"],
                             OccupationState=0), timeout=60)

        # Through the AAS: the Operation's answer is the method's.
        assert invoke(env, "Occupy.Start.Start", Session=session) == {"Accepted": "true", "ErrorID": "0"}
        ua.expect("Occupation/Occupied", True)
        assert invoke(env, "Reset.Start.Start", Session=session)["Accepted"] == "true"
        ua.expect("Module/State", STATES["Idle"], timeout=15)
        assert invoke(env, "Start.Start.Start", Session=session)["Accepted"] == "true"
        ua.expect("Module/State", STATES["Execute"])
        # Refused by the module, and said so: someone else's session.
        assert invoke(env, "Dispensing.Start.Start", Session="someone else", Volume=1.5) == {"Accepted": "false", "ErrorID": "5"}
        assert invoke(env, "Dispensing.Start.Start", Session=session, Volume=1.5) == {"Accepted": "true", "ErrorID": "0"}
        ua.expect("Skills/Dispensing/State", SKILL_STATES["Succeeded"], timeout=30)

        # The rows: the module's state and occupation, the skill's run with its parameter and result.
        until(lambda: _check(latest("FillingModuleAAS", "state_module", started), PackMLState=STATES["Execute"], OccupationState=1))
        def done():
            found = _check(latest("FillingModuleAAS", "state_dispensing", started), Dispensing_Parameter_Volume=1.5)
            # Each value is a monitored item of its own, each change a row: the result may come a row later.
            assert found["Dispensing_State"] in (SKILL_STATES["Succeeded"], SKILL_STATES["Idle"]), found
            assert found["Dispensing_Result_Weight"] > 0 and found["Dispensing_ErrorID"] == 0, found
            return found
        until(done)

        # Every call is logged, the refused one as well: the last is the accepted one, with its volume.
        call = until(lambda: _check(latest("FillingModuleAAS", "log_dispensing_start", started), **{
            "Outcome": "Succeeded", "Operation.Session": session, "Operation.Volume": 1.5, "Operation.Accepted": "true",
            "Operation.ErrorID": 0}))
        assert call["DurationMs"] >= 0


def _check(found: dict, **wanted) -> dict:
    assert {k: found.get(k) for k in wanted} == wanted, found
    return found
