"""lineagents: the agents of the filling line (SPADE over XMPP, the I4.0 language of VDI/VDE 2193).

- ``i40``: the messages (VDI/VDE 2193-1) and the bidding protocol's types (VDI/VDE 2193-2), carried
  in XMPP messages;
- ``aas``: what an agent reads from the AAS server: a module's environment, what it offers for a
  required capability, a product's steps;
- ``resource``: a resource agent, one per module (and the planar table's shuttles): it bids for a
  step its module can carry out, and carries it out when its bid is accepted;
- ``execute``: how a resource agent runs a skill: over the module's OPC UA (modlink), or by invoking
  the skill's Operation on the AAS server (the DMP carries it to the module);
- ``product``: a product agent, one per order: it asks for one step at a time and chooses a bid;
- ``manager``: starts a resource agent for each module the AAS server holds, and stops it when the
  module goes; starts a product agent for an order.

The design and the plan: docs/agents.md.
"""
