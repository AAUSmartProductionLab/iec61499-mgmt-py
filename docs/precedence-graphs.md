# The Production Sequence as a precedence graph

Proposed on 2 Nov 2026, for the authors and for the colleagues who model products with joints and
process orders. It describes version 4.0 of the Production Sequence:
- a product's steps in a partial order, not a list;
- the joints the colleagues model (`JointConnection`, `JointParams`, `ProcessOrder`) placed in the
  steps that make or break them;
- one sequence per archetype (Assembly, Disassembly) in an AAS.

The rest of the product, process and resource model ([ppr-model.md](ppr-model.md)) stays as it is.
The figure is the page `production-sequence` of [figures/journal-figures.drawio](figures/journal-figures.drawio),
with `-battery` and `-pharma` beside it. The design decisions are in
[design-log.md](design-log.md) (2 Nov). Nothing of this is built yet.

## 1. Why

Today's Production Sequence (3.0, [aas-models.md](aas-models.md) section 4) is a list of steps in
`Order` with nested blocks (`parallel`, `call`, `conditional`, `decision`). That has three limits:

- **Nested blocks express only series-parallel orders.** In a battery pack, the busbars come off
  after the cover and the HV connector, the BMS after the HV connector only. In blocks, the BMS
  either waits for the busbars or for the cover; both lose freedom the product has.
- **The agents ask for one step at a time**, the next in `Order`
  (`line-agents/lineagents/aas.py`, `steps`). With a partial order, a product agent calls for
  proposals on every step that is ready and takes the station that is free.
- **Nothing says what holds a product together.** Disassembly and remanufacturing are planned on
  joints: the literature uses liaison graphs and disassembly precedence graphs, and the colleagues
  model products so. Our bill of material only says what is part of what.

## 2. Where it sits in the PPR model

| AAS | Holds | Changes with 4.0 |
| --- | --- | --- |
| **Product AAS** (general recipe) | Hierarchical Structures (the parts, `HasPart`), Process Parameters (the processes, their parameters and materials), Capability Description (required), Production Sequence (the recipe) | The recipe becomes a partial order; the joints move into its steps; one sequence per archetype |
| **Subassembly and part AASs** | The same submodels, one level down | A subassembly with a recipe of its own has its own sequence, called from the parent's |
| **Process AAS** (master recipe, per product and line) | Process Information (product, line, recipe), Bindings (per step: resource, skill, inputs), Validation | `Recipe` names the sequence of one archetype; Validation checks the new rules (section 6) |
| **Resource AASs** | Line, modules, components: capabilities, skills, interface, mapping, variables | None |

The partial order belongs to the product: what must happen before what, whatever line runs it.
A line that needs a fixed order (a validated pharma process) fixes it in the process AAS, not in
the product.

## 3. The structure

```
ProductionSequence                    semantic id .../SubmodelTemplate/ProductionSequence/4/0
├─ ArcheType                          Assembly | Disassembly
├─ Name, Revision, Subject            as in 3.0 (Subject → the product's AAS)
└─ Steps
    └─ Step_0000                      Kind partial, NodeId, Name, Order
        └─ Steps
            ├─ Step_0000              Kind step, NodeId UnscrewCover, Order 0
            │   ├─ ProcessReference   → ProcessParameters/Unscrewing
            │   └─ Joints             (SMC)
            │       └─ J_Cover        AnnotatedRelationshipElement
            │           ├─ first      → HierarchicalStructures/EntryNode/Cover
            │           ├─ second     → HierarchicalStructures/EntryNode/Housing
            │           └─ annotations: JointType Screw, JointStandard DIN 8593-3
            ├─ Step_0001              Kind step, NodeId UnplugHV, Order 1     (Joints: J_HV)
            ├─ Step_0002              Kind step, NodeId RemoveBusbars, Order 2
            │   ├─ After              (SML) → Step_0000, → Step_0001
            │   └─ Joints             J_Busbar1…4: first Busbars, second BatteryModule1…4
            ├─ Step_0003              Kind step, NodeId RemoveBMS, Order 3
            │   └─ After              → Step_0001
            └─ Step_0004              Kind call, NodeId BatteryModule1, Order 4
                ├─ SequenceReference  → the module's own Disassembly sequence
                └─ After              → Step_0002
```

What is new against 3.0:

| Element | Kind | Meaning |
| --- | --- | --- |
| `Kind` = `partial` | Property value | A block whose steps run in any order that respects their `After` |
| `After` | SubmodelElementList of ReferenceElements | The sibling steps that must be done before this one starts |
| `Joints` | SubmodelElementCollection | The joints this step makes (Assembly) or breaks (Disassembly) |
| A joint | AnnotatedRelationshipElement | The colleagues' `JointConnection`: `first` and `second` are two entities of the bill of material; `JointType` and `JointStandard` are its annotations |
| `ArcheType` | Property | Assembly or Disassembly, one sequence of each at most in an AAS |

Some details of the AAS metamodel:
- **`Joints` is a collection, not a list.** Elements of a SubmodelElementList have no idShort
  (AASd-120), and a joint must keep its name to be referred to from the other archetype.
- **`After` is a list.** Its references need no names.
- **An AnnotatedRelationshipElement takes only data elements as annotations** (Property, Range,
  File, ReferenceElement, Blob, MultiLanguageProperty), never a collection. This is why the
  colleagues' model has `JointParamsRef`: it points at the collection their parameters are in.
- **The kind of joint is also its meaning.** It gets a supplemental semantic id from the
  vocabulary (a screwed joint, a plug, a press fit, a crimp), as every other meaning in our model
  does. `JointType` and `JointStandard` stay as strings for the colleagues' tools.

## 4. The colleagues' model, element by element

| Their element | In 4.0 | Why |
| --- | --- | --- |
| `JointConnection` (ARE) | A joint in the `Joints` of a step | Hierarchical Structures stays the tree of parts; the joint is held by the step that handles it |
| `first`, `second` | The same: references to two entities of Hierarchical Structures | The bill of material is referred to, not changed |
| `JointType`, `JointStandard` | The same annotations, and the kind of joint as supplemental semantic id | Matched by meaning like the rest of the model |
| `JointParamsRef` | Left out | It would point at the process the step's `ProcessReference` already names: the same link twice. An export to their format fills it in from `ProcessReference` |
| `JointParams` (SMC) | The process in Process Parameters | No second container of parameters |
| `TypeParam` (Properties) | The process's product parameters | Where the value chain to the skill starts: BreakawayTorque → Torque → MaxTorque |
| `TypeRange` (Ranges) | The ranges of the process's required capability | What matching checks against the offered capability |
| `TypeFile` (File) | A File in the process | E.g. the fastener's data sheet |
| `ProcessOrder` (joint to joint) | `After` between the steps that hold the two joints | The order is kept once, on the steps |

Why the order is put on the steps and not on the joints:
- not every step is a joint: filling, testing and inspection are not;
- one joint can need more than one step (position, then screw); the joint is held by the one that
  makes or breaks it;
- the same joints come in another order when the product is assembled than when it is taken apart.

Their models convert without loss:
1. A step for each joint, or for each group of joints with the same process (the four busbar
   joints are one step).
2. The joint into that step's `Joints`.
3. `JointParams` into the process of Process Parameters that the step refers to.
4. `ProcessOrder` into `After`.

When only the assembly order is known, it can be turned around to give the disassembly order. That
is a proposal to be checked, not a rule: access and damaged parts can change the order of
disassembly.

## 5. How the other submodels take part

- **Hierarchical Structures (IDTA 02011)** keeps the parts and `HasPart` only.
  - A joint's `first` and `second` point at its entities.
  - A joint sits in the sequence of the smallest AAS whose bill of material holds both parts. The
    busbar-to-module joint is in the pack's sequence and points at the pack's entity of the module.
    The lid-to-housing joint of a module is in the module's own sequence.
- **Process Parameters (IDTA 02031, extended)** is unchanged.
  - A step's `ProcessReference` gives the process, and with it:
    - the parameters (the joint's);
    - the materials and their roles (`incorporated`, `output`, `workpiece`);
    - the required capability.
  - The material roles say what a step adds or takes out. The joints say how the parts are held.
- **Capability Description (IDTA 02020)** is unchanged.
  - The required capability is matched against the offered one, by meaning and range.
  - Alternatives are left to matching. A step that requires Separating can be done by a module
    offering Unscrewing or Cutting. The recipe needs no OR branch for it.
- **Subassemblies:**
  - A `call` step is a node of the parent's graph. Its `SequenceReference` points at the
    subassembly's own sequence, in the subassembly's AAS.
  - A subassembly bought in (the pharma flip-off seal) has no sequence; its joints are the
    supplier's.
- **Decisions and outputs (3.0, unchanged):**
  - A step declares its outputs (TestCells: StateOfHealth), and a `decision` compares them
    (StateOfHealth ≥ 80 %: Reuse or Recycle).
  - In a partial block, an output can be used by a step that comes after its producer, through
    `After`.
- **The process AAS:**
  - Binds each step to a resource, a skill and the skill's inputs, as today.
  - `Recipe` names the sequence of the archetype the line runs.
  - The fixed resource and skill per step in the product's sequence (open point F6) leave the
    product AAS. When the agents choose a station at run time, the binding is theirs.

## 6. The rules

1. **Edges only between siblings** of one `partial` block, never across block boundaries. Blocks
   still nest: a `partial` block may hold `call`, `decision`, `parallel` and `conditional` steps,
   and sit inside them.
2. **No cycles.**
3. **`Order` stays and must respect `After`.**
   - In a normal block it is binding, as in 3.0.
   - In a `partial` block it is one valid order, the default. A reader that knows only `Order` (the
     agents today, the planner's older views) runs the plan correctly, without the freedom.
4. **At most one sequence per archetype in an AAS.** A joint is defined once, in one of them; the
   other archetype's step refers to it with a ReferenceElement in its `Joints`.
5. **A joint's parts are found** in the bill of material of the AAS holding the step.
6. **Not in a module's skills.** Composite skills use the same step elements, but FORTE runs
   blocks only. The rules for modules reject `partial` unless the planner turns it into blocks
   first, as it does for its own plans ([skill-planning.md](skill-planning.md) section 6).

The process AAS's Validation reports rules 2, 3 and 5, and that every step is bound.

## 7. How it runs

- **Multi-agent orchestrator:** a product agent keeps the set of ready steps: those whose `After`
  steps are all done.
  - It calls for proposals on each of them and takes the offers that come.
  - A `call` starts an agent for the subassembly. The four modules of a pack are taken apart at
    the same time on different stations.
  - Since one workpiece is at one station at a time, real parallelism comes from the
    subassemblies. For a single workpiece, the gain is in the choice of order.
- **Centralized orchestrator:** the policy (FOND, run as a behaviour tree) is generated from the
  graph and the bindings. Any order that respects `After` is valid.
- **Pharma:** GMP fixes the order. The vial's steps form a chain (Filling → Stoppering → Capping →
  Inspection). It is the same model with one order allowed.

## 8. The two use cases

**Battery remanufacturing** (`production-sequence-battery`, a simulated disassembly cell):
- **The pack's Disassembly sequence:**
  - UnscrewCover (J_Cover) and UnplugHV (J_HV) have nothing before them, so they are ready at the
    start.
  - RemoveBusbars (J_Busbar1…4) comes after both; RemoveBMS after UnplugHV.
  - The four modules' sequences are called after RemoveBusbars.
- **Each module's Disassembly sequence:** RemoveLid (J_Lid), TestCells (output StateOfHealth),
  then a decision to reuse or recycle.
- **The pack's Assembly sequence** closes the pack again. BoltBusbars refers to J_Busbar1…4 rather
  than defining them a second time.

**Pharma** (`production-sequence-pharma`, the example line):
- **The vial's Assembly sequence:**
  - Filling has no joint, since it incorporates the liquid.
  - Stoppering makes J_Stopper (press fit) and Capping makes J_Seal (crimp).
  - Inspection outputs TopPassed and SidePassed.
- **The flip-off seal** is bought: it has an AAS with a bill of material and no sequence.

## 9. From 3.0 to 4.0

- **Every 3.0 sequence is a valid 4.0 sequence:** it simply has no `partial` blocks and no
  archetype. Assembly is assumed.
- **3.0 to 4.0 converts without loss:** every block becomes edges.
  - A sequence gives each step an edge from the one before it.
  - A `parallel` block gives edges from the step before it to the first step of each branch, and
    from the last step of each branch to the step after it.
- **4.0 to 3.0 loses freedom** wherever the graph is not series-parallel. `Order` is what remains.
- **The changes this needs** (estimated on 2 Nov, [design-log.md](design-log.md)):
  - the template in aas-model, together with the pending 3.0 update (F5);
  - the plan check;
  - the agents' loop over the ready steps;
  - the planner in the web UI fork: a `partial` node, `After` in the inspector, a layered layout
    inside the block, joints picked from the bill of material, a tab per archetype;
  - in the BPMN editor, an ad-hoc subprocess with free wiring inside.

## 10. Open

- **The name `ArcheType`.** It clashes with IDTA 02011's `ArcheType` (Full, OneDown, OneUp), which
  means something else. `SequenceType` would avoid that.
- **Which archetype pharma uses.** Is filling an Assembly, or does it need a third value
  (Production)?
- **Where a used product's measured condition lives** (a pack's state of health before it is
  tested), for decisions before the first test.
- **What the colleagues' `ProcessOrder` points between:** joints (assumed here) or processes.
  Either way it becomes `After`.
- **Dependencies other than "after the end".** ISA-95 has others, such as `NotInParallel` and
  `AfterStart`. They could be qualifiers on an `After` reference. They are left out until a case
  needs them.
