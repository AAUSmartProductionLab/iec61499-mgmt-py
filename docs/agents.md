# The line's agents: design and plan to the demo in January

Started 30 Oct 2026, after the CIRP paper's experiments were set up. The goal is the demo in January
2027: orders come in, a product agent per order asks for one step at a time, the modules' agents bid,
the planar table carries the product between the modules, and a module that cannot do a step yet
gets the skill it needs, planned and created online. A module that is plugged in is found,
registered and given its agent without anybody starting one.

What exists and what the literature does: [agents-literature.md](agents-literature.md). The code:
`line-agents/` (`lineagents`).

## 1. The parts and where they run

| Part | Runs where | What it does |
| --- | --- | --- |
| A module | its Raspberry Pi: FORTE with the module's IEC 61499 program | Occupation, the module's states, its skills over OPC UA; announces itself (LDS-ME) |
| Its AAS | the AAS server (BaSyx), on the lab's server | What it is and offers: skills, capabilities, interface, variables |
| The registration service | the lab's server (`modreg serve --discover`) | Finds the modules (mDNS), fetches each one's manifest, checks and publishes its AAS |
| The DMP | the lab's server | Carries an AAS Operation to the module's OPC UA method; writes the module's values to InfluxDB |
| The XMPP server | the lab's server | Carries the agents' messages (SPADE's own for now) |
| **The agent manager** | the lab's server (`python -m lineagents`) | A resource agent for each module on the AAS server, the order agent, a product agent per product ordered |
| **The order agent** | in the manager's process (`orders@<domain>`; `POST /orders` with `--http`) | Takes an order (product, quantity) and starts a product agent for each unit |
| **A resource agent** | in the manager's process | Bids for steps its module can do; reconfigures its module when a bid needs a new skill; runs the skill |
| **A product agent** | in the manager's process | One per unit: walks its product's steps (calls for proposals, chooses, has the product carried and the step done) and reports to whoever ordered |

Agents run on the server, not on the Pis. The Pi runs the module's control program and nothing that
decides; the agent is the module's active part (the AAS its passive part, the I4.0 component of
Plattform Industrie 4.0), and it talks to the module over the network as any client does. This keeps
the module what the paper delivers (an IEC 61499 program and an AAS) and the agents replaceable. In
IEEE 2660.1's terms it is the "hybrid" location with a tightly coupled OPC UA client, the practice the
standard's own example recommends when the device should not host agents; the real-time logic stays
in IEC 61499, wrapped in skills (Leitão et al. 2023; [agents-literature.md](agents-literature.md) 4.3).

## 2. How an agent is started

1. A module is plugged in: FORTE starts and announces its OPC UA server by mDNS.
2. The registration service finds it, fetches its manifest (`http://<Pi>:8088/manifest.json`, the
   profiles of its AAS and its components') and publishes the AAS on the AAS server.
3. The agent manager sees a module's AAS it has no agent for and starts a resource agent
   (`<idShort>@<domain>`, registering its XMPP account on first start). When the AAS changes (a skill
   built), the agent gets the new AAS; when the module's AAS goes, the agent stops.

**Built 30 Oct:** with `--mqtt` the manager listens to the AAS server's events (BaSyx publishes
`aas-repository/<repo>/shells/created`, `.../updated`, `.../deleted` and the submodels' events over
MQTT, to the stack's Mosquitto) and reads the server as soon as one comes (after a second, so that the
shell's submodels are there too); it still reads the server every `--every` seconds in case an event
was missed. `test_events.py`: an agent starts within seconds of its module's AAS being published and
stops when it is deleted. In the lab stack:

```powershell
python -m lineagents --aas http://localhost:8081 --mqtt localhost:1883     # XMPP: Prosody (lab-xmpp)
```

## 3. How an agent talks to its module

| Way | How | For | Against |
| --- | --- | --- | --- |
| **OPC UA, with modlink** (built) | The agent reads the module's interface from its AAS (Asset Interfaces Description) and calls the module's methods itself: occupy, bring to Execute, start the skill, follow its state by subscription, release | Fast; the skill's state as it changes; the occupation is the agent's own session; tested on FORTE | A second path beside the AAS: what the agent does is not in the AAS's call log |
| **Through the AAS and the DMP** (built 30 Oct, `--executor dmp`) | The agent invokes the skill's Operation on the AAS server; the DMP calls the module; the state is read from the time series (InfluxDB) | One way in for every client; every call logged (`Variables/Log`); works for assets that are not OPC UA | Slower (a round trip through two services, the state polled from the database); the DMP becomes a dependency of production |

**Proposed:** OPC UA with modlink for running skills (the demo needs the state as it changes), the
AAS for everything the agent reads and writes about the module (its offers, a new skill, the record
of what was built), and the DMP way built next to it as a second executor, chosen per module. The
executor is a part of the agent (`lineagents.execute`), so the choice is a setting.

## 4. The protocol

The I4.0 language of VDI/VDE 2193-1 (a frame and interaction elements) and its bidding protocol
(VDI/VDE 2193-2), carried over XMPP by SPADE (the JSON in the body; the protocol, the message type
and the conversation in the message's metadata). One conversation per step:

| Message | From → to | Carries |
| --- | --- | --- |
| `callForProposal` | product agent → every resource agent | The step's required capability: the container of the product's Capability Description (meaning, values); and the product's state (`State`: HeldBy, who has it in custody) |
| `proposal` | resource agent → product agent | Its offer: the offered capability, the skill, whether a reconfiguration comes first, the skill's arguments (the required values mapped by meaning onto the skill's inputs) |
| `refuseProposal` / `notUnderstood` | resource agent → product agent | Why not / a call without a required capability |
| `acceptProposal` / `rejectProposal` | product agent → resource agents | The chosen offer |
| `informConfirm` / `failure` | resource agent → product agent | The skill's results, or why it failed; the product's new state if it changed (HeldBy, after Receiving or Releasing) |

**Orders** (built 30 Oct, `lineagents.orders`), a small protocol of the lab's own in the same frame
(VDI/VDE 2193-2 has no ordering):

| Message | From → to | Carries |
| --- | --- | --- |
| `order` | whoever orders → the order agent | Product (AAS idShort or id), Quantity |
| `orderConfirm` / `refuseProposal` | order agent → orderer | The product agents' JIDs / why not (no such product) |
| `informConfirm` / `failure` | each product agent → orderer | Its steps: who did each, the results / where it stopped |

The same over HTTP: `POST /orders {"product": "Vial2mLAAS", "quantity": 3}`, `GET /orders` (each
product agent's steps so far: what an order screen shows). Three vials ordered at once share the line:
a module refuses a call with `Busy` while it carries out a step or while one of its proposals waits for
the decision (a proposal is binding, so it reserves the module), and a product agent that hears only
busy refusals asks again a second later (`test_orders.py`; over Prosody from another process and over
HTTP, `test_processes.py`).

The frame's fields (`inReplyTo`, `replyBy`, ...), the message types and the roles (`serviceRequester`,
`serviceProvider`) are those of VDI/VDE 2193 as the OvGU testbed implements them; no implementation over
XMPP was found, so this one is the first (literature, 5.1).

**Planned:** transport between the steps (section 6), booking a module ahead (the accept books it, a
second message starts the step once the product is there), proposals that carry a time (when the
module is free, how long the skill takes, and the setup: the time to plan and create a skill online),
and every decision written into the product's AAS (the batch record a pharmaceutical line needs). A
proposal is binding (VDI/VDE 2193-2).

## 5. What is built (30 Oct)

- Later on 30 Oct: custody (vocabulary 0.7): a shuttle receives a vial, only the shuttle that has it
  transports it, it releases it at the end; all three are capabilities with constraints in the
  shuttle's AAS, checked by any resource agent (`test_transport.py`). See section 6.
- Later on 30 Oct: orders (the order agent, a product agent per unit, `POST /orders`), a module
  reserved by its proposal, and A2 (a step that needs a reconfiguration, done on FORTE); see sections
  4 and 7.

- `lineagents.i40`: the messages; `aas`: a product's steps from its Production Sequence, a module's
  offer for a required capability (meaning, values covered, the realizing skill, built or described,
  the arguments); `resource`: the bidding and the carrying out, a described skill created first with
  `modsync` (reconfigure, record, store back on the AAS server); `execute`: OPC UA (modlink) and
  simulated executors; `product`: the steps one at a time; `manager`: an agent per module on the AAS
  server; `xmpp`: SPADE's own XMPP server in the process; `python -m lineagents`.
- Tried: the example line's four modules bid for the vial's four steps, each won by the module that
  offers it (`test_bidding.py`); a failing step ends the order; the filling module's agent runs
  Dispensing on FORTE over OPC UA with the vial's 2.0 mL and reports the weight
  (`test_agents_live.py`); `python -m lineagents --aas http://localhost:8081 --embedded --order
  Vial2mLAAS` starts an agent for each module the local AAS server holds and runs the order.
- Discovery (the step before): FORTE announces itself (LDS-ME), `modreg serve --discover` registers
  it from its manifest.

## 6. Gaps found while building

| Gap | Why it matters | Proposal |
| --- | --- | --- |
| ~~**One offer per capability**~~ | The derivation already wrote a container per realizing skill (`Filling_DoubleDose`); what was missing was a capability of its own for a new skill, so that a product can ask for it, and a described skill's steps that resolve (they did not: `described_skill` named the components after "Module") | **Done 30 Oct**: a skill written for a narrower capability (BottomUpFilling, a Filling; vocabulary 0.6) offers it |
| ~~**The shuttles offer nothing**~~ | No transport bids | **Done 30 Oct**: `modreg/planar.py` writes the shuttle's offered Transporting (TargetX, TargetY, TargetRz over the table), realized by MoveToPosition |
| **Where a product is** | The product agent has to know whom to ask to move it, and where to | **Custody (30 Oct, your decision: as generic as possible)**: who has the product is a state (HeldBy, Holding) that Receiving, Transporting and Releasing constrain in the resources' AASs; every call goes to every agent and the constraints decide. The product agent keeps its state (later the product instance's AAS). Loading as the step that starts it waits for the loading module's AAS |
| ~~**The station of a module**~~ | The target of a transport | **Done 30 Oct**: `lineagents.aas.station`, the module's TransferPoint in the table's frame; the manager gives each agent its station, the module's proposal carries it |
| ~~**Accept starts at once**~~ | The module would start before the product is there | **Done 30 Oct**: the product agent accepts the module's proposal only once the product is at its station (the proposal holds the module meanwhile) |
| **One step at a time per module, no queue** | A busy module refuses (with `Busy`, and the product agent asks again: built 30 Oct) | Proposals with a time: when it is free |
| ~~**The XMPP path is not tested across processes**~~ | A distributed deployment | Done 30 Oct (`test_processes.py`, over Prosody) |

## 7. Plan to January

| # | When | Work | Done when |
| --- | --- | --- | --- |
| A1 | Nov, after 18 Nov | ~~Transport: the shuttles' Transporting offer (8.1), the station of a module from the AASs, the product agent asks for transport before each step (any free shuttle first, then the one carrying the product)~~ **Built 30 Oct** with the shuttles simulated (`test_transport.py`: one vial on one shuttle; three vials on three). Left: MoveToPosition on the planar controller's simulation (the shuttles' AASs published, `OpcUaExecutor` on the controller); loading and unloading as steps | The vial goes loading → filling → stoppering → unloading on the planar controller's simulation, and on the table |
| A2 | Nov | ~~Offers per skill (8.2), proposals that need a reconfiguration, the product agent preferring a built skill~~ **Built 30 Oct** on FORTE on the PC: the syringe asks for BottomUpFilling, the filling module's agent creates it online (`execute.rebuild`), records it and runs it (`test_agents_live.py`). Left: the same on the filling Pi; the example line's syringe asking for BottomUpFilling itself (now only in the tests: its process AAS binds Dispensing) | A product that needs a described skill gets it created online by the module's agent and the step runs (on FORTE on the PC, then on the filling Pi) |
| A3 | Nov–Dec | Planned skills in a bid: a resource agent that has no skill for a required capability plans one (`modplan.compose`), describes it, and bids "after a reconfiguration" | The syringe's BottomUpFilling (the paper's scenario) planned by the filling module's agent for an order |
| A4 | Dec | Deployment: the agents as a service of the lab's AAS stack (`deploy/aas`); ~~an XMPP server~~ (Prosody, built 30 Oct); ~~the manager started by the AAS server's events~~ (MQTT, built 30 Oct); ~~passwords not in files~~ (derived from a secret outside the repository) | Plug in the filling Pi: its agent is up within seconds; unplug: it goes |
| A5 | Dec | ~~The DMP executor (invoke the Operation, follow the state in InfluxDB)~~ **Built 30 Oct** (`DmpExecutor`, `test_dmp_executor.py`: Dispensing through the AAS on FORTE, the weight from InfluxDB). Left: the series' names from the Variables submodel instead of the DMP's naming; chosen per module | The same order runs through the AAS |
| A6 | Dec | Failures: ~~a step that fails is asked of another module~~ (**built 30 Oct**, `retries`); a module that goes away during a step; timeouts; an agent restarted keeps nothing it needs | The order finishes when one of two modules that offer a step fails (done on simulated modules) |
| A7 | Dec–Jan | The demo: an order screen (place orders, see each order's conversation and where the product is), the agents' messages logged (InfluxDB), the scenario script | The demo runs three orders (vial, syringe, cartridge) end to end on the line |
| A8 | Jan | Rehearsal on the hardware; what cannot be ready falls back to the simulators | – |

## 8. Decisions

| # | Question | Decided |
| --- | --- | --- |
| 8.1 | The shuttles' offer: Transporting in each shuttle's AAS (Capability Description written by `modreg/planar.py`), or transport left out of the bidding (the product agent commands the table directly)? | **In the AAS (30 Oct, yours)**: the shuttles bid like modules; the slides show it too |
| 8.2 | One offered capability container per realizing skill (`modreg` derivation)? | **Yes (30 Oct, yours)**, and a new or changed skill gets a capability of its own (BottomUpFilling: filling while the needle rises), so that a product can ask for it |
| 8.3 | XMPP server for the lab: SPADE's own (pyjabber), Prosody or ejabberd? | **Prosody, done 30 Oct** (`lab-xmpp` in the lab stack): pyjabber left an agent of another process unanswered now and then (a registration never answered, a stream without a version); SPADE's own stays for tests in one process |
| 8.4 | Running skills: modlink over OPC UA (built), or through the AAS and the DMP? | modlink for the demo, the DMP executor next to it (section 3) |
| 8.5 | Agents as a few processes on the server, or one container per agent (as SMIA deploys them)? | **One process, the manager (30 Oct, yours)**; per-agent containers only if a module brings its own agent |
| 8.6 | The orders: from where? An order screen in the web UI, a REST call to the manager, or an order AAS? | **The order agent (30 Oct, yours: the product agents receive the order and carry it out, one per product)**: an `order` message over XMPP or `POST /orders`; the screen on top (A7) |

## 9. Where this stands in the literature

From [agents-literature.md](agents-literature.md) (survey of 30 Oct, every reference checked):

| Work | What it does | Against ours |
| --- | --- | --- |
| SMIA (Hurtado et al., JII 2025; github.com/ekhurtado/SMIA, 1.0.3, Oct 2026) | SPADE agents configured from an AAS enriched with the CSS ontology; asset connections from the AID; FIPA-ACL dialect; capability discovery through an OWL knowledge base; Docker or Kubernetes YAML generated beforehand | The closest system. Not IDTA 02020, not VDI/VDE 2193, OPC UA without method calls, never changes the asset's control. Copyleft and pinned to SPADE 4.0: ideas reused, not the package |
| TU Wien/ACIN (Lepuschitz et al. 2011; Zoitl 2010; Vallée 2011) | Agents reconfigure IEC 61499 low-level control from an ontology | The ancestor of an agent reconfiguring FORTE, but choosing among prepared configurations, without the AAS or planning |
| Lyu and Brennan (2020, 2025) | SPADE with 4diac on a Raspberry Pi | Two layers of control; no AAS |
| DFKI SmartFactory (Bernhard et al. 2023; Jungbluth et al. 2022, 2023) | SARL agents, Kafka, BaSyx, VDI/VDE 2193 bidding with changeover time in the bids, OPC UA skills, skill-based transport | The closest architecture; skills fixed, no reconfiguration of control |
| OvGU (Diedrich, Belyaev, Stolze) | The I4.0 language, proactive AAS, the testbed over MQTT | Where the message names here come from |
| IEEE 2660.1-2020; Leitão et al. 2023 | How agents interface with devices | Our interface is the recommended "hybrid, tightly coupled, OPC UA" |

**What is new here** (for the journal paper, [journal-paper.md](journal-paper.md)): a resource agent that,
having no skill for a required capability, plans one from the module's Capability Description and
creates it online in the running IEC 61499 program before it carries the step out; the cost of that
in the bid; one chain from LDS-ME discovery to an agent's start (IDTA 02020, AID, AIMC, VDI/VDE 2193,
OPC UA skills, the IEC 61499 management interface); planar transport bid for like a module; the
decisions in the batch record.
