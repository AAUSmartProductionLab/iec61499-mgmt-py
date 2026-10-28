# Paper outline (CIRP CMS 2026, six pages, due 18 Nov)

A draft of 28 Oct, for the authors. Each paragraph of the paper as a topic sentence, then why we
chose it and instead of what. Citation keys are in [paper-references.bib](paper-references.bib). DD n
points to [design-decisions.md](design-decisions.md), where each reason is given at length.

## The argument

1. Modular production makes changeovers frequent, but a module's behaviour is its vendor's control
   program, changed in the vendor's tools [schwoerer2025modular].
2. Every module ships with an AAS that describes its skills and capabilities. Yet planning from AAS
   models only sequences skills that modules already have, and adds planning-specific submodels to
   do so [bernhard2024leverage, nabizada2026capability, schwoerer2026fond].
3. IEC 61499 changes running programs through standard management commands, and skill-based work
   generates orchestrators from production plans [dorofeev2021orchestrator]. The module's own
   description does not drive these changes.
4. We make the AAS the desired state of the module's IEC 61499 program. Fixed rules make every
   composite skill a network of block instances that can be read back, compared and created online.
5. The module's standard Capability Description (IDTA 02020) is also its planning domain. The module
   plans a composite skill for a requirement that no skill meets, and creates it online like any
   described skill.
6. On a filling module, a skill nobody wrote is planned in milliseconds and created online in 0.04 s
   while another skill keeps running. A restart stops the module for 3.3 s.

## Budget

| Section | Words | Figures, tables |
| --- | --- | --- |
| Abstract | 170 | |
| 1 Introduction | 400 | |
| 2 Related work | 550 | Table 1 |
| 3 Concept and method | 1,250 | Figs. 1 to 3 |
| 4 Case study and evaluation | 600 | Fig. 4, Table 2 |
| 5 Discussion and conclusion | 280 | |
| References | about 26 | |

Our CIRP CMS 2025 paper [jensen2026service] had 4,250 words in all, with 17 references and six
figures and tables.

This outline cites 36 works; the paper keeps about 26. The first to drop: zoitl2006dynamic,
dai2017self, dorofeev2019agile, koecher2022model, klose2019orchestration, martin2021plansys2,
bennulf2021goal, blair2009models, scala2016interval, godet2022chronicles.

Section 3 below runs to about 1,200 words, close to the section's budget: each bullet is meant to
become one sentence of the paper.

## 1 Introduction

1. **Pharmaceutical production moves to small batches built from modules** [schwoerer2025modular].
   The behaviour of each module is the vendor's control program.
2. **Our earlier work orchestrated modules** [jensen2026service] **and planned line-level policies
   from their AASs** [schwoerer2026fond], but both take a module's skills as given.
   [jensen2026service] names two limits: hand-written orchestration, and MQTT messaging without the
   real-time guarantees that low-level control needs. This paper turns to the module itself.
3. **The claim:** *a module delivered with an IEC 61499 program and an AAS can be verified, operated
   and changed online from those two alone; new skills are planned from its skill and capability
   models and created online the same way.*
4. **Contributions**, in the order of Section 3: the module architecture (C3); the skill and
   capability models (C1); updating a running module (C4); planning new skills (C2). One filling
   module shows all four.

## 2 Related work and gap

1. **Composing skills.**
   - Skills are built from device primitives and check their pre- and postconditions
     [pedersen2016robot, schou2018skill].
   - CSS separates a capability from the skill that executes it
     [koecher2020formal, koecher2023reference, css2022].
   - Skills have been modelled as OPC UA programs [dorofeev2018skill]. Orchestrators are generated
     from skill interfaces and a production plan [dorofeev2021orchestrator].
   - Behaviour trees compose skills on PLCs and IEC 61499 controllers
     [sidorenko2024bt, sidorenko2024composition], or orchestrate modules from outside
     [jensen2026service].
   - Skill code is generated from SysML [koecher2022model]. MTP modules offer services that an
     orchestration layer calls [klose2019orchestration].
   - *Where it stops:* compositions are designed or generated at engineering time and deployed;
     the running program is not read back and checked against its description.
2. **Changing IEC 61499 programs online.**
   - Management commands create, connect and start blocks at run time [iec61499], with no downtime
     [zoitl2006dynamic, rooker2007zero].
   - Agents reconfigure the low-level control from an ontology of it [lepuschitz2011self].
   - Autonomic service management modifies software automatically [dai2017self].
   - A device adapter keeps a device description current and adapts the software
     [dorofeev2019agile]. A PLC reads its configuration from its AAS [wenger2018connecting].
   - *Where it stops:* the change comes from an engineering tool or an agent's own knowledge. Where
     the AAS is used, it configures a fixed program; it does not describe behaviour to build.
3. **Planning from capabilities.**
   - IDTA 02020 and the CSS extensions give capabilities property and transition constraints and
     compositions [idta02020, css2025].
   - Capability sequences are planned with SMT from a capability ontology [koecher2024smt].
   - PDDL is generated from condition elements in the AAS [bernhard2024leverage] or from planning
     submodels per component [nabizada2026capability]. A dedicated planning submodel feeds FOND
     policies run as behaviour trees [schwoerer2026fond].
   - In robotics, PDDL is generated from skills' pre- and postconditions and executed as behaviour
     trees [mayr2023skiros2, martin2021plansys2]. Agents meet parts' goals with skill sequences
     [bennulf2021goal].
   - *Where it stops:* the plans sequence skills that resources already have, for an orchestrator.
     The AAS-based works keep the planning knowledge in a model beside the capability model.
4. **Gap.** No work combines the three at the level of a module: the module's standard AAS as the
   desired state of its control program; new skills planned from its capability model with nothing
   planning-specific added; and the result created in the running program, verified and recorded,
   so the line can use it.

**Table 1** compares the works on five points:
- where new behaviour comes from;
- whether it is planned, and at which level;
- where it runs;
- whether it is changed online and verified;
- whether the AAS is the source.

The "where it stops" claims, and Table 1's cells for [dorofeev2018skill, dorofeev2019agile,
dorofeev2021orchestrator, rooker2007zero, lepuschitz2011self], rest on abstracts and are to be
confirmed in the full texts.

## 3 Concept and method

### 3.1 Concept (200 words, Fig. 1)

1. **The AAS is the desired state of the module's IEC 61499 program.** An engineer or the module's
   planner edits the AAS. A reconciler then brings the running program to it, verifies the change
   and records it [blair2009models].
   - *Why the AAS:* every module ships with it, and every client already reads it, such as the line's
     orchestrator [jensen2026service]. The integrator has the AAS but not the vendor's project.
   - *Instead of:* the vendor's spec, which the integrator lacks; the running program, which says
     what is, not what is wanted; or a change recipe, which must agree with the AAS (DD 1.1).
2. **Three levels, each composing only the one below.** Components offer primitive skills; a module
   composes them into composite skills, planned here; the line orchestrates modules
   [jensen2026service, schwoerer2026fond].
   - *Why:* a module's knowledge is local and its problem small. Relational problems (carriers,
     products, uncertain outcomes) stay with the line, as in device primitive, skill and task
     [schou2018skill].
   - Changing (management protocol) and operating (OPC UA) are kept apart (DD 1.4).

### 3.2 Module architecture (C3, 300 words, Fig. 2)

1. **Fixed rules make a composite skill data, not code.**
   - A fixed shell: occupation, PackML state, equipment blocks that own their IO, one INIT chain.
   - A primitive skill is a block type: one equipment command, until a sensor or a time ends it.
   - A composite skill is a subapplication of instances only. Its parallel blocks and decisions come
     from three library blocks, and the rules draw its wiring.
   - Every skill shares one state machine.
   - *Why:* every IEC 61499 runtime creates instances and connections online. Loading a new type is
     optional (FORTE needs a Lua loader for it, and cannot load service interface blocks at all).
     Instances also keep each step visible, both for reading back and for monitoring (DD 2.4).
   - *Instead of:*
     - a type per skill, which means a build per skill;
     - a behaviour-tree interpreter in the controller [sidorenko2024bt], which turns the sequence
       into data the IDE cannot show;
     - orchestrating primitives over MQTT [jensen2026service], which has no real-time guarantees.
2. **A new skill touches nothing that runs.** Equipment and occupation are reached over local
   publish/subscribe channels, so a new composite joins the program by one connection, at the end
   of the INIT chain. Downtime is zero by construction rather than by ordering reconfiguration steps
   [rooker2007zero] (DD 2.3).
3. **What may change online follows.** Values and new composites change online; a reordered or
   removed skill needs a restart; a new primitive or new IO needs a build (DD 2.10).
4. **The rules are the contract, not our generator.** Generation is compositional, so reading a
   program back is a parse, and a hand-written module in the same shell works alike (DD 1.3).

### 3.3 Skill and capability models (C1, 300 words, Fig. 3 left)

The models are written in ARSO [jensen2026ontology], as extended in this work (version 0.12).

1. **A skill is its commands; a composite also has its flow.**
   - Commands are Operations: parameters with unit, limits, default and meaning, plus results.
   - A composite's flow uses the process planner's recipe elements: step, bindings, parallel,
     decision.
   - `Deployment` (Described or Built) gives matching a third answer: offered after a reconfiguration
     (DD 3.2 to 3.4).
2. **The Capability Description is the planning domain; nothing planning-specific is added.**
   - Offered process capabilities (Filling); one set per component of capabilities realized by its
     primitives (Dosing by Dispense).
   - Constraints are 02020 property constraints [idta02020, css2025]: Pre, Post or Invariant, one
     operator each (`= 40.0`, `+= Volume`, `unchanged`).
   - Properties name their data points (`SameProperty`). The planner's state, the live start state
     and the skill's run-time checks are thus the same signals.
   - Kind-level constraints are written once, in the vocabulary. Per module only the integration
     constraints are written: 4 of the filling module's 16 (DD 3.9).
   - *Why not a planning submodel* [bernhard2024leverage, nabizada2026capability, schwoerer2026fond]:
     - It restates pre- and postconditions the capability model already holds, and drifts from them.
     - It makes the engineer model types, predicates, objects and deletes: 77 AAS elements for one
       action in [nabizada2026capability].
     - Inside a module the cast is fixed, so its state is a handful of values and the deletes can be
       generated.
     - Execution constraints, which are hard to state as CSS constraints [schwoerer2026fond] (is the
       module occupied, is it operational), are the shell's business.
     - PDDL and HDDL are still available: generated, not modelled.

### 3.4 Updating a running module (C4, 200 words)

1. **Verification is an equation:** `read(Π) = described(A)`. The program Π is read back over the
   management protocol and parsed by the rules; the AAS A gives the same structure.
2. **Reconfiguration applies the least disruptive change, and proves it.**
   - Values are written while the module is neither executing nor occupied; new composites are
     created in any state; everything else is refused as needing a restart.
   - It then reads back and compares again, appends to the boot file, and records the skill as Built
     with its interface, so clients find it by reference unchanged.
   - *Why:* each step answers a question the engineer would otherwise check by hand: is it what the
     AAS says, possible online, done, persistent, usable? (DD 4.1)
   - *Instead of:* a new boot file, which stops the module; or deploying without reading back. The
     generator's own function creates the skill, so the changed program and a generated one are
     identical by construction (DD 4.2).

### 3.5 Planning a composite skill (C2, 300 words, Fig. 3 right)

1. **The module plans a composite skill for a requirement that no skill meets.** The goal is the
   capability's postconditions with the requested values, the state the requested results need,
   then the rest state (what Reset leaves).
2. **HTN with goal regression: the integrator's way first, generated methods last**
   [nau2021gtpyhop].
   - Methods, in order: the capability's 02020 compositions; existing composites, inlined; then
     goal regression over the component capabilities.
   - `+=` beyond one dose is reached in the fewest equal doses. The first plan found is taken.
   - *Why HTN:* compositions and existing skills carry the engineer's conventions, so plans read like
     the skill an engineer would write. A classical planner's plans were valid but weighed the empty
     vial first.
   - *Why deterministic and first-found:* a composite is one controller's deterministic sequence;
     the line decides what is optimal; branching outcomes belong to the line's FOND policies
     [schwoerer2026fond], which complement this.
3. **Lifting gives parallel blocks.** Steps stay ordered if they share a component, or if one
   changes a state the other needs, changes or keeps. The rules draw the wiring, so a flow is all a
   plan must produce.
4. **The same model checks and discovers.**
   - Check: an unmet precondition is reported with the step that fixes it.
   - Discover: a capability the module can plan but has no skill for is offered after a
     reconfiguration.
   - Assumptions, stated: a few known values; numbers only added and compared; no time; rest at both
     ends.

## 4 Case study and evaluation (600 words)

**Setup.**
- The filling module (axis, pump, scale) and the stoppering module (axis, piston) of
  [jensen2026service].
- FORTE on a PC with simulated IO, and on a Raspberry Pi 5.
- The AASs on a BaSyx server, checked against ARSO [jensen2026ontology].

**Measures**, with the practice borrowed from related work. E1 to E4 are core; E5 to E9 go in if space
allows.

| # | Question | Measure (borrowed from) | State |
| --- | --- | --- | --- |
| E1 | Online without stopping? | Change, verify and down time against a restart [rooker2007zero] | PC: 0.02 to 0.04 s against 3.3 s (a value is written in Idle: 2.2 s back to Execute); Pi 5 to do |
| E2 | Planned skills right? | T1 to T12 against the module's own skills; an independent validator; run on FORTE | Done |
| E3 | Planning cost and scaling? | Time against Aries on HDDL [godet2022chronicles, hoeller2020hddl] and ENHSP on PDDL [scala2016interval], and against plan size [schwoerer2026fond, nabizada2026capability] | 1 to 2 ms (GTPyhop), 41 to 66 ms (Aries), 282 to 348 ms (ENHSP). Probe, 1 to 20 doses: GTPyhop 2 to 4 ms, ENHSP 0.37 s, Aries 0.08 to 6.8 s; medians to do |
| E4 | What must be modelled? | Constraints written per module; planning AAS elements; PDDL/HDDL never written [nabizada2026capability] | Filling: 16 constraints (102 elements), 4 written for the module; its HDDL (9 tasks, 17 methods, 5 actions) generated. Stoppering: 9 constraints, 2 written |
| E5 | Plan quality? | Against the skill an engineer wrote | GTPyhop: the module's Dispensing. Aries: same steps, but MoveAxis(0) for Home. ENHSP: weighs the empty vial first |
| E6 | Edits for a new requirement? | Description edits needed [schwoerer2026fond] | None for 15 mL; stoppering reuses the vocabulary |
| E7 | Clients unchanged? | A skill built online, run by modlink from the AAS | DoubleDose done; add to the scenarios |
| E8 | Repeatable? | Successful runs out of N [schwoerer2026fond] | 5 of 5 per scenario; N = 50 to do |
| E9 | How big is a composite? | Function blocks per skill [dorofeev2019evaluating] | 5 to 23 instances, 31 to 98 connections, 64 to 224 commands |

**Table 2** gives E1 and E3; **Fig. 4** is `figures/evaluation-downtime.pdf`. To do: the planned
scenario still plans 2.0 mL, which Dispensing already does; it should plan 15 mL.

## 5 Discussion and conclusion (280 words)

- **What cannot change online, and why.** Next: delete and create while the module is idle.
- **Plans are only as right as the constraints.** T12: without "needle at the fill position" the plan
  fills with the needle up. Taring is open. Hence the checker in the editor and a review before
  building. Every change is a verified and recorded AAS difference, which suits GMP.
- **Module and line are complementary.** A planned composite is one new action for the line's planner
  [schwoerer2026fond], and the module's constraints could seed the line's domain.
- **Outlook:** agents that call the planner; the Pi 5 runs; locations from Hierarchical Structures.

## Figures and tables

| | Content | Source |
| --- | --- | --- |
| Fig. 1 | Two artefacts; verify, operate, change, plan; three levels | `figures/reconfiguration-pipeline.drawio`, redraw smaller |
| Fig. 2 | A skill as blocks | `figures/skill-blocks.drawio` |
| Fig. 3 | Capability Description, then the 15 mL plan and its flow | `figures/capability-description.drawio` and `figures/planned-skill.drawio`, merged |
| Fig. 4 | Downtime, online and by restart | `figures/evaluation-downtime.pdf` |
| Table 1 | Related work against the gap | New |
| Table 2 | Change, verify and planning times | `cell/eval/results` |

## Terms

- **Module** (a CPPM [jensen2026service]) and **component**.
- **Primitive skill** and **composite skill**, the AAS kinds; the docs say "module level skill" for a
  composite.
- **Offered capability** and **component capability**.
- **Precondition, postcondition, invariant.**
- **Requirement, flow, rest state.**
- **Described and built.**
- **Verify, reconfigure, record.**

## For the authors to decide

| Question | Proposal |
| --- | --- |
| "Composite skill" instead of "module level skill", in paper and docs | Yes: the AAS kind and the literature's word |
| The planned scenario to 15 mL | Yes, before the Pi runs |
| Taring | Decide before 3.5, or name it as a limit |
| The full texts behind Table 1 | [dorofeev2018skill, dorofeev2019agile, dorofeev2021orchestrator, rooker2007zero, lepuschitz2011self] |
