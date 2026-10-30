# Design log

A running log of design considerations made while building, for writing the papers afterwards.

**What each entry holds:**
- what was chosen;
- why;
- what it was chosen instead of;
- which paper it serves: *CIRP* ([paper-outline.md](paper-outline.md)), *Journal*
  ([journal-paper.md](journal-paper.md)), or both.

**Rules:**
- Newest entries first, dated.
- Add an entry whenever code or a design changes for a reason a reader of the paper would want to
  know.
- What was decided, without the reasons, still goes into [decisions.md](decisions.md). The method's
  settled decisions are in [design-decisions.md](design-decisions.md).

## 30 Oct 2026

- **The BPMN editors draw freely, and a validator reads the drawing back into the block-structured
  flow.** *Journal*.
  - What: steps, calls and blocks are dragged from a catalog (a product's process steps, a module's
    component skills, the gateways) onto an arrow, after a shape, or anywhere on the canvas, and wired
    by hand: from a shape's port, by moving an arrow's end, single gateways too. After each change a
    validator reads the drawing back into the flow (sequence, parallel blocks, decisions, conditional
    steps), or names what keeps it from being one: a shape not on the way from Start to End, a task with
    two ways out, a gateway that neither splits nor joins, branches that do not meet at one join of
    their kind, a loop, an exclusive split without one otherwise. Until it is a flow, the last valid
    flow is kept and Save is off. Auto layout (default) lays the drawing out as the flow's structure
    says; off, shapes stay where they are put. The skill service's checker (modplan) runs on a skill by
    itself after each change. The layout is not saved: the AAS keeps the flow, not a diagram.
  - Why: drawing by hand is what users of a BPMN modeler expect, and the block-only editing of the
    first version felt like a form. Reading the drawing back into blocks keeps what the blocks gave:
    every flow that is saved is well structured (a split has its join, no step runs twice), so FORTE's
    rules for a module and the agents' plans need nothing new; the validator only says what to fix. This
    is the classic result that well-structured BPMN is the part that maps to blocks without loss.
  - Instead of: block-only editing (sound by construction but rigid); a free graph saved as it is and
    checked on save (the flows would need a graph model in the AAS and in FORTE's rules); saving
    diagram positions in the AAS (a second, presentational model next to the flow; asked first if wanted).

- **Plans and composite skills in BPMN notation, as a view of the block-structured flow, without an
  engine.** *Journal*.
  - What: a second planner module and a second skill editor in the web UI fork (`ProcessSequenceBpmn`)
    draw the same flows in BPMN: a step is a service task, a call a call activity, a parallel block a
    pair of AND gateways, a decision or conditional steps a pair of XOR gateways (otherwise is the
    default flow). Editing is by blocks only (insert on a sequence flow or after a step), so every
    diagram is a well-structured BPMN process. Both read and write the existing AAS data; a step links
    to the skill it runs, so a plan, a module's skill and its building blocks open in one notation. A
    flow exports as a BPMN 2.0 file with its diagram, marked not executable. The classic editors stay;
    a setting chooses which skill editor shows.
  - Why: BPMN is the notation the related work and industry use (koecher2022bpmn, Lindorfer and
    Froschauer, Stolze et al.), but as a free graph it allows unpaired gateways (a flow that hangs, a
    step that runs twice) and knows nothing of equipment, stop propagation or parameter ranges. Drawing
    our blocks in its symbols gives the familiar notation and the exchange file, keeps the flows sound
    by construction and keeps the checks; FORTE runs a skill and the agents a plan, so an engine would
    only add a central server.
  - Instead of: bpmn-js as a free modeler with rules and a check on save (its licence also requires its
    logo); executing BPMN in Camunda as koecher2022bpmn does; storing BPMN XML in the AAS.

- **The kit installs FORTE on a Pi over SSH, without the internet.** *Journal* (a module needs no
  cloud to be set up).
  - What: the kit carries the container files and the arm64 base images (alpine, busybox, saved with
    `docker save`); `install-pi.ps1` copies them with FORTE and `install.sh` to the Pi with scp and runs
    the installer over ssh. The installer downloads only what is not next to it, and checks the
    clock only before a download.
  - Why: lab and shop-floor networks often have no internet, and a Pi without a clock chip starts
    with a wrong date, which only matters for certificates.
  - Instead of: the installer fetching the container files from GitHub and the images from Docker
    Hub every time. Docker itself is still installed from the internet when missing.

- **A FORTE kit for others' block types: the lab's runtime plus theirs, from any 4diac project.**
  *Journal* (the runtime can be extended by people outside the project).
  - What: `runtime/make-kit.ps1` zips the build scripts, FBE configurations, FORTE patches and the
    lab's exported modules; `build-project.ps1` exports any 4diac IDE project next to them and builds
    FORTE for the Pi (or the PC). Without modgen's type manifest, a type whose header path FORTE has
    already (a copied standard block) is not compiled again.
  - Why: a FORTE runs only the types compiled into it, so one binary per Pi has to hold the lab's
    modules and the newcomer's blocks; with the lab's exports in the kit, the newcomer's FORTE still
    runs the module programs and can go on a lab Pi.
  - Instead of: sending the whole repository (modgen, Python, the module specs), or a FORTE with
    only the newcomer's types, which would break the lab module on the same Pi.

- **Custody: a product and the resource that carries it are bound by capability constraints, not by
  a rule of the agents.** *Journal* (and the slides).
  - What: vocabulary 0.7. A resource that carries or holds a container has it in its custody from
    Receiving to Releasing. Holding (the resource has this container), Occupancy (how many it has) and
    Capacity (how many it can have) are states; HeldBy is the container's side of Holding. The
    constraints: Transporting needs `Holding = true`; Receiving needs `Occupancy < Capacity` and gives
    `Holding = true`; Releasing needs `Holding = true` and gives `Holding = false`. A shuttle's AAS
    offers Receiving (Capacity 1) and Releasing next to Transporting; no skill realizes them, they
    change only the custody, so the agent carries them out itself. The product agent sends its state
    (HeldBy) with every call and sends every call to every resource agent: for its first transport it
    asks for Receiving (the free shuttles propose, the modules refuse), then for Transporting (only the
    shuttle that holds it proposes), and at the end for Releasing. A resource agent checks the Pre
    constraints of its offered capabilities against the product's state and its own custody; a
    constraint about a state nobody gives is not checked. A refusal only because of the resource's own
    state that changes (Occupancy: a full shuttle) says Busy, so the product agent asks again; the rest
    are for good. Custody is a lease (an hour), renewed by every call of the product's agent, so a
    product agent that is gone does not hold a shuttle for ever.
  - Why: the binding is the same kind of fact as a vial's content volume: a state that a capability
    needs and changes. In the AAS it is what the IDTA Capability Description already has (Pre and Post
    as BasicConstraints), so a resource's AAS says who may carry a product, and nothing in the agents
    is about shuttles: an AGV, a gripper or a tray with room for twenty works the same. It answers the
    question of the holonic literature (PROSA's order holon bound to its workpiece; the intelligent
    product bound to its pallet, McFarlane et al. 2003) with the commitment rules of Jennings (1993):
    how it starts (Receiving), how it ends (Releasing), when it lapses (the lease).
  - Instead of: the product agent remembering its carrier and asking only it, and the shuttle refusing
    others until a release message (built earlier the same day: two rules in the agents' code, one of
    them about shuttles); one agent for the whole table (transport out of the bidding); custody as a
    message protocol of its own. Loading as the step that starts the custody waits for the loading
    module's AAS (the Kuka has none yet): when it exists, Loading is a step at the loading station and
    Receiving happens before the shuttle drives there.
  - Open: a handover between two carriers (a robot moving the vial from one shuttle to another) is
    Releasing by one and Receiving by the other, with the robot's step between; not tried. `Holding`
    from a product's side and from a resource's side is one fact seen twice (HeldBy, Holding), which
    the vocabulary says in words, not in a rule.

- **Transport: each shuttle bids for Transporting like a module; the product is carried to the
  module's station before the module's proposal is accepted.** *Journal* (and the slides).
  - What: a shuttle's AAS offers Transporting (TargetX, TargetY, TargetRz over the table's extent;
    vocabulary 0.6), realized by MoveToPosition, whose parameters now mean those properties
    (`modreg.planar`). A module's proposal carries its station: its transfer point in the table's
    frame, computed by the manager from the module's, the line's and the table's coordinates. The
    product agent chooses the module, calls for Transporting to that station (every resource the first
    time, then only the shuttle carrying the product), and accepts the module's proposal once the
    shuttle reports the product there. The carrying shuttle bids for no other product until the
    product agent releases it at the end. A proposal holds its module for up to 300 s; a late proposal
    is rejected at once so it holds nothing.
  - Why: the user's decision (30 Oct: the shuttles bid like modules). It keeps one mechanism for every
    resource, and the transport is in the same conversation record as the steps. Accepting only once
    the product is there makes VDI/VDE 2193-2's binding proposal the booking, without a message type of
    our own.
  - Instead of: the product agent commanding the table directly (transport outside the bidding); one
    agent for the whole table (it would have to decide which xbot, which is the controller's or the
    shuttle's own business); accepting the module first and moving afterwards (the module would start
    with no vial under the needle); a separate "start" message after booking (not in VDI/VDE 2193).

- **A product agent's step can need a reconfiguration: the syringe asks for BottomUpFilling, the
  filling module's agent creates the skill online and runs it.** *Journal* (and the CIRP demo).
  - What: a resource agent offers a capability of the required meaning or a narrower one (an exact
    one first, then a built skill first); on acceptance of an offer whose skill is only described,
    the agent rebuilds the module (`execute.rebuild`: modsync creates the skill in the running FORTE
    program, records it with its interface, derives the capabilities anew) and runs it over OPC UA.
    `test_agents_live.py`: the syringe's Filling step goes to BottomUpFilling, created online, run with
    1 mL, the weight back. modlink skips a capability offered after a reconfiguration (no interface yet).
  - Why: this is the step from "a module that can be changed" to "a line that changes a module because
    a product asks for it", the journal paper's claim; a narrower capability meets a broader request
    (a bottom-up filler can fill a vial) but never the reverse.
  - Instead of: matching capabilities by identical meaning only (a module that only fills bottom-up
    would refuse a vial); a planned-only reconfiguration in the agent (the agent now does the real one
    on FORTE).

- **A skill can be written for a narrower capability than its steps contribute: BottomUpFilling, a
  Filling (vocabulary 0.6).** *CIRP* and *Journal*.
  - What: `lab:BottomUpFilling rdfs:subClassOf lab:Filling`; a composite skill names the capability it
    was written for (`capability:` in the spec, a supplemental semantic id of the skill element in the
    lab's semantics, `pprl:writtenFor` in the projection); the derivation offers that capability
    instead of the one its steps contribute, characterized by the broader class's properties; what
    holds of Filling (its constraints, the machine's stated facts: the containers it takes) holds of
    it. `discover` does not plan narrower capabilities.
  - Why: the user's call (30 Oct): a new or changed skill needs a capability of its own, or a product
    cannot ask for it and the offer of "the same Filling, after a reconfiguration" is no reason to
    reconfigure. What makes bottom-up filling different (the needle rising with the liquid) is how
    the skill moves, which no constraint on the states before and after states, so it is declared by
    whoever writes or plans the skill, not inferred.
  - Instead of: a capability per skill name (`Filling_BottomUpFilling`: the product cannot name it);
    inferring it from the flow's shape (a Dispense beside a rising axis: clever, and wrong for an axis
    that moves down); planning narrower capabilities from their constraints (they are Filling's, so
    any Dispense would be "bottom-up").
  - Found on the way: `described_skill` named the components after "Module", so the steps of every
    skill described through it referred to components that do not exist (`ModuleLinearAxisAAS`) and
    the derivation saw no steps; it now takes the module's name from its components' AASs.

- **Orders go to an order agent, which starts a product agent per unit; a module is reserved from its
  proposal until the decision.** *Journal*.
  - What: an `order` message (Product, Quantity) to `orders@<domain>`, or `POST /orders` on the
    manager, starts one product agent per unit (`<product>-<n>`); the orderer gets `orderConfirm`
    with the agents' JIDs, then from each product agent `informConfirm` with its steps (who did each,
    the results) or `failure`, all in the order's conversation. A resource agent refuses a call with
    `Busy` while it carries out a step or while one of its proposals waits for a decision; a product
    agent that hears only busy refusals asks again a second later.
  - Why: an agent per product is how product-driven control is described (the product carries its
    own process through the line), and it lets three vials share four modules without a central
    schedule. A binding proposal (VDI/VDE 2193-2) must reserve the module, or two products that both
    accept the same module's proposals collide. Ordering is not in VDI/VDE 2193-2, so it is a small
    protocol of the lab's own in the same frame.
  - Instead of: one product agent per order walking the units one after another (no sharing of the
    line); the manager as a plain REST service only (orders could not come from another agent);
    refusing a busy module's call like any other (the product would end with "nobody").

- **The line's agents: SPADE on the server, VDI/VDE 2193 over XMPP, an agent per module started by a
  manager that watches the AAS server.** *Journal*.
  - What: `line-agents` (`lineagents`): a resource agent per module bids for one step at a time with
    the module's offer (the offered capability of the required meaning whose properties cover the
    product's values, the realizing skill, built or only described, the skill's arguments mapped by
    meaning); on acceptance it creates a described skill first (modsync, recorded back on the AAS
    server) and runs the skill over the module's OPC UA with modlink; a product agent per order walks
    the Production Sequence; the manager starts, updates and stops resource agents to match the
    module AASs on the AAS server. Messages are VDI/VDE 2193-1 frames as JSON in XMPP bodies;
    Prosody in the lab stack.
  - Why: the agent is the module's active part and the module stays an IEC 61499 program and an AAS;
    the server location with a direct OPC UA client is IEEE 2660.1's recommended practice when the
    device should not host agents, and it keeps the skills' state as it changes; the AAS registration
    is the one place a module becomes known, so the agents follow it rather than a list of their own.
    VDI/VDE 2193 is the I4.0 standard the AAS community implements (over MQTT and Kafka so far).
  - Instead of: SMIA (closest system, but its own FIPA-ACL dialect, an OWL capability model instead of
    IDTA 02020, OPC UA without method calls, copyleft and pinned to an older SPADE); agents on the Pis;
    executing through the AAS and the DMP (kept as a second executor: slower, the state polled);
    SPADE's own XMPP server for deployment (it lost registrations from other processes).

## 29 Oct 2026

- **Modules are discovered: FORTE announces itself (LDS-ME), the service fetches the module's
  manifest and registers it.** *CIRP* (the plug step), *Journal*.
  - What: FORTE is built with `FORTE_COM_OPC_UA_MULTICAST` (open62541 with mdnsd, our own recipe), so
    its OPC UA server announces itself by mDNS as OPC UA Part 12's multicast discovery has it.
    `modreg serve --discover` browses for `_opcua-tcp._tcp`, connects to each server, finds the modules
    by the module rules' layout (Occupation and Module), fetches the module's manifest (the pydantic
    dumps of its AAS and its components', `{"module", "profiles"}`) from
    `http://<host>:8088/manifest.json`, and registers it as a profile sent to it is. The planar
    controller is recognised by its namespace and described from what it shows.
  - Why: plug and produce means the integrator does not have to tell the service a module is there;
    the module brings what describes it. The standard OPC UA discovery is what any client of the line
    already understands, and it comes from the runtime itself, not from a helper on the device.
  - Instead of: an Avahi service file on each Pi (no rebuild, but a second thing to keep in step with
    FORTE's port); a scan of address ranges; the manifest inside the OPC UA address space (FORTE would
    need blocks to serve it); an AASX package (the service takes the profiles already). The manifest
    sits beside FORTE over HTTP because FORTE's mDNS record carries only the server's name, path and
    capabilities.
  - Found on the way: the FBE leaves mDNS out because GitHub's release archive of open62541 lacks the
    mdnsd submodule, and its unpack helper fails on Windows (a rename onto an empty folder); mdnsd also
    needs `inet_pton`, which the XP-compatible Windows target does not declare.

- **The evaluation's scenario is a changeover to the prefilled syringe, with filling from the bottom.**
  *CIRP*.
  - What: one product changeover, timed as one: the filling module gets a new composite skill that
    fills from the bottom (NeedleDeep → Dispense ∥ NeedleRise → Home → Weigh: the needle starts low in
    the barrel and rises while the pump doses), with the syringe's values, and the stoppering module a
    new stopper depth. Online against a restart of both modules; the new skill written in the skill
    editor, and planned if a model of the liquid level fits.
  - Why: the change has to be one no parameter can make, and one a product asks for. Filling from the
    bottom is what a tall barrel or a foaming liquid needs; it runs two components at once, which is
    what the parallel block of the module rules is for (one join block, where a generated type has 2ⁿ
    states). The filling module is the one whose primitives span three components and whose Pi moves
    an axis, so the run is visible at the bench.
  - Instead of: DoubleDose or a planned 15 mL (two equal doses next to each other: what a larger
    range would give); the net fill weight (Tare moved into the skill; not chosen by the authors);
    stoppering, capping or inspection (one sensible sequence, or no program and hardware yet).
- **Dosing's integration constraint: the needle in the container, not the needle still.** *CIRP*,
  *Journal*.
  - What: on the filling module Dispense needs `Position >= FillPosition` and keeps it while it runs
    (an invariant that is a comparison). The checker accepts a parallel branch that moves the
    variable as long as the comparison holds at each state the branch passes through (a move goes
    straight, so its ends are enough); the planner and the PDDL and HDDL exports reach a comparison's
    bound when it does not hold. Cases T13 and T14.
  - Why: "unchanged" said more than the machine needs: it ruled out filling from the bottom, which
    is sound as long as the needle stays in the container. The constraint states what is physically
    required, so the checker tells a skill that may move the needle while dosing from one that takes
    it out of the vial.
  - Instead of: keeping "unchanged" and a second Dosing capability for filling from the bottom; or
    leaving the check to the engineer.
- **The replanning example needs a new step, not a new value: TaredDispensing.** *Journal*, *CIRP*.
  - What: a step that needs the dose's own weight checked is not covered by Dispensing (it weighs the
    vial and the liquid together); the composite made of the filling module's primitives puts Tare in
    front of Dispensing's steps, and its derived capability covers the step after a reconfiguration.
    The agents call for proposals one step at a time (Filling, then the transport), and the table's
    agent is a resource agent like the modules'.
  - Why: DoubleDose is, on our module, a parameter change (one dose within range twice is a volume);
    an example of replanning should change the structure of a skill. The table is a resource in the
    model, so its agent is one too.
  - Instead of: DoubleDose for 12 mL; a call for the whole recipe at once; a separate transport agent.

- **The figures' shapes as a draw.io shape pack.** *Journal* (figures, and anyone drawing the lab).
  - What: six draw.io libraries in `docs/figures/library` (the line, parts, computers and software, AAS,
    planes and sketches, flat), 125 shapes taken by cell id from the pages they were drawn on, each a
    group with its shadow; the AAS shell as an isometric solid, standing or lying flat; a catalogue page
    per library; registered for the VS Code draw.io extension in `.vscode/settings.json`.
  - Why: new figures then reuse the same drawn things, at the same angles, instead of copying cells
    out of old pages.
  - Instead of: copying from the figure files by hand.

- **In an isometric figure the AAS shell is an isometric solid.** *Journal* (figures).
  - What: the shell's outline, with the logo's rounded corners, extruded and drawn on the figure's own
    30° axes, shaded like the stations, its name on the band; it stands on the AAS plane, and the lines
    from the tools end on its top.
  - Why: a flat logo in an isometric drawing reads as pasted on; the solid belongs to the scene.
  - Instead of: the flat shell, kept for flat diagrams.

- **An agent is drawn as the active part of an AAS, in our parts.** *Journal* (agents, future work).
  - What: a module's agent is a SPADE agent; its messenger is XMPP, carrying VDI/VDE 2193 messages; an interaction manager with the
    service provider's state machine, bidding (capability, availability, time), reconfiguration (the
    planner composes, modsync builds online) and execution (modlink over OPC UA, or an Operation of the
    AAS over HTTP that the DMP turns into the OPC UA call); its passive part is the module's AAS. A
    product agent is the same build as the service requester, writing the process AAS.
  - Why: it places the tools that exist (planner, modsync, modlink, DMP) inside the agent, so the
    agents are a role around them, not a new system.
  - Instead of: agents as one box beside the tools.

- **The talk shows modsync as the commands it sends, and agents in the I4.0 language.** *Journal*
  (how the method is shown to people who did not build it).
  - What: the slide from the AAS to function blocks has a console beside the network: per step the
    operations of the management API that build it (create_fb, connect, write, start) and, last, those
    that verify it (query_fbs, query_connections, query_type, read) before the skill is recorded as
    Built. The agents are shown on the line, the vial's product agent calling for proposals and the
    modules' agents proposing or refusing, as VDI/VDE 2193 messages; replanning is one slide: match,
    the missing effect (12 mL), a composite from the module's primitives, matched again.
  - Why: the network alone shows the result, not that it is built step by step online and read back;
    the commands are the method's evidence. Interaction protocols make the agents' part concrete
    without claiming more than is planned.
  - Instead of: a pipeline of six boxes for modsync; agents as boxes beside a picture; two slides
    for the change from recipe to running program.

- **The DMP rides out a module that restarts: two more changes on its `lab-modules` branch.**
  *Journal* (what an AAS-driven connection needs from its runtime when modules come and go).
  - What: a route's OPC UA subscription is deleted without waiting for the server's answer, and a
    method call or a signature read that finds the shared connection reconnecting waits for it (a
    call a third of its timeout, a read 10 s) instead of failing; a read that meets a stale session
    is made once more.
  - Why: a module that restarts (FORTE, a Pi rebooting) is normal on a reconfigurable line. Before,
    the first call after a restart failed for about 13 s (`Device transport failed`, HTTP 424 at the
    AAS server), and removing the routes of a module that had gone away waited out a request timeout
    per consumer: the DMP took 71 to 213 s to converge after a republish, 47 s with the delete sent
    and not waited for. A server that is gone drops the subscription with its session anyway.
  - Instead of: retrying the call itself (a method is not idempotent: Dispensing must not start
    twice), so only what has not been sent waits, and only the read is made again.
  - Checked: the DMP's OPC UA tests (37), and `test_dmp_live.py` three runs in a row against the
    same DMP, where the second run had failed before. Left as found: a mapping blocked on a submodel
    published after its AIMC is not resolved when the submodel arrives (publishing order avoids it).

- **The planner's bindings make the process AAS: the registration service writes it after a save.**
  *Journal, CIRP* (ISA-88's master recipe, apart from the general recipe).
  - What: `POST /process/<product>` (`modreg/process.py`) reads the product's recipe as the planner
    saved it, with a module, a skill and input bindings per step, finds the line that holds every
    bound module (its Hierarchical Structures), and writes the process AAS: Process Information,
    a step binding per bound step (the recipe's step, the module, the skill, each input's source or
    constant and the Operation variable it is handed to), and the plan check's result as its
    Validation. The planner asks for it after saving a recipe with a bound step. The plan check
    moved into `modreg` (`modreg.plancheck`) for it.
  - Why the service and not the planner: the process AAS is built with aas-model's classes and
    checked by the same plan check as the reference processes, so the hand-written ones and the
    planner's are one structure; the planner has no notion of a line, and the service finds it.
    Instead of: the planner writing the process AAS's JSON itself (a second copy of the structure in
    TypeScript), or asking the engineer for the line.
  - First step: the bindings stay in the product's recipe as well, since the planner and the HMI
    read them there. Taking them out is the next step, once every reader reads the process AAS.

- **The skill editor asks the checker and the planner.** *Journal* (the engineer's side of planning).
  - What: in the skill editor, Check sends the skill as it is on screen (not saved) to `modreg
    serve`'s `/check` and shows each finding at its step, with the skills that would fix it; a
    changed flow clears the result. In the skills overview, Plan a skill takes a capability the
    module offers, its range properties as the values and what it should report as results, shows
    the planner's steps, and on "Plan and describe" has the skill described on the AAS server and
    opens it in the editor; `modsync reconfigure` builds it.
  - Why the check before saving: a finding is cheapest while the flow is being drawn; saving
    first would put a skill on the server the module cannot run. Instead of: checking on save only.
  - The values come from the Capability Description the editor already reads (its ranges), so the
    dialog asks for no names: what a module can be planned for is what it offers.

- **Every call of a module's command is logged, as a time series in `Variables/Log`.** *Journal.*
  - What: per command an Operation invokes (`Dispensing_Start`, `Occupy`, ...), a series
    `Log/<action>` (aas-model's `operation_log`): how the call ended (`Outcome`), how long it took
    (`DurationMs`), and the Operation itself, referenced, so its variables are fields (the session,
    the parameters, Accepted and ErrorID). The DMP writes the row from the bridge mapping's response
    half, also for a call that failed (then the log row only).
  - Why: who called which skill with what, and what the module answered, was in no record; the
    module's own state series show what it did, not who asked. With the session in the row, a
    module's history can be read per client (an agent, the HMI, the planner).
  - A reference, not copies of the variables: the record follows the Operation when its parameters
    change, as aas-model's stations do. Instead of: one log per skill with a command field (a
    record refers to one Operation), or a log in FORTE (it has no clock or storage to keep it in).

## 28 Oct 2026

- **The lab's AAS stack runs the DMP beside BaSyx, with InfluxDB behind the Variables and MQTT
  for BaSyx's submodel events.** *Journal* (the architecture: an AAS that is the configuration of
  its own connection). Asked for by the user.
  - What: `deploy/aas/compose.yaml` (`python deploy/aas.py up`): the BaSyx AAS environment with
    operation delegation and its MQTT feature, registries, discovery, the web UI, Mosquitto,
    InfluxDB 2 (org and bucket `ap2030`, as aas-model's segments name them) and the DMP built from
    the `aas-camel-dmp` submodule, named `dmp` because the delegation URLs name `http://dmp:8080`.
  - Why MQTT for the events, not Kafka: the DMP takes either; Mosquitto is one small container and
    the lab's stations speak MQTT already. Kafka needs a broker and its coordination for one
    consumer. The modules' values do not go through the broker: the DMP observes them over OPC UA
    and writes them to InfluxDB.
  - The secrets (InfluxDB's password and token) are made up on the first `up` and kept in
    `deploy/aas/.env`, which is not committed: the repository is public.
  - The DMP did not run our modules out of the box. Four changes, on a branch of the DMP fork
    (`lab-modules`), each with a test:
    - it refused aas-model's AIDs: since 24 Oct aas-model has every interface select its `nosec_sc`
      (AID 1.1 requires a selection), and the DMP (23 Oct) refused any selection, since it holds no
      credentials. A `nosec` scheme needs none: a selection of `nosec` schemes only is accepted now.
      Instead of: leaving the selection out of our AID (no longer AID, and aas-model adds it back);
    - it bound an Operation to the action named like the Operation's parent (aas-model's
      `Skills/<skill>/operation` and action `<skill>`). ARSO has `Skills/<skill>/<command>/<command>`
      and an action per command of every skill (`Dispensing_Start`), which cannot all be named
      `Start`. Now, where the names differ, the one action all the mapping's Sinks address: the
      AIMC states the binding. Instead of: changing ARSO's skill structure for a naming rule;
    - it could not call a method whose owning object is named by a browse path (it read the
      signature only with a NodeId owner, and resolved a missing one at the call). FORTE numbers its
      nodes anew at every start, so we name them by browse path; aas-model's stations have fixed
      NodeIds, so this had not come up;
    - it connected to the host a server names in its endpoints (FORTE: the computer's hostname,
      `MartinPC`, the Pi's name), which does not resolve in the DMP's container. It now reaches a
      server at the AID's base (Camel Milo's `overrideHost`), as the AID says.
  - Found, not changed (the first is fixed on 29 Oct, see there): removing or replacing a route
    whose OPC UA server has gone away waits out a shutdown timeout per route, and leaves the mapping
    stale and the DMP degraded until it is restarted; and a mapping whose referenced submodel is published after the AIMC stays blocked
    (not resolved when the submodel arrives). So the components' AASs are published before the
    module's (`modreg.service.mapped_last`), and within an AAS its AIMC after its other submodels
    (`AasServer.publish`); a module keeps its OPC UA address across restarts.
  - Checked end to end (`cell/tests/test_dmp_live.py`): the filling module simulated on FORTE;
    Occupy, Reset, Start and Dispensing invoked at the AAS environment, answered by the module
    through the DMP (and a refusal for another session), and the rows of the module's state and of
    the Dispensing run, with its volume and weight, in InfluxDB. And a shuttle of the planar table
    (the planar controller, a Python OPC UA server, which names a method's arguments by meaning:
    the describer says how a server names them): the table to Execute, the shuttle occupied and
    moved, its run, its pose and the call log in InfluxDB.

- **A module's AAS is what the DMP (aas-camel-dmp) runs: a skill's Operation calls the module's
  OPC UA method through it, and its values reach InfluxDB through it.** *Journal.* Asked for by
  the user.
  - What changed in the generated AAS:
    - each Operation's delegation URL is filled in: the DMP's origin and the path where the AAS API
      invokes that Operation (`/submodels/{base64url(id)}/submodel-elements/{idShortPath}/invoke`),
      as aas-model now writes it. Before, the `{operation_path}` placeholder was left in it;
    - an action's arguments are named as FORTE names them: `RD_1, RD_2, …` in, `SD_1, SD_2` out.
      FORTE's OPC UA server names a method's arguments after the data ports of the SERVER block
      that serves it, and the DMP calls a method with its arguments by name. What each argument is
      (Session, Volume; Accepted, ErrorID) is its title;
    - a mapping that invokes an action writes into the action's `input`, and has a response half:
      the method's answer (`SD_1, SD_2`) becomes the Operation's Accepted and ErrorID. A skill's
      results are marked Optional (aas-model's qualifier): the method answers at once, the results
      come when the skill is done, and the DMP requires every output not marked so;
    - a Boolean (the occupation) goes into its decimal field as 0 or 1: the DMP writes a field as
      its type and refuses a Boolean for a float;
    - aas_pydantic's `temp_id_short_attribute_*` Properties (it keeps a list item's idShort in them
      to read the model back) are stripped before publishing, as aas-model does. The DMP refuses a
      mapping with elements it does not know, and every mapping had them.
  - Why the AID names FORTE's argument names: the AID describes the device as it is, and the DMP
    checks it against the server. Instead of: renaming FORTE's arguments (its server takes them
    from the block's port names) or a mapping by position (the DMP matches by name on purpose,
    so that a reordered method cannot be called with the wrong values).
  - Nothing else needed: the DMP already resolves browse paths (`uav_browsePath`, and
    `uav_componentOf` as one), which FORTE's changing numeric node ids require.

- **Every block of a generated program explains itself in plain words, in 4diac and in the docs.**
  *Journal.* Asked for by the user.
  - What: the generator (`modgen/explain.py`) writes a type comment on every type ("what it does,
    for whom", then "Technical:" the detail) and an instance comment on every block of the
    application and of every composite: where its calls come from and where its data goes (a
    parameter "from Dispensing's Volume", a result "is Dispensing's result"). The same is written
    out once by hand in [filling-program.md](filling-program.md), with each OPC UA call followed to
    the pins, and [building-skills.md](building-skills.md) says how to add a skill, a primitive or
    equipment.
  - Why: an engineer opening the program in the 4diac IDE sees dozens of blocks and their wires; without
    the comments it takes reading the generator to know what a channel carries or why a block is
    there. Written by the generator, the comments follow every regeneration and never go stale.
  - Comments are not part of a type's hash (checked with the 4diac IDE 3.3 export), so they need
    no FORTE rebuild and a running module keeps matching its program.
  - Instead of: a separate manual only (goes stale and is not where the engineer looks), or
    comments written in the IDE by hand (lost on the next `modgen`).
  - The guide states the rule the architecture gives: a module level skill is blocks of types FORTE
    has and is added while the module runs; a primitive or equipment is new types and needs a new
    FORTE. That is the split between reconfiguring a module and changing it.

- **A module keeps no live value in its AAS: its values are time series in the database, and the
  AAS says where.** *Journal.* Decided by the user.
  - Why: the values change fast (a position while the axis moves, a weight while it fills). Pushing
    each change into the AAS server loads it with writes nobody reads there, and keeps no history.
    A time series database keeps every row; a reader asks it for the latest or for a span.
  - The Variables of a module hold aas-model's time series SMCs (IDTA 02008 as SMCs): `State/Module`
    (PackML state, occupation), `State/<Skill>` (one skill's run: its state, error, parameters and
    results and its steps'), `State/Procedures`, `Measurements/<Item>` (an item of equipment's
    inputs). A series groups what changes together, as aas-model asks, not one value each. Each field
    is a decimal with its meaning as supplemental id; each series has a segment naming its InfluxDB
    measurement (`state_dispensing`, `measurements_linearaxis`), tagged with the module's AAS.
  - Instead of: a Property per value that the mapping keeps current (45 for the filling module), and
    instead of aas-model's stations' both (a Property and a series).
  - One mapping per series writes a row: each interface property is the field its SourceId names.
    modlink finds what a skill's state shows through that (the field's meaning); a capability's
    `SameAs` and a coordinate's `ZSource` refer to a record field. `Log` (the calls of skills) is
    not written yet.
- **A shuttle is its xbot: no AAS of the xbot apart from the shuttle's.** *Journal.* The shuttle's
  `MoveToPosition` is its own skill. Until now the xbot was a component (`PlanarShuttle<N>XbotAAS`)
  because it is the shuttle spec's equipment that the skill moves; but there is no part to tell
  apart from the shuttle. Decided by the user. The table's PMC was never a component (no skills).
- **Three products and their process AASs, written out in Python.** *Journal.*
  - A 2 mL vial, a prefilled syringe of 1 mL and a cartridge of 3 mL (`cell/examples/products`),
    with the values of the planner's pharma example. One process AAS each on the filling line
    (`cell/examples/processes`).
  - **Long files, every element constructed with its class,** instead of helpers that build
    elements. They are the reference a reader looks up ("this is how this part looks"), so nothing
    is hidden. Decided by the user.
  - **The recipe names no equipment; the process AAS holds the bindings** (the model of 26 Oct,
    `ppr-model.md`). The planner still writes bindings into the product's recipe (F6); `plan_check`
    reads both (`check_process`, `check`).
  - **The plan check guards the reference:** a process AAS whose Validation says something else than
    the check finds is refused by `example_line.py`.
  - **The syringe accepts a fill error of 0.05 mL,** where the planner's example asks 0.01 mL: the
    line's filling module fills to 0.05 mL. A product asks for its fill error as a range (0 to the
    most it accepts); the check now compares an offered value against a required range.
- **A capability property may list the values a module takes** (IDTA 02020's `SubmodelElementList`
  property). *Journal.*
  - Filling, stoppering and inspection take vials, syringes and cartridges (`ContainerType`); capping
    takes vials. The spec says `values: [vial, syringe, cartridge]`.
  - Why: one capability with the set of containers it takes, instead of one capability per container
    as the planner's example has it (Filling_vial, Filling_syringe, ...), which multiplies offers and
    skills that are the same.
  - Read by the plan check, modlink and `modreg offer`. The planner's matching is not checked yet.
- **The table's three shuttles are part of the example line**, so the line's resources are complete.
  Loading and unloading are still named only (each a Kuka robot and a Pi; no spec yet).
- **The reference models: the library in aas-model, the instances here.** *Journal.*
  - aas-model (branch `lab-ppr-models`) holds the lab's own submodel templates (ARSO's Skills,
    Parameters, Control Configuration; the product's Process Parameters and Production Sequence; the
    process AAS's Process Information, Bindings, Validation), the classes generated from them
    (`scripts/lab_generate.py`), and the types `Module`, `Component`, `ProductionSystem`, `Product`,
    `Process`.
  - This repository builds the instances with them: the modules from their specs (`modreg`), the
    products and the processes as Python.
  - Why: the module spec stays the one source of a module's program and its AAS (a module's AAS is
    4 to 7 MB, about 1,200 interface and 600 mapping elements, all derived). The types and
    templates are shared with the lab's stations. Instead of: the instances in aas-model as well,
    which would duplicate the specs.
  - modreg's own generated classes and templates are gone; `modreg generate` writes the ARSO
    templates into aas-model and has it make the classes.
- **aas-model's Variables replace ARSO's Operational Data.** *Journal.*
  - Variables has the shape decided for the operational data: live values as Properties, and
    `State`, `Measurements` and `Log` holding time series (IDTA 02008 as SMCs, an InfluxDB segment
    each). One model for the lab's stations and the modules.
  - A data point is a `VariableProp`: the semantic id says it is a variable, its meaning (what it
    shows) is its supplemental id. modlink reads the meaning there, and still the semantic id of
    the older AASs.
  - The coordinates are in `Variables/Measurements/Coordinates`, with their own semantic ids
    (`.../variables/Coordinate/1/0`). Their classes have names of their own (`RelativeCoordinate`,
    `CoordinateX`): aas_pydantic reads an element back as the class its dump names, among all
    classes, and aas-model already has a `Coordinate`.
  - ARSO follows (0.14).
- **The skill protocol's variables keep their id.** *Journal.* Session, Accepted and ErrorID carry
  `.../ControlComponent/Skill/OperationVariable/1/0`, stated where it holds. aas-model used to give
  it to every Operation variable; its variables are plain Properties now. The planner, the skill
  editor and the projection tell protocol from parameter by it.
- **The process AAS's templates are written by hand, not from an ontology.** *Journal.* AProSO is
  not remade yet. The templates follow the draft of 26 Oct (`process_aas.py`). Their classes are
  named apart from the skills' and the recipe's (`ProcessStepBinding`, `InputBinding`), which have
  the same idShorts but other fields.
- **Coordinates built (ARSO 0.13, vocabulary 0.5).** *Journal.*
  - What exists: modules (base, a mount and an end effector per axis, points), the table (base and
    flyways), the shuttles (the xbot, following the controller's X, Y, Rz) and the line's points.
    The example line places each module's base on the table, as a module will report it.
  - **A moving part is a fixed mount plus the moving coordinate.** Then every moving value is a plain
    data point (the end effector's Z is the axis' actual position), not an offset plus a signal, and
    a time-series record of it is just that value.
  - **The source of a moving value is a reference to the existing data point,** not a second
    mapping in AIMC. A client needs nothing new to follow it.
  - **No `History` segment yet:** it would be an empty container until the database exists.
  - **Operational Data may now hold no data points:** the line's has only its points. The rule
    requiring one was dropped.
  - **A module described from its spec alone is not placed:** its base is the root of its own small
    tree until `place` puts it on the table.
  - **Products are not done.** A product's coordinate (relative to the xbot, or a fixture on it) is
    instance data that changes at each handover. The product AAS (APSO) has no Operational Data
    yet; it comes with the product instances.
- **Coordinates: settled with the user.** *Journal.*
  - **One measurement series per coordinate,** in Operational Data's `Measurements`. It is shaped
    like every series of the plan of 26 Oct ([state-and-parameters.md](state-and-parameters.md),
    section 3): records in a time-series database, a `Latest` in the AAS. Positions will be
    reported by the modules themselves (RFID), so even fixed ones are measured.
  - **The parent is part of the record.** A record holds the time, the coordinate it is relative
    to, and x, y, z, roll, pitch, yaw.
    - A product on a shuttle: the xbot's series gets a record per move (the controller); the
      fixture is fixed relative to the xbot; the product's series gets a record only when it is put
      somewhere else, with the new parent and offset.
    - Where the product was at time t is composed from these. It is never stored.
  - **Rotation:** R = Rz(yaw)·Ry(pitch)·Rx(roll), about the parent's fixed axes (ROS's RPY;
    `modreg/frames.py` already composes so). Units mm and degrees.
  - **Granularity:** a module may hold several coordinates. Ours hold two: the module base, and the
    sled or end effector relative to it. No coordinate per component.
  - **Root:** the table.
- **Proposed (the user's whiteboard): coordinates as a transform tree in the operational data,
  instead of frames on Hierarchical Structures nodes.** *Journal.* Under evaluation, not built.
  - **Structure:**
    - a `Measurements` collection holding `Coordinates`;
    - each coordinate holds a reference to the coordinate it is relative to, and x, y, z, roll,
      pitch, yaw;
    - the semantic id says *Coordinate*; a supplemental id gives its meaning (end effector, top of
      vial).
  - **Why better than frames on nodes:**
    - The parent is a reference, not the part-of tree, so a product can sit on a fixture on a
      shuttle without being part of it, and be re-parented as it moves.
    - Coordinates that move (the needle, a shuttle) live with the other live data.
    - IDTA 02011 is no longer extended.
  - **Pitfalls to settle:**
    - Live values are not streamed into the AAS: a moving coordinate names the signal it follows,
      as data points do through the mapping.
    - A moving coordinate should change only in its joint: a fixed mount, then the moving part
      relative to it.
    - The rotation order and the units must be stated (roll, pitch, yaw about fixed axes,
      Rz·Ry·Rx, as ROS and `modreg/frames.py` already take it).
    - Each coordinate lives in the AAS of the asset it belongs to; references across AASs must
      resolve.
    - The tree must have one root (the table) and no cycles: a check.
    - Fixed poses under "Measurements" mislabel configuration as measurement.
    - "Variables" (aas-model) or Operational Data (ours) must be chosen.

- **No building, no hall, no IDTA 02045: the line is the root of all locations.** *Journal.*
  Decided by the user, overriding the entry below: the site level is not needed.
- **The frame on a Hierarchical Structures node extends IDTA 02011.** *Journal.*
  - What it adds: a statement the template does not define.
  - Why it is acceptable: 02011 (1.1, section 1.6) is meant to be "extended upon … specified
    further". The frame sits beside the template's elements and changes none, and its six properties
    carry IDTA 02075's ids. A reader of the bill of material is not affected.
  - The difference from extending 02045: there, a missing concept (orientation) would have been
    pushed into elements that mean something else (time-stamped records). Here a new, separately
    identified element is added. Both are extensions; this one is milder.
  - Open: the six properties straight on the node, without the `Frame` collection (fewer wrappers);
    or the placement in the part's own AAS, if IDTA 02075 has a submodel for it.
- **Locations: IDTA 02045 Asset Location for the site, frames for the line.** *Journal.* (Superseded
  above.)
  - 02045 holds the site and hall level: the address, the hall's coordinate system (local, with
    ground control points to WGS84), the hall as an area, and time-stamped records of where an asset
    was.
  - The line's geometry stays as frames on Hierarchical Structures nodes (AutomationML Frame, IDTA
    02075 ids): a module in the line, a component and its transfer points in the module.
  - The two meet at one place: the line's origin is a location record in the hall's coordinate
    system.
  - Why not 02045 alone: it has no orientation (it says so: no 6DoF "for now"), no frames relative
    to a parent, and positions only as event records with a time, not as a static pose.
  - Why not extend 02045: an extended template no longer conforms to the standard, and its readers
    would not understand the additions; frames on 02011 nodes are already standard elements.
  - A use for 02045 that fits it exactly: each station as a fence (an area in the line's coordinate
    system), and the product AAS recording entry and exit events as it passes. That is a location
    trace for the batch record.
  - Needs the lab's address and a measured origin of the hall; not built.
- **The CIRP paper's scope is narrowed to restructuring a module through its AAS.** *CIRP, Journal.*
  - Why: four contributions and three planners in six pages left each half-shown.
  - Instead of: models, planning, architecture and updating as equal contributions.
  - The capability model, the planner comparison, discovery, agents and locations move to the
    journal paper.
- **Effort is counted as user actions, as Dorofeev et al. (ETFA 2021) count them** (`cell/eval/effort.py`).
  *CIRP.*
  - Three ways of making the same skill: by hand in 4diac, in the skill editor, planned.
  - Why: the method is published and is the closest work's own measure, so the numbers compare.
  - Instead of: timing engineers (needs a study), or counting AAS elements (no counterpart in the IDE).
  - By hand counts every instance, subapplication, connection and value the rules build. The editor
    counts each element entered: 2 for a parameter or a step, 1 per field or binding. Planned counts
    the requirement.
  - First numbers: 131 to 151 by hand, 19 to 26 in the editor, 3 planned.
- **The argument for composites as instances rests on the standard, not on FORTE's limits.** *CIRP.*
  - FORTE can load basic and composite types online with its optional Lua loader, though never
    service interface blocks.
  - Why it still holds: creating instances and connections is what every IEC 61499 runtime does
    through management commands. Instances keep each step readable and monitorable.
  - Instead of: "FORTE cannot load types", which is not true.
- **Dorofeev et al. (ETFA 2021) generate one basic function block per composite, from a given
  sequence.** *CIRP.*
  - Their parallel steps grow as 2ⁿ states. Their future work is to keep the skill description in
    the AAS.
  - This is what our instance-only composites, join block and AAS-as-desired-state answer, and is
    why the paper cites them as the closest work.
- **The three planners' plans differ.** *Journal.*
  - GTPyhop follows the module's convention (home after every operation).
  - Aries returns by MoveAxis(0).
  - ENHSP adds a weighing of the empty vial.
  - Why it matters: it is the case for HTN methods carrying the integrator's way.
- **Scaling probe** (1 to 20 doses). *Journal.*
  - Aries grows from 0.08 s to 6.8 s on our HDDL encoding, whose value objects and sum facts grow
    with the doses.
  - GTPyhop and ENHSP stay flat.
  - To report as a property of the encoding, not of Aries alone.
