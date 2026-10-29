"""The agent manager: a resource agent for every module the AAS server holds, and a product agent for
every order.

The AAS server is where a module becomes known: the registration service publishes its AAS there
when the module is registered (by hand, or found by discovery: ``modreg serve --discover``). The
manager reads the server's shells every ``every`` seconds; for a module's AAS that is new it starts a
resource agent (``<idShort in lower case>@<domain>``), for one that is gone it stops it, and for one
whose AAS changed (a skill built, a value changed) it gives the agent the new AAS. With ``mqtt`` (the
broker the AAS server publishes its events to) it reads the server as soon as a shell or submodel is
created, changed or deleted, and every ``every`` seconds anyway. It also answers who the resource
agents are, so a product agent knows whom to call.

    manager = Manager("http://localhost:8081", domain="localhost", executor="opcua")
    await manager.start()                    # watches until stopped
    order = await manager.order("Vial2mLAAS")
    await order.finished.wait(); order.history
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets

from .aas import AasServer, is_module
from .execute import OpcUaExecutor, SimulatedExecutor
from .product import ProductAgent
from .resource import ResourceAgent


def executor_kind(kind: str):
    """How the resource agents run their skills: ``opcua`` (modlink), or ``simulated``."""
    if kind == "opcua":
        return lambda env: OpcUaExecutor(env)
    if kind == "simulated":
        return lambda env: SimulatedExecutor()
    raise ValueError(f"no executor {kind!r}: opcua or simulated")


def agents_secret() -> str:
    """The secret the agents' passwords are made from: LINEAGENTS_SECRET, else one made at random on
    first use and kept in ~/.lineagents-secret (outside the repository, which is public)."""
    if os.environ.get("LINEAGENTS_SECRET"):
        return os.environ["LINEAGENTS_SECRET"]
    kept = Path.home() / ".lineagents-secret"
    if not kept.exists():
        kept.write_text(secrets.token_urlsafe(32), encoding="utf-8")
    return kept.read_text(encoding="utf-8").strip()


def password(jid: str, secret: str | None = None) -> str:
    """An agent's XMPP password: the same for the same JID at every start (its account outlives the
    agent on a server such as Prosody)."""
    secret = secret if secret is not None else agents_secret()
    return hmac.new(secret.encode(), jid.encode(), hashlib.sha256).hexdigest()[:24]


def digest(env: dict) -> str:
    return hashlib.sha256(json.dumps(env, sort_keys=True).encode()).hexdigest()


class Manager:
    def __init__(self, server: str, domain: str = "localhost", port: int = 5222, executor: str = "opcua",
                 every: float = 5.0, reconfigure: bool = True, mqtt: str | None = None):
        self.server, self.domain, self.port = AasServer(server), domain, port
        self.executor_for = executor_kind(executor)
        self.every, self.reconfigure, self.mqtt = every, reconfigure, mqtt
        self._poke: asyncio.Event | None = None
        self._events = None
        self.agents: dict[str, ResourceAgent] = {}       # by the module's AAS id
        self.seen: dict[str, str] = {}                    # by AAS id: the digest of the AAS last read
        self.orders: list[ProductAgent] = []
        self._task: asyncio.Task | None = None

    def jid(self, name: str) -> str:
        return f"{name.lower()}@{self.domain}"

    def resources(self) -> list[str]:
        """The resource agents' JIDs (a product agent's directory)."""
        return [str(a.jid) for a in self.agents.values()]

    async def start(self) -> None:
        self._poke = asyncio.Event()
        await self.sync()
        if self.mqtt:
            self._events = self._listen(self.mqtt, asyncio.get_running_loop())
        self._task = asyncio.get_running_loop().create_task(self._watch())

    def _listen(self, broker: str, loop):
        """The AAS server's events over MQTT (BaSyx: aas-repository/<repo>/shells/created, updated,
        deleted; the submodels' likewise): each pokes the manager to read the server again."""
        import paho.mqtt.client as mqtt
        host, _, port = broker.partition(":")
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"lineagents-{os.getpid()}")
        client.on_connect = lambda c, *a: c.subscribe([("aas-repository/+/shells/+", 0), ("sm-repository/+/submodels/+", 0),
                                                       ("aas-repository/+/shells/+/submodels/+", 0)])
        client.on_message = lambda c, u, message: loop.call_soon_threadsafe(self._poke.set)
        client.connect(host, int(port or 1883))
        client.loop_start()
        return client

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
        if self._events is not None:
            self._events.loop_stop()
            self._events.disconnect()
        for agent in [*self.orders, *self.agents.values()]:
            await agent.stop()
        self.agents.clear()

    async def _watch(self) -> None:
        """Read the server again when it says something changed (a short pause, so that the shell's
        submodels are there too), and every ``every`` seconds anyway."""
        while True:
            try:
                await asyncio.wait_for(self._poke.wait(), self.every)
                await asyncio.sleep(1.0)
            except asyncio.TimeoutError:
                pass
            self._poke.clear()
            try:
                await self.sync()
            except OSError as e:                        # the AAS server is away for a moment
                print(f"agent manager: the AAS server did not answer: {e}", flush=True)

    async def sync(self) -> list[str]:
        """Start, update and stop resource agents to match the modules on the AAS server; what changed."""
        shells = await asyncio.to_thread(self.server.shells)
        changed = []
        present = set()
        for shell in shells:
            if not (shell.get("assetInformation", {}).get("assetType") or "").endswith("Resource/Module"):
                continue
            present.add(shell["id"])
            env = await asyncio.to_thread(self.server.environment, shell)
            if not is_module(env):
                continue
            found = digest(env)
            if self.seen.get(shell["id"]) == found:
                continue
            self.seen[shell["id"]] = found
            agent = self.agents.get(shell["id"])
            if agent is None:
                jid = self.jid(shell["idShort"])
                agent = ResourceAgent(jid, password(jid), env, self.executor_for,
                                      server=self.server.url if self.reconfigure else None,
                                      management_host=self._host(env), port=self.port)
                await agent.start(auto_register=True)
                self.agents[shell["id"]] = agent
                changed.append(f"started {agent.jid}")
            elif not agent.busy:
                agent.module, agent.executor = env, self.executor_for(env)
                changed.append(f"updated {agent.jid}")
        for gone in set(self.agents) - present:
            agent = self.agents.pop(gone)
            self.seen.pop(gone, None)
            await agent.stop()
            changed.append(f"stopped {agent.jid}")
        for line in changed:
            print(f"agent manager: {line}", flush=True)
        return changed

    async def order(self, product: str, name: str | None = None) -> ProductAgent:
        """A product agent for one order of ``product`` (its AAS's idShort or id)."""
        shell = next((s for s in await asyncio.to_thread(self.server.shells) if product in (s["idShort"], s["id"])), None)
        if shell is None:
            raise KeyError(f"the AAS server holds no product {product}")
        env = await asyncio.to_thread(self.server.environment, shell)
        jid = self.jid(name or f"order-{len(self.orders) + 1}-{shell['idShort']}")
        agent = ProductAgent(jid, password(jid), env, self.resources, port=self.port)
        await agent.start(auto_register=True)
        self.orders.append(agent)
        return agent

    @staticmethod
    def _host(env: dict) -> str | None:
        """Where FORTE's management port is: the host of the module's OPC UA endpoint."""
        from urllib.parse import urlsplit
        from modreg.plancheck import at, children
        for sm in env["submodels"]:
            if sm.get("idShort") == "AssetInterfacesDescription":
                for interface in children(sm):
                    base = at(interface, "EndpointMetadata", "base")
                    if base and base.get("value"):
                        return urlsplit(base["value"]).hostname
        return None
