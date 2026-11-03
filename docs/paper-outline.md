# Paper outline (CIRP CMS 2026, six pages, due 18 Nov)

A draft of 28 Oct, for the authors; its numbers are those of the runs of 29 Oct (`cell/eval/results`).
Each paragraph of the paper as a topic sentence, then why we chose it and instead of what. The paper
has a narrow scope: restructuring a running IEC 61499 module through its AAS. What goes deeper (the
capability model, planning, agents) is kept for the journal papers, in
[journal-paper.md](journal-paper.md) (the models) and [orchestration-paper.md](orchestration-paper.md)
(planning and agents). Citation keys are in
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
5. On a filling module, a new skill takes 131 to 155 user actions by hand in 4diac, 19 to 22 in the
   skill editor and 3 when planned. It is created online in 0.05 s while another skill keeps
   running, where a restart stops the module for 3.3 s.

## Budget

| Section | Words | Figures, tables |
| --- | --- | --- |
| Abstract | 170 | |
| 1 Introduction | 400 | |
| 2 Related work | 500 | Table 1 |
| 3 Concept and method | 1,200 | Figs. 1 to 3 |
| 4 Evaluation | 650 | Fig. 4 and one or two more, Table 2 |
| 5 Discussion and conclusion | 300 | |
| References | 17 | |

Our CIRP CMS 2025 paper [jensen2026service] had 4,250 words in all, with 17 references and six
figures and tables.

## 1 Introduction

1. **Pharmaceutical production moves to small batches built from modules** [schwoerer2025modular].
   Restructuring a module's behaviour, such as another sequence or filling from the bottom, means its
   control program: the vendor's project, the IDE and a restart.
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

Drafted in LaTeX on 1 Nov: [paper/cirp/method.tex](paper/cirp/method.tex), with the design
considerations below written in, about 2,000 words to cut down to the budget. Sources still to add are
marked `\todocite`.

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
| E1 | How much effort is a new skill? | User actions, as [dorofeev2021orchestrator] counts them: by hand in 4diac, in the skill editor, planned (`cell/eval/effort.py`) | By hand 131 to 155; editor 19 to 22; planned 3 (Dispensing, BottomUpFilling, a planned 15 mL; 29 Oct) |
| E2 | Does it reach the running module without stopping it? | Change, verify and down time, online against a restart (`cell/eval/scenarios.py`) | PC, 29 Oct: a new skill 0.05 s with the running skill kept running, a value 0.03 s (the module out of Execute 2.2 s), against 3.3 s down by a restart; the changeover of both modules 3.2 s down online (the stoppering module, for its value) against 7.1 s. Pi 5 to do |
| E3 | Is the result right? | Read back equals the AAS, before and after a restart; a planned skill equals the hand-written one (T2, T5); it runs on FORTE | Done |

**Figs. 5 and 6** are the effort (E1) and the downtime (E2), drawn by `cell/eval/figures.py` into
[paper/cirp/figures](paper/cirp/figures), the downtime with the changeover. **Table 2** keeps the
commands and the times of change and verify.

To do:
- The planned scenario plans 2.0 mL; it should plan 15 mL.
- Count E1 for the Pi deployment as well: the IDE route then also includes the restart.

### Proposal of 1 Nov: test what only this method does (to decide)

**Why change.**
- E1 counts user actions as [dorofeev2021orchestrator] counts them, and our composite made from a flow
  is close to their generated orchestrator. With their measure as well, the paper reads as a variant
  of theirs.
- E2's zero downtime is the classic claim of [rooker2007zero].
- The plan of September ([archive/build-and-modelling-plan.md](archive/build-and-modelling-plan.md),
  "Evaluation plan") left effort out for this reason.
- What no other work has is the closed loop: the AAS as the desired state, the program read back and
  reconciled to it, and a new skill from a product's requirement. The evaluation should test that loop.

| # | Question | Measure | Baseline | Needs |
| --- | --- | --- | --- | --- |
| R1 | Does the program stay what its AAS says? | Differences injected n times per kind. Into the program: a value written from the IDE, a connection deleted, a stray instance, a composite half created. Into the AAS: a value, a new step, a reordered flow, a removed skill. Each is to be detected, classified (online, restart, record) and repaired where allowed. Also: a reconfiguration cut after each of its k commands and run again must converge | A deployment that does not read back (the IDE's) | A harness (`cell/eval/drift.py`); modsync completing a half-created described composite (today it asks for a restart) |
| R2 | Does a change reach the running machine without disturbing it? | On the physical filling module: the running skill's step times and axis motion, with and without a change made meanwhile. The internal setup time of the control change (SMED), online against a restart; on the machine a restart also re-references the axis and re-occupies the module | A restart | Runs at the bench; step times from OPC UA timestamps |
| R3 | Which products can the module take, and do they come out right? | Product variants: volumes within one dose and above it, with and without weighing, from the bottom for a syringe, the scale removed. Each is offered now, after a reconfiguration, or not. Each planned skill runs on the simulated module, and the product's content and weight are compared with the requirement | Matching against the built skills only | A process model in the simulator: volume into the container while the needle is in it, weight on the scale |
| R4, if time | Does the checker catch the faults that matter? | Every single edit of Dispensing (a step deleted, swapped, duplicated or inserted; a bound value changed). The checker's verdict is compared with the product's outcome in the process model: precision and recall | A structural check (types and connections, what the IDE checks) | R3's process model |

- **Effort:** no longer a research question; at most one sentence.
- **Size:** stays an analytic argument. n parallel branches are 2ⁿ states in a generated type
  [dorofeev2021orchestrator], and one join block here.
- **Figures:** R2 as a timeline of the running skill's steps with the change marked; R1 and R3 as
  tables or one small chart.

**Against other approaches (1 Nov, to decide).** R1 to R4 measure the method against weaker
versions of itself. These put other approaches on the same module and the same task, so that each
side wins something:

| # | Compared with | Measured on the same task | What each side should win | Needs |
| --- | --- | --- | --- | --- |
| C1 | An outside orchestrator: a client calls the primitives one by one over OPC UA, as skill-based control usually composes [koecher2023reference, sidorenko2024composition] | Dispensing on the physical module, n runs each: the gap between steps, the cycle time and its spread; the network cut during a run; a step's condition broken during a run | Outside: a new sequence needs no change in the controller at all. Ours: timing, and the module finishes or stops safely on its own (no needle left in the vial) | A small orchestrator on modlink (the primitives have the same OPC UA methods; to verify); runs at the bench |
| C2 | A generated orchestrator type [dorofeev2021orchestrator] | The same skills with 1 to 4 parallel branches: states and blocks; whether the new skill can be added online (a new type needs a type loader in FORTE, else a restart) | Theirs: one block to read. Ours: online, and growing linearly | A generator of the ECC (about a day), or the size argument only |
| C3 | Standard planners on the domain generated from the AAS: Aries (HDDL), ENHSP (numeric PDDL) | R3's product variants: solved, time, plan length, the makespan after lifting | Standard planners: speed and generality. GTPyhop: the integrator's compositions first, numbers and invariants | Built (`cell/eval/planners.py`); the variants added |
| C4 | AAS2PDDL [nabizada2026capability] | The filling module modelled in their four planning submodels: AAS elements needed, what can be stated (numbers, invariants, task structure), the plans | Theirs: many objects and relations (transport). Ours: nothing planning-specific added | Modelling the module in their metamodel (about half a day) |
| C5 | Reported numbers | Downtime of an online change [rooker2007zero], call overhead of OPC UA skills, planning times [nabizada2026capability] | One table, each setup named | Reading |

Recommendation: C1 and C3 in the paper, C4 as one sentence with its numbers, C2 and C5 only if room
is left.

## 5 Discussion and conclusion (300 words)

- **The effort moves into the AAS,** and from there into the module's capabilities. As in
  [dorofeev2021orchestrator], the more steps a skill has, the bigger the saving.
- **What cannot change online, and why.** Next: delete and create while the module is idle.
- **Plans are only as right as the constraints:** without "needle at the fill position" the plan
  fills with the needle up (T12).
- **Further work, in the journal paper:** the capability model and its planning in depth; agents that
  call the planner when they accept a request; line-level orchestration.

## Figures and tables

Drawn on 1 Nov, in [paper/cirp/figures](paper/cirp/figures). The diagrams are the pages of
[figures/cirp-figures.drawio](figures/cirp-figures.drawio), exported by
`python docs/figures/export_pdf.py docs/figures/cirp-figures.drawio docs/paper/cirp/figures`;
the evaluation's charts are in [paper/cirp/figures-evaluation.tex](paper/cirp/figures-evaluation.tex).
The skill hierarchy was folded into Fig. 1 on 1 Nov. The evaluation's figures follow section 4's
proposal; if space runs out, Fig. 3 goes first.

| | Content | Source |
| --- | --- | --- |
| Fig. 1, two columns | The pipeline over the three levels (rows): the assets as small icons (the line on its planar table, the filling module, its components), their AASs, the tools, the running system; change over the management protocol, operate over OPC UA, the restart as the baseline | `cirp-figures.drawio`, page pipeline |
| Fig. 2 | A skill in the AAS and the blocks it becomes, in numbered pairs | page aas-to-blocks |
| Fig. 3 | A planned skill: goal regression, the lifted flow. Proposed 1 Nov (to decide): replaced by page product-to-process, the product's, module's and process's AASs as trees: (1) the requirement, (2) the match, (3) the plan, (4) the skill built online, (5) the process AAS binding step, module and skill. Goal regression is then text only | page planned-skill; page product-to-process |
| Fig. 4 | The filling module, drawn and as built, its parts numbered alike | page filling-module; the photo to come (`figures/filling-module-photo.jpg`) |
| Figs. 5, 6 | Effort (E1) and downtime (E2), until section 4's proposal is decided | `cell/eval/figures.py` |
| Table 1 | Related work against the gap | New |
| Table 2 | Commands, times of change and verify | `cell/eval/results` |

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
