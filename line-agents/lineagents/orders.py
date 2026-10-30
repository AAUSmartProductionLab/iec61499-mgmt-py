"""Orders: an order of a product in a quantity goes to the order agent (``orders@<domain>``, in the
manager's process), which starts a product agent for each unit; each product agent carries out its
product's steps (lineagents.product) and informs whoever ordered when its product is done or cannot
be.

The messages are the I4.0 language's (lineagents.i40) under a protocol of the lab's own: VDI/VDE
2193-2 has the bidding, not the ordering.

| Message | From → to | Carries |
| --- | --- | --- |
| ``order`` | orderer → order agent | Product (the product's AAS idShort or id), Quantity |
| ``orderConfirm`` / ``refuseProposal`` | order agent → orderer | Agents: the product agents' JIDs / why not |
| ``informConfirm`` / ``failure`` | each product agent → orderer | Product: its steps, who did each, the results / where it stopped |

All in the conversation the order opened. Over HTTP the same (``--http`` on the manager): ``POST
/orders`` with ``{"product": "Vial2mLAAS", "quantity": 3}`` answers the product agents; ``GET
/orders`` each product agent's steps so far.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.template import Template

from . import i40

ORDERING = "https://smartproductionlab.aau.dk/agents/ordering"
ORDER, CONFIRM = "order", "orderConfirm"
ORDERER, TAKER = "orderer", "orderTaker"            # the roles


def prop(name: str, value, kind: str = "xs:string") -> dict:
    return {"modelType": "Property", "idShort": name, "valueType": kind, "value": str(value)}


def order_message(orderer: str, taker: str, product: str, quantity: int = 1) -> i40.I40Message:
    """An order of ``quantity`` of ``product``, from ``orderer`` to the order agent ``taker``."""
    return i40.I40Message(ORDER, orderer, taker, i40.new_id(), [prop("Product", product), prop("Quantity", quantity, "xs:int")],
                          ORDERER, TAKER, protocol=ORDERING)


def ordered(message: i40.I40Message) -> tuple[str | None, int]:
    """The product and the quantity an order asks for."""
    found = {e.get("idShort"): e.get("value") for e in message.elements}
    try:
        quantity = int(found.get("Quantity") or 1)
    except ValueError:
        quantity = 0
    return found.get("Product"), quantity


# Places an order: the product, the quantity, to whom and in which conversation the product agents
# report; the JIDs of the product agents it started. KeyError: no such product.
Place = Callable[[str, int, tuple[str, str] | None], Awaitable[list[str]]]


class OrderAgent(Agent):
    def __init__(self, jid: str, password: str, place: Place, **options):
        super().__init__(jid, password, **options)
        self.place = place

    async def setup(self) -> None:
        self.add_behaviour(TakeOrders(), Template(metadata={"protocol": ORDERING, "type": ORDER}))


class TakeOrders(CyclicBehaviour):
    async def run(self) -> None:
        message = await self.receive(timeout=1)
        if message is None:
            return
        order = i40.I40Message.from_spade(message)
        product, quantity = ordered(order)
        if not product or quantity < 1:
            answer = order.answer(i40.REFUSE, [prop("Reason", "an order names a Product and a Quantity of at least 1")], TAKER)
        else:
            try:
                agents = await self.agent.place(product, quantity, (order.sender, order.conversation))
                answer = order.answer(CONFIRM, [{"modelType": "SubmodelElementCollection", "idShort": "Agents",
                                                 "value": [prop(f"Agent{i:02d}", jid) for i, jid in enumerate(agents, 1)]}], TAKER)
            except KeyError as e:
                answer = order.answer(i40.REFUSE, [prop("Reason", str(e).strip("'\""))], TAKER)
        answer.protocol = ORDERING
        await self.send(answer.to_spade())
