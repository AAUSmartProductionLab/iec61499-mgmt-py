# Next steps

Plan of 6 Oct 2026. The guiding star is the integrated architecture in *Plug and produce
architecture: components, flow and status* (the ten-step loop: connect, identify, discover,
verify, register, match, plan and bind, execute, monitor, reconfigure). What is built and how is
in [work.md](work.md); what each AAS holds and how the submodels connect in
[aas-models.md](aas-models.md); how the work divides into repositories in
[repositories.md](repositories.md).

## What we are aiming at

The work specifies three things: how a module is built, what its AAS holds, and how the AAS is
used to control and reconfigure it. The test is a module we did not generate:

> A vendor builds a module in an IEC 61499 IDE inside our module shell, describes it with the AAS
> generator from its spec sheets, and delivers the program and the AAS. We plug it in. From the
> AAS and the running program alone it is verified, registered, matched to a product's process,
> operated, and given a new skill or new parameter values online.

Today the bottom of the loop works (spec → FORTE → AAS on the server → HMI and `modlink`), but
the integrator's tools still lean on our own module spec, and the middle of the loop (match,
bind, execute across modules) is missing. The CIRP full paper is due 18 Nov 2026.

## The phases

Each step names where the work lands and how we know it is done. Days are working days and
rough.

### Phase 0: one vocabulary, one ontology, a volume to fill (about 3 days)

Small things everything else stands on.

| # | Step | Where | Done when | Days |
| --- | --- | --- | --- | --- |
| 0.1 | **One ARSO, one closed validator.** Bring the generation project's copy up to this repository's (reconfiguration elements of a skill, Control Configuration, parameter entry) and validate with its closed SHACL shapes. **Done 6 Oct (generation project, `main`, `fca2e76` to `04a38bd`):** its closed validation had not passed since the shapes were regenerated with the closed ruleset on 11 Sep (its own valid example: 2,962 violations), because nothing gathered `sh:ignoredProperties` into the list SHACL requires. Now a finishing step does; the valid example conforms, the regression suite requires that, and each invalid fixture has to fail for its own reason. Generating the shapes takes two minutes instead of hours. The projection takes an element for a class only where ARSO places that class, knows every AAS value type, keeps every class of a place and resolves a skill's Uses into `arso:usesSkill`. Rules as decided on 6 Oct: a mapping source may be a skill Operation whose skill references the sink's action; a Capability may follow IDTA 02020; a composite skill needs a capability, a primitive is a building block and needs none, Occupy and Release are access control and need none. Both projects hold the same ARSO 0.5 and CSS 2.0.2. On this side: a parameter entry's Value is optional, a skill's parameters are with the skill (no Parameters submodel is written), and an interface action names the command it carries out as a supplemental semantic id. **The filling and the stoppering module AAS conform (203 issues before)** | `ontology/`, generation project | The generation project's valid example passes its closed validation; both projects load the same ARSO; a module AAS passes | 1.5 |
| 0.2 | **Capability vocabulary.** **Done 6 Oct on this side:** `ontology/Vocabulary/capabilities.ttl` (8 capabilities, 7 properties with units, below CSS, IRIs `.../semantics/<Name>`); the module specs are tested against it. The planner's recipes and stations use the same IRIs since 6 Oct (fork, `058a03e`); demo data already on a server has to be seeded again | `ontology/`, `cell/modules`, planner | A required capability of a recipe and the offered one of a module carry the same IRI | 1 |
| 0.3 | **Fill volume.** **Done 6 Oct:** Dispensing takes a Volume (0.5 to 10 mL); the new building block Dispense waits Volume / FlowRate (1 mL/s, a constant of the step that reconfiguration can change); FillVolume of the Filling capability names the parameter; live test on the rebuilt FORTE | module spec format, `cell/modules/filling.yaml`, FORTE rebuild | `Dispensing.Start(Session, 2.5)` dispenses for 2.5 s on FORTE; the AAS links FillVolume to the parameter | 1.5 |

### Phase 1: the AAS is all the integrator needs (about 8 days)

This is the paper's core claim, and where this repository does not yet match the aim.

| # | Step | Where | Done when | Days |
| --- | --- | --- | --- | --- |
| 1.1 | **The model says what a skill can be built from.** Building blocks that are not offered (Dwell) with their block type, parameters and equipment; the fixed pattern of a module level skill written down as a rule of the module, not only as generator code. Declared in ARSO, classes regenerated. **Done 7 Oct:** the Skills submodel has `BuildingBlocks` (Dwell and Dispense in the filling module: block type, parameters with unit, limits and default, contract, equipment); steps and `Uses` refer to them. Every listed skill names its block type without the module being read. ARSO 0.6 also says what an Implementation and a Contract hold. The rules are in [module-rules.md](module-rules.md) (the shell, a primitive's interface, the pattern of a module level skill, what changes online), and the Control Configuration names the rule set. Both module AAS conform to the generation project's closed validation, which holds the same ARSO 0.6 | `ontology/ARSO`, `modreg`, module library notes | The AAS of the filling module lists Dwell as a building block; `modreg check` still passes | 1.5 |
| 1.2 | **Structure from the running module.** The structural half of a profile (skills, parameters, sequences, equipment, interface, type hashes) read from FORTE alone; the descriptive half (nameplate, capabilities, units, descriptions) from a description file; merged. **Started 7 Oct:** `modsync.structure` reads the structure back from a program by the module rules (equipment, offered primitives, building blocks, module level skills with parameters, sequences and bindings, procedures) and gives the same as the spec states, for every module and for a skill added online. Not from FORTE alone: what a primitive takes, and a primitive that is not offered, are only in its type file. What is bound to a step's parameter is now checked against its limits and type when a module is built (the controller does not check a value a parent hands down). **Left:** merging the structure with the vendor's manifest (descriptions, units, contracts, capabilities) instead of a spec, reading a live module | `modreg`, `modsync` | The profile built without the module spec equals the one built from it, for both modules | 2.5 |
| 1.3 | **Identify and verify against the AAS.** The module publishes its identity (asset id, AAS id, program digest); `modsync` compares the running program with what the AAS states, not with the spec | module library (one block, FORTE rebuild), `modsync` | A program that differs from its AAS is reported; loop steps 2 and 4 hold without a spec | 1.5 |
| 1.4 | **Reconfigure from the AAS.** A new module level skill described as steps and bindings (as the AAS describes one) is created online from that description; a parameter value is changed; the change is recorded in Control Configuration and the AAS is registered again | `modsync`, `modreg` | The live test that creates DoubleDose online passes when driven by a skill description instead of a module spec; the change log shows it | 2 |
| 1.5 | **Conformance.** One command checks a module against the rules: the library blocks are present with their hashes, the address space equals the one the AAS describes, the AAS passes the ontology check | `modsync`, `modreg` | Both modules pass; a module with a missing block or an undescribed node fails with the reason | 0.5 |

### Phase 2: the middle of the loop (about 7 days)

| # | Step | Where | Done when | Days |
| --- | --- | --- | --- | --- |
| 2.1 | **Matcher.** Required against offered capability on the RDF projection of the Capability Descriptions (the generation project's projection), SHACL rules for values and ranges; the planner's and `modlink`'s matching stay as cross-checks | `ontology/`, validation code | The pharma recipes give the same verdicts as the planner's matcher, or the differences are explained | 2 |
| 2.2 | **Planner on our modules.** The planner reads ARSO's Skills submodel and the shared vocabulary, and binds a step's parameter to a skill parameter (FillVolume → Volume) | planner (TypeScript) | A recipe step binds to Dispensing of the registered filling module in the planner | 1.5 |
| 2.3 | **Execution by agents.** Decided 6 Oct: plans are executed by a multi-agent system, not a central executor. One agent per product and one per resource; I4.0 bidding (VDI/VDE 2193) assigns steps. A resource agent has three sets of tools: run its skills (`modlink`), look up its capabilities (its AAS), and reconfigure its IEC 61499 program (`modsync`); with an accepted bid it runs the task, rewiring or reconfiguring first if needed. What this repository owes it: the reconfiguration functions as a callable interface (create a skill from a description, set a parameter, verify) | a new agents component, `modlink`, `modsync` | A product agent gets Dispense and Close done by the two resource agents, on the simulators and on FORTE | 4 |
| 2.4 | **Check before running.** A plan is refused when a step has no candidate, a bound value is outside the skill's range, or a module's AAS no longer matches its program | executor, matcher | Three broken plans are refused with the reason | 1 |

### Phase 3: experiments and the paper (the last three weeks)

| # | Step | Done when |
| --- | --- | --- |
| 3.1 | **Scenario runner.** Plug in a module (register → match → bind → run); change a parameter (new fill volume); change the flow (inspection every fifth product: plan only); change the composition (a new skill created online). Each timed: downtime, commands sent, verification | The four scenarios run unattended and write their numbers |
| 3.2 | **Baseline.** The same changes by full redeployment (boot file and restart) | Numbers side by side |
| 3.3 | **Hardware.** The same scenarios on the two Pis once they are wired; until then FORTE on the Pi with simulated IO | Depends on the wiring |
| 3.4 | **Writing.** | 18 Nov |

### After the paper, or beside it when the lab answers

- **Module shell.** A 4diac template project with the fixed parts in place; one skill written by
  hand in the IDE goes through phase 1 like a generated one.
- **Generator on the pydantic profile.** The LLM writes the descriptive half of a profile; the
  generation project uses the shared model and validator.
- **Live side of the AAS.** Mapping execution into Operational Data (the lab's node or a small
  bridge), history, a registry.
- **Lab deployment.** Registration on the lab's AAS server; `modreg` beside or inside the lab's
  registration.
- **Repository split**, CI, retiring `modsync/aas.py`, agents.

## Timeline against 18 Nov

| Week | Work |
| --- | --- |
| 6 to 12 Oct | Phase 0; 1.1, 1.2 |
| 13 to 19 Oct | 1.3 to 1.5 |
| 20 to 26 Oct | 2.1 to 2.4 |
| 27 Oct to 2 Nov | 3.1, 3.2; hardware if wired; paper outline and figures |
| 3 to 18 Nov | Experiment runs, writing |

That is about 18 days of building in three weeks: it fits only if nothing slips. If it does, cut
in this order:

1. 1.5 Conformance (the tests already show it).
2. 2.1 The ontology matcher (the planner's matcher carries the demonstration; the ontology one
   becomes future work).
3. 1.2 for the stoppering module (show it on the filling module only).
4. 3.3 Hardware (FORTE on the Pi with simulated IO).

Not to be cut: 0.2, 0.3, 1.3, 1.4, 2.3 and 3.1. Without them there is no loop to show.

## What I need from you

Decisions, each blocking a step:

Decided on 6 Oct 2026:

| Decision | Answer |
| --- | --- |
| May ARSO be extended for building blocks and for what a skill's Contract, Step and Implementation contain? | Yes |
| Validator closed or open? | Closed, as the SHACL validation of the generation project is |
| Fill volume | A time at a fixed flow rate; the volume decides the time |
| Who executes plans | A multi-agent system: an agent per product and per resource, I4.0 bidding; resource agents use the skills, the AAS and the reconfiguration tools |
| Products | Prefilled syringe, cartridge or vial, as in the planner's examples |
| Planning | By hand in the planner's web UI for now; an automatic planner may write the same submodels later |
| Which skills need a capability? (7 Oct) | A composite skill does; a primitive is a building block and needs none; Occupy and Release are access control and need none |
| Where are a skill's parameters? (6 Oct) | With the skill: the inputs of its Operation. The Parameters submodel is optional and does not hold them |
| Capability element (6 Oct) | As IDTA 02020: the template's id, the meaning as a supplemental id |
| What does a step's binding hold? (7 Oct) | The smallest change: a parameter the skill hands down is a reference to that parameter of the skill (it was its name as a string); a constant stays a value. What a step runs with shows at the interface anyway; the planner's own bindings and the HMI are unchanged |
| Where do a contract's terms come from when there is no spec? (7 Oct) | From the AAS manifest the module's vendor provides: the descriptive half of step 1.2 is that manifest, not a file of our own |
| How is a product or a plan described? (7 Oct) | Like a module: an AAS type on the pydantic model (aas-model) and a profile that is its dump, built by the same tool. No description format of our own. Done for the product with its plan (`ProductTypeAAS`); the vial of the example line is such a profile |
| What does a module carry as its manifest? (7 Oct) | The pydantic dump (the profile). It is what `modreg profile` writes today, from the module spec (the YAML file a module's program is generated from) and the running program; storing it on the module is not built (step 1.3) |
| The planner reads its own skill catalog, the modules publish ARSO Skills. Which holds? (7 Oct) | The resource's skill definition. The web UI and the planner are adjusted to read it (step 2.2) |
| Is a plain wait (Dwell) kept, and is Dispense a skill of its own? (8 Oct) | Dwell is removed for now (its block types stay in the history); Dispense is offered like every other primitive |
| What has an AAS? (8 Oct) | The production system, each of its six modules (Loading, Filling, Stoppering, Capping, Inspection, Unloading) and every active component of a module: filling pump and linear axis; stoppering piston and linear axis; cap crimper and linear axis; top and side camera; Kuka robot and gripper (loading and unloading). The bill of material of the resources and the hierarchy of skills follow from these |
| What does a linear axis offer? (8 Oct) | The same two skills in every module: `MoveAxis(Position)` and `Home`. The axes are stepper motors with a limit switch, as on a 3D printer: the controller keeps the position itself (home at the switch, then the time it steps), and the direction follows from where the axis is and where it is to go. **Done 8 Oct** in the generator and in the filling and stoppering modules, run on FORTE with the simulator |
| Which way do capabilities and skills refer? (8 Oct) | One way: a capability names the skill that realizes it. A skill does not refer back |
| What is the stoppering module made of? (8 Oct) | As the others: a linear axis and one small linear actuator (the piston). **Done 8 Oct** |
| Is there a scale? (8 Oct) | Not physically. It is a part of the filling module with a simulated weight; it is tared when the module resets (**done**). The weight following what was dispensed is not built |
| How many robots? (8 Oct) | One Kuka for loading and one for unloading, each with a Raspberry Pi of its own. How 4diac controls them comes later (likely: start program 1, 2 or 3) |
| How is a component's AAS named? (8 Oct) | One per component as built in, with an id of its own (filling linear axis); what kind it is, is shared by all of that kind |
| How does a Raspberry Pi get its runtime? (8 Oct) | By one script, `runtime/install.sh`: Docker if missing, FORTE from the repository (`runtime/bin`), GPIO and PWM. **Done 8 Oct**, run on a Raspberry Pi 5 |

Still open:

| Question | Blocks |
| --- | --- |
| Occupy and Release are access control, not production. Do they stay in the list of skills, and are they called skills at all? (The rule leaves them out by their semantic id for now) | later |
| Interface actions name their command as a supplemental semantic id. Should it be the semanticId instead? | later |
| What belongs in the Parameters submodel (optional; not a skill's parameters)? A station constant such as the flow rate is a candidate | later |
| Elements ARSO does not describe pass both validators. Describe those the interface and the control need (operation type, browse path, owning object, data type, key, an action's input and output; a skill's Methods, ErrorReference and Results, the module's commands) and leave the descriptive ones (title, unit, observable, synchronous, security)? Not done with 1.1 | 1.4 |
| The generation tool's builder still writes a Capability's meaning as its semanticId and no Kind; change it to the form of IDTA 02020 (both are accepted now)? | later |
| A running program does not tell a constant that was bound to a step from a default that was left. When the profile is made from the program (1.2), does a step list every parameter of its skill, or only those that differ from the default? | 1.2 |
| The module specs (YAML) hold what the AAS does not: which output or input of the controller an equipment item is wired to, per target. Without them a program cannot be generated. **7 Oct: they stay for now.** Describing the wiring in the AAS is an idea to work out later (there are sources that do it) | later |
| The module AAS is too large and its Skills submodel too complex (7 Oct). The structure reached on 8 Oct, shown as a mock-up of the whole line on the local AAS server (`LineProposalAAS`, six `<Name>ModuleProposalAAS`, twelve component AASs): the module's own commands in a submodel of their own (Module); a skill is a collection whose semantic id says primitive or composite and whose `SemanticId` says what it does; it holds a command each for Start, Stop, Abort and Reset (generic semantic ids), a command holding its interface reference, an Operation named like it and, where it runs something, its steps (P1, P2, ...): a reference to the skill a step runs and one element per connected variable (a constant, or a reference to a variable of the command's Operation). Parameters, results and the error are variables of the Operation; no Uses, no Parameters, no references to state or results (the mapping configuration does that). The primitives are in the AAS of their component; the kind of resource is the asset type. Sequences only; a richer description of the logic (BPMN or similar) may follow. Not built yet: it changes the shape of ARSO's skill, which the AAS generation project builds and validates too, and what modlink and the HMI read. Proposed in the mock-up, to be confirmed: the kind of a resource as its asset type (`.../Resource/Component/LinearAxis`); a product's parameter reaches a skill by meaning, the skill's input variable carrying the semantic id of the capability property it takes, with no reference from skill to capability. Open: two components of one kind in one module (the cameras) need one skill name twice; what a component's AAS holds besides its skills; and from before, leaving step values out of the interface description and Operational Data in groups | 1.2 |
| The steppers' wiring and numbers: driver type and pins, steps per millimetre and step rate (the specs assume 20 mm/s and 60 mm of travel), which end the limit switch is at; and whether the Raspberry Pi 5 set up on 8 Oct replaces the Pi 4 as the filling module's target (on a Pi 5 GPIO18 is PWM channel 2, not 0) | wiring a module |
| The documents for an HMI (`docs/hmi/opcua-*.md`) describe the modules before 8 Oct in their sections on equipment and skills; the script that wrote them is not in the repository. Write it anew, from the module description and the running controller? | later |
| The plan is a submodel of the product AAS, as the planner writes it. Does it become an AAS of its own (a process AAS per product and line, as AProSO describes)? | 2.2 |
| Later, if needed: a binding whose value is an expression over the skill's parameters; a station setting (such as the flow rate) held once in the Parameters submodel and bound by every step that uses it | later |
| The agents are software agents in a framework such as SPADE; their inner structure (BDI, fixed plans) is not settled | 2.3 |
| Which changes does the paper show? | 3.1 |

Facts only you or the lab have: the measured values of each station (fill range and accuracy,
diameters) and the flow rate; whether we may publish to the lab's AAS server. One module is being
wired to its Pi now.
