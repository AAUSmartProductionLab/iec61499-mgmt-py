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
| Line | Agents: products and modules negotiate; since 31 Oct, for the demo, also centrally: FOND-AAS plans a policy with PDDL and a behaviour tree runs it ([framework-plan.md](framework-plan.md), section 1) | No |
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
| Invariant | `>= FillPosition`, `< …` | Holds all the time it runs: a step of a parallel branch may move it, inside the bound (since 29 Oct) |
| Pre, Post, Invariant | `>= NestPosition - RimHeight + InsertDepth`, `= 1000 * ContentVolume / …` | The operand a **formula** (since 6 Nov): numbers and properties with `+ - * /`, brackets and `pi`, linear in the states the capabilities change. An Invariant `=` a formula about a property nothing else sets *defines* it while the capability runs (a derived quantity: how deep the needle is in the liquid) |

The planner splits an expression into operator and operand. `=` and `+=` are **achieved** (a goal
method finds a capability whose Post makes them hold); the other comparisons are **checked**. A value
holds until a Post sets it again (the frame rule).

**A property is a state variable**, identified by:

1. its `SameProperty`, if it has one: the data point of the module's Variables it names, a field of
   its item's series (`LinearAxis_ActualPosition` and `LinearAxis_Homed` in
   `Measurements/LinearAxis`, `Scale_Weight` in `Measurements/Scale`). Every capability that points
   at the same data point talks about the same state; the start state can be read live; and the runtime
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
| LinearAxis | Referencing | Home | Position, Referenced, Speed (12.5 mm/s) | – | Referenced `= true`, Position `= 0.0` | – |
| LinearAxis | Positioning | MoveAxis | Position (0–60 mm), Referenced, Speed (12.5 mm/s), NestPosition (70.0 mm), BottomClearance (1.0 mm), InnerBottomHeight | Referenced `= true` | Position `given` | Position `<= NestPosition - InnerBottomHeight - BottomClearance` |
| Pump | Dosing | Dispense | Volume (0.5–10 mL), FlowRate, FillPosition (40.0 mm), NestPosition (70.0 mm), InsertDepth (5.0 mm), LinearAxisPosition, ContentVolume, Weighed, RimHeight, InnerBottomHeight, InnerDiameter, OutletImmersion | LinearAxisPosition `>= FillPosition` | ContentVolume `+= Volume`, Weighed `= false` | LinearAxisPosition `>= NestPosition - RimHeight + InsertDepth`; OutletImmersion `= LinearAxisPosition - NestPosition + InnerBottomHeight + 1000 * ContentVolume / (pi * InnerDiameter * InnerDiameter / 4)` |
| Scale | Taring | Tare | Tared | – | Tared `= true` | – |
| Scale | Weighing | Weigh | Tared, Weight, LinearAxisPosition, Weighed | Tared `= true`, LinearAxisPosition `= 0.0` | Weight `measured`, Weighed `= true` | LinearAxisPosition `unchanged` |
| Offered | Filling | Dispensing | FillVolume, FillWeight (a result), ContainerType, GraspDiameter, AbsoluteFillError, ContentVolume | ContentVolume `= 0.0` | ContentVolume `= FillVolume` | – |

**Time and the container (6 Nov, vocabulary 0.10).** Speed is the rate of Position, FlowRate the rate
of ContentVolume (`lab:rateOf`): MoveAxis and Home change the needle's position steadily at 12.5 mm/s,
Dispense the content at its flow rate, and each runs as long as its change takes; Tare and Weigh take
what their Completion says (2.0 s, 0.2 s). The container's geometry is the product's (InnerDiameter,
InnerBottomHeight and RimHeight above the face it stands on), where that face is on the axis the
module's (NestPosition): the needle never goes nearer than 1 mm to the inner bottom, stays 5 mm below
the rim while it doses (in place of the fill position, which it starts from: a syringe filled from the
bottom has the needle rise above it), and OutletImmersion is how deep its tip is in the liquid while it
doses. Without a product none of this is known, and the checker says nothing of it.

Position and LinearAxisPosition (the needle's height, named after the item the spec's condition is
about) name `LinearAxis_ActualPosition`, Referenced names `LinearAxis_Homed`,
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
    LinearAxisPosition –                       lab:Position, SameProperty → Variables/Measurements/LinearAxis, field LinearAxis_ActualPosition
    ContentVolume    –                         lab:ContentVolume
    Weighed          –                         lab:Weighed
  CapabilityRelations
    CapabilityRealizedBy → the pump's Skills/Dispense
    ConstraintSet
      Pre        LinearAxisPosition   ">= FillPosition"
      Post       ContentVolume        "+= Volume"
      Post       Weighed              "= false"
      Invariant  LinearAxisPosition   ">= FillPosition"
```

**Where it comes from.** modreg writes the description. What holds of a kind of capability wherever
it is used (Positioning needs the axis referenced) is in the vocabulary, on the capability classes.
What holds on this module (the needle in the vial, the vial on the scale) is in the module's spec,
next to the skill, in the words of ARSO (`cell/modules/filling.yaml`):

```yaml
  Dispense:
    capability:                          # of the Dosing it realizes, on this module
      values: {FillPosition: {value: 40.0, unit: mm}}
      precondition: {LinearAxis.Position: ">= FillPosition"}  # the needle in the container
      invariant: {LinearAxis.Position: ">= FillPosition"}     # and in it while dosing; it may rise
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
   process capability with its Pre and Post; the methods; the rest state; the named values. As built
   (28 Oct), it is read from the AAS's JSON (`modplan.read`) and the vocabulary's Turtle
   (`modplan.vocabulary`), not through the projection, which the few rules do not need.
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

   **As built (28 Oct, `modplan/export.py`).** Both are generated per requirement: the domain is the
   module's, the problem holds the values (as objects) the requirement needs. HDDL expresses adding
   after all: the problem states the sums of its values as static facts (`(sum v_7p5 v_7p5 v_15p0)`),
   and it offers the fewest equal doses, as GTPyhop takes, so a volume above one dose is planned in
   HDDL too. A numeric property is a predicate of one value object (`unknown` when not known); an
   action takes the value it replaces as a parameter and deletes it. Two lessons from Aries: its
   server stops on conditional effects (a `forall`/`when` delete), so the replaced value is a
   parameter; and a method must not bind that parameter in its precondition, since the method's first
   subtasks may change it, so the action's own precondition binds it. The compositions are left out of
   the HDDL (a method for one would need actions restricted to its parts). ENHSP plans from the PDDL
   and Aries from the HDDL, both through unified-planning, whose validator checks every plan; T1 to T12
   stay with GTPyhop, and the four cases of `cell/eval/planners.py` run through all three.

**Discovery.** With the generated methods a process capability is planned without any composition.
For each process capability of the vocabulary the module has no skill for, the planner tries its Post
from the rest state; if a plan exists, the module offers it after a reconfiguration, with the range the
limits of the plan's capabilities give. modreg adds such offers when it derives a module's capabilities
anew (after a skill is described or built): no skill realizes them yet. The derivation from the skills
(`lab:contributes`) stays for the skills that exist; it gives their ranges exactly. A capability
narrower than its parent (BottomUpFilling, a Filling) was not discovered while no constraint said what
makes it narrower (vocabulary 0.6, 30 Oct). Since 0.10 (6 Nov) a constraint says it (the needle kept
near the liquid's surface), with bounds only a product gives, so it is still not discovered but planned
when a product asks for it (below).

**Planning in time (6 Nov).** Every action keeps its own invariants and the requirement's from its
start to its end (`plan._Keeping`): a linear invariant that holds at both holds in between, as every
rate is constant while the action runs. A requirement that bounds a quantity a formula defines is kept
by **tracking** (`plan._tracking`): the action that changes it at a rate (the dose fills the barrel)
is paired with one that moves another state of the formula alongside (Positioning raises the needle),
the rate that can be set is set so that the quantity stays as it is (the pump's flow rate, the axis's
speed being fixed), and the other state is first brought to the middle of what every bound leaves at
the start and at the end. The pair is one planned step with the other `along`; lifting makes it a
parallel block. For 1 mL into the 1 mL syringe: the needle to 57.5 mm, then the dose at 0.396 mL/s with
the needle rising to 25.9 mm, then home: 9.4 s. Every plan is run through the checker in time against
the requirement before it is described (`compose.planned`); a capability the module does not offer is
planned as the vocabulary defines it (`compose.requiring`), and the skill planned for a narrower one
says what it was written for, so that the module offers that.

**Match and plan (6 Nov, the web UI's process planner).** One button binds every step of a product's
sequence: a skill that matches (the matching of Match resources: meaning, values, units, now before
after a reconfiguration); a skill that matches but states constraints, checked against the requirement
by the skill service (`POST /check` with `{"capability", "values"}`); otherwise a skill planned
(`POST /plan`) on a module the matching says can be planned for it, or one that offers a class the
required one narrows (`GET /vocabulary/<class>`: BottomUpFilling's lineage is BottomUpFilling,
Filling). The values are the requirement's properties and the recipe's parameters by meaning, the
container's geometry among them. No module type is used: a module can do what its capabilities say.

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

All done: 1 to 6 on 27 and 28 Oct, 7 on 28 and 29 Oct (the plan's G0 to G7,
[next-steps.md](next-steps.md)):

1. **Vocabulary 0.2 and PPRL 0.2**: the capabilities Referencing, Dosing, Taring, Pressing, Crimping,
   Imaging (auxiliary, each a class of its own: as subclasses they would inherit their parent's
   constraints), the properties Referenced, Tared, Volume (a dose), FillPosition ⊑ Position,
   FillWeight (a result), ContentVolume, Weighed, Stoppered, Capped, Inspected (of the product);
   `lab:realizes` on every skill type; each capability's constraints as `pprl:pre`, `pprl:post` and
   `pprl:invariant` with the expression a BasicConstraint holds; the process capabilities defined by
   what they do to the product. Checked by `aas61499-tools/tests/test_modplan_vocabulary.py`.
   Dispense's parameter keeps its meaning FillVolume for the derivation; the capability's property of
   that name is a Volume.
2. **ARSO 0.11**: `Conditions` and `Completion`; `CapabilityRealizedBy` to a component's skill; the
   constraint elements and conventions. modreg writes them, modsync also reads a 0.10 `Contract`; the
   module specs use the same words (`precondition`, `postcondition`, `invariant`, `after`, `timeout`).
3. **modreg** (`modreg/capabilities.py`): a set per component with its capabilities and their
   constraints, from the vocabulary and the spec (a skill's `capability`), `SameProperty` to the data
   points; the offered capabilities with their Pre and Post.
4. **modplan** (`read`, `check`): the domain from the AAS alone, the checker.
5. **modplan** (`plan`, `lift`, `compose`, `discover`): GTPyhop, the lifting, the skill described in the
   AAS and created online by `modsync reconfigure` (on FORTE:
   `aas61499-tools/tests/test_modplan_live.py`); discovery, with the offers modreg adds. The command
   line: `python -m modplan`.
6. HDDL and PDDL generation; a planner of each kind and VAL, for the evaluation (built with ENHSP,
   Aries and unified-planning's validator in place of VAL: section 6).
7. The recommendations in the editor (G7): `modreg serve` checks a skill (`POST /check/<shell>`) and
   plans one (`POST /plan/<shell>`); the skill editor shows each finding at its step, and its overview
   plans a skill for a capability the module offers.

## 9. Open points

| Point | Proposal |
| --- | --- |
| Position 0.0 by Home or by MoveAxis(0) | Both are plans (DoubleDose uses MoveAxis(0)); Referencing is tried first, as the spec homes after every operation |
| Which HDDL planner | ~~PANDA (pandaPI), which plans partial-order HDDL; check what runs on Windows~~ Aries, through unified-planning, runs on Windows (28 Oct) |
| Numbers in PDDL | ~~Values as objects with an amount; the candidate doses are the requested volume, the limits and what is left~~ Built so (28 Oct) |
| Decisions in a composed skill ("top up if light") | Not planned in the first version; offered as a pattern |
| Tare with the container on the scale (a net weight) | Not modelled. Found 28 Oct: from a start where the scale is not tared, the plan is MoveAxis, Dispense, **Tare**, Home, Weigh, and lifting puts Tare beside the first three; on the machine that would zero the filled vial and lose the fill weight. Nothing says when taring is allowed. A Pre `ContentVolume = 0.0` on Taring orders it before Dispense (and makes Tare and MoveAxis a parallel block), but then the rest state cannot be reached from nothing (the content is not known after power-up). To decide: a property for what is on the scale, or Taring's Pre on the module (the spec's `capability`) |
| The range of a discovered offer with `+=` | Bounded by the container's capacity, which the vocabulary does not have yet (its geometry since 0.10: the capacity follows from the rim, the bottom and the diameter) |
| A skill planned for one product | The plan is ground: the values of the requirement it was planned for are constants of its steps (a FillVolume of 1.0). A skill with parameters would need the tracking's rates as functions of them (the flow rate is not, the rise is) |
| Tracking more than one quantity | One quantity, by one other state, at a time; two bounds on different quantities, or a quantity of three moving states, would need a small linear program instead of one equation |
| The upper bound in Q4's oracle | O5 checks the needle no more than 2 mm above the liquid; nothing checks how deep it is, so the product's MaxImmersion (what makes the rise necessary) is validated by the planner's tests, not by the oracle |

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
| T9 DoubleDose's offer | DoubleDose, two doses of Dose (0.5–10 mL) | FillVolume 1.0–20.0: what the skill reaches, run through the states (done 28 Oct; a rule over its parameter's meaning gave 0.5–10.0) |
| T10 Discovery | Every composite deleted | Filling offered after a reconfiguration |
| T11 No scale | The scale removed | Filling offered without FillWeight; with FillWeight refused |
| T12 Missing constraint | "Needle at the fill position" removed | The plan fills with the needle up: the integration constraints carry the meaning |
| T13 From the bottom | NeedleDeep(58.0) → (Dispense ∥ NeedleRise(40.0)) → Home → Weigh: the needle rises while the pump doses, for a syringe barrel or a foaming liquid | No finding: Dosing's invariant `>= FillPosition` holds over the move (29 Oct) |
| T14 Out of the container | T13 with the needle rising to 30.0 | Dispense keeps Position `>= 40.0` while NeedleRise changes it |

Each case also runs through HDDL and PDDL where it fits, every plan through VAL, and the times are
recorded. As built (28 and 29 Oct): T1 to T14 are tests of `modplan`, GTPyhop's plans and the
checker's findings (`aas61499-tools/tests/test_modplan.py`, `test_modplan_discover.py`); four cases
also run through ENHSP and Aries, every plan validated by unified-planning, timed by
`cell/eval/planners.py` (section 6).
