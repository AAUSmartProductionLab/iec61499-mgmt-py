"""A product agent: one per product to make (an order of three vials has three). It walks its
product's steps (the Production Sequence of the product's AAS) and asks for one at a time.

For a step: a call for proposals with the step's required capability to every resource agent it
knows; answers are taken until each has answered or the call's replyBy has passed; of the proposals
it chooses the one whose skill is built (no reconfiguration first), else the first, and rejects the
others. When nobody proposes but a module that offers the step is busy (another product's step, or a
proposal of its own waiting for a decision), it asks again after ``again_seconds``, until
``step_seconds`` have passed.

Before it accepts, it has the product carried to the module: a module's proposal says where a shuttle
hands the product over (its station, in the planar table's frame), and unless the product is there
already, the product agent calls for Transporting to that pose. Who may carry it is the resources'
business, through custody (vocabulary 0.7): Transporting needs the resource to hold the product, so
the product agent first asks for Receiving if nobody holds it (a resource with room proposes; the one
accepted holds it from then on), and at the end for Releasing. Every call goes to every resource
agent with the product's state (its HeldBy), and the constraints decide who proposes: nothing here
is about shuttles. Once the product is there it accepts the module's proposal (the proposal is
binding, so the module waits for it) and waits for the result. A step that cannot be carried to its
module fails.

A step that fails is asked for again of the other resource agents (``retries`` times); a step nobody
proposes for, or that fails each time, ends the product (what was done, each attempt and each
transport and each change of custody, is in ``history``). ``report_to`` (whoever ordered, the order's conversation) is informed
at the end: ``informConfirm`` with the steps when every step was done, else ``failure``
(lineagents.orders).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import time
from typing import Callable

from spade.agent import Agent
from spade.behaviour import OneShotBehaviour

from . import i40
from .aas import HELD_BY, Offer, request, state_element, state_of, steps, transport_request
from .orders import ORDERING

ROLE = i40.REQUESTER
TRANSPORT, RECEIVE, RELEASE = "Transporting", "Receiving", "Releasing"     # their names in the history
HANDLING = (RECEIVE, TRANSPORT, RELEASE)       # what moves the product, not a step of it


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
    reconfigured: bool = False                 # the module was reconfigured for it first


class ProductAgent(Agent):
    def __init__(self, jid: str, password: str, product: dict, resources: Callable[[], list[str]],
                 answer_seconds: float = 3.0, step_seconds: float = 600.0, retries: int = 1,
                 again_seconds: float = 1.0, report_to: tuple[str, str] | None = None, **options):
        super().__init__(jid, password, **options)
        self.product, self.resources = product, resources
        self.answer_seconds, self.step_seconds, self.retries = answer_seconds, step_seconds, retries
        self.again_seconds, self.report_to = again_seconds, report_to
        self.history: list[Done] = []
        self.state: dict[str, object] = {HELD_BY: ""}           # the product's, by meaning: who holds it
        self.at: tuple[float, float, float] | None = None      # where the product is on the table
        self.finished = asyncio.Event()

    @property
    def name(self) -> str:
        return self.product["assetAdministrationShells"][0]["idShort"]

    @property
    def complete(self) -> bool:
        """Every step of the product was carried out."""
        return {s.name for s in steps(self.product)} <= {d.step for d in self.history if d.outcome == "done"}

    @property
    def held_by(self) -> str:
        """The resource that has the product in its custody (its AAS's idShort), empty if none."""
        return str(self.state.get(HELD_BY) or "")

    @property
    def done(self) -> bool:
        return self.finished.is_set() and self.complete

    def record(self) -> list[dict]:
        """What was done, as interaction elements: the product, its agent, each attempt at a step."""
        def prop(name, value, kind="xs:string"):
            return {"modelType": "Property", "idShort": name, "valueType": kind, "value": str(value)}
        attempts = []
        for i, d in enumerate(self.history, 1):
            results = [prop(k, v) for k, v in d.results.items()]
            attempts.append({"modelType": "SubmodelElementCollection", "idShort": f"Step{i:02d}", "value": [
                prop("Name", d.step), prop("Outcome", d.outcome), prop("Resource", d.resource or ""),
                prop("Skill", d.skill or ""), prop("Reconfigured", str(d.reconfigured).lower(), "xs:boolean"),
                prop("Seconds", round(d.seconds, 2), "xs:double"), prop("Detail", d.detail),
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
                    done = await self.ask(step.name, step.required, left_out)
                    agent.history.append(done)
                    if done.outcome != "failed" or done.agent is None:
                        break
                    left_out.add(done.agent)
                if done.outcome != "done":
                    break
        finally:
            if agent.held_by:                  # the product is off its carrier: the carrier is free
                agent.history.append(await self.custody(RELEASE))
            if agent.report_to:
                orderer, conversation = agent.report_to
                await self.send(i40.I40Message(i40.DONE if agent.complete else i40.FAILED, str(agent.jid), orderer,
                                               conversation, agent.record(), ROLE, protocol=ORDERING).to_spade())
            agent.finished.set()

    async def call(self, required: dict, resources: list[str]) -> tuple[str, list, int, int]:
        """One call for proposals: its conversation, the proposals, the refusals, and how many of
        those only because the module was busy."""
        agent: ProductAgent = self.agent
        conversation, deadline = i40.new_id(), i40.reply_by(agent.answer_seconds)
        for resource in resources:
            call = i40.I40Message(i40.CALL, str(agent.jid), resource, conversation, [required, state_element(agent.state)],
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

    async def proposals(self, name: str, required: dict, resources: list[str]):
        """Calls for proposals until one comes, asking again while the only ones that could propose
        are busy: the step's record so far, the proposals, the conversation, when it started."""
        agent: ProductAgent = self.agent
        started = time.monotonic()
        while True:
            conversation, proposals, refusals, busy = await self.call(required, resources)
            if proposals or not busy or time.monotonic() - started > agent.step_seconds:
                break
            await asyncio.sleep(agent.again_seconds)             # a module that offers it is busy
        done = Done(name, proposals=len(proposals), refusals=refusals)
        if not proposals:
            done.outcome = "nobody"
            done.detail = (f"{busy} resource agents that offer it stayed busy" if busy else
                           f"no proposal from {len(resources)} resource agents")
            done.seconds = time.monotonic() - started
        # A built skill before one a reconfiguration creates; then whoever answered first.
        return done, sorted(proposals, key=lambda p: not p[1].built), conversation, started

    async def ask(self, name: str, required: dict, left_out: set[str] = frozenset()) -> Done:
        """A step: the module chosen, the product carried there, the step carried out."""
        agent: ProductAgent = self.agent
        done, proposals, conversation, started = await self.proposals(
            name, required, [r for r in agent.resources() if r not in left_out])
        if not proposals:
            return done
        chosen, others = proposals[0], proposals[1:]
        await self.reject(others)
        station = chosen[1].station
        if station is not None and station != agent.at:
            moved = await self.custody(RECEIVE) if not agent.held_by else None    # Transporting needs a holder
            if moved is not None:
                agent.history.append(moved)
            if moved is None or moved.outcome == "done":
                moved = await self.transport(station)
                agent.history.append(moved)
            if moved.outcome != "done":
                await self.reject([chosen])
                done.resource, done.outcome = chosen[1].resource, "failed"
                done.detail = f"not carried to {chosen[1].resource}: {moved.detail or moved.outcome}"
                done.seconds = time.monotonic() - started
                return done
        return await self.carry_out(done, chosen, conversation, started)

    async def transport(self, station: tuple[float, float, float]) -> Done:
        """The product carried to ``station`` (by the resource that holds it: the others refuse)."""
        agent: ProductAgent = self.agent
        done = await self.handling(TRANSPORT, transport_request(*station))
        if done.outcome == "done":
            agent.at = station
        return done

    async def custody(self, name: str) -> Done:
        """Receiving or Releasing: who holds the product changes (the result says)."""
        return await self.handling(name, request(name))

    async def handling(self, name: str, required: dict) -> Done:
        """A call to every resource agent for something done to carry the product, not a step of it."""
        agent: ProductAgent = self.agent
        done, proposals, conversation, started = await self.proposals(name, required, agent.resources())
        if not proposals:
            return done
        await self.reject(proposals[1:])
        return await self.carry_out(done, proposals[0], conversation, started)

    async def reject(self, proposals: list) -> None:
        for answer, _ in proposals:
            await self.send(answer.answer(i40.REJECT, [], ROLE).to_spade())

    async def carry_out(self, done: Done, chosen: tuple, conversation: str, started: float) -> Done:
        """Accept the chosen proposal and wait for its result."""
        agent: ProductAgent = self.agent
        answer, offer = chosen
        await self.send(answer.answer(i40.ACCEPT, [offer.element()], ROLE).to_spade())
        done.resource, done.skill, done.agent = offer.resource, offer.skill, answer.sender
        result = await self.next_in(conversation, agent.step_seconds, types=(i40.DONE, i40.FAILED))
        if result is None:
            done.outcome, done.detail = "failed", "no result in time"
        elif result.type == i40.DONE:
            done.outcome = "done"
            done.results = {e["idShort"]: e.get("value") for r in result.elements for c in r.get("value", [])
                            if c.get("idShort") == "Results" for e in c.get("value", [])}
            done.reconfigured = any(c.get("idShort") == "Reconfigured" and c.get("value") == "true"
                                    for r in result.elements for c in r.get("value", []))
            agent.state.update(state_of(result.elements))          # who holds it now, if that changed
        else:
            done.outcome = "failed"
            done.detail = "; ".join(t["text"] for e in result.elements for t in e.get("value", []) if isinstance(t, dict))
        done.seconds = time.monotonic() - started
        return done

    async def next_in(self, conversation: str, seconds: float, types=None) -> i40.I40Message | None:
        """The next message of ``conversation`` (of one of ``types``) within ``seconds``. Others are
        left out: an answer to an earlier call that came too late, whose proposal is rejected so that
        it does not hold its module."""
        end = time.monotonic() + max(0.0, seconds)
        while (left := end - time.monotonic()) > 0:
            message = await self.receive(timeout=left)
            if message is None:
                return None
            found = i40.I40Message.from_spade(message)
            if found.conversation == conversation and (types is None or found.type in types):
                return found
            if found.type == i40.PROPOSAL:
                await self.send(found.answer(i40.REJECT, [], ROLE).to_spade())
        return None
