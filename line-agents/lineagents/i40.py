"""The I4.0 language (VDI/VDE 2193-1) and its bidding protocol (VDI/VDE 2193-2), as XMPP messages.

A message is a frame and interaction elements. The frame says which protocol it belongs to, which of
the protocol's messages it is, who sends it to whom, which conversation it is part of and which
message it answers; the interaction elements are AAS submodel elements, here the JSON an AAS server
holds (a required capability container in a call for proposals, an offer in a proposal):

    {"frame": {"semanticProtocol": {...}, "type": "callForProposal", "messageId": "...",
               "conversationId": "...", "replyTo": "...", "replyBy": 1730000000000,
               "sender": {"identification": {"id": "<jid>"}, "role": {"name": "ProductAgent"}},
               "receiver": {"identification": {"id": "<jid>"}, "role": {"name": "ResourceAgent"}}},
     "interactionElements": [...]}

SPADE carries it as an XMPP message: the JSON in the body, and the protocol, the message's type and
its conversation in the message's metadata, so a behaviour's template can select by them.

The bidding protocol, one step at a time: the product agent sends a call for proposals to every
resource agent; each answers with a proposal or refuses; the product agent accepts one proposal and
rejects the others; the accepted resource agent carries the step out and informs of the result
(``informConfirm``) or of its failure (``informFailure``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import time
import uuid

# The bidding protocol's id. Placeholder until checked against VDI/VDE 2193-2.
BIDDING = "https://admin-shell.io/vdi/2193/2/0/biddingprotocol"
CALL, PROPOSAL, REFUSE = "callForProposal", "proposal", "refuseProposal"
ACCEPT, REJECT = "acceptProposal", "rejectProposal"
DONE, FAILED = "informConfirm", "informFailure"
TYPES = (CALL, PROPOSAL, REFUSE, ACCEPT, REJECT, DONE, FAILED)


def new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class I40Message:
    type: str
    sender: str
    receiver: str
    conversation: str
    elements: list[dict] = field(default_factory=list)       # interaction elements (submodel elements)
    sender_role: str = ""
    receiver_role: str = ""
    message_id: str = field(default_factory=new_id)
    reply_to: str | None = None                              # the message this one answers
    reply_by: int | None = None                              # ms since the epoch: answers after it are not taken
    protocol: str = BIDDING

    def frame(self) -> dict:
        found = {
            "semanticProtocol": {"type": "ExternalReference",
                                 "keys": [{"type": "GlobalReference", "value": self.protocol}]},
            "type": self.type, "messageId": self.message_id, "conversationId": self.conversation,
            "sender": {"identification": {"id": self.sender}, "role": {"name": self.sender_role}},
            "receiver": {"identification": {"id": self.receiver}, "role": {"name": self.receiver_role}},
        }
        if self.reply_to:
            found["replyTo"] = self.reply_to
        if self.reply_by is not None:
            found["replyBy"] = self.reply_by
        return found

    def to_json(self) -> str:
        return json.dumps({"frame": self.frame(), "interactionElements": self.elements})

    @classmethod
    def from_json(cls, text: str) -> "I40Message":
        data = json.loads(text)
        f = data["frame"]
        return cls(type=f["type"], sender=f["sender"]["identification"]["id"],
                   receiver=f["receiver"]["identification"]["id"], conversation=f["conversationId"],
                   elements=data.get("interactionElements") or [],
                   sender_role=f["sender"].get("role", {}).get("name", ""),
                   receiver_role=f["receiver"].get("role", {}).get("name", ""),
                   message_id=f["messageId"], reply_to=f.get("replyTo"), reply_by=f.get("replyBy"),
                   protocol=f["semanticProtocol"]["keys"][0]["value"])

    def answer(self, type_: str, elements: list[dict] | None = None, role: str = "") -> "I40Message":
        """The message that answers this one: to its sender, in its conversation."""
        return I40Message(type_, self.receiver, self.sender, self.conversation, elements or [],
                          sender_role=role or self.receiver_role, receiver_role=self.sender_role,
                          reply_to=self.message_id)

    def to_spade(self):
        """The XMPP message SPADE sends."""
        from spade.message import Message
        found = Message(to=self.receiver, body=self.to_json())
        found.set_metadata("protocol", self.protocol)
        found.set_metadata("type", self.type)
        found.set_metadata("conversation", self.conversation)
        return found

    @classmethod
    def from_spade(cls, message) -> "I40Message":
        return cls.from_json(message.body)


def reply_by(seconds: float) -> int:
    """A replyBy that far from now."""
    return int((time.time() + seconds) * 1000)


def expired(message: I40Message) -> bool:
    return message.reply_by is not None and time.time() * 1000 > message.reply_by
