"""A product agent: one per product to make (an order of three vials has three). It walks its
product's steps (the Production Sequence of the product's AAS) and asks for one at a time.

For a step: a call for proposals with the step's required capability to every resource agent it
knows; answers are taken until each has answered or the call's replyBy has passed; of the proposals
it accepts the one whose skill is built (no reconfiguration first), else the first, and rejects the
others; then it waits for the result. When nobody proposes but a module that offers the step is
busy (another product's step, or a proposal of its own waiting for a decision), it asks again after
``again_seconds``, until ``step_seconds`` have passed. A step that fails is asked for again of the
other resource agents (``retries`` times); a step nobody proposes for, or that fails each time, ends
the product (what was done, each attempt, is in ``history``). ``report_to`` (whoever ordered, the
order's conversation) is informed at the end: ``informConfirm`` with the steps when every step was
done, else ``failure`` (lineagents.orders).

Transport between the steps (the planar table's shuttles as resource agents) and booking ahead are
planned (docs/agents.md).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import time
from typing import Callable

from spade.agent import Agent
from spade.behaviour import OneShotBehaviour

from . import i40
from .aas import Offer, Step, steps
from .orders import ORDERING

ROLE = i40.REQUESTER


@dataclass
class Done:
    step: str
    resource: str | None = None
    skill: str | None = None
    outcome: str = ""                          # done, failed, nobody
    detail: str = ""
    proposals: int = 0
    refusals: int = 0
    seconds: float = 0.0
    results: dict = field(default_factory=dict)
    agent: str | None = None                   # the resource agent that carried it out (its JID)


class ProductAgent(Agent):
    def __init__(self, jid: str, password: str, product: dict, resources: Callable[[], list[str]],
                 answer_seconds: float = 3.0, step_seconds: float = 600.0, retries: int = 1,
                 again_seconds: float = 1.0, report_to: tuple[str, str] | None = None, **options):
        super().__init__(jid, password, **options)
        self.product, self.resources = product, resources
        self.answer_seconds, self.step_seconds, self.retries = answer_seconds, step_seconds, retries
        self.again_seconds, self.report_to = again_seconds, report_to
        self.history: list[Done] = []
        self.finished = asyncio.Event()

    @property
    def name(self) -> str:
        return self.product["assetAdministrationShells"][0]["idShort"]

    @property
    def done(self) -> bool:
        """Every step of the product was carried out."""
        return self.finished.is_set() and len({d.step for d in self.history if d.outcome == "done"}) == len(steps(self.product))

    def record(self) -> list[dict]:
        """What was done, as interaction elements: the product, its agent, each attempt at a step."""
        def prop(name, value, kind="xs:string"):
            return {"modelType": "Property", "idShort": name, "valueType": kind, "value": str(value)}
        attempts = []
        for i, d in enumerate(self.history, 1):
            results = [prop(k, v) for k, v in d.results.items()]
            attempts.append({"modelType": "SubmodelElementCollection", "idShort": f"Step{i:02d}", "value": [
                prop("Name", d.step), prop("Outcome", d.outcome), prop("Resource", d.resource or ""),
                prop("Skill", d.skill or ""), prop("Seconds", round(d.seconds, 2), "xs:double"), prop("Detail", d.detail),
                {"modelType": "SubmodelElementCollection", "idShort": "Results", "value": results}]})
        return [{"modelType": "SubmodelElementCollection", "idShort": "Product", "value": [
            prop("Product", self.name), prop("Agent", str(self.jid)),
            {"modelType": "SubmodelElementCollection", "idShort": "Steps", "value": attempts}]}]

    async def setup(self) -> None:
        self.add_behaviour(Order())


class Order(OneShotBehaviour):
    async def run(self) -> None:
        agent: ProductAgent = self.agent
        try:
            for step in steps(agent.product):
                # A step that fails is asked for again, of the others (``retries`` times).
                left_out: set[str] = set()
                for _ in range(1 + agent.retries):
                    done = await self.ask(step, left_out)
                    agent.history.append(done)
                    if done.outcome != "failed" or done.agent is None:
                        break
                    left_out.add(done.agent)
                if done.outcome != "done":
                    break
        finally:
            agent.finished.set()
            if agent.report_to:
                orderer, conversation = agent.report_to
                await self.send(i40.I40Message(i40.DONE if agent.done else i40.FAILED, str(agent.jid), orderer,
                                               conversation, agent.record(), ROLE, protocol=ORDERING).to_spade())

    async def call(self, step: Step, resources: list[str]) -> tuple[str, list, int, int]:
        """One call for proposals: its conversation, the proposals, the refusals, and how many of
        those only because the module was busy."""
        agent: ProductAgent = self.agent
        conversation, deadline = i40.new_id(), i40.reply_by(agent.answer_seconds)
        for resource in resources:
            call = i40.I40Message(i40.CALL, str(agent.jid), resource, conversation, [step.required],
                                  ROLE, i40.PROVIDER, reply_by=deadline)
            await self.send(call.to_spade())
        proposals: list[tuple[i40.I40Message, Offer]] = []
        refusals = busy = 0
        while len(proposals) + refusals < len(resources) and time.time() * 1000 < deadline:
            answer = await self.next_in(conversation, (deadline - time.time() * 1000) / 1000)
            if answer is None:
                break
            if answer.type == i40.PROPOSAL and answer.elements:
                proposals.append((answer, Offer.from_element(answer.elements[0])))
            elif answer.type in (i40.REFUSE, i40.NOT_UNDERSTOOD):
                refusals += 1
                busy += any(e.get("idShort") == "Busy" and e.get("value") == "true" for e in answer.elements)
        return conversation, proposals, refusals, busy

    async def ask(self, step: Step, left_out: set[str] = frozenset()) -> Done:
        agent: ProductAgent = self.agent
        started = time.monotonic()
        resources = [r for r in agent.resources() if r not in left_out]
        while True:
            conversation, proposals, refusals, busy = await self.call(step, resources)
            if proposals or not busy or time.monotonic() - started > agent.step_seconds:
                break
            await asyncio.sleep(agent.again_seconds)             # a module that offers it is busy
        done = Done(step.name, proposals=len(proposals), refusals=refusals)
        if not proposals:
            done.outcome = "nobody"
            done.detail = (f"{busy} resource agents that offer it stayed busy" if busy else
                           f"no proposal from {len(resources)} resource agents")
            done.seconds = time.monotonic() - started
            return done
        chosen = sorted(proposals, key=lambda p: not p[1].built)[0]
        for answer, _ in proposals:
            await self.send(answer.answer(i40.ACCEPT if answer is chosen[0] else i40.REJECT,
                                          [chosen[1].element()] if answer is chosen[0] else [], ROLE).to_spade())
        done.resource, done.skill, done.agent = chosen[1].resource, chosen[1].skill, chosen[0].sender
        result = await self.next_in(conversation, agent.step_seconds, types=(i40.DONE, i40.FAILED))
        if result is None:
            done.outcome, done.detail = "failed", "no result in time"
        elif result.type == i40.DONE:
            done.outcome = "done"
            done.results = {e["idShort"]: e.get("value") for r in result.elements for c in r.get("value", [])
                            if c.get("idShort") == "Results" for e in c.get("value", [])}
        else:
            done.outcome = "failed"
            done.detail = "; ".join(t["text"] for e in result.elements for t in e.get("value", []) if isinstance(t, dict))
        done.seconds = time.monotonic() - started
        return done

    async def next_in(self, conversation: str, seconds: float, types=None) -> i40.I40Message | None:
        """The next message of ``conversation`` (of one of ``types``) within ``seconds``; others are
        left out (an answer to an earlier call that came too late)."""
        end = time.monotonic() + max(0.0, seconds)
        while (left := end - time.monotonic()) > 0:
            message = await self.receive(timeout=left)
            if message is None:
                return None
            found = i40.I40Message.from_spade(message)
            if found.conversation == conversation and (types is None or found.type in types):
                return found
        return None
