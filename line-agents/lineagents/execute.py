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
  - ``SimulatedExecutor``: no module, the time a skill takes (tests, a demo without hardware).

  Through the AAS server and the DMP (invoking the skill's Operation, reading its state from the
  time series) is the third way, planned (docs/agents.md).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import sys
import urllib.parse
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
