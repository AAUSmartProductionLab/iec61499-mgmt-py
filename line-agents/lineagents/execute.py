"""How a resource agent carries out a step it won: create the skill if it is only described, then
run it.

- **Reconfiguring** (``reconfigure``): the module's AAS and its components' from the AAS server,
  ``modsync``'s reconfiguration of the running program over FORTE's management protocol (a new
  composite skill created online, verified by reading it back), the skill recorded as Built with its
  interface, and the changed submodels put back on the AAS server. FORTE's management port is on the
  host of the module's OPC UA endpoint.
- **Running** a skill, one of two ways:
  - ``OpcUaExecutor``: straight to the module's OPC UA server with ``modlink``, from the module's AAS
    (occupy, bring the module to Execute, start the skill, wait for its end, release);
  - ``DmpExecutor``: through the AAS server, the module's Operations invoked there and carried to its
    OPC UA methods by the DMP, the module's and the skill's state read from the time series the DMP
    writes (InfluxDB): one way in for every client, every call in the module's log, slower;
  - ``SimulatedExecutor``: no module, the time a skill takes (tests, a demo without hardware).
"""
from __future__ import annotations

import asyncio
import base64
import csv
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .aas import Offer

MANAGEMENT_PORT = 61499
HMI = Path(__file__).resolve().parents[2] / "iec61499-opcua-hmi"      # modlink (a submodule)


class Failed(RuntimeError):
    """A step that could not be carried out."""


@dataclass
class Result:
    skill: str
    results: dict = field(default_factory=dict)
    reconfigured: list[str] = field(default_factory=list)    # what a reconfiguration did, if one ran


def reconfigure(server: str, module_id_short: str, host: str, port: int = MANAGEMENT_PORT) -> list[str]:
    """Create on the running module what its AAS on ``server`` describes and the program lacks, record
    it and put the AAS back (blocking: run it in a thread)."""
    from iec61499_mgmt.protocol import Client
    from modsync.desired import read, reconfigure as online, record
    from modsync.sources import load, store
    module, components = load(server, module_id_short)
    with Client(host, port) as client:
        done, after = online(client, host, port, module, components)
        if done and done[0].startswith("the program is what"):
            return done
        recorded, _ = record(module, after, done, "agent", components)
        done.append(f"recorded: {store(server, recorded, module)}")
        # What the module offers now that the skill is built, read again with its interface.
        assert read(client, host, port, recorded, components).differences.empty
    return done


class Executor:
    """Runs a skill of one module."""

    async def run(self, offer: Offer, session: str) -> Result:          # pragma: no cover (an interface)
        raise NotImplementedError


class SimulatedExecutor(Executor):
    """No module: a skill takes ``seconds``; ``fail`` names skills that fail."""

    def __init__(self, seconds: float = 0.2, fail: tuple[str, ...] = ()):
        self.seconds, self.fail, self.ran = seconds, fail, []

    async def run(self, offer: Offer, session: str) -> Result:
        await asyncio.sleep(self.seconds)
        self.ran.append((offer.skill, dict(offer.arguments)))
        if offer.skill in self.fail:
            raise Failed(f"{offer.skill} failed (simulated)")
        return Result(offer.skill)


class OpcUaExecutor(Executor):
    """Runs a skill over the module's OPC UA server (modlink), from the module's AAS environment."""

    def __init__(self, module: dict, components: list[dict] = (), timeout: float = 180.0):
        if str(HMI) not in sys.path:
            sys.path.insert(0, str(HMI))
        from modlink.aas import Environment, describe
        shell = module["assetAdministrationShells"][0]
        others = [s for env in components for s in env["submodels"]]
        self.resource = describe(Environment(shell, module["submodels"], others))
        self.timeout = timeout

    @property
    def host(self) -> str:
        return urllib.parse.urlsplit(self.resource.endpoint).hostname

    async def run(self, offer: Offer, session: str) -> Result:
        from modlink import Module
        skill = self.resource.skills.get(offer.skill)
        if skill is None:
            raise Failed(f"{self.resource.id_short} has no skill {offer.skill} on its interface")
        async with self.resource.connect() as link:
            await link.wait_connected(10)
            module = Module(link, self.resource.root, session=session, resource=self.resource)
            await module.occupy()
            try:
                await module.bring_to_execute()
                run = await module.run(skill.name, *skill.arguments(offer.arguments), timeout=self.timeout)
            finally:
                await module.release(check=False)
        if not run.succeeded:
            raise Failed(f"{offer.skill} ended {run.state.name if hasattr(run.state, 'name') else run.state}"
                         f" (ErrorID {run.error_id})")
        return Result(offer.skill, dict(run.results))


# The PackML module states and the skill states the module rules number (modgen.library).
IDLE, EXECUTE = 4, 6
SUCCEEDED, FAILED, ABORTED = 3, 4, 5
SECRETS = Path(__file__).resolve().parents[2] / "deploy" / "aas" / ".env"


class DmpExecutor(Executor):
    """Runs a skill through the AAS server: each command an Operation of the module's Skills submodel
    (``<Skill>.Start.Start``, ``Occupy.Start.Start``, ...), invoked there and carried by the DMP to the
    module's OPC UA method; the state read from the series the DMP writes to InfluxDB. The series are
    named as the DMP names them today: ``state_module`` (``PackMLState``), ``state_<skill>``
    (``<Skill>_State``, ``<Skill>_Result_<name>``); the Variables submodel says which (to be read from
    there)."""

    def __init__(self, module: dict, server: str, influx: str = "http://localhost:8086", token: str | None = None,
                 org: str = "ap2030", bucket: str = "ap2030", timeout: float = 180.0, poll: float = 0.5):
        self.module, self.server, self.influx = module, server.rstrip("/"), influx.rstrip("/")
        self.token = token or os.environ.get("INFLUX_TOKEN") or self._token()
        self.org, self.bucket, self.timeout, self.poll = org, bucket, timeout, poll
        self.asset = module["assetAdministrationShells"][0]["idShort"]
        self.skills = next(s for s in module["submodels"] if s.get("idShort") == "Skills")

    @staticmethod
    def _token() -> str | None:
        """The lab stack's InfluxDB token (deploy/aas/.env, written by deploy/aas.py; not committed)."""
        if SECRETS.exists():
            return next((line.partition("=")[2] for line in SECRETS.read_text(encoding="utf-8").splitlines()
                         if line.startswith("INFLUX_TOKEN=")), None)
        return None

    def _post(self, url: str, body: dict, headers: dict | None = None) -> bytes:
        request = urllib.request.Request(url, json.dumps(body).encode(), method="POST",
                                         headers={"Content-Type": "application/json", **(headers or {})})
        with urllib.request.urlopen(request, timeout=self.timeout) as answer:
            return answer.read()

    def invoke(self, path: str, **inputs) -> dict:
        """An Operation of the Skills submodel (``Skill.Start.Start``) with ``inputs``; its outputs."""
        operation = self.skills
        for step in path.split("."):
            operation = next(e for e in (operation.get("submodelElements") or operation.get("value") or [])
                             if e.get("idShort") == step)
        types = {v["value"]["idShort"]: v["value"]["valueType"] for v in operation.get("inputVariables") or []}
        body = {"inputArguments": [{"value": {"modelType": "Property", "idShort": k, "valueType": types[k],
                                              "value": str(v)}} for k, v in inputs.items() if k in types],
                "inoutputArguments": [], "clientTimeoutDuration": "PT60S"}
        sm = base64.urlsafe_b64encode(self.skills["id"].encode()).decode().rstrip("=")
        found = json.loads(self._post(f"{self.server}/submodels/{sm}/submodel-elements/{path}/invoke", body))
        return {v["value"]["idShort"]: v["value"].get("value") for v in found.get("outputArguments") or []}

    def rows(self, measurement: str, since: datetime, field_: str | None = None) -> list[dict]:
        """The rows of a series of this module since ``since``, oldest first: time, field, value."""
        only = f' and r["_field"] == "{field_}"' if field_ else ""
        flux = (f'from(bucket: "{self.bucket}") |> range(start: {since.strftime("%Y-%m-%dT%H:%M:%S.%fZ")}) '
                f'|> filter(fn: (r) => r["_measurement"] == "{measurement}" and r["asset"] == "{self.asset}"{only})')
        text = self._post(f"{self.influx}/api/v2/query?org={self.org}", {"query": flux},
                          {"Authorization": f"Token {self.token}", "Accept": "application/csv"}).decode()
        table = [row for row in csv.reader(text.splitlines()) if row]
        header = next((row for row in table if "_field" in row), [])
        at = {name: i for i, name in enumerate(header)}
        found = []
        for row in table:
            if row == header or len(row) != len(header):
                continue
            try:
                value = float(row[at["_value"]])
            except ValueError:
                value = row[at["_value"]]
            found.append({"time": row[at["_time"]], "field": row[at["_field"]], "value": value})
        return sorted(found, key=lambda r: r["time"])

    def wait(self, measurement: str, field_: str, wanted, since: datetime) -> float:
        """Until a row of ``field_`` since ``since`` has a value ``wanted`` (a test of the value)."""
        end = time.monotonic() + self.timeout
        while time.monotonic() < end:
            for row in reversed(self.rows(measurement, since, field_)):
                if wanted(row["value"]):
                    return row["value"]
            time.sleep(self.poll)
        raise Failed(f"{self.asset}: {field_} did not reach the state wanted in {self.timeout:.0f} s")

    def _run(self, offer: Offer, session: str) -> Result:
        def accepted(answer: dict) -> bool:
            return str(answer.get("Accepted")).lower() == "true"
        since = datetime.now(timezone.utc) - timedelta(seconds=2)
        answer = self.invoke("Occupy.Start.Start", Session=session)
        if not accepted(answer):
            raise Failed(f"{self.asset} was not occupied (ErrorID {answer.get('ErrorID')})")
        try:
            module = self.rows("state_module", datetime.now(timezone.utc) - timedelta(hours=1), "PackMLState")
            state = module[-1]["value"] if module else None
            if state != EXECUTE:
                if state != IDLE:
                    self.invoke("Reset.Start.Start", Session=session)
                    self.wait("state_module", "PackMLState", lambda v: v == IDLE, since)
                self.invoke("Start.Start.Start", Session=session)
                self.wait("state_module", "PackMLState", lambda v: v == EXECUTE, since)
            started = datetime.now(timezone.utc) - timedelta(seconds=1)
            answer = self.invoke(f"{offer.skill}.Start.Start", Session=session, **offer.arguments)
            if not accepted(answer):
                raise Failed(f"{offer.skill} was refused (ErrorID {answer.get('ErrorID')})")
            series = f"state_{offer.skill.lower()}"
            ended = self.wait(series, f"{offer.skill}_State", lambda v: v in (SUCCEEDED, FAILED, ABORTED), started)
            if ended != SUCCEEDED:
                raise Failed(f"{offer.skill} ended {'Failed' if ended == FAILED else 'Aborted'}")
            prefix = f"{offer.skill}_Result_"
            results = {r["field"][len(prefix):]: r["value"] for r in self.rows(series, started)
                       if r["field"].startswith(prefix)}
            return Result(offer.skill, results)
        finally:
            self.invoke("Release.Start.Start", Session=session)

    async def run(self, offer: Offer, session: str) -> Result:
        return await asyncio.to_thread(self._run, offer, session)
