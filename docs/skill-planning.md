# Composing skills from capabilities (HTN hybrid)

Design of 27 Oct 2026. A module makes a new module level skill by **planning** it from what its own
AAS says about capabilities, instead of having it written by hand. The planner is a hybrid of
hierarchical task networks (HTN) and goal regression, as GTPyhop (Nau, 2021) supports; the same
domain is also generated as HDDL and PDDL for standard planners. The plan becomes a flow in the AAS
like any skill the editor makes, and the rules of rule set 2 make it a program ([mapping.md](mapping.md),
[figures/skill-blocks.drawio](figures/skill-blocks.drawio)).

The same model **checks** a flow written by hand: it runs the state through every path and reports a
condition that does not hold, with the step that would make it hold. The editor shows that as a
recommendation.

## 1. Levels, and what is planned

| Level | Who decides | Planned here |
| --- | --- | --- |
| Line | Agents: products and modules negotiate; nothing plans the line centrally | No |
| Module | The module (its agent): which skill carries out a capability it is asked for | **Yes**: composite skills from its components' capabilities; now and then a composite of composites |
| Component | – | No: its skills are primitives (block types) |

Each level plans only with the level directly below it, from its own AAS. A module's problem is small
and has a fixed cast, its components and the one product in it, so its state is a handful of property
values and every capability is about known things. A relational model (many interchangeable objects,
as carriers on a transport system) is not needed and not attempted. Optimality is not a goal: the
first valid plan in the order the methods are tried is taken, the integrator's way first.

A module answers a requirement in one of three ways: a built skill realizes it; a skill is described
or can be planned (offered "after a reconfiguration"); or it cannot. The planner turns the second
answer into a skill.

## 2. The module's Capability Description is its planning domain

Everything the planner reads is in one submodel, the module's Capability Description (IDTA 02020).
02020 keeps its relations (`ComposedOf`, `ConstraintHasProperty`, `TransitionConstrainedBy`) inside one
submodel (its section 1.8.1); only `CapabilityRealizedBy` and `SameProperty` point outside. Its own
painting-station example does the same: "paint" is composed of spray, dosing, store and pressure
adjust.

| CapabilitySet | Capabilities | Role | Realized by |
| --- | --- | --- | --- |
| `OfferedCapabilities` (exists) | Process capabilities: Filling | Offered | A composite skill of the module, if one exists |
| One per component (`LinearAxis`, `Pump`, `Scale`), as 02020's best practice has a set per asset | The component's capabilities: Referencing, Positioning; Dosing; Taring, Weighing | NotAssigned (neither offered nor required) | The component's primitive |

A component capability is a part of module capabilities, never offered to a product. It belongs to the
component (its set, its primitive) but is described in the module, where the constraints that involve
the other components and the product can refer to it. A component's own AAS keeps only its skills, as
now.

ARSO 0.11 (27 Oct) allows it: `CapabilityRealizedBy` may point to a skill of a component, in the
words ARSO already uses for the skill of a step, "of the same AAS or of an AAS that is a part of it in
HierarchicalStructures (downward only)". It also declares the constraint elements and the conventions
of section 3 (`ontology/ARSO/Modules/capabilities.ttl`).

## 3. Constraints and state

**A constraint** is a 02020 `PropertyConstraintContainer` with a `BasicConstraint`: a Property holding
a one-operator expression, about the property its `ConstraintHasProperty` names, with an operand that
is a value or another property of the same capability.

| Kind (`PropertyConditionalType`) | Expression | Means |
| --- | --- | --- |
| Pre | `= 40.0`, `= true`, `= FillPosition`, `!= …`, `< …`, `>= …` | Holds when the capability starts |
| Post | `= …` | Holds when it has succeeded |
| Post | `+= Volume` | The property has grown by the value of another property |
| Post | `given` | Ends at the value the capability was given (an input, with a Range) |
| Post | `measured` | Ends at what the capability measured (an output) |
| Invariant | `unchanged` | Nothing changes it while the capability runs |

The planner splits an expression into operator and operand. `=` and `+=` are **achieved** (a goal
method finds a capability whose Post makes them hold); the other comparisons are **checked**. A value
holds until a Post sets it again (the frame rule).

**A property is a state variable**, identified by:

1. its `SameProperty`, if it has one: the data point of the module's Operational Data it names
   (`LinearAxis_ActualPosition`, `LinearAxis_Homed`, `Scale_Weight`). Every capability that points at
   the same data point talks about the same state; the start state can be read live; and the runtime
   conditions (section 5) talk about the same signals;
2. otherwise its meaning, if that is a property of the product (vocabulary): the product in the module;
3. otherwise its meaning, on the component whose CapabilitySet holds it (the scale's `Tared`, which has
   no signal).

The order of the steps follows from the state, so the filling module needs no transition constraint.
02020 has them for orders that no state expresses. In 02020 a transition **Invariant** means that the
other capability must run **at the same time** ("supplying lubricant during a milling operation"),
which would be a parallel block; not used yet.

## 4. The filling module

| Set | Capability | Realized by | Properties | Pre | Post | Invariant |
| --- | --- | --- | --- | --- | --- | --- |
| LinearAxis | Referencing | Home | Position, Referenced | – | Referenced `= true`, Position `= 0.0` | – |
| LinearAxis | Positioning | MoveAxis | Position (0–60 mm), Referenced | Referenced `= true` | Position `given` | – |
| Pump | Dosing | Dispense | Volume (0.5–10 mL), FlowRate, FillPosition (40.0 mm), NeedlePosition, ContentVolume, Weighed | NeedlePosition `= FillPosition` | ContentVolume `+= Volume`, Weighed `= false` | NeedlePosition `unchanged` |
| Scale | Taring | Tare | Tared | – | Tared `= true` | – |
| Scale | Weighing | Weigh | Tared, Weight, NeedlePosition, Weighed | Tared `= true`, NeedlePosition `= 0.0` | Weight `measured`, Weighed `= true` | NeedlePosition `unchanged` |
| Offered | Filling | Dispensing | FillVolume, FillWeight (a result), ContainerType, GraspDiameter, AbsoluteFillError, ContentVolume | ContentVolume `= 0.0` | ContentVolume `= FillVolume` | – |

Position and NeedlePosition name `LinearAxis_ActualPosition`, Referenced names `LinearAxis_Homed`,
Weight names `Scale_Weight`; ContentVolume and Weighed are the product's. A requirement's **result**
adds a goal: FillWeight needs Weighed `= true` at the end (the vocabulary says which state a result
needs), so a requirement without it is planned without weighing.

One container written out:

```
CapabilityContainer  Dosing                    lab:Dosing, NotAssigned                  (set Pump)
  PropertySet
    Volume           Range 0.5–10.0 mL         lab:Volume
    FlowRate         Range 0.1–5.0 mL/s        lab:FlowRate
    FillPosition     40.0 mm                   lab:FillPosition
    NeedlePosition   –                         lab:Position, SameProperty → OperationalData/LinearAxis_ActualPosition
    ContentVolume    –                         lab:ContentVolume
    Weighed          –                         lab:Weighed
  CapabilityRelations
    CapabilityRealizedBy → the pump's Skills/Dispense
    ConstraintSet
      Pre        NeedlePosition   "= FillPosition"
      Post       ContentVolume    "+= Volume"
      Post       Weighed          "= false"
      Invariant  NeedlePosition   "unchanged"
```

**Where it comes from.** modreg writes the description. What holds of a kind of capability wherever
it is used (Positioning needs the axis referenced) is in the vocabulary, on the capability classes.
What holds on this module (the needle in the vial, the vial on the scale) is in the module's spec,
next to the skill, in the words of ARSO (`cell/modules/filling.yaml`):

```yaml
  Dispense:
    capability:                          # of the Dosing it realizes, on this module
      values: {FillPosition: {value: 40.0, unit: mm}}
      precondition: {LinearAxis.Position: "= FillPosition"}   # the needle in the vial
      invariant: {LinearAxis.Position: unchanged}             # still while dosing
  Weigh:
    capability:
      precondition: {LinearAxis.Position: "= 0.0"}            # the needle out of the vial
      invariant: {LinearAxis.Position: unchanged}
```

**The rest state** is what the steps of the Reset procedure (`[Home, Tare]`) give from nothing known:
Referenced, Position 0.0, Tared. Every composed skill starts and ends there; nobody states that rule
(the spec's "homing after every operation" is what it encodes).

## 5. The skill's runtime conditions (ARSO 0.11)

The `Contract` of a primitive stays the executable check over the module's signals, renamed to the
words of 02020 and CSS (done 27 Oct):

| ARSO 0.10 | ARSO 0.11 | Example |
| --- | --- | --- |
| `Contract` / `Requires` | `Conditions` / `Precondition` | `Homed` |
| `Contract` / `Ensures` | `Conditions` / `Postcondition` | `NOT Moving AND ABS(ActualPosition - Position) < 0.001` |
| `Contract` / `Invariant` | `Conditions` / `Invariant` | |
| `Contract` / `After` | `Completion` / `After` | Ends the skill after a duration, if it has no Postcondition |
| `Contract` / `Timeout` | `Completion` / `Timeout` | |

They are linked to the capability's constraints by what is there: the primitive realizes the
capability, and both talk about the same data points (`SameProperty`). A check can compare them; later
one can be written from the other.

## 6. The planners

1. **One domain model** (Python), made by SPARQL from the projection of the module's AASs and the
   vocabulary: the state variables (section 3); an action per NotAssigned capability; a task per
   process capability with its Pre and Post; the methods; the rest state; the named values.
2. **One simulator** on it: the checker of the editor, and the validation of every plan.
3. **GTPyhop** plans on it directly, numbers included. For a task the methods are tried in this order:
   1. the capability's compositions (02020 `ComposedOfSet`), the integrator's way, if stated: the parts
      as subtasks, ordered by the state;
   2. an existing composite skill that realizes the capability: its steps as subtasks. This is how a
      composite of composites is planned: the inner one is inlined, since a step of rule set 2 runs a
      primitive;
   3. the generated method: reach each goal of the capability's Post, then the rest state.

   A goal ("ContentVolume = 2.0") is reached by "it already holds" or by a capability whose Post makes
   it hold, after its own Pre (goal regression).
4. **The plan is lifted** to a partial order: steps on different components with no state between them
   become a parallel block, unless an invariant forbids it (Weigh keeps the needle still, so Home and
   Weigh stay apart). The flow is written in the planner's elements; the derivation checks that the new
   skill offers the capability.
5. **HDDL and PDDL are generated** from the same model, for standard planners, for the evaluation, and
   to validate plans with VAL:
   - HDDL: the same tasks and methods, the goals as compound tasks with methods, so any HDDL planner
     runs it without task insertion; values become objects (`fill`, `ref`, the requested volume);
     deletes are generated (a property has one value);
   - PDDL 2.1 with numbers (ENHSP) for `+=`, which HDDL 1.0 cannot express: a volume above one dose;
   - invariants stay outside both: plans are sequential, and invariants matter only when lifting.

**Discovery.** With the generated methods a process capability is planned without any composition.
For each process capability of the vocabulary the module has no skill for, the planner tries its Post
from the rest state; if a plan exists, the module offers it after a reconfiguration, with the range the
limits of the plan's capabilities give. modreg adds such offers when it derives a module's capabilities
anew (after a skill is described or built): no skill realizes them yet. The derivation from the skills
(`lab:contributes`) stays for the skills that exist; it gives their ranges exactly.

## 7. Compared with AAS2PDDL (Nabizada et al., CASE 2026, arXiv 2606.02167)

They generate PDDL from four planning submodels in each component AAS
([AAS-Planning-Metamodel](https://github.com/hsu-aut/AAS-Planning-Metamodel)): TypeHierarchy (types),
DataElementTypes (predicates), Capabilities (VDI 3682
process operators whose inputs and outputs are tagged Requirement or Assurance and Equal or NotEqual,
bound to parameters by references) and Instances (objects, initial state, goals). Their `move` action
(3 parameters, 4 preconditions, 4 effects, 14 lines of PDDL) is 77 AAS elements. Here nothing
planning-specific is modelled:

| PDDL / HDDL | AAS2PDDL | Here |
| --- | --- | --- |
| Types, objects | TypeHierarchy, Instances | Not needed: a module is one fixed cast of components and a product |
| State | Predicates with typed parameters | Capability properties with a meaning, one value each |
| Actions, parameters | Process operators, parameter collections | NotAssigned capabilities, their properties with a Range |
| Preconditions, effects | Inputs and outputs; delete effects written by hand | Pre and Post constraints; deletes generated |
| Invariants | – | Invariant constraints |
| Initial state, goal | Instances (the goal in a component's AAS) | The rest state or the live values; the requirement |
| Tasks, methods | – | Process capabilities; compositions, existing composites, generated methods |
| Numbers | Future work | Ranges, values, `+=` |

Their model is general where this one is not: many interchangeable objects and relations between them
(carriers on belts) are what lifted PDDL is for, and what a transport system would need inside it. A
module does not. Köcher et al. (2023, arXiv 2312.08801) plan with SMT from capabilities modelled after
CSS, with inputs as preconditions and outputs as effects: the same view of state.

## 8. Changes, in order

All but 6 and 7 done on 27 and 28 Oct (the plan's G0 to G5, [next-steps.md](next-steps.md)):

1. **Vocabulary 0.2 and PPRL 0.2**: the capabilities Referencing, Dosing, Taring, Pressing, Crimping,
   Imaging (auxiliary, each a class of its own: as subclasses they would inherit their parent's
   constraints), the properties Referenced, Tared, Volume (a dose), FillPosition ⊑ Position,
   FillWeight (a result), ContentVolume, Weighed, Stoppered, Capped, Inspected (of the product);
   `lab:realizes` on every skill type; each capability's constraints as `pprl:pre`, `pprl:post` and
   `pprl:invariant` with the expression a BasicConstraint holds; the process capabilities defined by
   what they do to the product. Checked by `tests/test_modplan_vocabulary.py`. Dispense's parameter
   keeps its meaning FillVolume for the derivation; the capability's property of that name is a Volume.
2. **ARSO 0.11**: `Conditions` and `Completion`; `CapabilityRealizedBy` to a component's skill; the
   constraint elements and conventions. modreg writes them, modsync also reads a 0.10 `Contract`; the
   module specs use the same words (`precondition`, `postcondition`, `invariant`, `after`, `timeout`).
3. **modreg** (`modreg/capabilities.py`): a set per component with its capabilities and their
   constraints, from the vocabulary and the spec (a skill's `capability`), `SameProperty` to the data
   points; the offered capabilities with their Pre and Post.
4. **modplan** (`read`, `check`): the domain from the AAS alone, the checker.
5. **modplan** (`plan`, `lift`, `compose`, `discover`): GTPyhop, the lifting, the skill described in the
   AAS and created online by `modsync reconfigure` (on FORTE: `tests/test_modplan_live.py`); discovery,
   with the offers modreg adds. The command line: `python -m modplan`.
6. HDDL and PDDL generation; a planner of each kind and VAL, for the evaluation.
7. The recommendations in the editor.

## 9. Open points

| Point | Proposal |
| --- | --- |
| Position 0.0 by Home or by MoveAxis(0) | Both are plans (DoubleDose uses MoveAxis(0)); Referencing is tried first, as the spec homes after every operation |
| Which HDDL planner | PANDA (pandaPI), which plans partial-order HDDL; check what runs on Windows |
| Numbers in PDDL | Values as objects with an amount; the candidate doses are the requested volume, the limits and what is left |
| Decisions in a composed skill ("top up if light") | Not planned in the first version; offered as a pattern |
| Tare with the container on the scale (a net weight) | Not modelled |
| The range of a discovered offer with `+=` | Bounded by the container's capacity, which the vocabulary does not have yet |

## 10. Test cases with the filling module

The module's skills are the ground truth: Dispensing (the spec) and the test skills DoubleDose
(`aas61499-tools/tests/test_modsync.py`), Checked and Ready (`aas61499-tools/tests/test_modsync_flow_live.py`).

| Case | Given | Expected |
| --- | --- | --- |
| T1 Rest | The rest state as the goal, from nothing known | Home ∥ Tare, as Ready |
| T2 Filling | `Filling(FillVolume 2.0)` with the result FillWeight | MoveAxis(40.0) → Dispense(2.0) → Home → Weigh, as Dispensing |
| T3 No result | `Filling(FillVolume 2.0)` without FillWeight | MoveAxis(40.0) → Dispense(2.0) → Home |
| T4 Moved fill position | T2 after FillPosition is set to 35.0 in the AAS | MoveAxis(35.0) → …: the value comes from the AAS |
| T5 Two doses | T2 with Dispense limited to 1.0 mL per dose | Two doses of 1.0 mL, as DoubleDose (numbers: GTPyhop, ENHSP) |
| T6 Check: missing step | Dispensing without NeedleDown | Dosing's Pre fails; MoveAxis(40.0) recommended before it |
| T7 Check: invariant | Home ∥ Weigh | Weigh's invariant (the needle still) is broken by Home |
| T8 Check: the module's skills | Dispensing, DoubleDose, Ready, Checked | No finding, except Checked: it weighs with the needle in the vial (it was written to test decisions) |
| T9 DoubleDose's offer | DoubleDose, two doses of Dose (0.5–10 mL) | FillVolume 1.0–20.0; today's derivation says 0.5–10.0 |
| T10 Discovery | Every composite deleted | Filling offered after a reconfiguration |
| T11 No scale | The scale removed | Filling offered without FillWeight; with FillWeight refused |
| T12 Missing constraint | "Needle at the fill position" removed | The plan fills with the needle up: the integration constraints carry the meaning |

Each case also runs through HDDL and PDDL where it fits, every plan through VAL, and the times are
recorded.
