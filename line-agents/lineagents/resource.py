"""A resource agent: one per module. It bids for the steps its module can carry out and carries out
the steps it wins.

Bidding: a call for proposals carries a required capability (a container of the product's Capability
Description). The agent answers with its module's offer (``aas.offer``: the offered capability of
that meaning whose properties cover the values, the skill that realizes it, whether the skill is
built or only described, its arguments), or refuses with the reasons. A proposal is binding (VDI/VDE
2193-2): from the proposal until the product agent decides (or the decision is late) and while it
carries out a step it refuses, saying it is busy, so that the product agent asks again later: a
module does one step at a time.

Carrying out: on acceptance, a skill that is only described is created first (``execute.reconfigure``,
when the agent knows the AAS server and the module's management host; or ``reconfigurer``, e.g.
``execute.simulated_reconfigure``), then the executor runs it, and the agent informs the product agent
of the result or of the failure.
"""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.template import Template

from . import i40
from .aas import AasServer, Offer, offer
from .execute import Executor, Failed, reconfigure

ROLE = i40.PROVIDER
DECISION_SECONDS = 10.0          # how long after the call's replyBy a proposal waits for its decision


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
        found = offer(agent.module, call.elements[0])
        if isinstance(found, Offer) and (agent.busy or agent.reserved()):
            answer = call.answer(i40.REFUSE, refusal([f"{agent.name} is busy with another step"], busy=True), ROLE)
        elif isinstance(found, Offer):
            until = (call.reply_by / 1000 if call.reply_by else time.time()) + DECISION_SECONDS
            agent.proposed[call.conversation] = (found, until)
            answer = call.answer(i40.PROPOSAL, [found.element()], ROLE)
            agent.note(f"proposed {found.skill} for {call.conversation}")
        else:
            answer = call.answer(i40.REFUSE, refusal(found), ROLE)
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
            if not proposed.built:
                done = await agent.reconfigure(proposed.skill)
                agent.note(f"reconfigured for {proposed.skill}: {'; '.join(done)}")
            result = await agent.executor.run(proposed, session=decision.conversation)
            values = [{"modelType": "Property", "idShort": k, "valueType": "xs:string", "value": str(v)}
                      for k, v in result.results.items()]
            elements = [{"modelType": "SubmodelElementCollection", "idShort": "Result", "value": [
                {"modelType": "Property", "idShort": "Skill", "valueType": "xs:string", "value": proposed.skill},
                {"modelType": "Property", "idShort": "Reconfigured", "valueType": "xs:boolean",
                 "value": str(bool(done)).lower()},
                {"modelType": "SubmodelElementCollection", "idShort": "Results", "value": values}]}]
            answer = decision.answer(i40.DONE, elements, ROLE)
            agent.note(f"carried out {proposed.skill} for {decision.conversation}")
        except Exception as e:                       # noqa: BLE001 (the product agent is told why)
            answer = decision.answer(i40.FAILED, [{"modelType": "MultiLanguageProperty", "idShort": "Reason",
                                                   "value": [{"language": "en", "text": f"{type(e).__name__}: {e}"[:500]}]}], ROLE)
            agent.note(f"failed {proposed.skill} for {decision.conversation}: {e}")
        finally:
            agent.busy = False
        await self.send(answer.to_spade())
