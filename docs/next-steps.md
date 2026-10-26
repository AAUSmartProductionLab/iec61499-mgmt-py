# Next steps

Plan of 8 Oct 2026, reviewed and updated on 21 and 26 Oct; it replaces the plan of 6 Oct
([archive](archive/next-steps-2026-10-06.md)). The whole pipeline in one place is
[pipeline.md](pipeline.md); what is built and how is in [work.md](work.md); what each AAS holds in
[aas-models.md](aas-models.md); what was decided in [decisions.md](decisions.md); how the work
divides into repositories in [repositories.md](repositories.md).

## State on 26 Oct

| Area | Built | Missing |
| --- | --- | --- |
| Reconfigure from the AAS (A) | Verify, create a skill, change a value, record, operate the result: on FORTE on the PC and on the Pi 5. A skill written by the skill editor is built and run from its AAS alone. **New:** `modsync project` writes the 4diac project of what runs (a skill added online included) and checks that it deploys that program | One Python interface for all of it (A4, started). The editor's fixes from its look in a browser are not committed to the fork (waiting for your go-ahead) |
| Evaluation (B) | – | **Not started:** the scenario runner, the baseline by restart, the runs on the Pi. This is now the paper's largest gap |
| Models (D2) | ARSO 0.8 for the line, module and component; product AAS with its plan; ontologies; [pipeline.md](pipeline.md) describes the whole chain | The generation project's ARSO copy and closed validation at 0.8 (working copy, not committed) |
| aas-model (E) | `modreg` on aas-model `6a03f78` (E1, 19 Oct); ARSO knows AID 1.2 (E2); resources are aas-model's `Resource` with ARSO's submodels, `modreg serve` is the registration service (E3 built). ARSO's submodels, Module, Component, ProductionSystem and Product added to aas-model on a local branch (`arso-submodels`, 230 tests pass) | That branch reaching aas-model (fork and pull request, or push access: your decision); one module registered on a disposable server (E3); the findings for aas-model's author (E4) |
| Clients (C) | `modlink` reads 0.8; the HMI operates the filling module on its Pi from its AAS; its reader rewritten for 0.8 (`hmi/aas.py`, not committed in the submodule) | The HMI's tests, its stand-in module's skills and its built-in descriptions (C1); the planner's skill list leaves out ModuleControl; the planner reading ARSO skills |
| Program structure (new, 21 Oct) | Deployed inside the application's container, so the 4diac IDE monitors what the tools deployed; started by the resource's own START block; one address per IO point (`gpio[...]`, `pwm[...]`, `modbus[...]`, `sim`) and the IO blocks set up their own Pi lines (no line blocks; stand-ins for GPIOChip and PWMChip in the Windows FORTE); compact layout, a layout arranged in the IDE kept per application | Typed subapplications for module level skills (asked, not decided) |
| Hardware | Filling module on its own Pi 5 (192.168.0.203): TB6600 straight on the pins, normally open limit switch on GPIO23 (pressed by hand), homing until the switch (60 s at most), MoveAxis at 2 kHz, 12.5 mm/s. The program of 21 Oct (container naming, START) runs there and verifies; the HMI moves the axis. The Pi runtime of 22 Oct (new IO blocks, renamed skill pins, release in Control) is built, tested under emulation and committed. The stoppering module's Pi is the Pi 5 at 192.168.0.134 since 22 Oct (runtime copied, image built); the Pi 4 is no longer used | **Installing that runtime and the new program on both Pi 5s** (needs you: on the filling Pi at the bench, Reset homes; on the stoppering Pi the old container is removed first, see [onboarding.md](onboarding.md)); the switch mounted; a move measured with a ruler; Dispensing on the real axis; the stoppering axis wired |

The week of 19 to 25 Oct was planned for E, A4, B1 and B2. E was done. The rest of the week went
into the hardware and into the program's structure, which the paper's figures and the teaching
both use, so A4, B1 and B2 move to the coming days (see the timeline). 22 to 26 Oct went into the skill blocks'
pins and release, the layouts, the stoppering module's move to its Pi 5 and the guides for new
sessions ([onboarding.md](onboarding.md), [tooling.md](tooling.md)); A4, B1 and B2 are next.

## What the paper delivers

The CIRP CMS full paper is due 18 Nov 2026. Its claim:

> A module that is delivered with an IEC 61499 program and an AAS can be verified, operated and
> changed online from those two alone, without the files it was generated from.

That is four deliverables:

| # | Deliverable | What it is | State |
| --- | --- | --- | --- |
| D1 | Module rules | How a module is built: the module library (module state machine, occupation, skill state machine), the fixed pattern of a module level skill, what may change online ([module-rules.md](module-rules.md)) | Built |
| D2 | Information model | The resource AAS in ARSO 0.8: the line, each module and each component ([aas-models.md](aas-models.md)) | Built; the generation project's ARSO copy and closed validation are at 0.8 in a working copy, not committed |
| D3 | Method and tools | Register, verify, operate, reconfigure, record | Built for a value and for a new skill: `modsync verify`, `reconfigure`, the record, the skill editor (9 Oct), on the PC and on the Pi 5 (9 Oct); `modsync project` (21 Oct). Missing: the one Python interface (A4) |
| D4 | Evaluation | The same changes online and by full redeployment, timed, on a Raspberry Pi | Not built: the most urgent part |

Agents are not part of the paper; they are its future work ([after the paper](#after-the-paper)).

## Which part of the model is used for what

| Submodel | Written by | Read by | Used for |
| --- | --- | --- | --- |
| Nameplate, asset type | `modreg` | the checker | Which kind of resource this is (line, module, component), so which rules apply |
| Hierarchical Structures | `modreg` | plan check | The line's modules and a module's components |
| Capability Description | `modreg` | plan check, `modlink.run_capability` | What a module offers and within which ranges; names the skill that realizes it |
| Skills (in a module's and in each component's AAS) | `modreg`; the skill editor | `modlink`; `modsync verify` and `reconfigure` | How a skill is called (commands, variables with limits), what it is composed of (a flow of steps with their bindings), and the module's own commands |
| Asset Interfaces Description | `modreg` | `modlink` | The OPC UA endpoint and the browse path of every action and property |
| Asset Interfaces Mapping Configuration | `modreg` | `modlink` | Which interface element carries a skill's state, error and results |
| Control Configuration | `modreg`; `modsync reconfigure` (the record) | `modsync verify` | Block type, instance and type hash of every skill and step; the rule set; the record of a change |
| Operational Data | `modreg` | `modlink`, through the mapping | What a value at the interface means (a skill's state, its error, a result). No live values are written into it |
| Product AAS: bill of material, required capabilities, plan | `modreg` (product) | plan check | What a product needs; today the plan names a resource and a skill per step |

The Steps of a skill and the Control Configuration are what the claim stands on. Since 8 Oct
`modsync` reads both: the Skills submodel says what is wanted, the Control Configuration what was
built.

## Where a reconfiguration comes from

Confirmed on 8 Oct, with the changeover as its scope, and tried the same day
([work.md](work.md), *The AAS as the desired state*).

**The AAS is the desired state.** A reconfiguration is a change to the module's AAS that the
tools then carry into the running program. Who made the change is a separate matter.

What can change online is fixed by the module rules: the value of a parameter or of a step's
constant, and a module level skill (instances and connections of primitives the module already
has). Anything that needs a new block type or new IO is a new FORTE build and a redeployment.

| Change | When it is needed | Where the new content comes from |
| --- | --- | --- |
| A parameter value inside the offered range | Another order of the same product family | The product AAS; the value is handed over when the skill is called. No reconfiguration |
| A step's constant or a limit (flow rate, largest volume) | The required value is outside what the module's skill offers, but inside what its component can do | The limits in the component's AAS and the product's requirement; an engineer sets the new value in the module's AAS |
| A new module level skill | No skill realizes the required capability, or the process needs another sequence of the same primitives | A skill description in the form the AAS already has (commands, variables, steps that name the module's primitives). Written by the vendor as a variant delivered with the module, by the integrator's engineer, by the AAS generator, later by an agent |

A skill that is described in the Skills submodel but has no instance in the Control
Configuration is a skill the module can get. Its capability is listed like the others. Matching
then has three answers: offered now, offered after a reconfiguration (and by which description),
not offered.

When it happens, for the paper: at a changeover, on the engineer's request. One function takes the
module's AAS and its running program and does the following:

1. Compare: which described skills and values differ from the program.
2. Check: the steps name primitives the module has, bound values are inside their limits, the AAS
   passes the validation.
3. Guard: the module is not executing and not occupied by someone else.
4. Apply: online where the rules allow it, otherwise say that a restart is needed.
5. Verify: read the program back, compare type hashes.
6. Record: instances and the change in the Control Configuration; register the AAS again.

Later a resource agent calls the same function when a bid that needs a reconfiguration is accepted.

## The plan to 18 Nov

### A. Reconfigure from the AAS (deliverable D3)

| # | Step | Where | Done when |
| --- | --- | --- | --- |
| A0 | **Try-out.** **Done 8 Oct:** instead of a mock-up, the idea was built as far as it runs: DoubleDose described but not built, created on FORTE, recorded | `modsync/desired.py` | You have confirmed the structure |
| A1 | **Verify against the AAS.** Compare the running program with what the AAS states (instances, block types, hashes, steps, constants), not with the module spec. **Done 8 Oct** (`modsync verify`); hashes are verified once they are recorded | `modsync` | A program that differs from its AAS is reported with the difference; no module spec is read |
| A2 | **Reconfigure from the AAS.** Create a module level skill from its description in the AAS; change a constant; both verified by read-back and recorded. **Done 8 Oct** on FORTE on the PC (`modsync reconfigure`), with the change added to the boot file. On the Raspberry Pi 5 on 9 Oct (0.15 s to verify, 1.6 s to create DoubleDose, verify, amend the boot file over SSH and record). **Left:** a way to write the description (the tests take it from `modreg`), with the interface description of the new skill | `modsync`, `modreg` | The live test that creates DoubleDose passes when it starts from the AAS; the Control Configuration shows the change |
| A2b | **Edit a skill.** A plugin of the BaSyx web UI fork that opens on the Skills submodel and shows a module level skill as a flow, like the product's sequence editor: the module's components and their skills on the left, steps added, removed, reordered and bound, saved to the Skills submodel. ARSO 0.8 (9 Oct) gave the steps the planner's elements for this. **First version 9 Oct** (sequences, bindings, results, parameter limits, a new skill from an existing one; `modsync` builds what it saves); looked at and tested in Chrome the same day, its three fixes and the browser test not yet committed to the fork. Then, one kind at a time and each through the module rules, the generator's pattern, `modsync` and the editor: parallel, decision, conditional. No fallbacks for now | web UI fork, `modsync` | A skill changed in the editor is what `modsync reconfigure` builds |
| A3 | **Operate what was created.** A client that reads the registered AAS again finds and runs the new skill. **Done 9 Oct:** recording a change gives a built skill its interface (`modreg/offer.py`); `modlink` ran the skill editor's DoubleDose on FORTE from the recorded AAS alone | `modlink` (HMI repository), `modreg` | `modlink` runs DoubleDose on FORTE from the AAS alone |
| A4 | **Callable functions.** Verify, create a skill, set a value: one Python interface, so a script, the HMI or later an agent calls the same thing. **Started 8 Oct:** `desired.load`, `read`, `reconfigure`, `record`, `store` | `modsync` | The scenario runner (B1) uses only these |
| A5 | **Back to the IDE.** The 4diac project of what runs, from the program by the module rules, with the IDE's layout, checked against what runs. **Done 21 Oct** (`modsync project`), tried live with DoubleDose added online | `modsync` | An engineer opens what runs in the IDE and keeps working |

Step 1.2 of the old plan (a whole profile read from the running program) is no longer on the
path: the AAS is delivered with the module, the program is only compared with it.

### B. Evaluation (deliverable D4)

| # | Step | Done when |
| --- | --- | --- |
| B1 | **Scenario runner.** Plug in a module (register, verify, operate); change a constant; create a new skill. Each timed: downtime, commands sent, time to verify | The scenarios run unattended and write their numbers |
| B2 | **Baseline.** The same changes by a new boot file and a restart | Numbers side by side |
| B3 | **Hardware.** The filling module on the Raspberry Pi 5 with the stepper. **Axis moving since 20 Oct**, homing on the limit switch and operated from the HMI since 21 Oct. Next: install the runtime and program of 22 Oct (IO blocks that set up their lines), mount the switch, measure a 20 mm move, run Dispensing on the real axis. The stoppering module on its Pi 5 (192.168.0.134) if time allows | The scenarios run on the Pi with the axis moving |

### C. Keeping the clients in step

| # | Step | Where |
| --- | --- | --- |
| C1 | The HMI's own AAS reader, its built-in module descriptions and its stand-in module still describe the modules before 8 Oct. **Reader rewritten for 0.8 on 20 Oct** (operates the filling Pi; not committed in the submodule). Left: its tests, the stand-in module's skills (Home, MoveAxis, Dispense, Tare, Weigh), the built-ins dropped, one `modlink` test | `iec61499-opcua-hmi/` (submodule) |
| C2 | The scale's weight follows the dispensed volume (it is a constant 2.0 g) | module spec, simulator |
| C3 | The Pi 4: host name `stoppering-module`, the installer's setup, system updates, the stoppering program. **Done 9 Oct**, checked across a reboot. Superseded: the stoppering module runs on the Pi 5 at 192.168.0.134 since 22 Oct, the Pi 4 is no longer used | Pi 4 |
| C4 | Teaching material: the 4diac IDE monitors deployed modules; projects of what runs (`modsync project`); a three-FORTE pub/sub demo (outside the repository). **Done 21 Oct** | IDE, `modsync` |
| C5 | **The HMI as a module of the BaSyx web UI** (decided 26 Oct, [decisions.md](decisions.md)): a Vue and TypeScript module in the fork (`basyx-aas-web-ui/`, a submodule) that reads the module's AAS itself, and a small TypeScript bridge (node-opcua) for OPC UA over WebSocket; then the HMI's Python service and pages are retired. **After A4, B1 and B2.** Replaces C1's reader work in Python. The bridge is temporary (C6) | `basyx-aas-web-ui/`, `iec61499-opcua-hmi/` |
| C6 | **The HMI from the AAS alone** (the target, 26 Oct): commands through the elements of the Skills submodel (Operations invoked on the AAS server and carried to the module's OPC UA methods, e.g. by BaSyx's operation delegation), state from the Operational Data submodel: each series' `Latest` property with its current value and its reference to the series in a time-series database (such as InfluxDB), from which the history is read. Needs what carries an Operation to OPC UA, a collector that writes the `Latest` values and the database, and the modelling of [state-and-parameters.md](state-and-parameters.md) (S1 to S6). Replaces C5's bridge. After the paper | `basyx-aas-web-ui/`, ARSO, `modreg`, a collector |

C1 to C6 are not needed for the paper's claim; they go in when they block a figure or a run.

### E. aas-model of 18 Oct (new, 19 Oct)

aas-model moved from profiles merged with the type's defaults to resources authored in Python
(`Resource` and its subtypes, a catalog of the lab's stations), extended the interface description
with WoT actions and events of its own (`.../aid/ActionDefinition/1/0`, `EventDefinition`, `op`,
`response`), regenerated the IDTA classes, and changed its generator's output. The lab's
registration service now loads a `Resource` export and refuses one that does not validate as a
plain `Resource`.

| # | Step | Done when |
| --- | --- | --- |
| E1 | **Move `modreg` to it.** Replace what is gone (`deep_merge`, `nameplate()`, `DELEGATION_BASE`, `OpcuaProperty`), regenerate the classes of ARSO's own submodels with the new generator, write actions in aas-model's action form. **Done 19 Oct**; also a dump made linear (aas_pydantic's serializer dumped every level twice) and the live tests' simulator moved to a process of its own | The submodule and the pin are both `6a03f78` (or later) and every test passes |
| E2 | **ARSO follows the interface description.** Declare the new action, event and form terms in `aid.ttl`; the closed validation passes again. **Done 19 Oct in this repository** (AID 1.2, the action and event definitions, `synchronous`, `input`, `output`, `uav_componentOf`, `readOnly`); the generation project's copy follows with its 0.8 update | `modreg check` and the generation project's validation pass on the example line |
| E3 | **Registration.** **Decided and built 19 Oct:** our modules are AAS resources in the PPR sense, so a line, a module and a component are aas-model's `Resource` with ARSO's Skills, Operational Data and Control Configuration added (built the same day); the registration service is `modreg serve`, which also takes a plain `Resource` export of the lab's stations. Operational Data is left as it is; it may become Time Series Data | One module registered through `modreg serve` on a disposable server |
| E4 | **Findings.** Check the list of aas-model findings in [work.md](work.md) against the new version and raise what remains with its author (one resolved; a new one: the serializer's double dump) | The list is current |
| E5 | **ARSO's submodels in aas-model.** Templates and generated classes of Skills, Control Configuration, Operational Data, Process Parameters and Production Sequence, and the types Module, Component, ProductionSystem, Product. **Built 19 Oct on a local branch** (`arso-submodels`, 230 tests); not pushed: no access to aas-model. Then `modreg` uses aas-model's classes instead of its own | The branch is in aas-model (fork and pull request, or access) and `modreg` points at it |


### F. The product, process and resource model (new, 26 Oct)

The model as a whole, its ontologies and its figures: [ppr-model.md](ppr-model.md). F1 to F4 are
done before the paper: they close the product-driven loop the paper shows (a product's need, a
changed skill, the planner matching it again); the rest follows after it.

| # | Step | When | Done when |
| --- | --- | --- | --- |
| F1 | **Skill types in the vocabulary**: each primitive's type and the capability it contributes; which capabilities a product can require and which only serve other skills (Positioning). Changes `ontology/Vocabulary`: with your go | Before the paper | Every primitive of the line's modules has a type |
| F2 | **The projection** of the Skills and Capability Description submodels into RDF: elements typed by their `semanticId`, individuals by their `supplementalSemanticId`, references made relations | Before the paper | The filling module's skills, steps and capabilities are a graph PPRL's rules run on |
| F3 | **Capabilities derived from skills**, in `modreg`, marked as derived, written back; called by the skill editor on save, `modsync record` and `modreg profile`; a described skill that is not built is offered "after a reconfiguration", in the planner's matching too. Closes the gaps: a new skill without a capability, a changed limit the capability does not follow | Before the paper | What is derived equals the capabilities the specs state today; a skill made in the editor is offered after a reconfiguration, then offered |
| F4 | **The overview and its figures**: [ppr-model.md](ppr-model.md), `docs/figures/ppr-models.drawio`, `docs/figures/reconfiguration-pipeline.drawio`. Drafted 26 Oct | Before the paper | They serve as the paper's figures |
| F5 | **APSO and AProSO remade** like ARSO from the submodels that are built; `modreg`'s Production Sequence template brought to the planner's 3.0; templates and element descriptions of all our submodels generated from the ontologies | After | A product AAS and a process AAS are checked as a resource AAS is |
| F6 | **The process AAS**: its templates; the planner writes the bindings into it instead of the product's Production Sequence | After | One product has a process AAS per line |
| F7 | **Ids**: the per-instance semantic ids moved out (identity by reference), `modlink`'s join of a data point to its variable changed with them | After | Every semantic id names a concept an ontology declares |
| F8 | **The rest of the vocabulary**: variables and states (aligned with the lab's `apex` ids), equipment and product kinds, DIN 8580 and VDI 2860 | After | The inventory of ids finds none outside an ontology |


### D. Writing

Outline and figures by 1 Nov; experiment runs and text from 2 Nov; submission 18 Nov.

### Timeline

| Week | Work |
| --- | --- |
| 9 to 18 Oct | A2 (writing a description), A3 (both done) |
| 19 to 21 Oct | E1 to E3 (done); the filling hardware moving (B3, started); program structure and A5 (done) |
| 22 to 26 Oct | Skill block pins and release, layouts, the stoppering module to its Pi 5, guides for new sessions (done) |
| 27 Oct to 1 Nov | A4; B1 (scenario runner, with simulated IO on the PC first); B2 (baseline by restart); the new runtime and program on both Pi 5s; outline and figures |
| 2 to 18 Nov | B3 runs on the Pi with the axis; experiment runs, writing |

B has not started and is what the paper cannot do without: from now on it comes before anything
in C or E that does not block it. If time runs out, cut in this order: C, E4 and E5, then B3 on
real hardware (keep the Pi with simulated IO), then A3. Not to be cut: A1, A2, B1, B2.

## After the paper

**Decentralized, order-driven production.** A product agent per order asks for each process step,
resource agents answer with bids, the product agent chooses. What exists: `modlink` (occupy, run a
skill or a capability), capabilities with ranges, the range check of
[plan_check.py](../cell/examples/plan_check.py), occupation as the lock at execution time, and,
after step A4, the reconfiguration as functions. What is missing:

| # | Part | Why |
| --- | --- | --- |
| 1 | An unbound process | The plan names a resource and a skill per step. With bidding the product type holds required capabilities and their order; the binding is the result of a negotiation, per order. AProSO already describes it this way (candidates, then the chosen one) |
| 2 | An order | Nothing says "20 vials of 2.5 mL" and starts a product agent |
| 3 | Messages and protocol | Call for proposals, proposal, accept or reject, result (VDI/VDE 2193), and what carries them (the lab runs MQTT; SPADE needs an XMPP server) |
| 4 | A resource agent per module | Matches a request against its own AAS; answers yes, yes after a reconfiguration, or no, with a time; on acceptance reconfigures and runs the skill |
| 5 | A product agent | Walks the process, compares bids, records what was done to the product |
| 6 | Transport agents | A vial moves between the modules on the shuttles of the ACOPOS 6D table. Their control is Python code, not IEC 61499: the table needs a resource AAS (a Transport capability, an interface the agent can call) and an agent like a module's. It also shows the model on a resource that is not IEC 61499 |
| 7 | Reservation | A module can be occupied now, not booked for later |
| 8 | A matcher both sides use | Required against offered capability, including "after a reconfiguration" |
| 9 | Failure handling | A skill that fails, a module that goes away: ask again |

A first slice: one product agent, two resource agents (filling, stoppering) and the simulators;
one call for proposals per step; then a bid that needs a reconfiguration.

**Also after the paper** (or earlier where B1 needs it): states, measurements and events as time
series in Operational Data, and the Parameters submodel ([state-and-parameters.md](state-and-parameters.md),
planned 21 Oct, decisions open); drivers where FORTE has no block: a stepper whose position is counted
from its pulses (today it is estimated from the time it ran), a real scale (e.g. HX711), as
service interface blocks; typed subapplications for module level skills, if skills are to be
dragged in from a library; the planner reading a module's skills; a module shell for the 4diac IDE
so a hand-written module goes the same way; the AAS generator writing profiles; live values and
history in the AAS; registration on the lab's AAS server; the repository split and CI.

## Open questions

| Question | Blocks |
| --- | --- |
| **Waiting for you:** go to install the runtime and program of 22 Oct on both Pi 5s (the filling Pi at the bench; the stoppering Pi after its old container is removed) | B3 |
| **Waiting for you:** the eleven open decisions of the state and parameters model ([state-and-parameters.md](state-and-parameters.md), Sections 7 and 8.8; decision 1 answered 26 Oct); the modelling is picked up again after them | S1 to S5 |
| **Waiting for you:** how ARSO's submodels reach aas-model (fork and pull request, or push access) | E5 |
| **Waiting for you:** go-ahead to commit the skill editor's fixes to the fork and the generation project's ARSO 0.8 | A2b, D2 |
| Should module level skills become typed subapplications in the IDE (reusable, with an interface), or stay untyped (created online without type files)? | later |
| Commit the HMI's 0.8 reader to the submodule now, or with its tests and stand-in module (C1)? | C1 |
| `modsync reconfigure` puts the recorded AAS back where it came from (a file, or every changed submodel on the AAS server). The registration service keeps its own copy of a module's profile and does not learn of the change | A4 |
| The HMI's committed reader still reads the modules of before 8 Oct (its 0.8 rewrite fails 7 of its tests until the stand-in module follows); the generation project's pushed ARSO copy and closed validation are 0.7 (0.8 in a working copy); `modlink` reads 0.8 | C1, D2 |
| ARSO's Condition follows the planner's elements of 8 Oct; the planner got grouped AND and OR conditions on 9 Oct. Follow it when a decision step is built | A2b |
| The planner lists every skill with a Start; with 0.8 that includes the module's own commands. Leave them out there by their kind (ModuleControl) | A2b |
| A skill that is described but not built is told by its missing instance in the Control Configuration (as tried). Does it also get a state of its own that a client can read (described, deployed)? | A3 |
| A change that needs a restart (a sequence changed, a skill removed) is refused. For the baseline a boot file is needed, and the AAS does not hold the wiring: is the vendor's boot file part of what is delivered? | B2 |
| Which changes does the paper show: a constant and a new skill, or more? | B1 |
| Where do F1 to F3 go in the order of what is cut if time runs short? | F |
| Two components of one kind in a module (the two cameras) need one skill name twice | later |
| What a component's AAS holds besides its skills (a nameplate?) | later |
| Step values are also in the interface description; leave them out there? Operational Data in groups? | later |
| Occupy and Release are access control: are they called skills at all? | later |
| An interface action names its command as a supplemental semantic id; should it be the semanticId? | later |
| What belongs in the Parameters submodel (it does not hold a skill's parameters)? | later |
| Does the plan become an AAS of its own, per product and line? (With bidding it becomes per order) | agents |
| The ACOPOS 6D table: where is its Python code, and which interface does it offer (OPC UA, MQTT, a library)? | transport agents |
| The agents' framework and inner structure (SPADE or plain asyncio over MQTT; fixed plans or BDI) | agents |
| The module specs (YAML) still hold the wiring of each IO point per target; describing it in the AAS is an idea for later | later |

Facts only you or the lab have: the measured values of each station (fill range and accuracy,
diameters, flow rate, the real speed of the axes), and whether we may publish to the lab's AAS
server.
