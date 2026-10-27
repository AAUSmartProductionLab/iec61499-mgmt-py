# Composing skills from the ontology (HTN hybrid)

Design of 27 Oct 2026: a new module level skill is **composed by a planner** from what the AASs say
about capabilities, not copied from an existing skill. The planner is a hybrid of hierarchical task
networks (HTN) and goal regression, as GTPyhop (Nau, 2021) supports. What it plans with is stated in
the Capability Descriptions (IDTA 02020) of the module and its components, with the constraints
02020 already has (pre-, postcondition and invariant, on properties and between capabilities):

| Planning element | What it is here | Where it comes from |
| --- | --- | --- |
| **Action** (operator) | A capability of a component, realized by one of its primitive skills | The component's Capability Description: its capabilities, their **property constraints** (Pre, Post, Invariant) |
| **State** | The values of capability properties, per component (the axis's `Position`, the scale's `Tared`) | The vocabulary's properties; no separate state variables |
| **Task method** (task → subtasks) | A process capability of the module → the component capabilities it is composed of | The module's Capability Description: **ComposedOfSet**, and the constraints that hold between the parts |
| **Goal method** (a value → a capability) | "Make a property have a value" → the capability whose Post sets it | Generated from the Post constraints |
| **Final goal** | The module's rest state: every skill leaves the module so that the next can start | The effects of the module's Reset procedure (section 5) |

The result is a total order of steps. It is lifted to a partial order: steps on different components
with nothing between them become a parallel block, unless an invariant forbids it. The flow then goes
into the AAS like any skill the editor makes, and the rules of rule set 2 make it a program. Why the
wiring rules matter for this: [mapping.md](mapping.md) and
[figures/skill-blocks.drawio](figures/skill-blocks.drawio).

The same model **checks** a flow written by hand. It runs the states through every path and reports
a precondition that does not hold, with the step that would make it hold. The editor shows that as a
recommendation.

Related work: Köcher et al. (2023, arXiv 2312.08801) plan with SMT from capabilities modelled after
CSS, with inputs as preconditions and outputs as effects; Nabizada et al. (CASE 2026, arXiv
2606.02167) generate PDDL from AAS capability descriptions. Neither plans from the 02020
`ConstraintSet`, nor compiles the plan into an IEC 61499 program created online.

## 1. Two levels of capability

| Level | Whose AAS | Capabilities | Who asks for them | Says |
| --- | --- | --- | --- | --- |
| **Component** | The axis, the pump, the scale | Auxiliary (`Referencing`, `Positioning`, `Dosing`, `Taring`, `Weighing`), each realized by one primitive | Nobody outside the module: no product requires them | What holds of the component wherever it is used: MoveAxis needs the axis homed and leaves it at the position asked for |
| **Module** | The filling module | Process (`Filling`), offered, realized by a composite skill if one exists | A product's required capability | What it is composed of and what holds between the parts **on this module**: the pump doses only with the needle at the fill position; the scale is read with the needle out of the vial |

A component capability is a part of a module capability (`CapabilityComposedOf`), never offered on
its own. The constraints between the parts belong to the module, not to the components: the pump
needs the needle in the vial only when it fills, not when it is primed, and only on a module where
the needle is on that axis. The module's integrator states them; the component's vendor states the
rest.

A module capability that is composed of parts but realized by no skill is offered "after a
reconfiguration": the planner can make the skill. Today the derivation finds a module's capabilities
from its skills (`lab:contributes`); with compositions it finds them from the parts the skills' steps
realize (section 6).

The product side has the same structure (required capabilities, transition constraints for the
order of a recipe), so the same planner can later work one level up, on a line.

## 2. The form of a constraint

02020 leaves the form open: a `BasicConstraint` is a string, a `CustomConstraint` a collection one
defines. Chosen: a **CustomConstraint with an operator and an expected value**, the words of a flow
Condition (`eq`, `ne`, `gt`, `gte`, `lt`, `lte`), flat:

```
PropertyConstraintContainer    DosingAtFillPosition
  ConstraintType               CustomConstraint
  PropertyConditionalType      Pre
  CustomConstraint
    Part                       ReferenceElement → the pump's Dosing        (whose start; absent: this capability's)
    Operator                   eq
    Expected                   ReferenceElement → Filling's FillPosition   (or a Property with the value)
  ConstraintPropertyRelations
    ConstraintHasProperty      this container → the axis's Position
```

| Kind | Operator | Expected | Means |
| --- | --- | --- | --- |
| Pre | eq, ne, gt, … | a value or a property | Holds when the capability (or the `Part`) starts |
| Post | eq | a value | Holds when it has succeeded |
| Post | – | – | The property ends with the value the capability was given (an input) or found (an output) |
| Invariant | – | – | Nothing else changes the property while it runs |

Why this form: the planner reads it as triples, with no expression to parse, and its state is a map
from (component, property meaning) to a value, which is what GTPyhop works on. Only `eq` is
**achieved** (a goal method finds the capability whose Post sets the value); the other operators are
**checked**. A value holds until a Post of another capability sets the same property (the frame rule,
as Köcher et al.'s continuation constraints). Two capabilities of one component that have a property
of the same meaning share it: `Referencing` and `Positioning` both set the axis's `Position`.

A `TransitionConstraintContainer` (02020) orders two capabilities with no value involved: Weighing
**Pre** Dosing (weigh after filling). In the module, its first element is a part (the scale's
Weighing), not the module's own capability: the constraint holds only within this composition. That
is a liberty with the template's wording, which has the container's own capability in mind.

## 3. The lab's content (Vocabulary 0.2)

New capabilities and properties in `capabilities.ttl`, all auxiliary except what Filling had:

| Term | Kind | Characterizes |
| --- | --- | --- |
| `lab:Referencing` ⊑ `lab:Positioning` | capability | Move an axis to its reference, where its position is known |
| `lab:Dosing` | capability | Deliver a volume of liquid through a pump's outlet |
| `lab:Taring` ⊑ `lab:Weighing` | capability | Set a scale to zero |
| `lab:Referenced` (Boolean) | property | Referencing, Positioning |
| `lab:Volume` (mL) | property | Dosing |
| `lab:Tared` (Boolean) | property | Taring, Weighing |
| `lab:FillPosition` ⊑ `lab:Position` (mm) | property | Filling: where the needle is in the container |
| `lab:FillWeight` (g) | property | Filling: the weight of the container after filling, a result |

The constraints of the component capabilities, on the capability classes (written into each
component's AAS by modreg):

| Capability | Realized by | Pre | Post | Invariant |
| --- | --- | --- | --- | --- |
| Referencing | Home | – | Referenced eq true, Position eq 0.0 | – |
| Positioning | MoveAxis | Referenced eq true | Position (given) | – |
| Dosing | Dispense | – | Volume (given) | – |
| Taring | Tare | – | Tared eq true | – |
| Weighing | Weigh | Tared eq true | Weight (found) | – |

```turtle
lab:Positioning
  pprl:pre  [ a css:PropertyConstraint ; pprl:onProperty lab:Referenced ; pprl:operator "eq" ; pprl:expected true ] ;
  pprl:post [ a css:PropertyConstraint ; pprl:onProperty lab:Position ] .
```

`pprl:pre`, `pprl:post`, `pprl:invariant`, `pprl:onProperty`, `pprl:operator` and `pprl:expected` are
new in PPRL 0.2 (annotation properties, as `lab:contributes` is: they are said of classes). A skill
type says which capability it realizes (`lab:realizes`: Home → Referencing, MoveAxis → Positioning,
Dispense → Dosing, Tare → Taring, Weigh → Weighing), which replaces `lab:contributes`.

The filling module's composition, in its spec (modreg writes the 02020 elements from it):

```yaml
capabilities:
  Filling:
    properties:
      FillPosition: {value: 40.0, unit: mm}        # a placeholder, as NeedleDown's constant today
    composed_of:
      parts: {Positioning: LinearAxis, Dosing: FillingPump, Weighing: Scale}
      same: {FillVolume: FillingPump.Volume, FillWeight: Scale.Weight}     # 02020 SameProperty
      constraints:
        - {pre: Dosing, property: LinearAxis.Position, eq: FillPosition}  # the needle in the vial
        - {pre: Weighing, after: Dosing}                                   # a transition constraint
        - {pre: Weighing, property: LinearAxis.Position, eq: 0.0}         # the needle out of the vial
        - {invariant: Weighing, property: LinearAxis.Position}            # no motion while weighing
```

`SameProperty` binds the module's properties to the parts': a requirement's FillVolume becomes the
Volume the pump is given, and the scale's Weight is the FillWeight the product asked for.

## 4. The skill's runtime conditions (ARSO 0.11)

The `Contract` of a primitive stays the executable check over the module's signals, renamed to the
words of 02020 and CSS:

| ARSO 0.10 | ARSO 0.11 | |
| --- | --- | --- |
| `Contract` / `Requires` | `Conditions` / `Precondition` | `Homed` |
| `Contract` / `Ensures` | `Conditions` / `Postcondition` | `NOT Moving AND ABS(ActualPosition - Position) < 0.001` |
| `Contract` / `Invariant` | `Conditions` / `Invariant` | |
| `Contract` / `After` | `Completion` / `After` | Ends the skill after a duration, if it has no Postcondition |
| `Contract` / `Timeout` | `Completion` / `Timeout` | |

They are linked to the capability's constraints by what is there already: the primitive realizes the
capability (`CapabilityRealizedBy`), so its `Precondition` is the runtime form of that capability's
Pre constraints. No reference is added. A later check can say whether the two agree.

## 5. How the planner reads it

1. The projection of the module's and the components' AASs (`modreg graph`) and the vocabulary in
   one graph. A new projection query turns the 02020 constraints into `css:PropertyConstraint` and
   `css:TransitionConstraint`.
2. SPARQL makes the domain: for each component capability an action (Pre, Post, Invariant); for each
   module capability a method per composition (its parts, ordered by the transition and Part
   constraints); for each property a Post sets, a goal method; the named values (FillPosition).
3. The start state is the rest state: the Reset procedure's steps, applied to "nothing known", give
   Referenced = true, Position = 0.0, Tared = true. Every composed skill must end there; nobody
   states that rule (the spec's comment, "homing after every operation", is what it encodes).
4. GTPyhop is given the task `Filling(FillVolume=2.0, FillWeight)` and the rest state as a goal.
5. The plan is lifted to a partial order, parameters are bound by `SameProperty` (Volume becomes a
   parameter of the new skill with the requirement's range), and the flow is written in the
   planner's elements.
6. The derivation checks that the new skill offers the required capability.

## 6. Changes, in order

1. Vocabulary 0.2 and PPRL 0.2 (section 3), with the ontology checks.
2. ARSO 0.11: `Contract` → `Conditions` and `Completion` in ARSO, modreg, modsync and modgen.
3. modreg: a Capability Description in each component's AAS (its capabilities, realized by its
   primitives, with their constraints); the module's composition from the spec.
4. The projection of the constraints; the derivation of a module's capabilities from its
   compositions instead of `lab:contributes`.
5. The planner and the checker (GTPyhop), then the recommendations in the editor.

## 7. Open points

| Point | Proposal |
| --- | --- |
| A requirement without FillWeight still gets a weighing | Two compositions of Filling (with and without Weighing); the planner takes the one whose Posts cover the goals |
| Position 0.0 by Home or by MoveAxis(0) | Both are plans; goal methods are tried in order, Referencing first (it also restores Referenced), as the module's own skill does |
| Decisions in a composed skill ("top up if light") | Not planned in the first version; offered as a pattern |
| Tare with the container on the scale (a net weight) | Not modelled |
| More than one dose for a volume above the pump's range | Not planned in the first version |

## 8. The test case with the filling module

The module's own skills are the ground truth:

| Case | Given | Expected |
| --- | --- | --- |
| T1 Rest | The goal of the Reset procedure, from nothing known | Home ∥ Tare |
| T2 Filling | `Filling(FillVolume 2.0, FillWeight)` | MoveAxis(40.0) → Dispense(2.0) → Home → Weigh, as Dispensing |
| T3 Moved fill position | T2 after FillPosition is set to 35.0 in the module's AAS | MoveAxis(35.0) → …: the value comes from the AAS |
| T4 Check: missing step | Dispensing without NeedleDown | Dispense's Pre (Position eq FillPosition) fails; MoveAxis(40.0) recommended before it |
| T5 Check: invariant | Home ∥ Weigh | Weigh's invariant on Position is broken by Home |
| T6 Check: own skills | Every skill of the module | No finding |
