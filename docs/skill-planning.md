# Composing skills from the ontology (HTN hybrid)

Design of 27 Oct 2026, decided the same day: a new module level skill is **composed by a planner**
from what the ontology says about skill types, not copied from an existing skill. The planner is a
hybrid of hierarchical task networks (HTN) and goal regression, as GTPyhop (Nau, 2021) supports:

| Planning element | What it is here | Where it comes from |
| --- | --- | --- |
| **Action** (operator) | A primitive skill of a component, with its precondition and effect | The skill type in the vocabulary (section 2); the module's components from its AAS |
| **Task method** (task → subtasks) | A required capability → the skill type that contributes it, after its precondition is reached; or an existing composite skill that already offers it | `lab:contributes` (exists); the derived offered capabilities (exist) |
| **Goal method** (state → an action) | "Reach a value of a state variable" → the skill type whose effect sets it | Generated from the effects (section 2) |
| **Final goal** | The module's rest state: every skill leaves the module so that the next can start | The effects of the module's Reset procedure (derived, section 4) |

The result is a total order of steps. It is lifted to a partial order: steps on different components
with no condition between them become a parallel block, unless an invariant forbids it (section 3).
The flow then goes into the AAS like any skill the editor makes, and the rules of rule set 2 make it
a program. Why the wiring rules matter for this: [mapping.md](mapping.md) and the figure
[figures/skill-blocks.drawio](figures/skill-blocks.drawio).

The same model **checks** a flow written by hand. It runs the states through every path and reports
a precondition that does not hold, with the step that would make it hold. The editor shows that as a
recommendation.

## 1. What has to be said that is not said today

| Needed | Today | Extension |
| --- | --- | --- |
| What a skill type needs and what it changes | Only a comment ("needs the axis homed") | Preconditions, effects and invariants on the skill types, over **state variables** (section 2) |
| The state of a component and of the product | Not modelled. The AAS `Contract` of a primitive has runtime expressions over the module's signals (`Homed`, `NOT Moving AND ABS(ActualPosition - Position) < 0.001`), which a planner cannot read | A small vocabulary of state variables per component kind and of the container (section 2) |
| Named values: where "the fill position" is | Only the constant 40.0 in Dispensing's NeedleDown step | A meaning on the constant: `lab:FillPosition` (section 4) |
| What a product asks the module to measure | Filling has no result property; that Dispensing weighs is not required by anything | A result property `lab:FillWeight` of Filling (section 4) |
| The rest state | Implicit in the Reset procedure `[Home, Tare]` | Derived from the procedure's steps (section 4) |
| Task and goal methods | – | **Nothing new.** Read from `lab:contributes`, the derived capabilities and the effects |

Nothing changes in the structure of the AAS (ARSO stays 0.10): the additions are meanings
(supplemental semantic ids) and the vocabulary they point to.

## 2. The schema: state variables and conditions (PPRL 0.2)

Generic terms go into PPRL, which already holds the CSS-level relations. The lab's content goes into
the vocabulary. CSS has the three kinds of condition as `css:Constraint` (precondition, postcondition,
invariant) on capabilities. Here they sit on the skill types, which is where the planner needs them,
and are subclasses of it.

```turtle
pprl:StateVariable a owl:Class ;
  rdfs:comment "A variable of the state of a kind of component or of the product, which a skill reads or sets." .
pprl:ofKind a owl:AnnotationProperty ;          # the component kind, or the product (pprl:Container)
  rdfs:comment "The kind of thing a state variable belongs to." .
pprl:Container a owl:Class ; rdfs:subClassOf css:Product .

pprl:Condition a owl:Class ; rdfs:subClassOf css:Constraint .
pprl:Precondition rdfs:subClassOf pprl:Condition .   # holds when the skill starts
pprl:Effect       rdfs:subClassOf pprl:Condition .   # holds when it has succeeded (a postcondition)
pprl:Invariant    rdfs:subClassOf pprl:Condition .   # no other step changes the variable while it runs

pprl:onVariable  a owl:ObjectProperty .              # the state variable
pprl:hasValue    a owl:AnnotationProperty .          # a value: true, a named state, a number
pprl:valueOf     a owl:AnnotationProperty .          # or the value of the skill's parameter that means this property
pprl:onComponent a owl:AnnotationProperty .          # whose variable: the skill's own (default) or another of the module

# On a skill type (a class, so annotations, as lab:contributes is):
pprl:requires a owl:AnnotationProperty .   pprl:sets a owl:AnnotationProperty .   pprl:keeps a owl:AnnotationProperty .
```

A condition is "variable = value", an effect "variable := value". This is the SAS+ form a planner
like GTPyhop works on directly (its state is a set of variables), and the form the runtime `Contract`
already has ("conditions over the resource's state variables", ARSO).

## 3. The lab's content (Vocabulary 0.2)

A new file `Vocabulary/states.ttl` with the state variables, and the conditions added to `skills.ttl`:

| State variable | Of | Values |
| --- | --- | --- |
| `st:Homed` | a linear axis | true / false: its position is known |
| `st:AxisPosition` | a linear axis | `st:Reference` (at its switch) or a position (`lab:Position`, mm) |
| `st:Tared` | a scale | true / false |
| `st:Volume` | the container | what has been filled into it (`lab:FillVolume`, mL) |
| `st:WeightKnown` | the container | true / false: it has been weighed since it was last filled |

| Skill type | Requires | Sets | Keeps |
| --- | --- | --- | --- |
| Home | – | Homed := true, AxisPosition := Reference | – |
| MoveAxis(Position) | Homed = true | AxisPosition := Position | – |
| Dispense(Volume) | AxisPosition = `lab:FillPosition`, of the module's axis | Volume := Volume, WeightKnown := false | AxisPosition |
| Tare | – | Tared := true | – |
| Weigh | Tared = true | WeightKnown := true | AxisPosition (the scale must not be read while the needle moves) |
| PressStopper, RetractPiston, Crimp, Capture… | later, with the stoppering module | | |

For example:

```turtle
skl:MoveAxis
  pprl:requires [ a pprl:Precondition ; pprl:onVariable st:Homed ; pprl:hasValue true ] ;
  pprl:sets     [ a pprl:Effect ; pprl:onVariable st:AxisPosition ; pprl:valueOf lab:Position ] .

skl:Dispense
  pprl:requires [ a pprl:Precondition ; pprl:onVariable st:AxisPosition ; pprl:hasValue lab:FillPosition ;
                  pprl:onComponent pprl:OfTheModule ] ;
  pprl:sets     [ a pprl:Effect ; pprl:onVariable st:Volume ; pprl:valueOf lab:FillVolume ] ,
                [ a pprl:Effect ; pprl:onVariable st:WeightKnown ; pprl:hasValue false ] ;
  pprl:keeps    [ a pprl:Invariant ; pprl:onVariable st:AxisPosition ; pprl:onComponent pprl:OfTheModule ] .
```

The invariants matter only when the plan is lifted to a partial order. Without the one on Weigh,
Home and Weigh (no condition between them, different components) would run in parallel, and the
scale would be read while the needle moves.

## 4. What the module's AAS adds

**The fill position.** The constant of NeedleDown's Position binding carries the meaning
`lab:FillPosition` (a subclass of `lab:Position` in `capabilities.ttl`) as its supplemental
semantic id. The projection reads it as a named value of the axis: the planner learns that the fill
position of this module's axis is 40.0 mm. It also learns which axis is the needle's, if a module has
several. modreg writes the meaning from the spec (`{MoveAxis: {Position: 40.0}, as: NeedleDown,
meaning: {Position: FillPosition}}` or similar).

**The result a product asks for.** `lab:FillWeight` (g, characterizes Filling): the weight of the
container after filling, for the batch record. A requirement of Filling with a FillWeight result
becomes the goal WeightKnown = true at the end. Weighing stays an auxiliary capability.

**The rest state.** The steps of the module's Reset procedure, applied to "nothing known", give
Homed = true, AxisPosition = Reference, Tared = true. Every composed skill must end there, so the
planner adds Home at the end of Dispensing. Nobody states that rule.

**Which components a module has**, and the kind of each, are in the AAS already (the components'
AASs and their asset types `.../Component/LinearAxis`). The projection needs one more rule to type
a primitive skill by the kind of the component it is on.

## 5. How the planner reads it

1. The projection of the module's AASs (`modreg graph`) and the vocabulary in one graph.
2. SPARQL turns them into a planning domain: for each primitive the module has, an action with its
   conditions; for each process capability, the task methods; for each variable a skill sets, a goal
   method; the initial state (the rest state) and the named values.
3. GTPyhop is given the task `Filling(FillVolume=2.0)` plus the goals of the required results and
   the rest state.
4. The plan (MoveAxis(40.0), Dispense(2.0), Home, Weigh) is lifted to a partial order, parameters
   are bound by meaning (Volume is a parameter of the new skill with the requirement's range), and
   the flow is written in the planner's elements.
5. The derivation (F3) checks that the new skill offers the required capability.

## 6. Open points

| Point | Proposal |
| --- | --- |
| Where the fill position is stated | A meaning on the step's constant (above). Alternative: a named position in the module's Parameters submodel, if a module has no skill that goes there yet |
| The runtime `Contract` and the planning conditions | Later: the Contract's Requires and Ensures carry the state they check as a supplemental semantic id (`Homed` checks `st:Homed`), so a check can say that the module's runtime guard and the vocabulary agree |
| Decisions in a composed skill ("top up if light") | Not planned in the first version; offered as a pattern |
| Tare with the container on the scale (a net weight) | Not modelled; Tare has no precondition |

## 7. The test case with the filling module

Next, after the vocabulary: requirements against the filling module, each with what the planner
should return. The module's own skills serve as ground truth (from the requirement of Dispensing the
planner should give Dispensing back; from the Reset procedure's goal, Home and Tare in parallel).
