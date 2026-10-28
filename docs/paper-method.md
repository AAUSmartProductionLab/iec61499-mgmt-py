# The paper's concept and method: an outline

A draft of 28 Oct, for the authors. Section 3 of the paper, paragraph by paragraph: what each
paragraph says, the figure or table it uses, and the material in this repository it rests on. The
paper's outline as a whole is [paper-outline.md](paper-outline.md); the reasons behind each choice
are [design-decisions.md](design-decisions.md), cited below as DD and a number.

## Where the section sits

The four contributions form one section, "Concept and method", in five subsections. The tools,
FORTE, BaSyx and the lab's modules come after it, in Section 4 (Implementation). The method is stated
by the module rules, not by our tools (DD 1.3), so a reader can follow it with other tools.

| Subsection | Contribution | Length | Figure |
| --- | --- | --- | --- |
| 3.1 Concept | – | 0.4 page | 1: the two artefacts and the four operations (`figures/reconfiguration-pipeline.drawio`) |
| 3.2 The module architecture | C3 | 0.6 page | 2: a skill as blocks (`figures/skill-blocks.drawio`) |
| 3.3 The skill and capability models | C1 | 0.6 page | 3: the Capability Description (`figures/capability-description.drawio`) |
| 3.4 Updating a running module | C4 | 0.5 page | Table: the four classes of difference |
| 3.5 Planning new skills | C2 | 0.6 page | 4: a planned skill (`figures/planned-skill.drawio`) |

About 2.7 pages of six (check the 2026 call for the page limit), with Figure 5 (the evaluation) still to come. If
space runs short, Figures 3 and 4 become one: the Capability Description on the left, the plan and
its flow on the right.

The order follows the claim: verified, operated and changed online (3.2 to 3.4), then planned
(3.5). Updating comes before planning because a planned skill is then "built like any other
described skill" (3.4), with no forward reference.

## The running example

One example runs through every subsection: **the filling module** (`cell/modules/filling.yaml`).

- **Components and skills.** A linear axis (Home, MoveAxis), a pump (Dispense) and a scale (Tare,
  Weigh).
- **Its one module level skill.** Dispensing: MoveAxis(40.0), Dispense, Home, Weigh.
- **Its offered capability.** Filling (FillVolume 0.5 to 10 mL, the result FillWeight).
- **The requirement in the example.** A product needs **Filling of 15 mL with its weight**. That is
  more than one dose of the pump, so no skill offers it.
- **What the module plans.** MoveAxis(40.0) → Dispense(7.5) → Dispense(7.5) → Home → Weigh.
- **What happens next.** The plan is described in the AAS and created online while another skill
  runs. modlink then runs it from the AAS.

To do: the evaluation's planned scenario (`cell/eval/scenarios.py`, `with_planned`) plans 2.0 mL,
which Dispensing already does. Planning 15 mL instead makes the example the case that is measured.
The planner comparison already has 15 mL (`cell/eval/results/planners-2026-10-28T0218.md`).

## 3.1 Concept

1. **The problem.** A reconfigurable module changes at a changeover: another volume, another
   sequence. Today that change is made in the IEC 61499 IDE, by whoever has the project. The module's
   AAS comes with it and describes its skills, but nothing uses the AAS to change them.
2. **The idea.** A module is delivered with two artefacts, its IEC 61499 program and its AAS, and
   nothing else is needed afterwards. The AAS is the module's **desired state**: a change is an edit
   of the AAS, and the program is brought to it. This is desired-state reconciliation, as a
   Kubernetes controller does it, or as models@run.time proposes, applied to an IEC 61499 program
   (mapping.md section 1; DD 1.1).
3. **Why it can work.** The program's form is fixed by rules (Figure 2). A skill is then data: the
   instances and connections of block types the module already has. The AAS can describe that data
   completely, and FORTE can create it online.
4. **Planning closes the loop.** The same AAS holds the module's capabilities, with what each needs
   and does. A module can therefore plan a skill nobody wrote. The plan is written into the AAS as a
   skill description and built by the same reconciliation.
5. **Three levels, one form.**
   - The line, its modules and their components each have an AAS (Hierarchical Structures links
     them).
   - Each level composes only the level directly below. A component's skills are primitives; a
     module's skills are compositions of them; the line is run by agents (outlook, Section 6).
   - Only the module plans.
6. **Roles and interfaces.**
   - Who does what. The vendor delivers the program and the AAS, and may generate both. The
     integrator has only those two. An engineer (later an agent) edits the AAS.
   - Two interfaces, kept apart (DD 1.4). The program is changed only over the IEC 61499 management
     protocol, and operated only over its OPC UA interface. Operating never changes the module, and
     a change never runs a skill.
7. **The claim**, set off: *a module that is delivered with an IEC 61499 program and an AAS can be
   verified, operated and changed online from those two alone; new skills are planned from its
   skill and capability models and created online the same way.*

**Figure 1.** The draft (`figures/reconfiguration-pipeline.drawio`) has nine steps, from the
product's recipe to the run, with the restart as the baseline. For the paper it needs two changes:
- Planning goes in at "Change a skill", which becomes "written by hand or planned".
- It is drawn smaller: the two artefacts in the middle, and the four operations around them
  (verify, operate, change, plan), each labelled with the interface it uses.

## 3.2 The module architecture (C3)

The rules are [module-rules.md](module-rules.md), rule set 2. Here they are stated as what they
make possible.

1. **The shell** is fixed and never changes online.
   - One application on one resource.
   - Occupation: a client holds the module under a session id.
   - The module's PackML state.
   - One block per equipment item, which owns its IO points and knows nothing of their meaning.
   - One INIT chain from the resource's START.
2. **Equipment is reached over local channels, not connections** (DD 2.2, 2.3). Skills command the
   equipment by publishing to its command channel. A block added online therefore needs no
   connection to anything that runs.
3. **A skill primitive is a block type.**
   - What it does: one equipment command, until a sensor or a time says it is done.
   - Its interface is fixed: START, HALT, ABORT, RESET; SUCCESS, FAILURE; one input per parameter,
     whose value is the default; State, ErrorID and the results.
   - Every skill has the same small state machine, primitive or not: Idle, Running, Stopping,
     Succeeded, Failed, Aborted.
   - Its commands Start, Stop, Abort and Reset answer `[Accepted, ErrorID]` at once.
   - PackML runs once, for the module (DD 2.5).
4. **A module level skill is only instances** (DD 2.4).
   - What it holds: a subapplication of library blocks (the skill's state machine, a latch per
     parameter, the publishers) and primitive instances.
   - Flows: parallel blocks and decisions are made of three library blocks (join, condition,
     merge).
   - It has no type of its own, so a new skill needs no build.
5. **The rules work as a compiler** (mapping.md sections 2 and 4).
   - The primitives and five library types are the instruction set.
   - Each construct of the flow has one fixed pattern of instances and connections, and patterns
     join by event connections only.
   - Generating is deterministic and compositional, so reading back is a parse, not a search.
   - Names are the join keys: skill to subapplication, step to instance, parameter to latch, and to
     the OPC UA paths.
6. **What may change online** (DD 2.10). This is the paragraph the rest of the paper leans on:

   | Change | How | Why |
   | --- | --- | --- |
   | A parameter's default or limits, a step's constant | Written online | An input value; taken at the skill's next start |
   | A new module level skill from the module's primitives | Created online | Instances and connections only; touches nothing that runs |
   | Another order of steps, a removed skill | A restart (new boot file) | Would delete instances a running skill may use |
   | A new primitive, new equipment or IO | A FORTE build | FORTE cannot load a block type online |

**Figure 2.** A primitive as a block type; a module level skill as a subapplication of instances;
what the AAS says of a sequence and of a parallel block, and the wiring the rules draw around it.

Left out: the hardware (an axis that keeps its position by time), the IO notation and the
occupation's details. Those belong in Section 4 or nowhere.

## 3.3 The skill and capability models (C1)

The model is ARSO 0.12 ([aas-models.md](aas-models.md), [skill-planning.md](skill-planning.md)
sections 2 to 4).

1. **The resource AASs.**
   - There is one AAS per line, module and active component (DD 3.1).
   - A component's skills are described once in its own AAS, since every linear axis offers MoveAxis
     and Home.
   - A module composes them.
   - The submodels used: Skills, Capability Description (IDTA 02020), Asset Interfaces Description
     and its Mapping Configuration, Operational Data, Hierarchical Structures (IDTA 02011).
2. **A skill is its commands** (DD 3.2).
   - Each command is an Operation whose inputs are the parameters (unit, limits, default, meaning)
     and whose outputs are the results.
   - It refers to the interface action that calls it.
   - The kind of skill (primitive, composite, module control) and its skill type are supplemental
     ids, not structure.
   - `Deployment` says whether a skill is Built or only Described.
3. **A module level skill's steps are written like a product's recipe** (DD 3.3).
   - The elements are those of the process planner's Production Sequence: step, order, skill,
     bindings, parallel blocks with branches, decisions with a condition.
   - So one flow language and one editor serve both the product and the skill.
   - It maps element by element onto 3.2: a short form of the table in mapping.md section 3, three
     or four rows.
4. **The capability model** (DD 3.9). The module's one Capability Description has two kinds of
   capability:
   - **Offered** capabilities: process capabilities such as Filling, said by what they do to the
     product.
   - **Component capabilities**, one CapabilitySet per component. They are neither offered nor
     required (02020's NotAssigned), and each is realized by a primitive: Positioning by MoveAxis,
     Dosing by Dispense.
   - A component capability is never offered to a product. It is described in the module, where its
     constraints can name the other components and the product.
5. **Constraints** are 02020 property constraints. Each is one BasicConstraint expression with one
   operator:

   | Kind | Expression | Means |
   | --- | --- | --- |
   | Pre | `= 40.0`, `= FillPosition`, `< …` | Holds when the capability starts |
   | Post | `= …`, `+= Volume`, `given`, `measured` | Holds when it has succeeded |
   | Invariant | `unchanged` | Nothing changes it while the capability runs |

   An example in the text: Dosing needs the needle at the fill position, adds Volume to the
   content, and keeps the needle still.
6. **Properties are state.** A property is a state variable. It is identified by the first of
   these it has:
   - its `SameProperty`, a data point of Operational Data (the axis' position), so the start state
     can be read live and the runtime conditions name the same signal;
   - otherwise its meaning, if it is a property of the product;
   - otherwise its meaning, on the component that holds it.
7. **Where the constraints come from.** What holds of a kind of capability wherever it is used is
   in the vocabulary: Positioning needs the axis referenced. What holds on this module is in its own
   description: the needle in the vial while dosing.
   - These integration constraints carry the meaning. Without "needle at the fill position", the
     planner fills with the needle up (test case T12).
8. **Three ids, three jobs** (DD 3.5).
   - The semanticId says what the element is in its template.
   - The supplemental semanticId says what it means in the domain.
   - The element's own id says which individual it is.
   - Matching a product's need against a module's offer then uses meanings, never names.
9. **Compared with AAS2PDDL** (one or two sentences, the detail in Section 2). Nabizada et al.
   model types, predicates, actions and objects in planning submodels per component; their `move`
   action takes 77 AAS elements. Here nothing planning-specific is added: a module has a fixed cast,
   so its state is a handful of property values (skill-planning.md section 7).

**Figure 3.** The filling module's Capability Description: Filling offered; the sets LinearAxis,
Pump and Scale with their capabilities; Dosing's constraints written out; SameProperty to
Operational Data; CapabilityRealizedBy to the pump's Dispense.

Optional, by space: **locations** (locations-and-layout.md). Each part's node in Hierarchical
Structures carries its frame (AutomationML's Frame, with IDTA 02075's ids), and points of interest
are nodes with a meaning. The stations of the planar table are then derived from the AASs. This
takes one sentence here and one in the outlook, or it stays out of the paper.

## 3.4 Updating a running module (C4)

From [tools.md](tools.md) section 3 and DD 4.1 to 4.5.

1. **Definition.**
   - `described(A)` takes the module's AAS to a structure: its equipment, primitives, skills with
     their flows and values, and procedures.
   - `read(Π)` takes the running program, read back over the management protocol by the rules, to
     a structure of the same form.
   - The module is what its AAS says when `read(Π) = described(A)`. That is **verify**.
2. **Reconfigure** is one function; in the paper an algorithm box of about eight lines:
   1. Read the program back and read it by the rules.
   2. Compare it with what the AAS describes.
   3. Sort each difference into a class (table below).
   4. Refuse what the module could not carry out: a step on a skill no component has, a value
      outside a primitive's limits, two parallel branches on one component.
   5. Guard: values are written only while the module is Stopped, Idle or Aborted and not occupied.
      A new skill is created in any state.
   6. Apply in a fixed order: write values; create instances; write their values; connect, the one
      link from the end of the INIT chain included; start; fire INIT once into the new skill.
   7. Read back and compare again.
   8. Add the commands to the boot file, so a restart keeps the change.
   9. Record it.

   | Class | Example | Action |
   | --- | --- | --- |
   | create | A skill the AAS describes that the program lacks | Created online |
   | write | A step's constant, a parameter's default or limits | Written online, guarded |
   | restart | Another order of steps, a skill no longer described | Refused: needs a restart |
   | record | The record names an instance or type the program lacks | Refused: the record is wrong |

3. **Created with the generator's own pattern** (DD 4.2). The function that generates a module
   level skill from a spec is the one that creates it online. The program created online and the
   one a vendor would generate are the same by construction, and a test compares them.
4. **Recording closes the loop for the clients.**
   - The AAS gets `Deployment = Built`.
   - A skill built online gets its interface (actions, data points, mappings), written by the rules
     the vendor's AAS was written by.
   - Capabilities are derived again: what was offered "after a reconfiguration" is offered now.
   - What was built (instances, types, hashes, the change log) is the integrator's record, outside
     the AAS.
5. **Operated from the AAS alone** (DD 4.5). A client finds every node it calls by following the
   AAS's references (capability to skill to command to interface action to browse path), never by
   names. A skill built online is therefore run as soon as it is recorded, with no change to the
   client. This is a short paragraph, since it is the "operated" of the claim, not a contribution
   of its own.

No figure of its own: Figure 1 shows the loop, and the table above the classes.

## 3.5 Planning new skills (C2)

From [skill-planning.md](skill-planning.md) and DD 4.8.

1. **What is planned, and what is not.**
   - Only a module plans, and only its module level skills from its components' capabilities.
   - The line is run by agents, which negotiate; that is the outlook.
   - A module's problem is small, has a fixed cast and is known locally. No relational model (many
     carriers on a transport system) is needed.
   - Optimality is not a goal: the first valid plan is taken, the integrator's way first.
2. **The domain is read from the AAS alone.**
   - The state variables come from 3.3.
   - An action per component capability: its Pre, Post and Invariant.
   - A task per offered capability.
   - The rest state is what the module's Reset procedure leaves (Referenced, Position 0, Tared).
3. **The problem.**
   - The requirement gives a capability, the values of its properties and the results asked for.
   - The goal is the capability's Post with those values, the state each result needs (FillWeight
     needs Weighed), and then the rest state.
4. **The planner** is an HTN with goal regression, as in GTPyhop. A task's methods are tried in this
   order:
   1. the capability's compositions in 02020 (`ComposedOf`): the integrator's way, where stated;
   2. an existing composite that realizes it, inlined, so composites of composites are planned too;
   3. a generated method: reach each goal of the Post, then the rest state.

   How a goal is reached:
   - `=` and `+=` are achieved: the goal holds already, or a capability whose Post sets it is taken,
     after its own Pre, which becomes a goal in turn.
   - The other comparisons are checked.
   - `+=` beyond one dose is reached in the fewest equal doses within the parameter's range: that is
     the example's 7.5 + 7.5.
5. **Lifting to a flow.**
   - Two steps stay ordered if they use the same component, or one changes a state the other needs,
     changes or keeps.
   - The series-parallel form of that order is the flow, with parallel blocks where nothing orders
     two steps. Weigh keeps the needle still, so Home and Weigh stay apart.
6. **From plan to program.**
   - The flow is written into the Skills submodel as a Described skill: parameters, steps, results
     from the steps that measured them, and the module's Stop procedure as its stop flow.
   - 3.4 builds it. The plan needs nothing beyond the flow, because the rules draw the wiring (3.2).
7. **Checking and discovery** come from the same model.
   - Check: a flow written by hand is run through the states. A precondition that does not hold is
     reported with the step that would make it hold, as is an invariant a parallel branch breaks.
   - Discover: for each process capability of the vocabulary the module has no skill for, a plan
     from the rest state means it is offered "after a reconfiguration".
8. **Standard planners.** The same domain is generated as HDDL (for Aries) and as numeric PDDL 2.1
   (for ENHSP), and a validator checks every plan. They serve as a comparison and a check of the
   GTPyhop plans, not as the method. One sentence here; the numbers go in Section 5.
9. **What it assumes.**
   - A module's state is a few known values.
   - Numbers are only added and compared.
   - There is no time.
   - Every skill starts and ends at rest.
   - These go in the text, so a reviewer finds the limits stated.

**Figure 4.** The example: the requirement (Filling 15 mL, FillWeight) → the plan → the lifted flow
→ the skill described in the AAS → created online.

## Section 4 (Implementation), not here

- The tools that carry out the method: modgen, modreg, modsync, modlink, modplan, with their sizes
  (tools.md section 1).
- The runtime and the libraries: Eclipse 4diac FORTE with its OPC UA server, BaSyx, ARSO 0.12 and
  the vocabulary 0.4 with the ontology checks.
- The skill editor.
- The lab's filling and stoppering modules, on a PC with simulated IO and on a Raspberry Pi 5.

## Each statement and what backs it

| Statement in Section 3 | Backed by |
| --- | --- |
| Reading back is a parse; the program created online equals the generated one | Tests that compile every shape of flow and read it back (`aas61499-tools/tests/test_modsync.py`, `test_modsync_flow.py`) |
| A new skill is created while another runs | Scenarios B1 and B2: the running skill kept running; 0.04 s online against 3.3 s down by a restart |
| A skill built online is operated with no client change | DoubleDose, built online, found and run by modlink from the recorded AAS alone ([work.md](work.md)); `iec61499-opcua-hmi/tests/test_modlink_aas.py`. The scenarios call skills by browse path; to do: run the new skill through modlink there |
| The planner finds the module's own skills, and skills nobody wrote | T1 to T12 (skill-planning.md section 10); the 15 mL case |
| Plans are valid by a standard validator | `cell/eval/planners.py`: every plan of GTPyhop, ENHSP and Aries valid |
| The constraints carry the meaning | T12 (`aas61499-tools/tests/test_modplan.py`) |

## Terms used throughout

The same words in the paper, the AASs and these docs:

| Term | Means | Not |
| --- | --- | --- |
| Module, component, line | The three levels of resource, each with an AAS | Station, device |
| Skill primitive (primitive) | A component's skill; a block type | Atomic or basic skill |
| Module level skill ("module-level" in the paper) | A composition of primitives; its AAS kind is Composite | Composite skill (except when naming the kind) |
| Offered capability, process capability | What a module offers a product (Filling) | Service |
| Component capability | A capability a primitive realizes, NotAssigned (Dosing) | Skill capability, sub-capability |
| Precondition, postcondition, invariant | The three kinds of constraint (Pre, Post, Invariant) | Contract, requires, ensures |
| Requirement | A capability with values and results asked for | Request, order |
| Flow, step, parallel block, decision | What a module level skill runs | Sequence (except for steps in order), recipe |
| Rest state | What the Reset procedure leaves; every skill starts and ends there | Home position |
| Described, built | A skill in the AAS only, and also in the program | Planned, deployed |
| Verify, reconfigure, record | The three steps of updating | Sync, deploy |
| Online change, restart, build | The three ways a program changes | Hot swap |

## For the authors to decide

| Question | Proposal |
| --- | --- |
| One section with five subsections, instead of four sections as in paper-outline.md before 28 Oct? | Yes: six pages; one concept carries the four contributions |
| Updating (3.4) before planning (3.5)? | Yes: it follows the claim, and a planned skill is then built "like any other" |
| The running example 15 mL? | Yes; switch the planned scenario to it before the Pi runs (B3) |
| Taring (skill-planning.md section 9) | Decide before writing 3.5; otherwise one sentence among the assumptions |
| Locations in 3.3 or only in the outlook | Only in the outlook, unless the planar table's run is shown |
| Occupy and Release as skills of the kind ModuleControl, or as part of the shell | In the shell (3.2); their AAS form in a footnote |
