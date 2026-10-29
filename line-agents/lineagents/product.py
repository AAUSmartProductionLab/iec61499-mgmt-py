"""A product agent: one per order. It walks its product's steps (the Production Sequence of the
product's AAS) and asks for one at a time.

For a step: a call for proposals with the step's required capability to every resource agent it
knows; answers are taken until each has answered or the call's replyBy has passed; of the proposals
it accepts the one whose skill is built (no reconfiguration first), else the first, and rejects the
others; then it waits for the result. A step nobody proposes for, or one that fails, ends the order
(what was done is in ``history``).

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

ROLE = "ProductAgent"


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


class ProductAgent(Agent):
    def __init__(self, jid: str, password: str, product: dict, resources: Callable[[], list[str]],
                 answer_seconds: float = 3.0, step_seconds: float = 600.0, **options):
        super().__init__(jid, password, **options)
        self.product, self.resources = product, resources
        self.answer_seconds, self.step_seconds = answer_seconds, step_seconds
        self.history: list[Done] = []
        self.finished = asyncio.Event()

    @property
    def name(self) -> str:
        return self.product["assetAdministrationShells"][0]["idShort"]

    async def setup(self) -> None:
        self.add_behaviour(Order())


class Order(OneShotBehaviour):
    async def run(self) -> None:
        agent: ProductAgent = self.agent
        try:
            for step in steps(agent.product):
                done = await self.ask(step)
                agent.history.append(done)
                if done.outcome != "done":
                    break
        finally:
            agent.finished.set()

    async def ask(self, step: Step) -> Done:
        agent: ProductAgent = self.agent
        started, conversation = time.monotonic(), i40.new_id()
        resources = agent.resources()
        deadline = i40.reply_by(agent.answer_seconds)
        for resource in resources:
            call = i40.I40Message(i40.CALL, str(agent.jid), resource, conversation, [step.required],
                                  ROLE, "ResourceAgent", reply_by=deadline)
            await self.send(call.to_spade())
        proposals: list[tuple[i40.I40Message, Offer]] = []
        refusals = 0
        while len(proposals) + refusals < len(resources) and time.time() * 1000 < deadline:
            answer = await self.next_in(conversation, (deadline - time.time() * 1000) / 1000)
            if answer is None:
                break
            if answer.type == i40.PROPOSAL and answer.elements:
                proposals.append((answer, Offer.from_element(answer.elements[0])))
            elif answer.type == i40.REFUSE:
                refusals += 1
        done = Done(step.name, proposals=len(proposals), refusals=refusals)
        if not proposals:
            done.outcome, done.detail = "nobody", f"no proposal from {len(resources)} resource agents"
            done.seconds = time.monotonic() - started
            return done
        chosen = sorted(proposals, key=lambda p: not p[1].built)[0]
        for answer, _ in proposals:
            await self.send(answer.answer(i40.ACCEPT if answer is chosen[0] else i40.REJECT,
                                          [chosen[1].element()] if answer is chosen[0] else [], ROLE).to_spade())
        done.resource, done.skill = chosen[1].resource, chosen[1].skill
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
