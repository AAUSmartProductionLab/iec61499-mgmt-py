"""A resource agent: one per module. It bids for the steps its module can carry out and carries out
the steps it wins.

Bidding: a call for proposals carries a required capability (a container of the product's Capability
Description). The agent answers with its module's offer (``aas.offer``: the offered capability of
that meaning whose properties cover the values, the skill that realizes it, whether the skill is
built or only described, its arguments), or refuses with the reasons. While it carries out a step it
refuses: a module does one step at a time.

Carrying out: on acceptance, a skill that is only described is created first (``execute.reconfigure``,
when the agent knows the AAS server and the module's management host), then the executor runs it,
and the agent informs the product agent of the result or of the failure.
"""
from __future__ import annotations

import asyncio
from typing import Callable

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.template import Template

from . import i40
from .aas import AasServer, Offer, offer
from .execute import Executor, Failed, reconfigure

ROLE = "ResourceAgent"


class ResourceAgent(Agent):
    def __init__(self, jid: str, password: str, module: dict, executor_for: Callable[[dict], Executor],
                 server: str | None = None, management_host: str | None = None, **options):
        super().__init__(jid, password, **options)
        self.module, self.executor_for = module, executor_for
        self.executor = executor_for(module)
        self.server, self.management_host = server, management_host
        self.proposed: dict[str, Offer] = {}       # by conversation: what was proposed and not yet decided
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


class Bidding(CyclicBehaviour):
    async def run(self) -> None:
        message = await self.receive(timeout=1)
        if message is None:
            return
        call = i40.I40Message.from_spade(message)
        agent: ResourceAgent = self.agent
        if i40.expired(call):
            return
        found = offer(agent.module, call.elements[0]) if call.elements else ["no required capability given"]
        if agent.busy and isinstance(found, Offer):
            found = [f"{agent.name} is carrying out another step"]
        if isinstance(found, Offer):
            agent.proposed[call.conversation] = found
            answer = call.answer(i40.PROPOSAL, [found.element()], ROLE)
            agent.note(f"proposed {found.skill} for {call.conversation}")
        else:
            answer = call.answer(i40.REFUSE, [{"modelType": "MultiLanguageProperty", "idShort": "Reason",
                                                "value": [{"language": "en", "text": "; ".join(found)[:500]}]}], ROLE)
        await self.send(answer.to_spade())


class Award(CyclicBehaviour):
    async def run(self) -> None:
        message = await self.receive(timeout=1)
        if message is None:
            return
        decision = i40.I40Message.from_spade(message)
        agent: ResourceAgent = self.agent
        proposed = agent.proposed.pop(decision.conversation, None)
        if decision.type == i40.REJECT or proposed is None:
            return
        agent.busy = True
        asyncio.get_running_loop().create_task(self.carry_out(decision, proposed))

    async def carry_out(self, decision: i40.I40Message, proposed: Offer) -> None:
        agent: ResourceAgent = self.agent
        done: list[str] = []
        try:
            if not proposed.built:
                if not (agent.server and agent.management_host):
                    raise Failed(f"{proposed.skill} is only described, and {agent.name} cannot reconfigure its module")
                done = await asyncio.to_thread(reconfigure, agent.server, agent.name, agent.management_host)
                agent.module = await asyncio.to_thread(AasServer(agent.server).environment,
                                                       agent.module["assetAdministrationShells"][0]["id"])
                agent.executor = agent.executor_for(agent.module)
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
