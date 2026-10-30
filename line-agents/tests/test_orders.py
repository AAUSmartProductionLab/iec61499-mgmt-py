"""Orders on the example line: an order of three vials to the order agent, a product agent for each,
the three at once on the four modules (one step at a time on each), over SPADE's own XMPP server in
this process, the skills simulated.
"""
import asyncio
from pathlib import Path
import sys

import pytest

pytest.importorskip("spade")
pytest.importorskip("aas_model")

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "line-agents"), str(ROOT / "cell" / "examples")]

import example_line                                                         # noqa: E402
from spade.agent import Agent                                                # noqa: E402
from lineagents import i40                                                   # noqa: E402
from lineagents.aas import is_module                                         # noqa: E402
from lineagents.execute import SimulatedExecutor                             # noqa: E402
from lineagents.orders import CONFIRM, OrderAgent, order_message             # noqa: E402
from lineagents.product import ProductAgent                                  # noqa: E402
from lineagents.resource import ResourceAgent                                # noqa: E402
from lineagents.xmpp import embedded_server, run                             # noqa: E402

DOMAIN = "localhost"


class Watched(SimulatedExecutor):
    """A simulated module that notes how many of its steps ran at once."""

    def __init__(self, seconds: float):
        super().__init__(seconds)
        self.running = self.most = 0

    async def run(self, offer, session):
        self.running += 1
        self.most = max(self.most, self.running)
        try:
            return await super().run(offer, session)
        finally:
            self.running -= 1


async def take_orders(orders: list[tuple[str, int]]):
    resources, products = example_line.build()
    modules = {k: v for k, v in resources.items() if is_module(v)}
    async with embedded_server(DOMAIN, port=0) as port:
        executors = {name: Watched(0.2) for name in modules}
        agents = [ResourceAgent(f"{name.lower()}@{DOMAIN}", "secret", env, lambda env, n=name: executors[n], port=port)
                  for name, env in modules.items()]
        started: list[ProductAgent] = []

        async def place(product, quantity, report_to):
            if product not in products:
                raise KeyError(f"no product {product}")
            found = []
            for _ in range(quantity):
                agent = ProductAgent(f"{product.lower()}-{len(started) + 1}@{DOMAIN}", "secret", products[product],
                                     lambda: [str(a.jid) for a in agents], answer_seconds=2, again_seconds=0.2,
                                     report_to=report_to, port=port)
                await agent.start(auto_register=True)
                started.append(agent)
                found.append(str(agent.jid))
            return found

        taker = OrderAgent(f"orders@{DOMAIN}", "secret", place, port=port)
        orderer = Agent(f"customer@{DOMAIN}", "secret", port=port)
        for agent in [*agents, taker, orderer]:
            await agent.start(auto_register=True)
        received = []

        async def ask():
            from spade.behaviour import OneShotBehaviour

            class Ask(OneShotBehaviour):
                async def run(self):
                    expected = 0
                    for product, quantity in orders:
                        await self.send(order_message(str(orderer.jid), str(taker.jid), product, quantity).to_spade())
                        expected += 1 + (quantity if product in products else 0)
                    while len(received) < expected:
                        message = await self.receive(timeout=60)
                        if message is None:
                            return
                        received.append(i40.I40Message.from_spade(message))
            behaviour = Ask()
            orderer.add_behaviour(behaviour)
            await behaviour.join()

        await asyncio.wait_for(ask(), 120)
        for agent in [*started, taker, orderer, *agents]:
            await agent.stop()
        return received, started, executors


def test_an_order_of_three_vials_gets_a_product_agent_for_each():
    received, started, executors = run(take_orders([("Vial2mLAAS", 3)]))
    confirm = [m for m in received if m.type == CONFIRM]
    assert len(confirm) == 1 and len(confirm[0].elements[0]["value"]) == 3
    reports = [m for m in received if m.type in (i40.DONE, i40.FAILED)]
    assert [m.type for m in reports] == [i40.DONE] * 3, [m.elements for m in reports]
    assert {m.sender for m in reports} == {str(a.jid) for a in started}
    assert all(m.conversation == confirm[0].conversation for m in reports)      # the order's conversation
    assert all([d.outcome for d in a.history] == ["done"] * 4 for a in started)
    assert executors["FillingModuleAAS"].ran == [("Dispensing", {"Volume": 2.0})] * 3
    assert all(e.most == 1 for e in executors.values())                       # one step at a time on a module
    # The three shared the line: the vials overlapped (one filled while another was stoppered).
    assert any(d.outcome == "done" and d.seconds > 0.3 for a in started for d in a.history)


def test_an_order_of_a_product_nobody_knows_is_refused():
    received, started, _ = run(take_orders([("Unknown", 1)]))
    assert [m.type for m in received] == [i40.REFUSE] and not started
    assert "Unknown" in received[0].elements[0]["value"]
