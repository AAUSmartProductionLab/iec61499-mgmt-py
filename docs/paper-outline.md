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

**3 Nov:** the paper's main file is on Overleaf (Elsevier CRC template, `elsarticle` 5p with `ecrc`),
with the title "Asset Administration Shell-driven reconfiguration of skill-based IEC 61499 devices" and
an abstract that frames the work in the product, process and resource AASs. Since 3 Nov the whole paper
is one file, [paper/cirp/paper.tex](paper/cirp/paper.tex), pasted into Overleaf as it is: no comments,
one line per paragraph, its 17 sources in [paper/cirp/references.bib](paper/cirp/references.bib). The page budget is now: introduction and
related work two pages and a little more; architecture and method at least two; evaluation one;
conclusion and references the last. The scope is wider again than on 28 Oct: the skill and product
hierarchies, both routes to a new skill (handcrafted, or planned from a product's requirement), the
check against the product's need, and planning in brief.

## Rescoped 7 Nov: three contributions on one pipeline

The planner moves in beside the model and the deployment, not in place of them. **Claim:** a
product's requirement, stated in its AAS, becomes a new skill running in a module's IEC 61499 program,
from the AASs alone: modelled (C1), planned (C2), deployed (C3).

| | Contribution | Section | Figure | Evaluated by |
| --- | --- | --- | --- | --- |
| C1 | **The PPR model in the AAS**: a product requires a capability with values and bounds; the process AAS binds its steps; the module and component AASs describe the skills down to the primitives; offered capabilities are derived from the skills, and capabilities carry pre, post, keep and rates on a vocabulary placed under DIN 8580 and VDI 2860 | 3.2 | Fig. 1 | Q4b matching (104/104, nothing offered that the module cannot do); E1 |
| C2 | **The planner**: a composite skill derived from the requirement and the components' capabilities, steps run in parallel at rates it sets where a bound requires it, checked in time; requested by Match and plan in the process planner | 3.3 | Fig. 2 (planned-bottom-up) | Q4a check (recall 90 %, precision 88 %); Q4b planning (23/23 right); Q4t (15/15 tracked fills right); E1 (6 inputs planned) |
| C3 | **The deployment**: a composite is a network of instances, so the reconciler creates it online, verifies it by reading the program back and records it | 3.4 | (Eq. 1) | Q1 (activation, commands, unavailability against redeployment); Q3 (drift) |

**Budget** (about 1,000 words a page, page 1 about 550 below the abstract; six pages leave about 4,000
words of text beside three figures, two tables and 17 references):

| Section | Words on 7 Nov | Target | Figures, tables |
| --- | --- | --- | --- |
| Abstract | 191 | 180 | |
| 1 Introduction | 790 | 600 | |
| 2 Related work | 495 | 420 | Table 1, a column "Planned" added |
| 3.1 Overview | about 220 | 180 | Fig. 1: pipeline-planning (two columns) |
| 3.2 The PPR model in the AAS (C1) | about 450 | 500 | |
| 3.3 Planning a composite from a requirement (C2) | about 330 | 600 | Fig. 2: planned-bottom-up (one column, trimmed to about 10 cm) |
| 3.4 Deploying it on the module (C3) | about 650 | 550 | |
| 4 Evaluation | 0 | 800 | Fig. 3: activation (Q1); Table 2: Q3, Q4, E1 |
| 5 Conclusion | 0 | 180 | |
| Text | 2,850 | about 4,000 | 3 figures, 2 tables |

**What goes, so that it fits:**
- Figs. aas-to-blocks and product-to-process leave the paper: Fig. 1 carries the PPR flow, the mapping
  takes two sentences. primitives-to-composite stays for slides and the journal.
- The shell (occupation, PackML, one holder per item) becomes one sentence; the comparisons of state
  machines with [dorofeev2021orchestrator, huang2026plug] go; the change classes take two sentences.
- BPMN, the skill editor and the handcrafted route: a sentence each. The abstract loses BPMN and the
  disturbance (Q2 was not run).
- Not in this paper: agents, orchestration, Q2, Q5, the time model beyond a paragraph (journal and
  orchestration paper).
- References: stolze2024proactive out, koecher2024smt in (capability planning with SMT, no durative
  actions: the gap the time model fills).

**Evaluation: no new experiments.** Q1 on the Pi (B3) if run at the bench, else the PC only, and said
so. Possibly one more E1 row at no cost: Match and plan, one press.

**Coping with the scope:** from 7 Nov nothing new is built for this paper, only the Pi runs and what
writing turns up as wrong. Every paragraph serves C1, C2, C3 or their evaluation; the rest goes to
[journal-paper.md](journal-paper.md) or [orchestration-paper.md](orchestration-paper.md). Order: the
method (3.2 to 3.4) first, then the evaluation, then introduction, related work, abstract and
conclusion against them, then cut to six pages in Overleaf.

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

Since 3 Nov (the pages as decided; the words are what the two-column template holds, about 1,000
a page, page 1 about 550 below the abstract):

| Section | Pages | Words | Figures, tables | Draft |
| --- | --- | --- | --- | --- |
| Abstract | (page 1) | on Overleaf | | Overleaf |
| 1 Introduction | 2 and a little, with section 2 | 750 | | 850 words, 3 Nov |
| 2 Related work | | 850 | Table 1 | 830 words and Table 1, 3 Nov |
| 3 Concept and method | 2 at least | 1,600 | Figs. 1 to 3 | 2,400 words, 1 Nov: to cut |
| 4 Evaluation | 1 | 600 | one figure, Table 2 | |
| 5 Discussion and conclusion | last page, with the references | 250 | | |
| References | | 17 at most | | [paper/cirp/references.bib](paper/cirp/references.bib), 3 Nov |

The first draft of sections 1 and 2 is about a quarter page over; the sentences to cut first are
marked `% cut first` in the two files.

The budget before (28 Oct): abstract 170 words, introduction 400, related work 500 with Table 1,
method 1,200 with Figs. 1 to 3, evaluation 650, conclusion 300, 17 references.

Our CIRP CMS 2025 paper [jensen2026service] had 4,250 words in all, with 17 references and six
figures and tables.

## 1 Introduction

Drafted on 3 Nov, now in [paper/cirp/paper.tex](paper/cirp/paper.tex) and condensed to four paragraphs the same day (structure paragraph cut, contributions inline). The draft had seven:
the setting and what IEC 61499 and the AAS promise; where the state of the art leaves it; our earlier
work; the approach in the abstract's terms (the three AASs, the module's fixed design, the translation
rules); the two routes to a new skill and the one path every change takes; the contributions C1 to
C4; the structure. The outline of 28 Oct it was written from:

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

Drafted on 3 Nov, now in [paper/cirp/paper.tex](paper/cirp/paper.tex), from the full texts
of the eight papers in `Papers-cirp-cms` and `Downloads/AAS-IEC61499-Paper` (not in the repository):
the four strands below, the gap, and Table 1. What the full texts changed:

- **Closest work: Huang et al. 2026** (IEC 61499 and MTP). An MTP file sent to the runtime is compared
  with what runs and turned into management commands, online, in at most 96 ms. But the orchestration
  is redrawn by hand, the MTP describes services and not a product's need, and nothing is read back
  after the change. It goes in the online-change strand.
- **Terzimehić et al. 2021**: recipe, topology and component models give an SMT deployment and a
  generated IEC 61499 application (sequence, parallel, repetition). It is engineering time only; how
  the result reaches running PLCs is not described.
- **Lindorfer and Froschauer 2019**: BPMN skill sequences validated against a rule set before they run,
  in an external workflow engine; FORTE is their future work. Our checker answers the same question
  from the capabilities' conditions instead of hand-written rules.
- **Albus et al. 2025** (CIRP CMS 2025): product-driven, from the CAD model to a bill of process, capability
  matching, line rebalancing and agents orchestrating OPC UA skills. It has no AAS and no change of a
  control program.
- **Blumhofer et al. 2025**: CSS in the AAS (offered capabilities with constraints, a Skills submodel
  with OPC UA endpoints and conditions). How a skill is composed of atomic skills stays inside the
  machine, not in the AAS.
- **Stolze et al. 2024**: the proactive AAS as BPMN workflows on a process engine, for bidding; no
  control program.
- **Nabizada et al. 2024**: PDDL generated from SysML at engineering time, for evaluating variants. It
  is not the AAS2PDDL paper (nabizada2026capability).
- **Dorofeev et al. 2021**: the 2.7- to 5.5-fold lower effort, measured in 4diac user actions, is
  theirs; so is the future work of keeping the skill in the AAS.

The outline of 28 Oct:

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

Drafted in LaTeX on 1 Nov; rewritten on 3 Nov against the related work and condensed to about 1,450
words, now in [paper/cirp/paper.tex](paper/cirp/paper.tex). Fig. 1 was redrawn the same day, generic
and flat (no use case, little text; 206 by 65 mm instead of 256 by 138); Fig. 3 is the page
product-to-process.

Two candidates of 6 Nov for the planner's place in the paper (pages of
[figures/cirp-figures.drawio](figures/cirp-figures.drawio), made by `figures/planning_pages.py`, PDFs in
`paper/cirp/figures/`): **pipeline-planning**, Fig. 1 with the planning spelled out (Match and plan; Plan:
the task from the vocabulary, regression to the primitives, tracking a bound with rates set, the check in
time; the capabilities feeding it; S′ with a parallel block), 206 by 78 mm, to replace Fig. 1; and
**planned-bottom-up**, one column (8.4 cm wide, 13.6 cm tall), BottomUpFilling for the syringe planned from
the module's primitives: requirement, task, actions, the regression with the dose alone refused and the
tracking that sets 0.396 mL/s and starts the needle at 57.5 mm, the needle's depth in the liquid over time
(the dose alone through the bounds, tracking flat inside them), the parallel block, described and offered.
It can replace planned-skill (plain Filling).

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
| E1 | How much effort is a new skill? | User actions, as [dorofeev2021orchestrator] counts them: by hand in 4diac, in the skill editor, planned (`cell/eval/effort.py`) | Measured 6 Nov, inputs (editor and planner driven in a browser, 4diac from the generated program): a value 3 / 4 / -; DoubleDose 55 / 14 / -; BottomUpFilling 60 / 25 / -; a 15 mL product 71 / 14 / 6 (4diac / editor / planner; [cirp-evaluation.md](cirp-evaluation.md), E1) |
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

### Proposal of 3 Nov: five quantitative experiments (to decide)

**Why.** E1 to E3 are five scenarios with five runs each, on a PC with simulated IO, reported as medians.
They show that the method works, not how well it works, how it scales, or how often it catches what it
should. Each experiment below has a baseline, a ground truth that does not come from the method itself,
and enough runs for intervals (medians with 95 % bootstrap intervals, rates with Wilson intervals).

| # | Question | Varied | Measured | Baseline | Runs | Needs | Effort |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Q1 | How fast does a change take effect, and how does that scale? | change class (parameter, new composite, reorder, structural); composite size (2 to 32 steps, 1 to 4 parallel branches); program size (1 to 20 composites); PC and Pi 5 | activation time from the AAS write to Built, per phase (read back, compare and check, apply, verify, record); management commands and bytes; internal setup time (module unavailable) against external (prepared while it runs), as SMED splits a changeover | full redeployment: a boot file and a restart; for a structural change on the Pi, `deploy-pi.ps1` with its build. On hardware the restart also homes the axis | 30 per cell, in random order | synthetic composites from the module's primitives; per-phase timers in modsync; the Pi at the bench | 1.5 days |
| Q2 | Does a running skill notice a reconfiguration? | a change made meanwhile, per class, or none | the running skill's step durations and inter-step gaps from FORTE's event timestamps; cycle time | the same skill without a change | 100 cycles each; Mann-Whitney U and the largest deviation | step events with timestamps over OPC UA | 0.5 day |
| Q3 | Does the program stay what its AAS says? | nine kinds of drift: in the program a value written from the IDE, a connection deleted, a stray instance, a half-created composite, a wrong type version; in the AAS a value, an added step, a reordered flow, a removed skill. Also a reconfiguration cut after command i | detection rate; false alarms on clean runs; class accuracy (a confusion matrix of parameter, flow, structural, record); repair rate; convergence after a cut | a deployment that does not read back (as the IDE's); a comparison with the boot file instead of the running program | 30 per kind, 100 clean; every i of one change | `cell/eval/drift.py`; modsync completing a half-created composite (else it is refused, and counted so) | 1 day, and 1 for completing |
| Q4 | Are the skills right for the product? | product variants (volume 0.25 to 25 mL, weight required or not, vial or syringe) on module variants (full, no scale, slower pump, moved fill position); all single mutants of the module's skills (a step deleted, swapped, duplicated or inserted, a value beyond its limit, two steps made parallel) | match accuracy (offered, after a reconfiguration, not offered); plan success and time; first-time-right products; the checker's precision and recall | the structural check only (types and connections, what 4diac checks); hand-written sequence rules as in [lindorfer2019user] | about 70 variants and 200 mutants | an oracle that does not use the AAS's constraints: a process model of the filling module (needle depth, liquid in the container, spill, weight) run with each skill | 2 days |
| Q5, if time | Why in the controller and not in an orchestrator? | Dispensing as a composite in FORTE, or its primitives called one by one over OPC UA | inter-step gap; cycle time and its spread; a safe end (needle out, pump off) after a network cut mid-skill | an external orchestrator, as [lindorfer2019user, albus2025automated] and our earlier work run skills | 100 cycles; 20 cuts | a small orchestrator on modlink; blocking the OPC UA port | 0.5 day and the bench |

**In the paper:** Fig. 4 is Q1, activation time against composite size, online and by redeployment, on
the PC and the Pi (log scale), with Q2 in one sentence. Table 2 gives the rates of Q3 and Q4. The
effort (E1) and the planners' times become a sentence each.

**Q4 with the time model (6 Nov):** check recall 90 % (123/136, the 13 Tare insertions left), precision
88 %; matching 104/104 with nothing offered the module cannot do; 23/23 planned skills right; and, added,
15/15 bottom-up fills planned by tracking (the needle rising with the liquid at a flow rate the planner
sets) right in the oracle ([cirp-evaluation.md](cirp-evaluation.md), Q4). For the paper's planner
story: a required capability that bounds how something moves in time (BottomUpFilling) is planned from
the module's primitives, with the parallel move and its rates derived, and found by one press (Match and
plan) on the module that offers what it narrows.

**Validity:** the oracle of Q4 must not reuse the capability constraints the checker reads, or Q4
measures the model against itself. Since 6 Nov the syringe's least immersion (2 mm) is the product's
requirement and O5's number both: the check and the oracle say the same of it, the oracle by its own
10 ms simulation; its greatest immersion (3 mm, Q4t) no rule of the oracle checks. Simulated IO on the PC, one module type and synthetic flows are the
other limits to state.

**Setup, decided 4 Nov:** of the FORTE patches only 0008 goes into the paper (a note in paper.tex's
Evaluation marks the sentence): verification reads the program back, and stock FORTE 3.3.0 cuts every
management answer at 64 KiB with an unfiltered connection query, about 600 connections; the evaluation's
FORTE reads by part. The event lists of 1,024 go into the same sentence. Patches 0001 to 0007 (Pi IO,
restarts, the IDE's type check) are left out ([cirp-evaluation.md](cirp-evaluation.md), the setup).

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
the evaluation's charts (`effort.pdf`, `downtime.pdf`) are drawn by `cell/eval/figures.py`.
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

## The references

At most 17, decided again on 3 Nov. They are in
[paper/cirp/references.bib](paper/cirp/references.bib), the file uploaded to Overleaf. It is
written from the sections' citations, copied out of [paper-references.bib](paper-references.bib),
which stays the library for the journal paper. The 17, in the order first cited:

- **Our work:** schwoerer2025modular, jensen2026service, schwoerer2026fond, schou2018skill.
- **Standards and models:** iec61499, idta02020, koecher2023reference.
- **The closest works:** dorofeev2021orchestrator, terzimehic2021service, lindorfer2019user,
  huang2026plug, rooker2007zero, blumhofer2025enhancing, stolze2024proactive, albus2025automated,
  nabizada2026capability.
- **The planner:** nau2021gtpyhop.

Named in the text without a reference: PackML, 4diac FORTE, IDTA 02017, the process planner.
Dropped for the count: sidorenko2024composition, wenger2018connecting, lepuschitz2011self,
koecher2024smt, bernhard2024leverage, nabizada2024workflow, css2022, strasser2008framework,
jensen2026ontology. The last was dropped on the authors' word (3 Nov): the Skills submodel now
points to blumhofer2025enhancing, the closest skill model in an AAS, and its slot went to
stolze2024proactive. The first to swap in, if a reviewer asks: PackML (ISA-TR88.00.02) for
albus2025automated.

The 17 of 28 Oct were: schwoerer2025modular, jensen2026service, schwoerer2026fond, jensen2026ontology,
schou2018skill, koecher2023reference, iec61499, dorofeev2021orchestrator, sidorenko2024composition,
rooker2007zero, lepuschitz2011self, wenger2018connecting, koecher2024smt, bernhard2024leverage,
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
| The abstract (3 Nov): "process parameters, including loop counts, to parameter writes" and "dosing cycles". A flow has steps, parallel blocks, decisions and conditional steps, and the BPMN validator refuses a loop | Say "number of doses" (DoubleDose, or a plan with two doses), or build a counted repeat block first |
| The abstract: "the process AAS holds the procedure in BPMN, ... the BPMN procedure to a subapplication". The flow that becomes a subapplication is a composite skill's, in the module's Skills submodel. The process AAS binds the product's steps to modules and skills. Both are written in the same flow elements and drawn in BPMN | Say so: the procedure binds steps to skills, and a composite's flow becomes a subapplication. The introduction is written that way |
| The abstract: every change is "applied online". Today a reordered or removed skill needs a restart, and a new primitive or IO a new build (DD 2.10) | "Applied online where its class allows it" (as the introduction says), or build delete-and-create while the module is idle |
| The abstract: the resource AAS describes "the deployed control configuration". Since DD 3.7 the AAS holds each skill's Deployment and interface; the instances, types and hashes are the integrator's record, outside the AAS | Keep DD 3.7 and reword the abstract, or move the record into the AAS |
| Which conference: the docs say CIRP CMS 2026, the Overleaf head says the 60th CIRP CMS (2027). Albus et al. give the 58th as 2025 | The head is right; the docs' "2026" to be corrected |
