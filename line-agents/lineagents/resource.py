"""A resource agent: one per module. It bids for the steps its module can carry out and carries out
the steps it wins.

Bidding: a call for proposals carries a required capability (a container of the product's Capability
Description). The agent answers with its module's offer (``aas.offer``: the offered capability of
that meaning whose properties cover the values, the skill that realizes it, whether the skill is
built or only described, its arguments), or refuses with the reasons. A proposal is binding (VDI/VDE
2193-2): from the proposal until the product agent decides (or the decision is late) and while it
carries out a step it refuses, saying it is busy, so that the product agent asks again later: a
module does one step at a time. A module's proposal says where a shuttle hands it the product (its
``station``, set by the manager from the AASs).

Custody (vocabulary 0.7): the agent keeps which products its resource has, from the Receiving it
carried out to the Releasing, and checks its capabilities' Pre constraints against it and against
the product's state the call gives (``aas.offer``): only the shuttle that has a product transports
it, a full one receives no other. Nothing in it is about shuttles. Custody is a lease: each call
from the product's agent renews it, and it lapses after ``CUSTODY_SECONDS`` without one, so that a
product agent that is gone does not hold its shuttle for ever.

Carrying out: on acceptance, a skill that is only described is created first (``execute.reconfigure``,
when the agent knows the AAS server and the module's management host; or ``reconfigurer``, e.g.
``execute.simulated_reconfigure``), then the executor runs it, and the agent informs the product agent
of the result or of the failure. A capability no skill realizes (Receiving, Releasing) is only its
Posts: the custody changes, and the result says who holds the product now (its HeldBy).
"""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.template import Template

from . import i40
from .aas import HELD_BY, HOLDING, OCCUPANCY, AasServer, Offer, offer, state_element, state_of
from .execute import Executor, Failed, reconfigure

ROLE = i40.PROVIDER
# How long after the call's replyBy a proposal waits for its decision: the product agent decides once
# the product has been carried to the module.
DECISION_SECONDS = 300.0
# How long a resource keeps a product in its custody without hearing from the product's agent.
CUSTODY_SECONDS = 3600.0


def refusal(reasons: list[str], busy: bool = False) -> list[dict]:
    """The interaction elements of a refusal: why, and whether only because the module is busy."""
    found = [{"modelType": "MultiLanguageProperty", "idShort": "Reason",
              "value": [{"language": "en", "text": "; ".join(reasons)[:500]}]}]
    if busy:
        found.append({"modelType": "Property", "idShort": "Busy", "valueType": "xs:boolean", "value": "true"})
    return found


class ResourceAgent(Agent):
    def __init__(self, jid: str, password: str, module: dict, executor_for: Callable[[dict], Executor],
                 server: str | None = None, management_host: str | None = None,
                 reconfigurer: Callable[["ResourceAgent"], Awaitable[list[str]]] | None = None, **options):
        super().__init__(jid, password, **options)
        self.module, self.executor_for = module, executor_for
        self.executor = executor_for(module)
        self.server, self.management_host, self.reconfigurer = server, management_host, reconfigurer
        self.proposed: dict[str, tuple[Offer, float]] = {}   # by conversation: proposed, not decided; until when
        self.busy = False
        self.station: tuple[float, float, float] | None = None   # where a shuttle hands it the product
        self.custody: dict[str, float] = {}    # the product agents whose products it has: until when
        self.log: list[str] = []

    @property
    def name(self) -> str:
        return self.module["assetAdministrationShells"][0]["idShort"]

    async def setup(self) -> None:
        self.add_behaviour(Bidding(), Template(metadata={"type": i40.CALL}))
        decided = Template(metadata={"type": i40.ACCEPT}) | Template(metadata={"type": i40.REJECT})
        self.add_behaviour(Award(), decided)

    def note(self, line: str) -> None:
        self.log.append(line)

    async def reconfigure(self, skill: str) -> list[str]:
        """Create on the module what its AAS describes and its program lacks (``skill`` among it), and
        take the AAS as it is afterwards; what was done."""
        if self.reconfigurer is not None:
            return await self.reconfigurer(self)
        if not (self.server and self.management_host):
            raise Failed(f"{skill} is only described, and {self.name} cannot reconfigure its module")
        done = await asyncio.to_thread(reconfigure, self.server, self.name, self.management_host)
        self.module = await asyncio.to_thread(AasServer(self.server).environment,
                                              self.module["assetAdministrationShells"][0]["id"])
        self.executor = self.executor_for(self.module)
        return done

    def holds(self) -> set[str]:
        """The product agents whose products it has (a lapsed lease no longer counts)."""
        now = time.time()
        for product in [p for p, until in self.custody.items() if until < now]:
            del self.custody[product]
            self.note(f"custody of {product} lapsed")
        return set(self.custody)

    def state(self, product: str, given: dict) -> dict:
        """What a call's Pre constraints are checked against: the product's state as given, and
        the resource's custody (it has this product; how many it has)."""
        held = self.holds()
        if product in held:
            self.custody[product] = time.time() + CUSTODY_SECONDS     # its agent is there: renewed
        return {**given, HOLDING: product in held, OCCUPANCY: float(len(held))}

    def reserved(self) -> bool:
        """A proposal waits for its decision (one whose decision is late no longer counts)."""
        now = time.time()
        for conversation in [c for c, (_, until) in self.proposed.items() if until < now]:
            del self.proposed[conversation]
        return bool(self.proposed)


class Bidding(CyclicBehaviour):
    async def run(self) -> None:
        message = await self.receive(timeout=1)
        if message is None:
            return
        call = i40.I40Message.from_spade(message)
        agent: ResourceAgent = self.agent
        if i40.expired(call):
            return
        if not call.elements:
            await self.send(call.answer(i40.NOT_UNDERSTOOD, [], ROLE).to_spade())
            return
        found = offer(agent.module, call.elements[0], agent.state(call.sender, state_of(call.elements[1:])),
                      frozenset({OCCUPANCY}))
        if isinstance(found, Offer) and (agent.busy or agent.reserved()):
            answer = call.answer(i40.REFUSE, refusal([f"{agent.name} is busy with another step"], busy=True), ROLE)
        elif isinstance(found, Offer):
            found.station = agent.station
            until = (call.reply_by / 1000 if call.reply_by else time.time()) + DECISION_SECONDS
            agent.proposed[call.conversation] = (found, until)
            answer = call.answer(i40.PROPOSAL, [found.element()], ROLE)
            agent.note(f"proposed {found.skill} for {call.conversation}")
        else:
            answer = call.answer(i40.REFUSE, refusal(found, found.busy), ROLE)
        await self.send(answer.to_spade())


class Award(CyclicBehaviour):
    async def run(self) -> None:
        message = await self.receive(timeout=1)
        if message is None:
            return
        decision = i40.I40Message.from_spade(message)
        agent: ResourceAgent = self.agent
        proposed, _ = agent.proposed.pop(decision.conversation, (None, 0.0))
        if decision.type == i40.REJECT:
            return
        if proposed is None:                 # accepted after the proposal lapsed
            await self.send(decision.answer(i40.FAILED, refusal([f"{agent.name}'s proposal had lapsed"]), ROLE).to_spade())
            return
        agent.busy = True
        asyncio.get_running_loop().create_task(self.carry_out(decision, proposed))

    async def carry_out(self, decision: i40.I40Message, proposed: Offer) -> None:
        agent: ResourceAgent = self.agent
        done: list[str] = []
        try:
            results = {}
            if proposed.skill:
                if not proposed.built:
                    done = await agent.reconfigure(proposed.skill)
                    agent.note(f"reconfigured for {proposed.skill}: {'; '.join(done)}")
                results = (await agent.executor.run(proposed, session=decision.conversation)).results
            values = [{"modelType": "Property", "idShort": k, "valueType": "xs:string", "value": str(v)}
                      for k, v in results.items()]
            elements = [{"modelType": "SubmodelElementCollection", "idShort": "Result", "value": [
                {"modelType": "Property", "idShort": "Skill", "valueType": "xs:string", "value": proposed.skill},
                {"modelType": "Property", "idShort": "Reconfigured", "valueType": "xs:boolean",
                 "value": str(bool(done)).lower()},
                {"modelType": "SubmodelElementCollection", "idShort": "Results", "value": values}]}]
            if HOLDING in proposed.effects:               # the custody changes: who has the product now
                if proposed.effects[HOLDING]:
                    agent.custody[decision.sender] = time.time() + CUSTODY_SECONDS
                else:
                    agent.custody.pop(decision.sender, None)
                elements.append(state_element({HELD_BY: agent.name if proposed.effects[HOLDING] else ""}))
            answer = decision.answer(i40.DONE, elements, ROLE)
            agent.note(f"carried out {proposed.skill or proposed.capability} for {decision.conversation}")
        except Exception as e:                       # noqa: BLE001 (the product agent is told why)
            answer = decision.answer(i40.FAILED, [{"modelType": "MultiLanguageProperty", "idShort": "Reason",
                                                   "value": [{"language": "en", "text": f"{type(e).__name__}: {e}"[:500]}]}], ROLE)
            agent.note(f"failed {proposed.skill} for {decision.conversation}: {e}")
        finally:
            agent.busy = False
        await self.send(answer.to_spade())

