# Paper outline (CIRP CMS 2026, six pages, due 18 Nov)

A draft of 28 Oct, for the authors. Each paragraph of the paper as a topic sentence, then why we
chose it and instead of what. The paper has a narrow scope: restructuring a running IEC 61499 module
through its AAS. What goes deeper (the capability model, planning, agents) is kept for the journal
paper, in [journal-paper.md](journal-paper.md). Citation keys are in
[paper-references.bib](paper-references.bib); at most 17 are cited (list at the end). DD n points to
[design-decisions.md](design-decisions.md); considerations found while coding go into
[design-log.md](design-log.md).

## The argument

1. Modular production makes changeovers frequent, but a module's behaviour is its vendor's control
   program: restructuring it means the IDE, the vendor's project and a restart [schwoerer2025modular].
2. Every module ships with an AAS that describes its skills. Yet the AAS is only read: skill
   compositions are generated at engineering time from a given sequence and deployed as new block
   types [dorofeev2021orchestrator], and plans from AAS models only sequence skills a module already
   has [nabizada2026capability, schwoerer2026fond].
3. We make the AAS the desired state of the module's IEC 61499 program. Fixed rules make every
   composite skill a network of block instances, so a skill described in the AAS is created in the
   running program online, verified by reading it back, and recorded.
4. A new skill is described in the AAS in a skill editor, or planned by the module from its
   standard Capability Description.
5. On a filling module, a new skill takes 131 to 151 user actions by hand in 4diac, 19 to 26 in the
   skill editor and 3 when planned. It is created online in 0.04 s while another skill keeps
   running, where a restart stops the module for 3.3 s.

## Budget

| Section | Words | Figures, tables |
| --- | --- | --- |
| Abstract | 170 | |
| 1 Introduction | 400 | |
| 2 Related work | 500 | Table 1 |
| 3 Concept and method | 1,200 | Figs. 1 to 3 |
| 4 Evaluation | 650 | Fig. 4, Table 2 |
| 5 Discussion and conclusion | 300 | |
| References | 17 | |

Our CIRP CMS 2025 paper [jensen2026service] had 4,250 words in all, with 17 references and six
figures and tables.

## 1 Introduction

1. **Pharmaceutical production moves to small batches built from modules** [schwoerer2025modular].
   Restructuring a module's behaviour, such as another sequence or a second dose, means its control
   program: the vendor's project, the IDE and a restart.
2. **Our earlier work orchestrated modules from their AASs** [jensen2026service] and planned
   line-level policies from them [schwoerer2026fond], but both take a module's skills as given.
   [jensen2026service] names two limits: hand-written orchestration, and MQTT without the real-time
   guarantees that control below the skill level needs. This paper turns to the module itself.
3. **The claim:** *a module delivered with an IEC 61499 program and an AAS can be restructured from
   its AAS alone: a new skill, described in the AAS or planned from its capabilities, is created in
   the running program online, verified and recorded.*
4. **Contributions:**
   - the module architecture that makes a skill data rather than code (C1);
   - the AAS as the desired state, with the program reconciled to it online (C2);
   - authoring a new skill in the AAS, by hand or by planning (C3);
   - an evaluation of effort, downtime and correctness on a filling module.

## 2 Related work and gap

1. **Composing skills on controllers.**
   - Skills are built from device primitives [schou2018skill]. CSS separates a capability from the
     skill that executes it, and gives skills a common state machine [koecher2023reference].
   - Dorofeev et al. generate a composite skill from a given orchestration sequence and from skill
     interfaces modelled as IEC 61499 adapters. The result is one new basic function block; its
     parallel steps grow the state machine as 2ⁿ. Their stated future work is to keep the skill
     description in the AAS [dorofeev2021orchestrator].
   - Behaviour trees compose skills inside reconfigurable modules on IEC 61499 controllers
     [sidorenko2024composition].
   - *Where it stops:* compositions are made at engineering time and deployed as new types or trees.
     The running program is not read back and compared with its description.
2. **Changing IEC 61499 programs online.**
   - Management commands create, connect and start blocks at run time [iec61499], with no downtime
     [rooker2007zero].
   - Agents reconfigure the low-level control from an ontology of it [lepuschitz2011self].
   - A PLC reads its configuration from its AAS [wenger2018connecting].
   - *Where it stops:* the change comes from an engineering tool or an agent's own knowledge. Where
     the AAS is used, it configures a fixed program; it does not describe behaviour to build.
3. **Planning from capabilities.**
   - Capability sequences are planned with SMT from a capability ontology [koecher2024smt].
   - PDDL is generated from conditions in the AAS [bernhard2024leverage] or from planning submodels
     per component [nabizada2026capability]. A dedicated planning submodel feeds FOND policies run as
     behaviour trees [schwoerer2026fond].
   - *Where it stops:* plans sequence skills that resources already have, for an orchestrator.
4. **Gap.** No work makes the module's standard AAS the desired state of its control program, so
   that a new skill, written there or planned, becomes part of the running program online, verified
   and recorded.

**Table 1** compares the works on four points: where new behaviour comes from; where it runs;
whether the running program is changed online and verified; and whether the AAS is the source.
Dorofeev et al. is confirmed from the full text. For Rooker et al. and Lepuschitz et al. we have the
abstracts only.

## 3 Concept and method

### 3.1 Concept (200 words, Fig. 1)

1. **The AAS is the desired state of the module's IEC 61499 program** [jensen2026ontology]. An engineer
   or the module's planner edits the AAS. A reconciler then brings the running program to it,
   verifies the change and records it.
   - *Why the AAS:* every module ships with it, and every client already reads it, such as the line's
     orchestrator [jensen2026service]. The integrator has the AAS but not the vendor's project.
   - *Instead of:* the vendor's project, which the integrator lacks; the running program, which says
     what is, not what is wanted; or a change recipe, which must agree with the AAS (DD 1.1).
2. **Three levels, each composing only the one below.** Components offer primitive skills; a module
   composes them into composite skills; the line orchestrates modules [jensen2026service,
   schwoerer2026fond], out of scope here. The split is that of device primitive, skill and task
   [schou2018skill].

### 3.2 Module architecture (C1, 300 words, Fig. 2)

1. **Fixed rules make a composite skill data, not code.**
   - A fixed shell: occupation, PackML state, equipment blocks that own their IO, one INIT chain.
   - A primitive skill is a block type: one equipment command, until a sensor or a time ends it.
   - A composite skill is a subapplication of instances only. Its parallel blocks and decisions come
     from three library blocks, and the rules draw its wiring.
   - *Why:* every IEC 61499 runtime creates instances and connections online [iec61499]. Loading a
     new type is optional (FORTE needs a Lua loader for it, and cannot load service interface blocks
     at all). Instances also keep each step visible, for reading back and for monitoring (DD 2.4).
   - *Instead of:*
     - a new type per composite [dorofeev2021orchestrator], which needs a build or a type loader,
       and whose parallel steps grow as 2ⁿ states (ours: one join block);
     - a behaviour-tree interpreter [sidorenko2024composition], which turns the sequence into data
       the IDE cannot show.
2. **A new skill touches nothing that runs.** Equipment and occupation are reached over local
   publish/subscribe channels, so a new composite joins the program by one connection, at the end
   of the INIT chain. Downtime is zero by construction (DD 2.3).
3. **What may change online follows.** Values and new composites change online; a reordered or
   removed skill needs a restart; a new primitive or new IO needs a build (DD 2.10).
4. **The rules are the contract, not our generator.** Generation is compositional, so reading a
   program back is a parse, and a hand-written module in the same shell works alike (DD 1.3).

### 3.3 The skill in the AAS (C2, 250 words, Fig. 3)

1. **A skill is its commands; a composite also has its flow.**
   - Commands are Operations: parameters with unit, limits, default and meaning, plus results.
   - A composite's flow uses the process planner's recipe elements (step, bindings, parallel,
     decision), so one editor serves products and skills.
   - Names join the AAS and the program: skill to subapplication, step to instance, parameter to
     latch.
2. **`Deployment` says Described or Built.** A described skill is one the module can get, so matching
   a requirement has a third answer: offered after a reconfiguration (DD 3.2 to 3.4).

### 3.4 Reconciling the running program (C2, 250 words)

1. **Verification is an equation:** `read(Π) = described(A)`. The program Π is read back over the
   management protocol and parsed by the rules; the AAS A gives the same structure.
2. **Reconfiguration applies the least disruptive change, and proves it.**
   - Values are written while the module is neither executing nor occupied; new composites are
     created in any state; everything else is refused as needing a restart.
   - It then reads back and compares again, appends to the boot file, and records the skill as Built
     with its interface, so clients find it by reference unchanged.
   - *Why:* each step answers what an engineer would otherwise check by hand: is it what the AAS
     says, possible online, done, persistent, usable? (DD 4.1)
   - *Instead of:* a new boot file, which stops the module; or deploying without reading back. The
     generator's own function creates the skill, so the changed program and a generated one are
     identical by construction (DD 4.2).

### 3.5 Authoring a new skill (C3, 200 words)

1. **In the skill editor:** the engineer writes the flow in the AAS, and the reconciler builds it.
2. **Planned:** the module's IDTA 02020 Capability Description holds, per component, capabilities with
   pre- and postconditions and invariants. The module plans a composite for a requirement with HTN
   and goal regression [nau2021gtpyhop], and lifts it to parallel blocks.
   - *Why no planning submodel* [bernhard2024leverage, nabizada2026capability]: inside one module the
     state is a handful of values, and the standard constraints already say what each capability
     needs and does. One sentence here; the argument in full goes to the journal paper.
3. **Either way the result is a described skill.** Section 3.4 builds it: planning needs nothing
   beyond the flow, because the rules draw the wiring.

## 4 Evaluation (650 words)

**Setup.**
- The filling module (axis, pump, scale) of [jensen2026service], and the stoppering module.
- FORTE on a PC with simulated IO, and on a Raspberry Pi 5.
- The AASs on a BaSyx server.

| # | Question | Measure | State |
| --- | --- | --- | --- |
| E1 | How much effort is a new skill? | User actions, as [dorofeev2021orchestrator] counts them: by hand in 4diac, in the skill editor, planned (`cell/eval/effort.py`) | By hand 131 to 151; editor 19 to 26; planned 3 (Dispensing, DoubleDose, 15 mL) |
| E2 | Does it reach the running module without stopping it? | Change, verify and down time, online against a restart (`cell/eval/scenarios.py`) | PC: 0.02 to 0.04 s against 3.3 s down; the running skill kept running. Pi 5 to do |
| E3 | Is the result right? | Read back equals the AAS, before and after a restart; a planned skill equals the hand-written one (T2, T5); it runs on FORTE | Done |

**Table 2** gives E1 and E2. **Fig. 4** is `figures/evaluation-downtime.pdf`.

To do:
- The planned scenario plans 2.0 mL; it should plan 15 mL.
- Count E1 for the Pi deployment as well: the IDE route then also includes the restart.

## 5 Discussion and conclusion (300 words)

- **The effort moves into the AAS,** and from there into the module's capabilities. As in
  [dorofeev2021orchestrator], the more steps a skill has, the bigger the saving.
- **What cannot change online, and why.** Next: delete and create while the module is idle.
- **Plans are only as right as the constraints:** without "needle at the fill position" the plan
  fills with the needle up (T12).
- **Further work, in the journal paper:** the capability model and its planning in depth; agents that
  call the planner when they accept a request; line-level orchestration.

## Figures and tables

| | Content | Source |
| --- | --- | --- |
| Fig. 1 | Two artefacts, the reconciliation loop, three levels | `figures/reconfiguration-pipeline.drawio`, redraw smaller |
| Fig. 2 | A skill as blocks | `figures/skill-blocks.drawio` |
| Fig. 3 | A skill in the AAS and its blocks; a planned flow | `figures/planned-skill.drawio`, adapted |
| Fig. 4 | Downtime, online and by restart | `figures/evaluation-downtime.pdf` |
| Table 1 | Related work against the gap | New |
| Table 2 | Effort and times | `cell/eval/results` |

## The 17 references

schwoerer2025modular, jensen2026service, schwoerer2026fond, jensen2026ontology, schou2018skill,
koecher2023reference, iec61499, dorofeev2021orchestrator, sidorenko2024composition, rooker2007zero,
lepuschitz2011self, wenger2018connecting, koecher2024smt, bernhard2024leverage,
nabizada2026capability, nau2021gtpyhop, and idta02020 (in 3.5).

Swap candidates:
- sidorenko2024bt (Procedia CIRP) for sidorenko2024composition;
- Lindorfer and Froschauer (INDIN 2019) for koecher2024smt. Their meta-model rules validate skill
  sequences, much as our checker does.

The rest of [paper-references.bib](paper-references.bib) is for the journal paper.

## Terms

- **Module** (a CPPM [jensen2026service]) and **component**.
- **Primitive skill** and **composite skill**, the AAS kinds. The docs still say "module level
  skill".
- **Requirement, flow, described and built.**
- **Verify, reconfigure, record.**

## For the authors to decide

| Question | Proposal |
| --- | --- |
| "Composite skill" instead of "module level skill", in paper and docs | Yes |
| The planned scenario to 15 mL | Yes, before the Pi runs |
