# Agents for a modular pharmaceutical line: literature and technology survey

Survey date: 2026-10-30. Scope: SMIA, SPADE, agents combined with IEC 61499, agents combined with the
AAS and the VDI/VDE 2193 "I4.0 language", negotiation methods, and planar-motor transport. The survey is
written to inform the planned multi-agent layer above the existing system: IEC 61499 modules on 4diac
FORTE (Raspberry Pi), OPC UA skills, AASs in Eclipse BaSyx (Skills, IDTA Capability Description, AID, AIMC),
the Camel-based DMP, LDS-ME discovery, online creation of composite skills, HTN planning, and a Planar
Motor table exposed as a module.

How it was verified. Every reference in section 8 was checked against Crossref, OpenAlex or Semantic
Scholar metadata, the publisher page, or the primary repository/documentation. Where a statement about a
paper's content comes only from its abstract, it says so. Statements marked **[unverified]** could not be
checked against a primary source. Code-level statements about SMIA and SPADE were checked in their
GitHub source on 2026-10-30 (SMIA `main`, SPADE `master`).

---

## 1. Summary and recommendation

### 1.1 Key findings

1. **SMIA is the closest existing system and is real, active and on SPADE.** SMIA (Self-configurable
   Manufacturing Industrial Agents, GCIS group, University of the Basque Country EHU; Ekaitz Hurtado's PhD)
   turns an AAS that has been enriched with a Capability-Skill-Service (CSS) OWL ontology into a running
   SPADE agent (Hurtado et al., 2025, JII; Hurtado et al., 2026, Software Impacts). Version 1.0.3 was released
   on 2026-10-21 (PyPI `smia`); the GitHub repo is `ekhurtado/SMIA`. It has OPC UA, HTTP and MQTT asset
   connections configured from the IDTA Asset Interfaces Description (AID), a FIPA-ACL dialect
   ("FIPA-SMIACL"), a capability registry (SMIA-I KB, an OWL knowledge base) behind an infrastructure agent
   (SMIA ISM), and Docker Compose/Kubernetes environment generation. It does **not** use VDI/VDE 2193 message
   frames, does **not** use the IDTA Capability Description submodel (it uses the HSU CSS ontology plus its
   own semantic IDs), its OPC UA connection only reads and writes variables (no method calls, no security),
   its negotiation compares one scalar criterion, and it never changes the asset's control logic.
2. **SPADE is a sound base.** SPADE 4.1.4 (2026-05-26, MIT, Python 3.10 to 3.14) ships its own XMPP server
   (PyJabber), a FIPA-ACL message builder/parser (since 4.1.3), the five behaviour types we need (Cyclic,
   OneShot, Periodic, Timeout, FSM), and in-process message delivery between agents in the same process.
   A 5.0.0 beta exists (drops Python 3.10). SMIA pins `spade~=4.0.3`, so installing SMIA forces SPADE 4.0.x.
3. **IEEE 2660.1-2020 classifies agent-to-device interfaces along location (on-device vs "hybrid", i.e.
   remote), interaction mode (direct client-server vs publish-subscribe; the papers call these tightly vs
   loosely coupled) and technology.** It recommends a practice by weighting response time, scalability and
   reusability. Its own worked examples recommend a tightly coupled OPC UA client on a hybrid location when
   the asset cannot host agents, and on-device only when soft real-time control is needed in the agent
   (Leitão et al., 2023). Our plan (agents on a server, calling OPC UA skills) is that "tightly coupled,
   hybrid, OPC UA" practice.
4. **Agents combined with IEC 61499 is an old and well-studied pairing (2003 to 2011), but the reconfiguration
   in that work came from predefined configurations and ontologies, without the AAS.** The TU Wien/ACIN
   line (Hegny 2008; Zoitl 2010; Lepuschitz 2010, 2011; Vallée 2011) is the direct ancestor of our
   "agent reconfigures FORTE online" idea: a JADE-style high-level agent reasons over an ontology and drives an
   IEC 61499 reconfiguration infrastructure. Recent work (Lyu & Brennan 2020, 2023) runs **SPADE with 4diac on
   Raspberry Pi**, but as a two-layer control architecture, without AAS and without capability-driven planning.
5. **Agents combined with the AAS is a busy field (2020 to 2026) that has converged on "AAS Type 3 /
   proactive AAS".** The main groups are Leitão/Sakurada (IPB, Bragança), GCIS/EHU (López, Casquero,
   Hurtado, i.e. SMIA), DFKI/SmartFactory-KL (Jungbluth, Sidorenko, Bernhard: SARL/Janus, Kafka, BaSyx,
   VDI/VDE 2193 bidding, OPC UA skills), OvGU Magdeburg (Diedrich, Belyaev, Stolze: I4.0 language,
   proactive AAS, BPMN) and TUM (Vogel-Heuser, Ocker: AAS to PADE agent initialization). None of them
   reconfigures IEC 61499 control logic online after winning a bid.
6. **VDI/VDE 2193-1/-2 defines a usable message frame and bidding protocol.** The frame has type, sender,
   receiver, conversationId, messageId, inReplyTo, replyBy, semanticProtocol and role, plus interactionElements
   that are AAS submodel elements. The bidding message types are callForProposal, proposal, refuseProposal,
   notUnderstood, acceptProposal, rejectProposal and informConfirm. It is reported as implemented over MQTT
   (OvGU 2019 testbed; Grunau et al. 2022; Dietrich et al. 2026) and over Kafka with SARL (Bernhard et al.
   2023). No open-source implementation on SPADE/XMPP was found.
7. **No literature was found on agents (or AAS) controlling a planar-motor (ACOPOS 6D / Planar Motor /
   XPlanar) transport in product-driven production.** The closest are skill-based transport over OPC UA
   (Jungbluth et al., 2023) and multi-agent path finding on a magnetic planar drive (Janning et al., 2025),
   which works at the motion level, not the production level.

### 1.2 Recommendation for our framework

| Decision | Recommendation | Why (sources) |
|---|---|---|
| Where agents run | One central agent host (server or edge PC) next to BaSyx and the XMPP server. Keep FORTE alone on the Pis. Do not run agents on the Pis unless a need appears. | In IEEE 2660.1 terms this is the "hybrid location"; it is recommended when the device should not host agents, and on-device only for soft real-time agent logic (Leitão et al. 2023). Our real-time logic is already in IEC 61499, and skills encapsulate it. Lyu et al. (2020) show SPADE can run on a Pi if needed later. |
| How agents talk to modules | **Execute skills directly over OPC UA** (method call Start/Stop, subscription to the skill and module state machines), with endpoints and node ids read from the AID/AIMC, never hard-coded. **Read the self-description from the AAS** (Skills, Capability Description, AID) at start-up and after changes. Use the **AAS/DMP operation path for reconfiguration** (create composite skill) and for writes the AAS must record. | Direct OPC UA keeps subscriptions and low latency (the 2660.1 "tightly coupled, hybrid, OPC UA" practice). The AAS path keeps the AAS the single source of truth for structural changes. SMIA and DFKI resource holons also execute through OPC UA and read the AAS for configuration (Bernhard et al. 2023). The DMP adds a hop and is request/response only, which is a poor fit for skill-state monitoring. |
| Spawning agents | An **agent manager** in the agent host subscribes to registration events and starts or stops one resource agent per registered AAS **in the same Python process** (SPADE container). Event sources, in order of preference: (a) our registration service (LDS-ME/mDNS discovery and AAS registration); (b) BaSyx AAS repository MQTT events (`aas-repository/<repoId>/shells/created`, `.../deleted`); (c) BaSyx AAS registry Kafka events. The JID is derived from the AAS id; with `auto_register=True` the agent creates its own XMPP account. | SPADE's container delivers messages between local agents without going through XMPP (checked in `spade/container.py`), and with 5 to 10 agents a process is enough. A container per agent (SMIA, DFKI) only pays off at larger scale or with heterogeneous hosts. No Kubernetes *operator* for agents was found in the literature; SMIA only generates Kubernetes YAML. |
| XMPP server | Development: SPADE's built-in PyJabber (`spade run` or `spade.run(main(), embedded_xmpp_server=True)`). Deployment: ejabberd (SMIA's choice, ready-made Docker image) or Prosody (light, good on small hosts). | Section 3.4. |
| Message protocol | **VDI/VDE 2193-1 frame as a JSON body over SPADE/XMPP**, with XMPP `thread` = conversationId and SPADE metadata `performative` = frame `type`. **VDI/VDE 2193-2 bidding** for allocation, plus a small "skill execution" protocol (request, agree/refuse, inform-done/failure) in the style of Sidorenko et al. (2021). interactionElements carry the required capability with its constrained properties (IDTA Capability Description) and, in proposals, price/time/setup. | It is the I4.0 standard; it is what OvGU, DFKI and Grunau implement; SMIA's FIPA-SMIACL is not 2193-compliant. SPADE's FIPA builder can be used for the transport envelope. |
| Negotiation | **Product-driven, step-by-step contract net with deadlines and reservations**: the product agent sends a callForProposal for the next process step with a replyBy; resource agents bid with earliest start/finish, setup time (including the time to create a new skill online) and confidence; acceptProposal books a time slot; transport is booked as a separate bid tied to the process slot (or the planar agent is asked after the process award). Failures produce a failure/inform, then a new CFP (replanning). | Contract net is the standard fit for few resources and one-step lookahead (Smith 1980; FIPA SC00029H); bids that include changeover time and use a 0..1 desirability are used by DFKI (Bernhard et al. 2023); replanning on breakdown follows Jungbluth et al. (2022). PROSA/ADACOR/potential fields are for larger systems (section 6). |
| Reuse from SMIA | Reuse **ideas and patterns**, cite as the closest related work, do not import the package. Possibly port its asset-connection abstraction (configure from AID, connect, execute, receive). | Licence is copyleft (GitHub: GPL-3.0; PyPI metadata: AGPL-3.0, inconsistent); it pins SPADE 4.0.x; its capability model is not IDTA 02020; its OPC UA client has no method calls; its negotiation and messaging differ from 2193. Building on plain SPADE is less code than adapting SMIA. |
| Build ourselves | Resource agent (module), resource agent (planar table), product agent, agent manager; the 2193 frame codec; the bidding behaviours (FSMBehaviour per conversation); the reconfiguration step after acceptance (calls the existing HTN planner and the IEC 61499 management path); logging of each decision into the product AAS (traceability, important for pharma). | This is the part that is new in the literature (section 7). |

### 1.3 Suggested architecture (text sketch)

```
                   XMPP (ejabberd/Prosody/PyJabber)  -- VDI/VDE 2193 frames as JSON bodies
   +--------------------------- agent host (one Python process, SPADE) ---------------------------+
   | AgentManager --(registration events: modreg / BaSyx MQTT)--> start/stop agents                |
   | ProductAgent(order k): FSM per step: CFP -> collect proposals (replyBy) -> accept/reject ->    |
   |                        await informConfirm/failure -> next step | replan                       |
   | ResourceAgent(module m): reads AAS (Skills, CapabilityDescription, AID, AIMC) at start;       |
   |    bid = f(capability match, occupation, queue, setup incl. "plan+deploy new skill" time)      |
   |    on accept: if no skill -> HTN plan -> create composite skill (AAS/DMP or mgmt path)         |
   |    execute: OPC UA method Start, subscribe skill state, informConfirm / failure               |
   | ResourceAgent(planar table): bids for moves A->B with time windows, reserves shuttles         |
   +-----------------------------------------------------------------------------------------------+
        | OPC UA (direct, endpoints from AID)          | AAS REST (BaSyx) / DMP operations
   [Pi: FORTE + OPC UA server]  ...  [Planar Motor OPC UA]      [BaSyx AAS repo/registry]
```

---

## 2. SMIA in detail

### 2.1 Identity, versions, licence

- Name: Self-configurable Manufacturing Industrial Agents (earlier "I4.0 Standardized Microservice-based
  Industrial Agent"; old repo name `I4_0_SMIA`). Origin: PhD thesis of Ekaitz Hurtado, GCIS (Systems
  Control and Integration) group, University of the Basque Country (EHU), with Oskar Casquero, Aintzane
  Armentia, Arantzazu Burgos, Isabel Sarachaga.
- Code: <https://github.com/ekhurtado/SMIA> (created 2024-04-29, last push 2026-10-21). Docs:
  <https://smia.readthedocs.io/> (1.0.3). PyPI: `smia` 1.0.3 (2026-10-21; 1.0.0 on 2026-07-29). Docker Hub:
  `ekhurtado/smia` (`latest-alpine`, `latest-alpine-base`).
- Licence: the GitHub repository declares **GPL-3.0**; the PyPI metadata says **GNU Affero GPL v3**. Either is
  copyleft; importing or copying SMIA code would put our derived code under GPL/AGPL terms.
- Dependencies (PyPI 1.0.3): `spade~=4.0.3`, `basyx-python-sdk~=1.2.1`, `owlready2~=0.48`, `asyncua>=2.0.1`,
  `aiomqtt~=2.5.1`, `aiohttp`, `jsonschema`, `slixmpp==1.8.5`; Python >= 3.10.
- Papers: Hurtado, Burgos, Armentia, Casquero, "Self-configurable Manufacturing Industrial Agents (SMIA): a
  standardized approach for digitizing manufacturing assets", *Journal of Industrial Information Integration*
  47 (2025) 100915, doi:10.1016/j.jii.2025.100915 (open access). Hurtado, Sarachaga, Armentia, Casquero, "An
  open-source reference framework for the implementation of type 3 Asset Administration Shells", *Software
  Impacts* 27 (2026) 100807, doi:10.1016/j.simpa.2025.100807. A performance-evaluation dataset at EHU
  compares SMIA's self-configuration with NOVAAS and FA³ST (from the repository record; details
  **[unverified]**).
- Predecessor work of the same group: López, Casquero, Marcos (2021, ICPS), design patterns for agent-based
  AASs; López et al. (2021, INDIN), four-layered architecture for agent-based AAS and physical assets,
  explicitly complementary to IEEE 2660.1; López et al. (2023, *Computers in Industry*), an industrial
  agent-based I4.0 platform.

The JII abstract (via OpenAlex) states the two layers: (1) "a methodology for characterizing proactive AAS
by enriching their descriptions with an OWL ontology based on the CSS model", and (2) "a software
toolchain that automatically generates Digital Twins, implemented as FIPA-compliant industrial agents
using SPADE, from these enriched AAS descriptions", validated "in a robotic logistics scenario". The
full text could not be retrieved (publisher and repository blocked automated access), so the architecture
below is taken from the documentation and source code.

### 2.2 Architecture (from docs and source)

- **Agent classes** (`smia.agents`): `SMIAAgent`, `ExtensibleSMIAAgent`, `SMIAResourceAgent`,
  `SMIAAppAgent`.
- **Life cycle** as a SPADE `FSMBehaviour` (`smia.states`): `StateBooting` (and `StateBootingResource`),
  `StateRunning`, `StateIdle`, `StateStopping`. In booting the agent loads the CSS ontology (owlready2),
  runs `InitAASModelBehaviour` (reads the AAS and builds ontology instances), and, if configured, registers
  its CSS elements and itself in the SMIA-I KB through the SMIA ISM (`RegisterCSSElements`,
  `RegisterSMIAInstance`).
- **Behaviours** (`smia.behaviours`): `ACLHandlingBehaviour` (dispatch of incoming ACL messages),
  `CheckPhysicalAssetBehaviour`, `NegotiatingBehaviour`, and per-request handlers
  `HandleCapabilityBehaviour`, `HandleNegotiationBehaviour`, `HandleAASRelatedSvcBehaviour`,
  `HandleSvcResponseBehaviour`. Handlers reserve the conversation thread so the generic dispatcher skips its
  messages.
- **CSS model**: uses the HSU Hamburg CSS ontology (`http://www.w3id.org/hsu-aut/css#`: `Capability`,
  `CapabilityConstraint`, `Skill`, `SkillInterface`, `SkillParameter`, `StateMachine`, properties
  `isRealizedBy`, `isRestrictedBy`, `accessibleThrough`, `hasParameter`, `behaviorConformsTo`) extended by a
  GCIS namespace (`http://www.w3id.org/upv-ehu/gcis/css-smia#`: `AgentCapability`, `AssetCapability`,
  `accessibleThroughAssetService`, `accessibleThroughAgentService`). AAS elements are tied to these concepts
  by semanticIds that point at ConceptDescriptions whose ids are the ontology IRIs, plus qualifiers
  (`ExpressionSemantic`, `SkillImplementationType`, `FeasibilityCheckingCondition`). The AASX Package
  Explorer plugin `GCIS/SubmodelWithCapabilitySkillOntology` creates the submodel. This is **not** the IDTA
  Capability Description submodel that we use; adopting SMIA would mean remodelling or writing a mapper.
- **Asset connections** (`smia.assetconnection`): abstract `AssetConnection` with
  `configure_connection_by_aas_model`, `check_asset_connection`, `connect_with_asset`,
  `execute_asset_service`, `receive_msg_from_asset`. Implementations: HTTP (aiohttp), MQTT (aiomqtt; since
  0.3.3, much improved in 1.0.3), OPC UA (asyncua; since 1.0.2). All are configured from the IDTA
  `AssetInterfacesDescription` submodel (several AID versions supported since 1.0.3). The **OPC UA
  connection** opens one persistent session, subscribes to "observable" interaction elements, and on
  `execute_asset_service` **reads a variable, or writes it if input is given; it does not call OPC UA
  methods**, and security is a TODO (`nosec_sc` only) (checked in `opcua_asset_connection.py`). Our modules
  expose skills as methods with state machines, so this would need extending.
- **Extension API** (`ExtensibleSMIAAgent`): `add_new_asset_connection(aas_interface_id_short, connection)`,
  `add_new_agent_capability(behaviour)`, `add_new_agent_service(service_id, method)`.
- **Configuration**: a properties file with DT, AAS and ONTOLOGY sections; the XMPP identity is
  `dt.agentID`, `dt.password`, `dt.xmpp-server` (in containers `AGENT_ID=smia-1@xmppserver`,
  `AGENT_PSSWD`, `AAS_MODEL_NAME`). The XMPP identity is **not** read from the AAS. The AAS can be a local
  AASX or fetched by AAS id from an AAS repository through the ISM.

### 2.3 Messaging

- FIPA-ACL mapped onto SPADE messages: sender, receiver (`Message.to`), conversation-id = `Message.thread`;
  protocol, performative, ontology, encoding (JSON), language (`smia-language`) in `Message.metadata`; content
  as JSON in `Message.body`, validated by JSON Schemas per ontology (since 0.2.4).
- Ontology values: `asset-related-service`, `agent-related-service`, `aas-service`,
  `aas-infrastructure-service`, `css-service`. Protocols: FIPA request, contract-net, query.
- The documentation calls this "FIPA-SMIACL" and uses it as SMIA's "I4.0 language". It is **not** the
  VDI/VDE 2193 frame (no semanticProtocol/role/replyBy fields; the glossary and communication guide do not
  mention VDI 2193).

### 2.4 Discovery and infrastructure (ISM, KB)

- **SMIA ISM** (Infrastructure Services Manager): an extended SMIA agent that translates FIPA-SMIACL requests
  into OpenAPI/HTTP calls to non-agent infrastructure, namely the **SMIA-I KB** (an OWL knowledge base with
  HTTP/OpenAPI) and a BaSyx AAS repository. Discovery by capability is two calls: `GetAllAssetIDByCapability`
  (capability IRI to asset ids), then `GetSMIAInstanceIDByAssetID` (asset id to agent JID).
- **SMIA Environment Builder**: generates local, Docker Compose or Kubernetes deployments with ejabberd, an
  AAS server (BaSyx Go or Java since 1.0.3), KB and ISM. No Kubernetes operator: environments are generated
  ahead of time; agents do not appear automatically when an AAS is registered (assets "self-register" with
  KB and ISM at start-up).
- **Ecosystem agents**: SMIA PE (production execution from CSS-annotated BPMN, with a Camunda Modeler
  plugin), SMIA HI (human interface), SMIA Operator (GUI to discover agents and launch negotiations), an
  OperationalHealthSupervisor (1.0.2), asset simulators.

### 2.5 Negotiation (from `handle_negotiation_behaviour.py`, `negotiation_utils.py`)

A requester sends a CFP (FIPA contract-net) to a list of target agents with a criterion. Each target
(1) runs a capability check when the CFP is a CSS service and refuses on failure (its value becomes -1);
(2) obtains its value for the criterion (an asset or agent service; criteria are declared with a
ConceptDescription `urn:ehu:gcis:conceptdescriptions:1:1:negotiationcriteria`); (3) sends PROPOSE with its
value **to all other targets**; (4) drops out as soon as it sees a higher value (ties broken by a seeded
random draw); (5) the remaining winner sends INFORM `{winner: true}` to the requester. So it is a
decentralized contract-net variant in which the bidders elect the winner themselves, on one scalar value
(for example remaining battery), with retries and dynamic waits (0.3.2). It has no deadlines (replyBy),
no time-slot reservation and no multi-attribute evaluation.

### 2.6 Use cases

- Cooperative transport logistics: two simulated TurtleBot3 robots (ROS Noetic) behind HTTP, an operator
  agent with a GUI, capability `EfficientTransport`, negotiation among robots that meet a weight constraint;
  Docker Compose with ejabberd. Lessons reported: starting from the AAS is complex at first; the CSS model
  simplifies encapsulation; a good dashboard and an efficient discovery system are needed.
- A CeDRI (Bragança) demonstrator is listed in the docs (details **[unverified]**).

### 2.7 What we can reuse, and the gaps

Reusable:
- The pattern: **one generic agent class, configured entirely from the AAS** at start-up (AID gives the
  endpoints, the capability/skill model gives what to offer). This is what our resource agents should do.
- The asset-connection abstraction (configure from AID / connect / execute / receive) and the observable
  subscription idea.
- Discovery by capability (KB, ISM). In our system the BaSyx registry plus the capability submodels can play
  the KB role without OWL.
- Deployment recipe: ejabberd in Docker with a healthcheck, agents as containers if needed.
- As related work: SMIA is the paper our journal article must position against.

Gaps relative to our system:
- No IEC 61499 and no reconfiguration of the asset: skills are fixed services of the asset.
- Capability model is OWL CSS with GCIS semantic IDs, not IDTA 02020 Capability Description; no HTN or
  other planning from capability pre/postconditions (planning is in BPMN, in SMIA PE).
- OPC UA without method calls and without security; no PackML or skill state machines.
- FIPA-SMIACL, not VDI/VDE 2193; negotiation is a single-criterion election without reservations.
- Agent spawning is static (environment generated beforehand), not event-driven from a registry.
- Copyleft licence and the SPADE 4.0.x pin.

---

## 3. SPADE in detail

### 3.1 Versions and project facts

- Repo <https://github.com/javipalanca/spade> (MIT), docs <https://spadeagents.eu> (legacy docs at
  spade-mas.readthedocs.io). Reference paper: Palanca, Terrasa, Julian, Carrascosa, "SPADE 3: Supporting the
  New Generation of Multi-Agent Systems", *IEEE Access* 8 (2020) 182537-182549.
- Release history (from `HISTORY.rst` and GitHub releases):
  - 4.0.0 (2024-12-19): built-in XMPP server as CLI, pyproject, selectable XMPP port, uvloop/winloop.
  - 4.0.1-4.0.3 (to 2025-02-17): fixes, `--debug`, in-memory DB for the server.
  - 4.1.0 (2025-05-22): XMPP server auto-launched transparently with agents, in-memory DB, better presence
    handling and subscription, overridable `presence_received`, Python 3.13.
  - 4.1.2 (2025-08-08): switch to the `slixmpp-multiplatform` fork.
  - 4.1.3 (2026-04-28): **FIPA-ACL message builder and parser** (`spade/fipa_message.py`), XEP-0363 HTTP file
    upload, `__slots__`, drops Python 3.9, supports 3.14.
  - 4.1.4 (2026-05-26): hotfix (FSMBehaviour `setup()` override), Python 3.10 to 3.14. **Current stable.**
  - 5.0.0b1 (2026-05-11): beta, drops Python 3.10 (Python 3.11 to 3.14); a newer slixmpp without a Rust
    toolchain requirement.
- Dependencies of 4.1.4: `slixmpp-multiplatform==1.12.0`, `pyjabber>=0.4.3`, aiohttp, jinja2 (web UI).
- Plugins on PyPI: `spade_bdi` 0.3.3 (BDI agents with AgentSpeak, requires spade>=4.1.4), `spade_pubsub`
  0.3.0 (XEP-0060 publish-subscribe), `spade-artifact` 0.3.2 (artifacts, i.e. environment objects),
  `spade-llm` 0.3.0 (LLM agents, MCP tools), `spade_norms` 0.1.4 (old, pins SPADE 3).

### 3.2 Programming model

- Agent: subclass `spade.agent.Agent`, implement `async setup()`, add behaviours with
  `self.add_behaviour(behaviour, template=None)`. Start with `await agent.start(auto_register=True)`
  (in-band account registration), stop with `await agent.stop()`. Launch with `spade.run(main())`;
  `spade.run(main(), embedded_xmpp_server=True)` starts PyJabber for the coroutine's lifetime;
  `spade.start_agents([...])` starts a list in parallel. Ctrl+C stops all agents.
- Behaviours (from `spade/behaviour.py`): `CyclicBehaviour` (base, `on_start`/`run`/`on_end`, `receive`
  with timeout, `send`, `kill`), `OneShotBehaviour`, `PeriodicBehaviour`, `TimeoutBehaviour`, `State` and
  `FSMBehaviour` (states and transitions). A per-conversation `FSMBehaviour` is the natural way to write the
  2193 bidding roles.
- Templates: `spade.template.Template` matches sender, to, thread, body and metadata; a behaviour receives
  only messages that match its template. Use `thread` (conversationId) and metadata `performative` to route
  2193 messages to the right conversation.
- Messages: `spade.message.Message(to, body, thread, metadata)`. Since 4.1.3 `spade.fipa_message` builds and
  validates FIPA-ACL messages (performatives per FIPA SC00061G).
- Presence: agents publish availability and can subscribe to each other's presence. Useful as a cheap
  liveness signal for resource agents (a module agent going "unavailable" when its OPC UA session drops).
- Web interface: each agent can serve a small aiohttp web UI (behaviours, messages, contacts) and add
  custom pages and menu entries (3.3.1, 3.3.2). PyJabber serves an admin page on port 9090.
- **Container**: `spade/container.py` is a process-wide singleton; when sender and receiver live in the same
  process the message is dispatched directly, otherwise it goes over XMPP. So many agents in one process
  are cheap and fast, and agents in other processes or hosts still work transparently.
- BDI: `spade_bdi` gives AgentSpeak plans and beliefs. Not needed for contract net; possibly interesting for
  the product agent if goals and plans become complex.

### 3.3 Scaling and known limits

- One asyncio event loop per process; CPU-heavy work (HTN planning, scheduling) inside a behaviour blocks
  all agents in the process, so run it in an executor or a separate process.
- XMPP adds a hop and XML serialization; fine for tens of messages per second per agent. No formal SPADE
  benchmark was found in this survey **[unverified]**. Dietrich et al. (2026) report that a multicast
  VDI 2193 bidding over MQTT with hundreds of Docker containers did not scale (message load grew sharply,
  up to 360 s simulation time), but they used neither SPADE nor XMPP, and at our size (fewer than 10
  resources) this is not a concern.
- SMIA's dependency pins (`spade~=4.0.3`, `slixmpp==1.8.5`) conflict with SPADE 4.1.x.

### 3.4 XMPP server options

| Server | Notes for us |
|---|---|
| PyJabber (built into SPADE 4.x) | Pure Python asyncio, MIT, client port 5222, server 5269, admin web 9090, SQLite or in-memory DB. Best for development and tests (start with `spade run` or embedded). Single process, not intended as a hardened production server. |
| ejabberd (ProcessOne, Erlang) | SMIA's choice; official image `ghcr.io/processone/ejabberd`; mature, clustering, admin API. In-band registration (`mod_register`) must be allowed for `auto_register=True`, or accounts created with `ejabberdctl register`. |
| Prosody (Lua) | Small footprint, easy config; enable `allow_registration = true` (or create users with `prosodyctl`). Mentioned in SPADE docs as an alternative. |
| Openfire (Java) | Web admin console, plugins; heavier. Needs in-band registration enabled in its settings. |

(The registration settings are standard XMPP server configuration knowledge, not taken from a cited
source.)

### 3.5 Deployment practice

- **Many agents per process** (SPADE container) is the default and fits a lab line. Isolation per agent
  (container per agent) is used by SMIA (Docker image per instance), DFKI (resource holons as Docker
  containers with CI/CD; Bernhard et al. 2023) and Dietrich et al. 2026 (Docker Swarm). It costs start-up
  time and orchestration delays (Dietrich et al. report delays when hundreds of containers start).
- A middle way: one process per *kind* of agent host (for example agent host A for resource agents, B for
  product agents) so a crashing product agent does not take module agents down.

---

## 4. Agents combined with IEC 61499, and IEEE 2660.1

### 4.1 Integration patterns

Three patterns appear in the literature:

- **Agent inside the IEC 61499 runtime (embedded, "on-device", in the FB network).** The agent logic is
  written as function blocks: Black & Vyatkin (2009/2010) build autonomous, collaborating conveyor-section
  components entirely in IEC 61499; Christensen (2003) defines the HMS/FB architecture for holonic
  manufacturing with function blocks at the lower level; Lyu & Brennan (2023) propose "agent-embedded"
  function blocks.
- **Agent next to the runtime, separate process, with a dedicated interface (two-layer HLC/LLC).** The agent
  (high-level control) reasons and plans; IEC 61499 (low-level control) executes; an interface couples them.
  TU Wien/ACIN automation agents (Merdan et al. 2009; Lepuschitz et al. 2009, 2010, 2011; Vallée et al.
  2011; Hegny et al. 2008) and Lyu, Fazlirad & Brennan (2020) with SPADE and 4diac. The agent may sit on the
  same device or a separate one.
- **Agent remote, talking a standard protocol (OPC UA, MQTT, REST) to skills on the device.** Typical of
  the recent AAS work (DFKI resource holons via OPC UA skills; SMIA; Köhle et al. 2026 with OPC UA methods
  via MCP tools). Our plan is this pattern.

Note on terminology: the user's "tightly coupled = on-device / loosely coupled = separate process" differs
from IEEE 2660.1, where location (on-device vs hybrid) and coupling (tightly = direct client-server call,
loosely = publish-subscribe) are separate dimensions (see 4.3). In 2660.1 terms our plan is
**tightly coupled, hybrid, OPC UA**.

### 4.2 Literature table: agents and IEC 61499

| Reference | Year, venue | Integration pattern | Where the agent runs | How it reconfigures | Relevance to us |
|---|---|---|---|---|---|
| Christensen, "HMS/FB architecture and its implementation" | 2003, book chapter in *Agent-Based Manufacturing* (Springer), 53-87 | Holonic architecture with IEC 61499 FBs at the lower level and agents above (details **[unverified]**, only metadata checked) | Mixed | Holonic (re)organization | Historical root of HMS plus IEC 61499 |
| Hegny, Hummer, Zoitl, Koppensteiner, Merdan | 2008, SIES, 249-252 | Agents integrated with IEC 61499 real-time control (title-level) | Separate HLC | Reconfiguration of distributed control | Early ACIN integration |
| Black & Vyatkin, "Intelligent component-based automation of baggage handling systems with IEC 61499" | 2009 online / 2010, IEEE TASE 7(2) 337-351 | Agents as IEC 61499 components (embedded) | In the IEC 61499 runtime, embedded hardware | Structure defined by interconnecting autonomous FB components | Shows agents can be FBs; not our pattern |
| Merdan, Lepuschitz, Hegny, Koppensteiner | 2009, ICARA, 628-633 | HLC agents plus IEC 61499 LLC with a generic communication interface | Separate HLC | Simulation of failure scenarios in transport | Interface design between agent and FORTE |
| Lepuschitz, Vallée, Merdan, Vrba, Resch | 2009, ETFA | Generic interface to heterogeneous LLCs | Separate HLC | n/a | Same |
| Zoitl, Lepuschitz, Merdan, Vallée | 2010, ETFA | Real-time reconfiguration infrastructure for IEC 61499 | Infrastructure in the runtime | Online reconfiguration of FB networks | Ancestor of our online skill creation |
| Lepuschitz, Vallée, Zoitl, Merdan | 2010, IECON, 1365-1370 | Automation agent with integrated LLC reconfiguration | Agent next to runtime | Online reconfiguration of the LLC, measured timing, no restart | Very close to our "reconfigure module online" |
| Lepuschitz, Zoitl, Vallée, Merdan, "Toward self-reconfiguration of manufacturing systems using automation agents" | 2011, IEEE TSMC-C 41(1) 52-69 | Ontology of LLC functionality at HLC; HLC reasons and triggers reconfiguration of IEC 61499 LLC | Agent next to runtime | Ontology-driven choice among LLC configurations, applied "on the fly" | **Key prior work**; our novelty: AAS + capability description + HTN-planned composite skills + bidding |
| Vallée, Merdan, Lepuschitz, Koppensteiner, "Decentralized reconfiguration of a flexible transportation system" | 2011, IEEE TII 7(3) 505-516 | MAS with ontology-driven local reconfiguration of control software | Agents per component | Local reconfiguration consistent with global behaviour | Transport reconfiguration by agents |
| Strasser, Sunder, Zoitl, Rooker, Brunnenkreef | 2007, INDIN, 1163-1168 | Enhanced IEC 61499 device management | n/a (reconfiguration control application) | Downtimeless reconfiguration services | Background for management-command reconfiguration |
| Kruger & Basson, "Multi-agent systems vs IEC 61499 for holonic resource control in reconfigurable systems" | 2013, Procedia CIRP 7, 503-508 | Compares agents vs IEC 61499 for holonic resource control | n/a | Four reconfiguration experiments | Found agents more suitable in their case; argues for agents above, not in, IEC 61499 |
| Dorofeev & Zoitl, "Skill-based engineering approach using OPC UA programs" | 2018, INDIN, 1098-1103 | Skills as FSMs exposed as OPC UA Programs (4diac context) | n/a | n/a | The skill interface our agents call |
| Profanter, Dorofeev, Zoitl, Knoll, "OPC UA for plug & produce: automatic device discovery using LDS-ME" | 2017, ETFA | Discovery | n/a | n/a | Exactly our discovery mechanism; trigger for spawning agents |
| Lyu, Fazlirad, Brennan, "Multi-agent modeling of CPS for IEC 61499 based distributed automation" | 2020, Procedia Manuf. 51, 1200-1206 | Two layers: multi-agent model above, IEC 61499 FBs below | **SPADE on Jetson Nano and Raspberry Pi, with Eclipse 4diac** | Real-time adaptation at device level (abstract) | Shows SPADE + 4diac on a Pi is feasible |
| Lyu & Brennan | 2023 online / 2025, IJCIM 38(5) 596-622 | Multi-agent cyber layer plus "agent-embedded" IEC 61499 FB model | Jetson Nano / Raspberry Pi; NetLogo simulation | Discover alternatives, coordinate reconfigurable modules, deploy functions (abstract) | Closest recent agent + IEC 61499 work; no AAS |
| Lv, Zhang, Dai, "Integrated asset management model based on IEC 61499 and Administration Shell" | 2021, IECON | AAS + IEC 61499 integrated model, no agents | n/a | Dynamic reconfiguration motivated | AAS + IEC 61499 modelling |
| Cruz Salazar et al., "Adaptive learning and interoperability in I4.0: agent-based DT with AAS" | 2025, IFAC-PapersOnLine 59, 202-207 | Predictive PADE agents embedded in PLCs, AAS, IEC 61131-3 and IEC 61499 | In the PLC (on-device) | Learning-based adaptation (abstract) | Recent on-device agent + AAS + IEC 61499 example |

Not found: "Kalachev/Taylor" on agents and IEC 61499 could not be identified in Crossref or web search
**[unverified]**. Dubinin & Vyatkin's IEC 61499 work found by the search is on formal semantics and
verification, not agents.

### 4.3 IEEE 2660.1-2020

- Title: *IEEE Recommended Practice for Industrial Agents: Integration of Software Agents and Low-Level
  Automation Functions*, IEEE Std 2660.1-2020, approved 2020-09-24, published 2021-01-29,
  doi:10.1109/IEEESTD.2021.9340089. Paywalled; the summary below is from the working-group papers
  (Leitão et al. 2017, 2018, 2021, 2023; Karnouskos et al. 2018).
- **Scope**: how to interface a software agent with a low-level automation function (sensor, robot
  controller, PLC/IPC), e.g. to monitor a value, start or stop a program, or read and write variables.
- **Clustering of practices** along three dimensions:
  - *Location*: **on-device** (agent on the same computational platform as the asset) or **hybrid** (agent on
    a remote platform).
  - *Interaction mode*: direct call, client-server (the papers' **tightly coupled**) or publish-subscribe
    (**loosely coupled**, better scalability). The four generic classes are therefore tightly coupled
    on-device, tightly coupled hybrid, loosely coupled on-device, loosely coupled hybrid. (The equivalence
    "tightly = client-server" is inferred from how the alignment paper uses the terms.)
  - *Technology*: e.g. OPC UA, Modbus, REST, sockets for client-server; MQTT and OPC UA for publish-subscribe.
- **Quality criteria**: from ISO/IEC 25010 the standard keeps response time, scalability and reusability
  (Karnouskos et al. 2018 analysed ISO/IEC 25010 and 25023 measures).
- **Recommendation method**: a repository of interface practices scored by experts on a five-level Likert
  scale; a scoring engine aggregates expert entries; a recommendation engine filters by the user's scenario
  (function: monitoring/control/simulation; domain: factory, energy, building; constraints such as "the
  controller can host agents") and ranks the rest with a weighted multi-criteria function (e.g. response time
  60 %, reusability 40 %). Output: a ranked list of practices (location, interaction mode, API/client).
- **Worked examples** (Leitão et al. 2023): a robot that cannot host agents, monitoring, 50/50 weights gives
  **tightly coupled OPC UA client (Apache Milo), hybrid location**; the same robot in production where the
  controller can host agents and control is time-critical (80/20) gives **tightly coupled on-device**; CNC data
  acquisition gives tightly coupled sockets/DPWS/OPC UA; energy and building cases with scalability weighted
  highest give **hybrid, loosely coupled, MQTT**.
- **Findings of the survey behind the standard** (Leitão et al. 2017): practices are very diverse, mostly
  custom, focused on I/O, without security, and "mostly coupled rather than embedded".
- **Limitations stated by the authors**: the expert dataset in the standard is indicative and must be kept
  up to date; it recommends a practice, not a specific interface standard; other criteria (cost, security)
  may matter (Leitão et al. 2023).
- **What it means for us**: our scenario (control function, factory domain, Pi could host agents but we do
  not want to load it, response time matters at the skill level, reusability high) fits "tightly coupled,
  hybrid, OPC UA" for skill execution, possibly with OPC UA subscriptions (or OPC UA PubSub/MQTT) for state
  monitoring, which would be a loosely coupled channel. Stating this classification explicitly in the papers
  answers the expected reviewer question "why not on the device?". López et al. (2021, INDIN) show how an
  agent-based AAS layering complements 2660.1.

---

## 5. AAS, agents and the I4.0 language

### 5.1 VDI/VDE 2193

- **VDI/VDE 2193 Blatt 1:2020-04**, *Language for I4.0 components: structure of messages*; **Blatt
  2:2020-01**, *Language for I4.0 components: interaction protocol for bidding procedures*. German/English,
  paywalled (DIN Media/VDI). Based on the Plattform I4.0 discussion paper "I4.0-Sprache" (2018).
- **Message structure** (as implemented in the OvGU "AAS networked" testbed report, 2019, following 2193-1):
  - frame: `type` (purpose), `sender`, `receiver` (AAS ids; may be omitted for broadcast), `conversationId`,
    `messageId`, `inReplyTo`, `replyBy` (deadline, Unix time), `semanticProtocol` (e.g. the bidding
    protocol id), `role` (`serviceRequester`, `serviceProvider` for bidding);
  - interactionElements: AAS submodels or submodel elements carrying the content; for bidding a
    property-based service description with a technical part (e.g. diameter) and a commercial part (price,
    time, place) using ECLASS/IEC 61360 semantic ids.
- **Message types** (German term, testbed English name): Ausschreibung `callForProposal`; Angebot `proposal`;
  Absage `refuse`/`refuseProposal`; Nicht verstanden `notUnderstood`; Angebotsannahme `acceptProposal`;
  Angebotsablehnung `rejectProposal`; Informieren/Bestätigung `informConfirm`; Fehler `failure`.
- **Bidding protocol** (2193-2): the requester sends a callForProposal (often broadcast) with replyBy;
  providers answer proposal, refuse or notUnderstood, or stay silent; after the deadline the requester
  evaluates proposals (the decision algorithms are not prescribed), sends acceptProposal to the winner and
  rejectProposal to others; the provider performs the service and sends informConfirm. Proposals are
  binding. The VDI press material describes it as setting up legally binding value chains between I4.0
  components.
- **Transports used in practice**: MQTT (OvGU testbed: broadcast topic `I40/BroadcastSP`, each component
  subscribes to its AAS id as topic; Grunau et al. 2022; Dietrich et al. 2026 with topics `cfp/<service>`
  and `message/<AAS-ID>`), Kafka (DFKI, Bernhard et al. 2023), OPC UA (Sidorenko et al. 2021, which defines a
  "skill execution" semantic interaction protocol in I4.0 language and represents it in the AAS). No
  XMPP/SPADE implementation was found.
- **Implementations**: the SAP-originated `i40-aas` toolset states support for "interactions between
  administration shells based on semantic protocols (VDI/VDE 2193-1)" (alpha; archived and moved into the
  Eclipse Digital Twin project); no maintained open-source 2193-2 bidding library was found. No BaSyx
  component implementing 2193-2 was found (BaSyx is used underneath by Grunau et al. 2022 and DFKI).

### 5.2 How agents appear when a resource appears

| Mechanism | Source | Notes |
|---|---|---|
| BaSyx v2 AAS repository MQTT eventing | `basyx-java-server-sdk`, `basyx.aasrepository-feature-mqtt` README | Topics `aas-repository/$repoId/shells/created`, `/updated`, `/deleted`, and submodel-reference events; payload is the AAS JSON; ids Base64URL-encoded. |
| BaSyx v2 AAS registry Kafka events | `basyx-java-server-sdk`, `basyx.aasregistry` README | Registry event sink delivers shell-descriptor and submodel registration events via Kafka (default: log only). Release images `...-kafka-mem`, `...-kafka-mongodb`. |
| OPC UA LDS-ME (mDNS) | Profanter et al. 2017 | Device announces itself; discovery server learns it. Our current mechanism. |
| Holon spawning by a parent holon | Bernhard et al. 2023 | Island resource holons have a lifecycle skill to create, destroy and reboot sub-holons; product holons spawn sub-holons per sub-task and a product AAS. |
| Pre-generated deployments | SMIA Environment Builder | Docker Compose/Kubernetes YAML generated beforehand; agents self-register at start. |
| Parser that initializes agents from AASs | Vogel-Heuser, Ocker, Scheuer 2021 | Parser extracts knowledge from AASs and initializes PADE agents. |
| Container-based proactive AAS services | Ellwein et al. 2025 (arXiv) | Containerized services deployed by trigger conditions embedded in an extended submodel (orchestrator not named in the abstract). |
| Kubernetes operator | none found | No paper or repository found that spawns agents with a Kubernetes operator on AAS registration. |

### 5.3 Literature table: AAS and agents

| Reference | Year, venue | Agent platform, transport | Where agents run | Interaction with assets | Reconfiguration / negotiation | Relevance |
|---|---|---|---|---|---|---|
| OvGU/IFAT, "Specification Testbed AAS networked: Proactive AAS, interaction according to VDI/VDE 2193" | 2019, technical report | Own; MQTT | Cloud service requester/provider | n/a | 2193-2 bidding (price, time) | Best open description of the 2193 frame and bidding messages |
| Schröder & Diedrich, proactive AAS system architecture | 2019, at 67(7) 599-616 | Conceptual | n/a | n/a | Cognitive architecture of proactive AAS | Concept background |
| Sakurada & Leitão, "MAS to implement I4.0 components" | 2020, ICPS, 21-26 | MAS (platform **[unverified]**) | n/a | UR3 inspection cell | Maps AAS functions to MAS features | Early agent-based AAS |
| Ocker, Urban, Vogel-Heuser, Diedrich | 2021, IFAC-PapersOnLine 54(1) 837-844 | n/a | n/a | n/a | Use AAS to create agents' knowledge bases | Agents configured from AAS |
| Vogel-Heuser, Ocker, Scheuer | 2021, at 69(12) 1026-1039 | PADE (Python) | n/a | n/a | Parser initializes agents from AASs | Same idea as SMIA, earlier, Python |
| López, Casquero, Marcos | 2021, ICPS, 213-218 | Industrial agents | n/a | n/a | Design pattern for agent-based AAS | SMIA precursor |
| López, Casquero, Estévez, Leitão, Marcos | 2021, INDIN | Industrial agents | Four layers (two in AAS, two in asset) | Robot in assembly cell | Complementary to IEEE 2660.1 | Layering asset integration |
| Sidorenko, Volkmann, Motsch, Wagner, Ruskowski | 2021, Procedia Manuf. 55, 191-199 | I4.0 language over OPC UA | n/a | OPC UA skills (FSMs) | "Skill execution" semantic interaction protocol | Template for our execution protocol |
| Sakurada, Leitão, De la Prieta | 2022, IFAC-PapersOnLine 55(2) 193-198; 2022 ICIT; 2023 ISIE | MAS + service orientation + holonic | n/a | Industrial automation system | Collaborative AAS, methodology vs RAMI layers | AAS Type 3 line |
| Jungbluth et al., "Dynamic replanning using MAS and AAS" | 2022, ETFA | DFKI MAS (see Bernhard) | n/a | SmartFactory-KL assembly | Product AAS with production-plan submodel; replanning on breakdowns | Replanning model for our product agent |
| Komesker et al. | 2022, Procedia CIRP 107, 991-998 | MAS, holonic | n/a | Simulated automotive | Semi-heterarchical structure with AAS | Modular production MAS |
| Grunau, Redeker, Göllner, Wisniewski | 2022, KommA (Springer), 131-144 | Java app on BaSyx SDK; MQTT | App next to reactive AAS | HTTP/OPC UA to AAS | Proactive AAS executes 2193 bidding for order-driven production | 2193 over MQTT with BaSyx |
| Bernhard et al., "I4.0 holonic multi-agent testbed enabling shared production" | 2023, Springer (AI in Manufacturing), 231-250 | **SARL/Janus**; inter-holon over **Kafka**; **BaSyx 1.3**; Docker + GitLab CI | Containers | Resource holon uses **OPC UA production skills** on each CPPM | PROSA-based; **2193 bidding**; bid in [0,1] from RL using processing time, **changeover time**, deadlines, availability; max-bid selection | Closest architecture to ours (minus IEC 61499 reconfiguration) |
| Sidorenko et al., "MAS4AI framework" | 2023, Front. AI 6 | MAS | n/a | n/a | AAS submodels for workers; plug-and-produce of modules | Human-in-loop |
| López et al., I4.0 platform | 2023, Computers in Industry 146, 103859 | Industrial agents | n/a | n/a | Infrastructure services per RAMI 4.0 | GCIS platform |
| Siatras et al. | 2023, Applied Sciences 13, 9540 | SARL | n/a | n/a | AAS model of scheduling agents | Scheduling agents as AAS |
| Xia, Shenoy, Jazdi, Weyrich | 2023, ETFA | LLM agents | Server | Services of a modular production system, digital twin registry | LLM plans sequences of skills | Alternative to HTN for planning |
| Stolze, Belyaev, Kosel, Diedrich, Barnard | 2024, ETFA | Workflow engine + BPMN | n/a | n/a | Proactive AAS via BPMN and a new submodel; I4.0 language integration | OvGU line |
| Hurtado, Burgos, Armentia, Casquero (SMIA) | 2025, JII 47, 100915 | **SPADE**, FIPA-ACL, ejabberd | Containers | AID-configured HTTP/MQTT/OPC UA | CSS OWL; decentralized CNP election | Closest software |
| Sakurada, De la Prieta, Leitão | 2025, Future Internet 17(7) 270 | Review | | | Reference model for agent-based AAS Type 3 from literature patterns | **Best review to cite** |
| Sakurada, De la Prieta, Leitão | 2025, IEEE Access 13, 206617-206638 | MAS (platform **[unverified]**) | n/a | Lab prototype and automotive line (from thesis record) | Agent-based AAS Type 3 approach | Most recent from the Leitão group |
| Rübel et al. | 2025, LNME, 157-170 | SARL/Janus; I4.0 language | n/a | n/a | I4.0 language messages for fault diagnosis | 2193 beyond bidding |
| Hurtado, Sarachaga, Armentia, Casquero | 2026, Software Impacts 27, 100807 | SPADE | Docker | AID | Open-source "type 3 AAS" framework | SMIA software paper |
| Dietrich, Lechler, Verl | 2026, arXiv 2602.13029 | Python, MQTT, Docker Swarm | Containers | n/a | Scaling study of 2193 bidding: message load grows sharply, judged unscalable for hundreds of assets | Scalability caveat |
| Köhle, Anicic, Runkler, Graf | 2026, arXiv 2610.01364 (accepted ETFA 2026) | LLM agents, MCP tools, MQTT | Server | **OPC UA method calls** for module skills | Orchestrator vs peer-to-peer vs monolithic | Recent comparison of MAS architectures on skills |

Also relevant for product and resource agents: Kovalenko, Ryashentseva, Vogel-Heuser, Tilbury, Barton
(2019, RA-L) on product agents exploring a network of resource agents; Ocker, Kovalenko, Barton, Tilbury,
Vogel-Heuser (2019, RA-L) on initializing product and resource agents with a priori knowledge bases to cut
online communication; Kovalenko, Tilbury, Barton (2019, CEP) on a model-based product agent.

Named in the task but not found as agent work: "Inigo" (found AAS interoperability and
manufacturing-as-a-service papers, Inigo et al. 2020, 2022, without agents), "Ye/Hong" (AAS for robot
manufacturing and data exchange, 2021 IEEE Access, without agents), "Kalhoff" (nothing found)
**[unverified]**.

---

## 6. Negotiation and scheduling methods, and their fit

| Method | Key references | Idea | Fit for a small modular pharma line with a planar transport |
|---|---|---|---|
| Contract Net Protocol | Smith 1980; FIPA SC00029H (2002) | Manager announces task, contractors bid, manager awards | **Good.** Few resources, one task at a time, simple to verify and to log for traceability. Weakness: myopic (one step), no global optimum, needs deadlines and reservation to avoid double booking. |
| VDI/VDE 2193-2 bidding | VDI/VDE 2193-2 (2020); OvGU 2019; Grunau 2022; Bernhard 2023 | Contract net with I4.0 frame, binding proposals, replyBy | **Good**, and standard-conformant. Same semantics as CNP; use it as the CNP of record. |
| Decentralized CNP election (SMIA) | SMIA code | Bidders exchange values and elect a winner | Removes the requester's evaluation; less transparent; single criterion. Not recommended for us. |
| Auctions with learned bids | Bernhard et al. 2023 | Bid in [0,1] from RL considering times, changeover, deadlines | Interesting later; for a lab line a transparent cost function is preferable (explainability, GMP). |
| Product-driven control with exploration | Kovalenko et al. 2019 (RA-L, CEP) | Product agent explores resource network, then requests actions | **Fits** "product agent asks for one step at a time"; exploration can be replaced by capability lookup in the AAS registry. |
| A-priori knowledge bases | Ocker et al. 2019 (RA-L) | Precompute feasible sequences to cut runtime messages | Useful with our HTN planner: plan the step sequence once per order, negotiate allocation per step. |
| Holonic PROSA, delegate MAS (ants) | Van Brussel et al. 1998; Valckenaers & Van Brussel 2005 | Product, resource, order holons; exploration and intention "ants" forecast and reserve | Strong for forecasting and booking ahead; heavier to implement; worth it if lookahead over several steps becomes necessary. |
| ADACOR / ADACOR2 | Leitão & Restivo 2006; Barbosa et al. 2015 | Holonic, switches between stationary (hierarchical) and transient (heterarchical) states; self-organization | Conceptual fit (a supervisor optimizes, agents take over on disturbances); more than we need now. |
| Potential fields | Zbib et al. 2012; Pach et al. 2014 | Resources emit attraction fields; products move to strongest field | Reactive and good for routing products to free resources; weak guarantees; less natural with explicit bookings. |
| Multi-agent path finding on a planar drive | Janning et al. 2025 | Conflict-based search plus MPC for movers | Motion level; Planar Motor's own controller already plans paths, so only relevant if we plan trajectories ourselves. |
| Skill-based transport | Jungbluth et al. 2023 | OPC UA information model and skills for a transport system, mission distribution between transport units | **Directly relevant** for modelling the planar table's skills (move, reserve) and state machines. |

Recommended protocol for our line (from the above; this is our design reasoning, not taken from one
source):

1. The product agent holds the recipe (from the HTN plan or the product AAS production-plan submodel, as in
   Jungbluth et al. 2022) and asks for **one process step at a time**, optionally with one-step lookahead.
2. **Process CFP**: callForProposal to all resource agents whose capability description matches (filter by
   capability semantic id and property constraints before sending). replyBy of a few seconds.
3. **Proposal content**: earliest start and finish, setup time (zero if the skill exists; the measured time to
   plan and deploy a composite skill if not), current occupation and queue, and a confidence or cost. Refuse
   if the capability constraints cannot be met even with reconfiguration.
4. **Award with reservation**: acceptProposal books a time window; rejectProposal releases tentative holds. A
   resource agent keeps a simple calendar; an unconfirmed booking expires.
5. **Transport**: after the process award, the product agent sends a transport CFP to the planar-table agent
   (move shuttle with the product from its current station to the winner's station by the booked start).
   Alternative: the process provider includes its transport need in the proposal and the product agent books
   both atomically (accept both or neither). Start with the sequential variant.
6. **Reconfiguration**: between acceptance and start the resource agent plans and deploys the composite skill
   if needed, then executes via OPC UA, watching the skill state machine.
7. **Failure handling**: a failed skill or a missed window yields `failure` (2193) with a reason; the product
   agent cancels downstream bookings and re-issues the CFP for the step (replanning, as in Jungbluth et al.
   2022). A module agent whose OPC UA session drops goes "unavailable" (XMPP presence) and refuses CFPs.
8. **Traceability**: every conversation (CFP, proposals, award, result) is written to the product AAS
   production log (Bernhard et al. 2023 use a product AAS production log). For pharma batch records this
   is a strong argument for transparent CNP over opaque learned bids.

---

## 7. Gaps our work could fill

1. **From bid to new control logic.** No reviewed work lets a resource agent that wins (or bids on) a
   capability it has no skill for **plan a new composite skill from the AAS capability description (HTN) and
   deploy it online into a running IEC 61499 runtime**, then execute it. Lepuschitz et al. (2011) chose among
   predefined LLC configurations from an ontology, without AAS and without planning; SMIA, DFKI, Sakurada and
   OvGU agents call fixed skills and never change control code.
2. **Setup cost of reconfiguration in the negotiation.** Bids that price the time and risk of creating a skill
   online (versus using an existing one) are not reported; DFKI include changeover time in RL bids, but not
   software reconfiguration.
3. **End-to-end standard chain.** IDTA Capability Description + AID + AIMC + VDI/VDE 2193 + OPC UA skills
   (PackML-like) + IEC 61499 management + OPC UA LDS-ME discovery to agent spawning. Each piece exists
   separately; no paper connects them, and no VDI/VDE 2193 implementation over SPADE/XMPP was found.
4. **IEEE 2660.1 applied to IEC 61499 modules.** Explicitly classifying and justifying the agent-module
   interface (tightly coupled, hybrid, OPC UA; AAS path for structural changes) and measuring response times,
   for example skill start latency direct versus via the DMP, would be a small but citable contribution.
5. **Planar-motor transport as a bidding resource.** No literature found on agents negotiating with a
   maglev planar transport in product-driven production; shuttle booking and the coupling of process and
   transport awards is open.
6. **Pharma context.** Agent decisions recorded in the product AAS as part of the batch record, and
   reconfiguration limited to verified skill compositions (our checker), is not addressed in the
   agent/AAS literature, which is mostly discrete assembly.
7. **Comparison with SMIA.** A direct comparison (capability model IDTA 02020 vs OWL CSS; 2193 vs
   FIPA-SMIACL; method-based OPC UA skills vs variable read/write; reconfiguring vs non-reconfiguring) is a
   natural related-work section for the journal paper.

---

## 8. References

### 8.1 Primary software and documentation

- SMIA repository: <https://github.com/ekhurtado/SMIA> (GPL-3.0, checked 2026-10-30). Documentation:
  <https://smia.readthedocs.io/en/latest/> (1.0.3). PyPI: <https://pypi.org/project/smia/>. Docker Hub:
  `ekhurtado/smia`.
- SPADE repository: <https://github.com/javipalanca/spade> (MIT); docs <https://spadeagents.eu>; PyPI
  <https://pypi.org/project/spade/> (4.1.4, 5.0.0b1). PyJabber: <https://github.com/DinoThor/PyJabber> (MIT).
  spade_bdi: <https://pypi.org/project/spade-bdi/>.
- Eclipse BaSyx Java server SDK: <https://github.com/eclipse-basyx/basyx-java-server-sdk> (AAS repository
  MQTT feature; AAS registry Kafka events).
- OvGU/IFAT LIA, *Specification Testbed "AAS networked": Proactive AAS, interaction according to the VDI/VDE
  2193*, technical report, 2019. <https://www.lia.ovgu.de/lia_media/LIA_Medien/AASnetworked.pdf>
- SAP i40-aas (archived): <https://github.com/SAP/i40-aas>.
- FIPA Contract Net Interaction Protocol Specification, SC00029H, 2002,
  <http://www.fipa.org/specs/fipa00029/SC00029H.html> (URL from memory, not re-checked **[unverified]**).
  FIPA ACL Message Structure Specification, SC00061G, 2002 (cited in SPADE's `fipa_message.py`).
- Plattform Industrie 4.0, *Information Model for Capabilities, Skills & Services*, discussion paper,
  2022 (record at RWTH publications 861160; content not read).

### 8.2 BibTeX

```bibtex
% ---------------- SMIA and agent-based AAS ----------------
@article{hurtado2025smia,
  author  = {Hurtado, Ekaitz and Burgos, Arantzazu and Armentia, Aintzane and Casquero, Oskar},
  title   = {Self-configurable Manufacturing Industrial Agents ({SMIA}): a standardized approach for digitizing manufacturing assets},
  journal = {Journal of Industrial Information Integration},
  volume  = {47},
  pages   = {100915},
  year    = {2025},
  doi     = {10.1016/j.jii.2025.100915}
}
@article{hurtado2026type3,
  author  = {Hurtado, Ekaitz and Sarachaga, Isabel and Armentia, Aintzane and Casquero, Oskar},
  title   = {An open-source reference framework for the implementation of type 3 Asset Administration Shells},
  journal = {Software Impacts},
  volume  = {27},
  pages   = {100807},
  year    = {2026},
  doi     = {10.1016/j.simpa.2025.100807}
}
@misc{smia2026repo,
  author       = {Hurtado, Ekaitz and {GCIS, University of the Basque Country}},
  title        = {{SMIA}: Self-configurable Manufacturing Industrial Agents, version 1.0.3},
  year         = {2026},
  howpublished = {\url{https://github.com/ekhurtado/SMIA}},
  note         = {Accessed 2026-10-30}
}
@inproceedings{lopez2021patterns,
  author    = {L{\'o}pez, Alejandro and Casquero, Oskar and Marcos, Marga},
  title     = {Design patterns for the implementation of Industrial Agent-based {AASs}},
  booktitle = {2021 4th IEEE International Conference on Industrial Cyber-Physical Systems (ICPS)},
  pages     = {213--218},
  year      = {2021},
  doi       = {10.1109/ICPS49255.2021.9468129}
}
@inproceedings{lopez2021fourlayered,
  author    = {L{\'o}pez, Alejandro and Casquero, Oskar and Est{\'e}vez, Elisabet and Leit{\~a}o, Paulo and Marcos, Marga},
  title     = {Towards the generic integration of agent-based {AASs} and Physical Assets: a four-layered architecture approach},
  booktitle = {2021 IEEE 19th International Conference on Industrial Informatics (INDIN)},
  pages     = {1--6},
  year      = {2021},
  doi       = {10.1109/INDIN45523.2021.9557568}
}
@article{lopez2023platform,
  author  = {L{\'o}pez, Alejandro and Casquero, Oskar and Est{\'e}vez, Elisabet and Armentia, Aintzane and Orive, Dar{\'i}o and Marcos, Marga},
  title   = {An industrial agent-based customizable platform for {I4.0} manufacturing systems},
  journal = {Computers in Industry},
  volume  = {146},
  pages   = {103859},
  year    = {2023},
  doi     = {10.1016/j.compind.2023.103859}
}
@inproceedings{sakurada2020multi,
  author    = {Sakurada, Lucas and Leit{\~a}o, Paulo},
  title     = {Multi-Agent Systems to Implement Industry 4.0 Components},
  booktitle = {2020 IEEE Conference on Industrial Cyberphysical Systems (ICPS)},
  pages     = {21--26},
  year      = {2020},
  doi       = {10.1109/ICPS48405.2020.9274745}
}
@article{sakurada2022agent,
  author  = {Sakurada, Lucas and Leit{\~a}o, Paulo and De la Prieta, Fernando},
  title   = {Agent-Based Asset Administration Shell Approach for Digitizing Industrial Assets},
  journal = {IFAC-PapersOnLine},
  volume  = {55},
  number  = {2},
  pages   = {193--198},
  year    = {2022},
  doi     = {10.1016/j.ifacol.2022.04.192}
}
@inproceedings{sakurada2022engineering,
  author    = {Sakurada, Lucas and Leit{\~a}o, Paulo and De la Prieta, Fernando},
  title     = {Engineering a Multi-agent Systems Approach for Realizing Collaborative Asset Administration Shells},
  booktitle = {2022 IEEE International Conference on Industrial Technology (ICIT)},
  pages     = {1--6},
  year      = {2022},
  doi       = {10.1109/ICIT48603.2022.10002770}
}
@inproceedings{sakurada2023methodology,
  author    = {Sakurada, Lucas and De la Prieta, Fernando and Leit{\~a}o, Paulo},
  title     = {A Methodology for Integrating Asset Administration Shells and Multi-agent Systems},
  booktitle = {2023 IEEE 32nd International Symposium on Industrial Electronics (ISIE)},
  pages     = {1--6},
  year      = {2023},
  doi       = {10.1109/ISIE51358.2023.10227964}
}
@article{sakurada2025role,
  author  = {Sakurada, Lucas and De la Prieta, Fernando and Leit{\~a}o, Paulo},
  title   = {The Role of Multi-Agent Systems in Realizing Asset Administration Shell Type 3},
  journal = {Future Internet},
  volume  = {17},
  number  = {7},
  pages   = {270},
  year    = {2025},
  doi     = {10.3390/fi17070270}
}
@article{sakurada2025type3,
  author  = {Sakurada, Lucas and De la Prieta, Fernando and Leit{\~a}o, Paulo},
  title   = {An Agent-Based Approach for Implementing Asset Administration Shell Type 3},
  journal = {IEEE Access},
  volume  = {13},
  pages   = {206617--206638},
  year    = {2025},
  doi     = {10.1109/ACCESS.2025.3640265}
}
@article{ocker2021leveraging,
  author  = {Ocker, Felix and Urban, Christian and Vogel-Heuser, Birgit and Diedrich, Christian},
  title   = {Leveraging the Asset Administration Shell for Agent-Based Production Systems},
  journal = {IFAC-PapersOnLine},
  volume  = {54},
  number  = {1},
  pages   = {837--844},
  year    = {2021},
  doi     = {10.1016/j.ifacol.2021.08.186}
}
@article{vogelheuser2021leveraging,
  author  = {Vogel-Heuser, Birgit and Ocker, Felix and Scheuer, Tobias},
  title   = {An approach for leveraging Digital Twins in agent-based production systems},
  journal = {at - Automatisierungstechnik},
  volume  = {69},
  number  = {12},
  pages   = {1026--1039},
  year    = {2021},
  doi     = {10.1515/auto-2021-0081}
}
@article{vogelheuser2020multi,
  author  = {Vogel-Heuser, Birgit and Seitz, Matthias and Cruz Salazar, Luis Alberto and Gehlhoff, Felix and Dogan, Alaettin and Fay, Alexander},
  title   = {Multi-agent systems to enable Industry 4.0},
  journal = {at - Automatisierungstechnik},
  volume  = {68},
  number  = {6},
  pages   = {445--458},
  year    = {2020},
  doi     = {10.1515/auto-2020-0004}
}
@inproceedings{jungbluth2022dynamic,
  author    = {Jungbluth, Simon and Hermann, Jesko and Motsch, William and Pourjafarian, Monireh and Sidorenko, Aleksandr and Volkmann, Magnus and Zoltner, Kuno and Plociennik, Christiane and Ruskowski, Martin},
  title     = {Dynamic Replanning using Multi-Agent Systems and Asset Administration Shells},
  booktitle = {2022 IEEE 27th International Conference on Emerging Technologies and Factory Automation (ETFA)},
  pages     = {1--8},
  year      = {2022},
  doi       = {10.1109/ETFA52439.2022.9921716}
}
@article{komesker2022enabling,
  author  = {Komesker, Simon and Motsch, William and Popper, Jens and Sidorenko, Aleksandr and Wagner, Achim and Ruskowski, Martin},
  title   = {Enabling a Multi-Agent System for Resilient Production Flow in Modular Production Systems},
  journal = {Procedia CIRP},
  volume  = {107},
  pages   = {991--998},
  year    = {2022},
  doi     = {10.1016/j.procir.2022.05.097}
}
@article{sidorenko2021opcua,
  author  = {Sidorenko, Aleksandr and Volkmann, Magnus and Motsch, William and Wagner, Achim and Ruskowski, Martin},
  title   = {An {OPC UA} Model of the Skill Execution Interaction Protocol for the Active Asset Administration Shell},
  journal = {Procedia Manufacturing},
  volume  = {55},
  pages   = {191--199},
  year    = {2021},
  doi     = {10.1016/j.promfg.2021.10.027}
}
@article{sidorenko2023mas4ai,
  author  = {Sidorenko, Aleksandr and Motsch, William and van Bekkum, Michael and Nikolakis, Nikolaos and Alexopoulos, Kosmas and Wagner, Achim},
  title   = {The {MAS4AI} framework for human-centered agile and smart manufacturing},
  journal = {Frontiers in Artificial Intelligence},
  volume  = {6},
  year    = {2023},
  doi     = {10.3389/frai.2023.1241522}
}
@incollection{bernhard2023holonic,
  author    = {Bernhard, Alexis T. and Jungbluth, Simon and Karnoub, Ali and Sidorenko, Aleksandr and Motsch, William and Wagner, Achim and Ruskowski, Martin},
  title     = {{I4.0} Holonic Multi-agent Testbed Enabling Shared Production},
  booktitle = {Artificial Intelligence in Manufacturing},
  publisher = {Springer},
  pages     = {231--250},
  year      = {2023},
  doi       = {10.1007/978-3-031-46452-2_13}
}
@incollection{ruebel2025fault,
  author    = {R{\"u}bel, Pascal and Motsch, William and Bernhard, Alexis and Jungbluth, Simon and Ruskowski, Martin},
  title     = {Agent-Based Communication for Fault Diagnosis in Skill-Based Production Environments Using Messages Based on {I4.0} Language and Asset Administration Shells},
  booktitle = {Lecture Notes in Mechanical Engineering},
  publisher = {Springer},
  pages     = {157--170},
  year      = {2025},
  doi       = {10.1007/978-3-031-86489-6_17}
}
@article{jungbluth2023transport,
  author  = {Jungbluth, Simon and Barth, Tobias and Nu{\ss}baum, Jonas and Hermann, Jesko and Ruskowski, Martin},
  title   = {Developing a skill-based flexible transport system using {OPC UA}},
  journal = {at - Automatisierungstechnik},
  volume  = {71},
  number  = {2},
  pages   = {163--175},
  year    = {2023},
  doi     = {10.1515/auto-2022-0115}
}
@article{siatras2023aas,
  author  = {Siatras, Vasilis and Bakopoulos, Emmanouil and Mavrothalassitis, Panagiotis and Nikolakis, Nikolaos and Alexopoulos, Kosmas},
  title   = {On the Use of Asset Administration Shell for Modeling and Deploying Production Scheduling Agents within a Multi-Agent System},
  journal = {Applied Sciences},
  volume  = {13},
  pages   = {9540},
  year    = {2023},
  doi     = {10.3390/app13179540}
}
@inproceedings{xia2023llm,
  author    = {Xia, Yuchen and Shenoy, Manthan and Jazdi, Nasser and Weyrich, Michael},
  title     = {Towards autonomous system: flexible modular production system enhanced with large language model agents},
  booktitle = {2023 IEEE 28th International Conference on Emerging Technologies and Factory Automation (ETFA)},
  pages     = {1--8},
  year      = {2023},
  doi       = {10.1109/ETFA54631.2023.10275362}
}
@inproceedings{stolze2024proactive,
  author    = {Stolze, Melanie and Belyaev, Alexander and Kosel, Christian and Diedrich, Christian and Barnard, Alfred},
  title     = {Realizing Automated Production Planning via Proactive {AAS} and Business Process Models},
  booktitle = {2024 IEEE 29th International Conference on Emerging Technologies and Factory Automation (ETFA)},
  pages     = {1--8},
  year      = {2024},
  doi       = {10.1109/ETFA61755.2024.10710731}
}
@incollection{grunau2022proactive,
  author    = {Grunau, Sergej and Redeker, Magnus and G{\"o}llner, Dennis and Wisniewski, Lukasz},
  title     = {The Implementation of Proactive Asset Administration Shells: Evaluation of Possibilities and Realization in an Order Driven Production},
  booktitle = {Kommunikation und Bildverarbeitung in der Automation},
  editor    = {Jasperneite, J{\"u}rgen and Lohweg, Volker},
  series    = {Technologien f{\"u}r die intelligente Automation},
  volume    = {14},
  publisher = {Springer Vieweg},
  pages     = {131--144},
  year      = {2022},
  doi       = {10.1007/978-3-662-64283-2_10}
}
@article{schroeder2019proactive,
  author  = {Schr{\"o}der, Tizian and Diedrich, Christian},
  title   = {Systemarchitektur f{\"u}r die Implementierung proaktiver Verwaltungsschalen auf Basis kognitionswissenschaftlicher Konzepte},
  journal = {at - Automatisierungstechnik},
  volume  = {67},
  number  = {7},
  pages   = {599--616},
  year    = {2019},
  doi     = {10.1515/auto-2019-0030}
}
@techreport{ovgu2019aasnetworked,
  author      = {{Otto-von-Guericke-Universit{\"a}t Magdeburg, Institut f{\"u}r Automatisierungstechnik (IFAT/LIA)}},
  title       = {Specification Testbed ``{AAS} networked'': Proactive {AAS} -- interaction according to the {VDI/VDE} 2193},
  institution = {OvGU Magdeburg},
  year        = {2019},
  url         = {https://www.lia.ovgu.de/lia_media/LIA_Medien/AASnetworked.pdf}
}
@misc{dietrich2026negotiation,
  author        = {Dietrich, David and Lechler, Armin and Verl, Alexander},
  title         = {Analysis of Asset Administration Shell-based Negotiation Processes for Scaling Applications},
  year          = {2026},
  eprint        = {2602.13029},
  archivePrefix = {arXiv},
  primaryClass  = {cs.SE}
}
@misc{koehle2026llm,
  author        = {K{\"o}hle, Kay and Anicic, Darko and Runkler, Thomas A. and Graf, Ren{\'e}},
  title         = {{LLM}-Driven Multi-Agent Control for Skill-Based Smart Manufacturing},
  year          = {2026},
  eprint        = {2610.01364},
  archivePrefix = {arXiv},
  note          = {Accepted at IEEE ETFA 2026 (per arXiv page)}
}
@misc{ellwein2025container,
  author        = {Ellwein, Carsten and Zhang, Jingxi and Wortmann, Andreas and Meckhael, Antony Ayman Alfy},
  title         = {A Container-based Approach For Proactive Asset Administration Shell Digital Twins},
  year          = {2025},
  eprint        = {2512.15452},
  archivePrefix = {arXiv}
}

% ---------------- Standards ----------------
@standard{ieee2021p26601,
  title        = {{IEEE} Recommended Practice for Industrial Agents: Integration of Software Agents and Low-Level Automation Functions},
  organization = {IEEE},
  number       = {IEEE Std 2660.1-2020},
  year         = {2021},
  doi          = {10.1109/IEEESTD.2021.9340089}
}
@standard{vdi2020language1,
  title        = {{VDI/VDE} 2193 Blatt 1: Sprache f{\"u}r {I4.0}-Komponenten -- Struktur von Nachrichten (Language for {I4.0} components -- Structure of messages)},
  organization = {VDI/VDE-Gesellschaft Mess- und Automatisierungstechnik},
  year         = {2020},
  month        = apr
}
@standard{vdi2020language2,
  title        = {{VDI/VDE} 2193 Blatt 2: Sprache f{\"u}r {I4.0}-Komponenten -- Interaktionsprotokoll f{\"u}r Ausschreibungsverfahren (Language for {I4.0} components -- Interaction protocol for bidding procedures)},
  organization = {VDI/VDE-Gesellschaft Mess- und Automatisierungstechnik},
  year         = {2020},
  month        = jan
}

% ---------------- IEEE 2660.1 working group ----------------
@inproceedings{leitao2017common,
  author    = {Leit{\~a}o, Paulo and Karnouskos, Stamatis and Ribeiro, Luis and Moutis, Panayiotis and Barbosa, Jos{\'e} and Strasser, Thomas I.},
  title     = {Common practices for integrating industrial agents and low level automation functions},
  booktitle = {IECON 2017 - 43rd Annual Conference of the IEEE Industrial Electronics Society},
  pages     = {6665--6670},
  year      = {2017},
  doi       = {10.1109/IECON.2017.8217164}
}
@inproceedings{leitao2018integration,
  author    = {Leit{\~a}o, Paulo and Karnouskos, Stamatis and Ribeiro, Luis and Moutis, Panayiotis and Barbosa, Jos{\'e} and Strasser, Thomas I.},
  title     = {Integration Patterns for Interfacing Software Agents with Industrial Automation Systems},
  booktitle = {IECON 2018 - 44th Annual Conference of the IEEE Industrial Electronics Society},
  pages     = {2908--2913},
  year      = {2018},
  doi       = {10.1109/IECON.2018.8591641}
}
@inproceedings{karnouskos2018assessing,
  author    = {Karnouskos, Stamatis and Sinha, Roopak and Leit{\~a}o, Paulo and Ribeiro, Luis and Strasser, Thomas I.},
  title     = {Assessing the Integration of Software Agents and Industrial Automation Systems with {ISO/IEC} 25010},
  booktitle = {2018 IEEE 16th International Conference on Industrial Informatics (INDIN)},
  pages     = {61--66},
  year      = {2018},
  doi       = {10.1109/INDIN.2018.8471951}
}
@inproceedings{leitao2021recommendation,
  author    = {Leit{\~a}o, Paulo and Strasser, Thomas I. and Karnouskos, Stamatis and Ribeiro, Luis and Barbosa, Jos{\'e} and Huang, Victor},
  title     = {Recommendation of Best Practices for Industrial Agent Systems based on the {IEEE} 2660.1 Standard},
  booktitle = {2021 22nd IEEE International Conference on Industrial Technology (ICIT)},
  pages     = {1157--1162},
  year      = {2021},
  doi       = {10.1109/ICIT46573.2021.9453511}
}
@article{leitao2023alignment,
  author  = {Leit{\~a}o, Paulo and Karnouskos, Stamatis and Strasser, Thomas I. and Jia, Xiaodong and Lee, Jay and Colombo, Armando Walter},
  title   = {Alignment of the {IEEE} Industrial Agents Recommended Practice Standard With the Reference Architectures {RAMI4.0}, {IIRA}, and {SGAM}},
  journal = {IEEE Open Journal of the Industrial Electronics Society},
  volume  = {4},
  pages   = {98--111},
  year    = {2023},
  doi     = {10.1109/OJIES.2023.3262549}
}
@article{leitao2016smart,
  author  = {Leit{\~a}o, Paulo and Karnouskos, Stamatis and Ribeiro, Luis and Lee, Jay and Strasser, Thomas and Colombo, Armando W.},
  title   = {Smart Agents in Industrial Cyber-Physical Systems},
  journal = {Proceedings of the IEEE},
  volume  = {104},
  number  = {5},
  pages   = {1086--1101},
  year    = {2016},
  doi     = {10.1109/JPROC.2016.2521931}
}
@article{karnouskos2020industrial,
  author  = {Karnouskos, Stamatis and Leit{\~a}o, Paulo and Ribeiro, Luis and Colombo, Armando Walter},
  title   = {Industrial Agents as a Key Enabler for Realizing Industrial Cyber-Physical Systems: Multiagent Systems Entering Industry 4.0},
  journal = {IEEE Industrial Electronics Magazine},
  volume  = {14},
  number  = {3},
  pages   = {18--32},
  year    = {2020},
  doi     = {10.1109/MIE.2019.2962225}
}
@article{leitao2013past,
  author  = {Leit{\~a}o, Paulo and Mar{\'i}k, Vladim{\'i}r and Vrba, Pavel},
  title   = {Past, Present, and Future of Industrial Agent Applications},
  journal = {IEEE Transactions on Industrial Informatics},
  volume  = {9},
  number  = {4},
  pages   = {2360--2372},
  year    = {2013},
  doi     = {10.1109/TII.2012.2222034}
}

% ---------------- Agents and IEC 61499 ----------------
@incollection{christensen2003hmsfb,
  author    = {Christensen, James H.},
  title     = {{HMS/FB} Architecture and its Implementation},
  booktitle = {Agent-Based Manufacturing},
  publisher = {Springer},
  pages     = {53--87},
  year      = {2003},
  doi       = {10.1007/978-3-662-05624-0_4}
}
@inproceedings{hegny2008integrating,
  author    = {Hegny, Ingo and Hummer, Oliver and Zoitl, Alois and Koppensteiner, Gottfried and Merdan, Munir},
  title     = {Integrating software agents and {IEC} 61499 realtime control for reconfigurable distributed manufacturing systems},
  booktitle = {2008 International Symposium on Industrial Embedded Systems (SIES)},
  pages     = {249--252},
  year      = {2008},
  doi       = {10.1109/SIES.2008.4577710}
}
@article{black2010intelligent,
  author  = {Black, Geoff and Vyatkin, Valeriy},
  title   = {Intelligent Component-Based Automation of Baggage Handling Systems With {IEC} 61499},
  journal = {IEEE Transactions on Automation Science and Engineering},
  volume  = {7},
  number  = {2},
  pages   = {337--351},
  year    = {2010},
  doi     = {10.1109/TASE.2008.2007216}
}
@inproceedings{merdan2009application,
  author    = {Merdan, Munir and Lepuschitz, Wilfried and Hegny, Ingo and Koppensteiner, Gottfried},
  title     = {Application of a communication interface between agents and the low level control},
  booktitle = {2009 4th International Conference on Autonomous Robots and Agents (ICARA)},
  pages     = {628--633},
  year      = {2009},
  doi       = {10.1109/ICARA.2000.4804006}
}
@inproceedings{lepuschitz2009integration,
  author    = {Lepuschitz, Wilfried and Vall{\'e}e, Mathieu and Merdan, Munir and Vrba, Pavel and Resch, Johannes},
  title     = {Integration of a heterogeneous Low Level Control in a multi-agent system for the manufacturing domain},
  booktitle = {2009 IEEE Conference on Emerging Technologies \& Factory Automation (ETFA)},
  pages     = {1--8},
  year      = {2009},
  doi       = {10.1109/ETFA.2009.5347061}
}
@inproceedings{zoitl2010realtime,
  author    = {Zoitl, Alois and Lepuschitz, Wilfried and Merdan, Munir and Vall{\'e}e, Mathieu},
  title     = {A real-time reconfiguration infrastructure for distributed embedded control systems},
  booktitle = {2010 IEEE 15th Conference on Emerging Technologies \& Factory Automation (ETFA)},
  pages     = {1--8},
  year      = {2010},
  doi       = {10.1109/ETFA.2010.5641259}
}
@inproceedings{lepuschitz2010online,
  author    = {Lepuschitz, Wilfried and Vall{\'e}e, Mathieu and Zoitl, Alois and Merdan, Munir},
  title     = {Online reconfiguration of the low level control for automation agents},
  booktitle = {IECON 2010 - 36th Annual Conference on IEEE Industrial Electronics Society},
  pages     = {1365--1370},
  year      = {2010},
  doi       = {10.1109/IECON.2010.5675483}
}
@article{lepuschitz2011toward,
  author  = {Lepuschitz, Wilfried and Zoitl, Alois and Vall{\'e}e, Mathieu and Merdan, Munir},
  title   = {Toward Self-Reconfiguration of Manufacturing Systems Using Automation Agents},
  journal = {IEEE Transactions on Systems, Man, and Cybernetics, Part C (Applications and Reviews)},
  volume  = {41},
  number  = {1},
  pages   = {52--69},
  year    = {2011},
  doi     = {10.1109/TSMCC.2010.2059012}
}
@article{vallee2011decentralized,
  author  = {Vall{\'e}e, Mathieu and Merdan, Munir and Lepuschitz, Wilfried and Koppensteiner, Gottfried},
  title   = {Decentralized Reconfiguration of a Flexible Transportation System},
  journal = {IEEE Transactions on Industrial Informatics},
  volume  = {7},
  number  = {3},
  pages   = {505--516},
  year    = {2011},
  doi     = {10.1109/TII.2011.2158839}
}
@inproceedings{strasser2007enhanced,
  author    = {Strasser, Thomas and Sunder, Christoph and Zoitl, Alois and Rooker, Martijn and Brunnenkreef, Jan},
  title     = {Enhanced {IEC} 61499 Device Management Execution and Usage for Downtimeless Reconfiguration},
  booktitle = {2007 5th IEEE International Conference on Industrial Informatics (INDIN)},
  pages     = {1163--1168},
  year      = {2007},
  doi       = {10.1109/INDIN.2007.4384940}
}
@inproceedings{strasser2008fourdiac,
  author    = {Strasser, Thomas and Rooker, Martijn and Ebenhofer, Gerhard and Zoitl, Alois and Sunder, Christoph and Valentini, Antonio and Martel, Allan},
  title     = {Framework for Distributed Industrial Automation and Control ({4DIAC})},
  booktitle = {2008 6th IEEE International Conference on Industrial Informatics (INDIN)},
  pages     = {283--288},
  year      = {2008},
  doi       = {10.1109/INDIN.2008.4618110}
}
@article{kruger2013multi,
  author  = {Kruger, Karel and Basson, Anton},
  title   = {Multi-agent Systems vs {IEC} 61499 for Holonic Resource Control in Reconfigurable Systems},
  journal = {Procedia CIRP},
  volume  = {7},
  pages   = {503--508},
  year    = {2013},
  doi     = {10.1016/j.procir.2013.06.023}
}
@inproceedings{dorofeev2018skill,
  author    = {Dorofeev, Kirill and Zoitl, Alois},
  title     = {Skill-based Engineering Approach using {OPC UA} Programs},
  booktitle = {2018 IEEE 16th International Conference on Industrial Informatics (INDIN)},
  pages     = {1098--1103},
  year      = {2018},
  doi       = {10.1109/INDIN.2018.8471978}
}
@inproceedings{profanter2017opcua,
  author    = {Profanter, Stefan and Dorofeev, Kirill and Zoitl, Alois and Knoll, Alois},
  title     = {{OPC UA} for plug \& produce: Automatic device discovery using {LDS-ME}},
  booktitle = {2017 22nd IEEE International Conference on Emerging Technologies and Factory Automation (ETFA)},
  pages     = {1--8},
  year      = {2017},
  doi       = {10.1109/ETFA.2017.8247569}
}
@article{lyu2020multi,
  author  = {Lyu, Guolin and Fazlirad, Alireza and Brennan, Robert W.},
  title   = {Multi-Agent Modeling of Cyber-Physical Systems for {IEC} 61499 Based Distributed Automation},
  journal = {Procedia Manufacturing},
  volume  = {51},
  pages   = {1200--1206},
  year    = {2020},
  doi     = {10.1016/j.promfg.2020.10.168}
}
@article{lyu2025multi,
  author  = {Lyu, Guolin and Brennan, Robert W.},
  title   = {Multi-agent modelling of cyber-physical systems for {IEC} 61499-based distributed intelligent automation},
  journal = {International Journal of Computer Integrated Manufacturing},
  volume  = {38},
  number  = {5},
  pages   = {596--622},
  year    = {2025},
  doi     = {10.1080/0951192X.2023.2294442},
  note    = {Published online 2023}
}
@inproceedings{lv2021integrated,
  author    = {Lv, B. and Zhang, Y. and Dai, Wenbin},
  title     = {Integrated Asset Management Model based on {IEC} 61499 and Administration Shell},
  booktitle = {IECON 2021 - 47th Annual Conference of the IEEE Industrial Electronics Society},
  pages     = {1--6},
  year      = {2021},
  doi       = {10.1109/IECON48115.2021.9589597}
}
@article{cruzsalazar2025adaptive,
  author  = {Cruz Salazar, Luis Alberto and Tovar, H. and Prada Salamanca, E. and M{\'a}rquez Ju{\'a}rez, J. and Cruz, E.},
  title   = {Adaptive Learning and Interoperability in {I4.0}: A Case Study of Agent-based Digital Twin with Asset Administration Shell},
  journal = {IFAC-PapersOnLine},
  volume  = {59},
  number  = {14},
  pages   = {202--207},
  year    = {2025},
  doi     = {10.1016/j.ifacol.2025.12.150}
}

% ---------------- Capabilities and skills ----------------
@article{koecher2023reference,
  author  = {K{\"o}cher, Aljosha and Belyaev, Alexander and Hermann, Jesko and Bock, J{\"u}rgen and Meixner, Kristof and Volkmann, Magnus and Winter, Michael and Zimmermann, Patrick and Grimm, Stephan and Diedrich, Christian},
  title   = {A reference model for common understanding of capabilities and skills in manufacturing},
  journal = {at - Automatisierungstechnik},
  volume  = {71},
  number  = {2},
  pages   = {94--104},
  year    = {2023},
  doi     = {10.1515/auto-2022-0117}
}
@inproceedings{koecher2020formal,
  author    = {K{\"o}cher, Aljosha and Hildebrandt, Constantin and Vieira da Silva, Luis Miguel and Fay, Alexander},
  title     = {A Formal Capability and Skill Model for Use in Plug and Produce Scenarios},
  booktitle = {2020 25th IEEE International Conference on Emerging Technologies and Factory Automation (ETFA)},
  pages     = {1663--1670},
  year      = {2020},
  doi       = {10.1109/ETFA46521.2020.9211874}
}

% ---------------- SPADE ----------------
@article{palanca2020spade,
  author  = {Palanca, Javier and Terrasa, Andr{\'e}s and Julian, Vicente and Carrascosa, Carlos},
  title   = {{SPADE} 3: Supporting the New Generation of Multi-Agent Systems},
  journal = {IEEE Access},
  volume  = {8},
  pages   = {182537--182549},
  year    = {2020},
  doi     = {10.1109/ACCESS.2020.3027357}
}
@misc{spade2026repo,
  author       = {Palanca, Javier and contributors},
  title        = {{SPADE}: Smart Python Agent Development Environment, version 4.1.4},
  year         = {2026},
  howpublished = {\url{https://github.com/javipalanca/spade}},
  note         = {Accessed 2026-10-30}
}

% ---------------- Negotiation, holonic control, product agents ----------------
@article{smith1980contract,
  author  = {Smith, Reid G.},
  title   = {The Contract Net Protocol: High-Level Communication and Control in a Distributed Problem Solver},
  journal = {IEEE Transactions on Computers},
  volume  = {C-29},
  number  = {12},
  pages   = {1104--1113},
  year    = {1980},
  doi     = {10.1109/TC.1980.1675516}
}
@article{vanbrussel1998prosa,
  author  = {Van Brussel, Hendrik and Wyns, Jo and Valckenaers, Paul and Bongaerts, Luc and Peeters, Patrick},
  title   = {Reference architecture for holonic manufacturing systems: {PROSA}},
  journal = {Computers in Industry},
  volume  = {37},
  number  = {3},
  pages   = {255--274},
  year    = {1998},
  doi     = {10.1016/S0166-3615(98)00102-X}
}
@article{valckenaers2005holonic,
  author  = {Valckenaers, Paul and Van Brussel, Hendrik},
  title   = {Holonic Manufacturing Execution Systems},
  journal = {CIRP Annals},
  volume  = {54},
  number  = {1},
  pages   = {427--432},
  year    = {2005},
  doi     = {10.1016/S0007-8506(07)60137-1}
}
@article{leitao2006adacor,
  author  = {Leit{\~a}o, Paulo and Restivo, Francisco},
  title   = {{ADACOR}: A holonic architecture for agile and adaptive manufacturing control},
  journal = {Computers in Industry},
  volume  = {57},
  number  = {2},
  pages   = {121--130},
  year    = {2006},
  doi     = {10.1016/j.compind.2005.05.005}
}
@article{barbosa2015adacor2,
  author  = {Barbosa, Jos{\'e} and Leit{\~a}o, Paulo and Adam, Emmanuel and Trentesaux, Damien},
  title   = {Dynamic self-organization in holonic multi-agent manufacturing systems: The {ADACOR} evolution},
  journal = {Computers in Industry},
  volume  = {66},
  pages   = {99--111},
  year    = {2015},
  doi     = {10.1016/j.compind.2014.10.011}
}
@article{zbib2012potential,
  author  = {Zbib, N. and Pach, C. and Sallez, Y. and Trentesaux, D.},
  title   = {Heterarchical production control in manufacturing systems using the potential fields concept},
  journal = {Journal of Intelligent Manufacturing},
  volume  = {23},
  number  = {5},
  pages   = {1649--1670},
  year    = {2012},
  doi     = {10.1007/s10845-010-0467-3}
}
@article{pach2014reactive,
  author  = {Pach, C. and Berger, T. and Sallez, Y. and Bonte, T. and Adam, E. and Trentesaux, D.},
  title   = {Reactive and energy-aware scheduling of flexible manufacturing systems using potential fields},
  journal = {Computers in Industry},
  volume  = {65},
  number  = {3},
  pages   = {434--448},
  year    = {2014},
  doi     = {10.1016/j.compind.2013.11.008}
}
@article{kovalenko2019dynamic,
  author  = {Kovalenko, Ilya and Ryashentseva, Daria and Vogel-Heuser, Birgit and Tilbury, Dawn and Barton, Kira},
  title   = {Dynamic Resource Task Negotiation to Enable Product Agent Exploration in Multi-Agent Manufacturing Systems},
  journal = {IEEE Robotics and Automation Letters},
  volume  = {4},
  number  = {3},
  pages   = {2854--2861},
  year    = {2019},
  doi     = {10.1109/LRA.2019.2921947}
}
@article{kovalenko2019model,
  author  = {Kovalenko, Ilya and Tilbury, Dawn and Barton, Kira},
  title   = {The model-based product agent: A control oriented architecture for intelligent products in multi-agent manufacturing systems},
  journal = {Control Engineering Practice},
  volume  = {86},
  pages   = {105--117},
  year    = {2019},
  doi     = {10.1016/j.conengprac.2019.03.009}
}
@article{ocker2019framework,
  author  = {Ocker, Felix and Kovalenko, Ilya and Barton, Kira and Tilbury, Dawn and Vogel-Heuser, Birgit},
  title   = {A Framework for Automatic Initialization of Multi-Agent Production Systems Using Semantic Web Technologies},
  journal = {IEEE Robotics and Automation Letters},
  volume  = {4},
  number  = {4},
  pages   = {4330--4337},
  year    = {2019},
  doi     = {10.1109/LRA.2019.2931825}
}
@article{janning2025conflict,
  author  = {Janning, K. and Housin, A. and Schulte, C. and Erkens, F. and Frenken, L. and Herbst, L.},
  title   = {Conflict-based model predictive control for multi-agent path finding experimentally validated on a magnetic planar drive system},
  journal = {Frontiers in Control Engineering},
  volume  = {6},
  year    = {2025},
  doi     = {10.3389/fcteg.2025.1645918}
}
@article{antzoulatos2014plug,
  author  = {Antzoulatos, Nikolas and Castro, Elkin and Scrimieri, Daniele and Ratchev, Svetan},
  title   = {A multi-agent architecture for plug and produce on an industrial assembly platform},
  journal = {Production Engineering},
  volume  = {8},
  number  = {6},
  pages   = {773--781},
  year    = {2014},
  doi     = {10.1007/s11740-014-0571-x}
}
@inproceedings{rocha2014agent,
  author    = {Rocha, Andr{\'e} and Di Orio, Giovanni and Barata, Jos{\'e} and Antzoulatos, Nikolas and Castro, Elkin and Scrimieri, Daniele},
  title     = {An agent based framework to support plug and produce},
  booktitle = {2014 12th IEEE International Conference on Industrial Informatics (INDIN)},
  pages     = {504--510},
  year      = {2014},
  doi       = {10.1109/INDIN.2014.6945565}
}
```

Notes on the reference list:
- `lyu2025multi`: Crossref gives issue year 2025 (vol 38, iss 5), online 2023-12-21.
- `zbib2012potential`: online 2010, issue 2012 (vol 23, iss 5).
- `black2010intelligent`: online 2009 (OpenAlex year 2009), issue 2010.
- PRIME (plug-and-produce MAS, EU FP7) is represented by Antzoulatos et al. 2014 and Rocha et al. 2014; the
  project itself was not looked up further.
- Christensen 2003 and Hegny 2008 were checked at metadata level only.
- Not cited because not found: "Kalachev/Taylor", "Kalhoff", agent work by "Inigo" or "Ye/Hong".
