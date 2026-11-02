# Journal paper: the method section, structure and draft

Started 2 Nov 2026, for the authors. It proposes the structure of the method section and the use
cases, and drafts the parts we write ourselves:
- the concepts: the three AASs and how they interact;
- the resource AAS, with the submodels of our own (Skills, Variables, Parameters, Control
  Configuration) and what we changed in IDTA's;
- the process AAS (Process Information, Bindings, Validation);
- the two use cases and how each is set up.

The colleagues write the product AAS (section 3.3). That subsection has a brief here instead of text:
what it has to say for the other subsections to hold.

The figures are the pages of [figures/journal-figures.drawio](figures/journal-figures.drawio), named
by page. What goes into the paper beyond the method is in [journal-paper.md](journal-paper.md). The
sources of the draft:
- [aas-models.md](aas-models.md) and [ppr-model.md](ppr-model.md);
- aas-model's `docs/lab-aas.md` and `docs/lab-submodels/`;
- [precedence-graphs.md](precedence-graphs.md).

Text in *[Authors: ...]* is a note for us, not paper text.

## The structure

| § | Title | What it says | Figure | Who |
| --- | --- | --- | --- | --- |
| 3 | The AAS models | One paragraph: three AASs, each owned by one party, joined by a capability and by references | – | us |
| 3.1 | Three AASs around a capability | Product, process, resource; the ISA-88 recipe levels; why the process is an AAS of its own; matching by meaning | `ppr-overview`, `isa88-levels` (or one of them) | us |
| 3.2 | How the models refer to each other | The chain from a product's step to a module's OPC UA method, reference by reference; the two links by shared meaning; one value followed through | `submodel-references` (generic), `ppr-map` | us |
| 3.3 | The product AAS | Bill of material, Process Parameters, required capabilities, the Production Sequence as a partial order with joints | `product-bom`, `production-sequence` | colleagues |
| 3.4 | The resource AAS | 3.4.1 the hierarchy; 3.4.2 the Skills submodel; 3.4.3 capabilities derived from skills; 3.4.4 interface and mapping; 3.4.5 Variables; 3.4.6 Parameters and the Control Configuration | `resource-bom`, `skill-hierarchy`, `capability-match` | us |
| 3.5 | The process AAS | Process Information, Bindings, Validation; checking a binding by following its references | `ppr-map` (if not used in 3.2), `bpmn-levels` | us |
| 3.6 | Who reads and writes what | The applications (planner, skill editor, the integrator's tools, the two orchestrators) against the submodels; plugging in a module and introducing a product | `model-use`, `bpmn-integration` | us |
| 3.7 | Templates, classes and ontologies | Each submodel of our own as a template with generated classes and a description; ARSO's templates written from the ontology | – (a table) | us |
| 4 | Use cases | Two cases that stress the models in different ways | – | us |
| 4.1 | Pharmaceutical filling on a modular line | The physical line, its modules and products, how the AASs are made and run | `submodel-references-pharma`, `production-sequence-pharma` | us |
| 4.2 | Battery pack remanufacturing | A pack taken apart in a simulated disassembly cell: subassemblies with sequences of their own, joints, a decision on measured condition | `submodel-references-battery`, `production-sequence-battery` | us, with the colleagues for the product |
| 4.3 | What each case exercises | A table: which model feature each case needs | – (a table) | us |

How we got to this order:
- **Concepts before the submodels:** the reader meets the three AASs and the chain between them
  (3.1, 3.2) before any element, so each submodel in 3.3 to 3.5 is read as a link in that chain.
- **Product, then resource, then process:** the process AAS binds the other two, so it comes last.
  The colleagues' subsection then stands alone between our two.
- **Generic figures in the method, case figures in the use cases.** The method uses the generic
  `submodel-references` and `production-sequence`. Their `-pharma` and `-battery` pages show the
  same structure filled in, in section 4.
- **The use cases say how they are set up, not how they perform.** The evaluation keeps the numbers
  ([journal-paper.md](journal-paper.md), "Evaluation").

Too many figures: 3.1 needs one of `ppr-overview` and `isa88-levels`, and 3.6 one of `model-use` and
`bpmn-integration`. We recommend `ppr-overview` and `model-use`, as the other two repeat what a table
can say.

---

## 3 The AAS models

A production system that adapts to its products has to answer three questions from models alone:
- what the product needs;
- what the resources can do;
- how the one is carried out by the other.

We give each answer an AAS of its own:
- the **product AAS** says what the product needs;
- the **resource AAS** what a line, a module or a component can do and how it is called;
- the **process AAS** how one product's recipe is carried out on one line.

The three meet in the capability. The product requires it, the resource offers it, and the process
binds the one to the other. Every other link between them is a model reference that a tool can
follow and check.

### 3.1 Three AASs around a capability

The split follows the recipe levels of ISA-88, which pharmaceutical batch production already
uses (Fig. `isa88-levels`):
- **The product AAS is the general recipe.** It holds what the product is, its bill of material,
  the processes it needs with the product's values for them, the capabilities those processes
  require, and the order of the steps. It names no equipment.
- **The process AAS is the master recipe.** It holds the general recipe bound to one line: per
  step, the resource and the skill that carry it out and what each input of the skill is handed.
- **The resource AAS describes the equipment:** one per line, module and component.

Each AAS has one owner and changes for one reason (Fig. `ppr-overview`):

| AAS | Owner | Changes when |
| --- | --- | --- |
| Product | Product designer | The product changes |
| Process | Line engineer | The line is reconfigured, or the product moves to another line |
| Resource | Vendor; the integrator's tools online | A resource is delivered, changed or rebuilt |

We keep the process AAS apart from the product AAS for three reasons:
1. A reconfiguration then changes the resource AASs and at most the process AAS, never the product.
2. One product on two lines is one product AAS and two process AASs.
3. An orchestrator that binds steps per order replaces only bindings and leaves the recipe alone.

**Matching by meaning.** A product's parameter, the property of the capability it requires, the
property of the capability a module offers, and the input of the skill that realizes it are four
elements in three AASs. They carry the same meaning, an IRI of the lab's vocabulary, as a
supplemental semantic id; the FillVolume of the vial is an example. The primary semantic id stays
the template's, so an IDTA reader still finds what it expects. The vocabulary's meaning is what
matching and binding compare. Two parties can therefore name their elements as they like.

### 3.2 How the models refer to each other

Fig. `submodel-references` draws every reference between the AASs of one product on one line. Read
from a step of the recipe to the module's program, they form a chain:

1. A **step** of the product's Production Sequence refers to its **process** in the product's
   Process Parameters.
2. The process refers to its **required capability** in the product's Capability Description.
3. The process AAS **binds** the step to a **module** and a **skill** in the module's Skills.
4. The module's **offered capability** is realized by that skill (`RealizedBy`, a model reference).
5. A **command** of the skill (Start) refers to an **action** of the module's Asset Interfaces
   Description. The Asset Interfaces Mapping Configuration maps the command's Operation onto that
   action.
6. The action is an **OPC UA method** of the module's IEC 61499 program.
7. A **composite** skill's steps refer to the **primitives** they run, in the AASs of the module's
   components; the module's Hierarchical Structures names those components by asset id.

Two links are made by shared meaning instead of a reference:
- **A skill's input and the capability property it sets.** Both carry the meaning of the product's
  parameter, so a product's value finds the input it is handed to (Fig. `ppr-map`).
- **A field of a time series and the Operation variable it shows.** A module publishes a skill's
  state and results through its interface. The mapping writes them as rows of a time series, and
  the field names the variable it shows by its meaning.

*[Authors: one value followed through, as a short paragraph or a margin of Fig. `ppr-map`. Source:
[aas-models.md](aas-models.md) section 6.]* The vial's FillVolume (2 mL) goes through four AASs:
1. it is a product parameter of the process Filling;
2. it is the value the required capability Filling asks for;
3. it lies within the range the filling module offers (0.5 to 10 mL);
4. the process AAS binds it to the input Volume of the skill Dispensing;
5. the first step of Dispensing hands it on to the primitive Dispense of the pump.

The reference chain makes three things checkable by following references alone:
- that a product can be made on a line;
- that a binding is complete;
- what a reconfiguration breaks.

### 3.3 The product AAS (the colleagues)

*[Authors: the colleagues write this subsection. For 3.2, 3.5 and 4 to hold, it needs to say the
following.]*

- **Bill of material** (IDTA 02011 Hierarchical Structures). Each part states its quantity and unit.
  A part with an AAS of its own is a self-managed entity naming its asset id: a subassembly with a
  sequence of its own, or a bought part. The bill holds parts only, no joints.
- **Process Parameters** (IDTA 02031-1, extended):
  - per process, the product's values, with the vocabulary's meanings and units;
  - `ProcessBoM`: what the process uses and in which role (workpiece, incorporated, output);
  - `RequiredCapability`: a reference into the Capability Description.
- **Capability Description** (IDTA 02020, role Required): the required capabilities with their
  values or ranges.
- **Production Sequence 4.0** (ours, proposed; [precedence-graphs.md](precedence-graphs.md)):
  - the recipe as a partial order, with `partial` blocks and `After` between sibling steps;
  - the joints as AnnotatedRelationshipElements in the steps that make or break them;
  - at most one sequence per archetype (Assembly, Disassembly);
  - calls of the sequences of subassemblies.
- **What 3.5 relies on:**
  - a step's `NodeId`, and its path through blocks and branches, which a binding names;
  - the sequence's `Revision`, which a binding records.

Figures: `product-bom` and `production-sequence`.

### 3.4 The resource AAS

#### 3.4.1 Line, module and component

A line is made of modules, and a module of components. Each is an AAS, and its asset type says which
kind it is (Fig. `resource-bom`):
- **A system** (the line) holds Hierarchical Structures naming its modules.
- **A module** holds the following (Table R1):
  - a Nameplate and Hierarchical Structures naming its components;
  - an Asset Interfaces Description and its Mapping Configuration;
  - a Capability Description of what it offers;
  - Skills;
  - Variables.
- **A component** is a part of a module that acts: an axis, a pump, a scale. It holds only Skills,
  its primitives. It has one AAS per module it is built into, so a module with three axes has three.
  All components of one kind share their asset type and so the same primitives. A component has no
  interface of its own: its module carries its skills out.

The resource types follow the resource ontology ARSO [jensen2026ontology]. ARSO says what each kind
must hold, and declares every element of our own submodels.

**Table R1.** The submodels of a module AAS.

| Submodel | Template | Status |
| --- | --- | --- |
| Nameplate | IDTA 02006-3 | as published |
| Hierarchical Structures | IDTA 02011-1-1 | as published |
| Asset Interfaces Description | IDTA 02017-1-1, W3C WoT terms | extended: actions, OPC UA binding |
| Asset Interfaces Mapping Configuration | IDTA 02027 | extended: an Operation as source |
| Capability Description | IDTA 02020 [idta02020] | one change: `RealizedBy` a model reference |
| Skills | ours (ARSO) | new |
| Variables | ours (with IDTA 02008 time series) | new |
| Parameters, Control Configuration | ours (ARSO) | optional; the latter kept outside the AAS |

#### 3.4.2 The Skills submodel

No published template describes a skill with its parameters, its composition and its conditions.
IDTA 02015's Control Component describes a skill as one Operation. We started from it and replaced
it. Fig. `skill-hierarchy` shows the filling module's skills. This is their structure:

```
Skills
├── {Skill}                       semantic id .../skill; kind and type as supplemental ids
│   ├── Deployment                Built | Described
│   ├── Start, Stop, Abort, Reset the commands
│   │   ├── InterfaceReference    → the action of the module's interface that calls it
│   │   ├── {Operation}           in: Session, parameters; out: Accepted, ErrorID, results
│   │   └── Steps                 of a composite: what the command runs
│   ├── Conditions                of a primitive: Precondition, Postcondition, Invariant
│   └── Completion                of a primitive: After, Timeout
├── RuleSet                       the rules the module's program is built by
└── Errors                        the codes an ErrorID can carry
```

**A skill is its commands.** An IEC 61499 skill is a state machine that is started, stopped,
aborted and reset, and each command is called and answers on its own. A skill therefore holds four
commands, each with three parts:
- the action of the module's interface that calls it;
- an Operation that is the call's signature;
- for a composite, the steps the command runs.

The Operation's variables are the protocol and the parameters:
- in: `Session`, the occupation the caller holds;
- out: `Accepted` and `ErrorID`;
- the skill's parameters and results, each with its unit, limits and default as qualifiers, and its
  meaning as a supplemental semantic id.

There is no separate list of parameters. One Operation per skill, as in the Control Component,
cannot say what stopping a skill runs.

**Three kinds of skill**, told apart by a supplemental semantic id:
- **Primitive:** one function block of the program that moves one component (MoveAxis, Dispense,
  Weigh). It is described in the AAS of that component.
- **Composite:** a module-level skill whose steps run primitives (Dispensing). It is described in the
  module's AAS.
- **ModuleControl:** the module's own commands (Occupy, Release, Reset, Start, Stop, Abort, Clear).
  They sit in the same list and are called the same way.

A second supplemental id gives the skill's type, a class of the vocabulary that says what the skill
does. A composite written for a narrower capability than its steps contribute names that capability
too. BottomUpFilling, a kind of Filling, is an example.

**A composite's steps are a recipe's steps.** They use the elements of the Production Sequence, with
the same idShorts and semantic ids:
- `NodeId`, `Kind`, `Name` and `Order`;
- `Skill`, a model reference to the primitive the step runs, usually in a component's AAS;
- `Bindings`: per input of that primitive, a constant or a variable of the command's own Operation;
- `Outputs`: which result of the command the step gives;
- `parallel`, `decision` and `conditional` steps, with their `Branches` and `Condition`.

A module's composition of skills and a product's recipe are then read, drawn and edited by the same
code (the web UI's planner and skill editor), and checked by the same rules.

**Conditions and Completion** are what a planner needs to compose new skills from primitives, and
what the program checks while a primitive runs:
- a primitive states its precondition, postcondition and invariant as expressions over the
  module's state variables;
- it states when it is complete (a duration, or a timeout).

The same constraints, written as capability constraints, are what the HTN planner composes skills
from (Section *[planning]*).

**Deployment and RuleSet** say what the program carries out:
- `Deployment` is `Built` when the module's program carries the skill out, and `Described` when the
  skill is in the AAS only. A described skill is built online by the integrator's tools; until then,
  the capability it realizes is offered "after a reconfiguration" (3.4.3).
- `RuleSet` names the rules by which a skill maps to the program (the module rules; Section
  *[IEC 61499]*), so a tool knows it can read the program back and build a described skill.

Which block of the program is which skill is the integrator's record, not the AAS's (3.4.6).

**What is not in Skills:**
- the skill's state and results as they are now (Variables, 3.4.5);
- which block of the program it is (Control Configuration, 3.4.6);
- which capability it realizes (the capability refers to its skill, never the other way);
- a list of the skills a composite uses (its steps refer to them).

*[Authors: Table R2 could set Skills against IDTA 02015 (kept: Errors; dropped: per-skill Modes and
device-level entries; ours: commands with InterfaceReference, Operation and Steps, Conditions,
Completion, Deployment, RuleSet). Source: [aas-models.md](aas-models.md) section 2.3.]*

#### 3.4.3 Capabilities derived from skills

A module's offered capabilities (IDTA 02020) follow from its skills and the vocabulary. We derive
them and write them into the Capability Description instead of typing them by hand:
- **Which capability:** from the skill types its steps run. The vocabulary says Dispense contributes
  Filling.
- **Its properties:**
  - from the parameters' meanings and limits (FillVolume 0.5 to 10 mL);
  - from the steps' constants (FlowRate);
  - from facts of the machine stated once per module (ContainerType vial).
- **The link:** `RealizedBy` is a model reference to the skill. The template has an external
  reference there; ours can be followed and checked.

Derived elements carry the qualifier `Derived`, so a new derivation replaces only what it derived.
A capability whose skill is only described carries `Availability = AfterReconfiguration`. A planner
then sees what the line could do after a change, not only what it does now. Fig. `capability-match`
sets the filling module's offer against the three products, property by property.

A module also lists its components' capabilities, with the role NotAssigned. Each carries the
constraints of the primitive that realizes it as `BasicConstraint` expressions. The HTN planner
composes new skills from these.

#### 3.4.4 The interface and its mapping

The Asset Interfaces Description (IDTA 02017) holds only how to reach things, and Skills holds what
they mean. The Mapping Configuration (IDTA 02027) joins the two. We extended both templates:
- **Actions:**
  - every method of the module's OPC UA server is an action with its input and output schemas in
    call order;
  - its owning object is named by browse path, since FORTE assigns new node ids at every start;
  - each action carries the command and the skill it carries out as supplemental semantic ids, so
    it is found by meaning.
- **The other direction of mapping.** The template maps interface elements onto submodel elements.
  We also allow a command's Operation as the source and an interface action as the sink. An
  Operation invoked at the AAS server is then delegated to the data management platform (DMP). The
  DMP calls the module's OPC UA method as the mapping says, and answers with the method's reply. The
  AAS is then the configuration of its own connection: nothing outside it says how a skill is
  called.

#### 3.4.5 Variables: time series, not values

A module keeps no live value in its AAS. Its Variables submodel (ours, built on IDTA 02008 time
series) names, per group of values that change together, a time series:
- `State/Module`, the PackML state and occupation;
- `State/<Skill>`, a skill's state, error and results;
- `Measurements/<Item>`;
- `Log/<command>`, one row per call.

Each series is a record of fields and a segment naming the table it is stored in. The mapping
writes a row whenever the module publishes; a reader asks the database for the latest value or a
span. A live value in the AAS would be written at the module's rate into a server that keeps none of
its history.

`Measurements/Coordinates` holds where the module and its points are, as a tree of transforms across
AASs:
- the root is the table's base;
- a module's base is relative to the root, its mounts relative to its base, an end effector to its
  mount;
- a shuttle is relative to the table, and a product to the shuttle it rides.

A coordinate that moves names the variable that moves it. *[Authors: keep to one paragraph or drop;
the locations are not this paper's argument. Source: [locations-and-layout.md](locations-and-layout.md).]*

#### 3.4.6 Parameters and the Control Configuration

- **Parameters** (ours, ARSO) holds a resource's settings that are not a skill's: a value, its unit
  and the interface property it is written through. They change when the resource is set up. A
  skill's parameters change with every call and stay in its Operation.
- **The Control Configuration** (ours, ARSO) is the integrator's record of what was built on the
  module's controller:
  - the source, generator and rule set;
  - per skill and per step of a command, the function block instance that carries it out, its type
    and the type's hash;
  - whether the running program still is the one its source generates (`SyncState`, with its
    differences);
  - a change log, one entry per reconfiguration.

  It refers to skills and steps by model reference. A tool can therefore go from a block of the
  running program to the skill and back, without names agreeing by convention. We keep it outside
  the module's AAS: it changes with every build, while the AAS says what the module should do. The
  AAS keeps only `RuleSet` and each skill's `Deployment`.

### 3.5 The process AAS

A process AAS binds one product's recipe to one line. It has three submodels of our own.

**Process Information** says what is bound:
- the product's and the line's AAS, and the recipe (the product's sequence of the archetype run);
- the recipe's `Revision` the bindings were made for;
- a `Status`: Draft, Approved or Withdrawn.

The shell names the product's and the line's assets as specific asset ids, so the processes of a
product, or of a line, are found by asset id. The revision is recorded because bindings name the
recipe's steps: a changed recipe can leave a binding pointing at a step that is gone.

**Bindings** holds one step binding per step of the recipe, named by the step's `NodeId`:
- `Step`, a model reference to the step, through its blocks and branches;
- `Resource`, the module's AAS;
- `Skill`, the skill in that module's Skills;
- `ExecutionMode`: station, or manual with no resource;
- per input the skill is handed something: its `Name`, and either a constant or a `SourceElement`
  in the product's Process Parameters; `InputReference` points at the input itself, a variable of
  the skill's Start Operation.

An input without a binding runs with its default. The elements are those of the Production Sequence,
moved out of the product: the planner wrote them into the recipe's steps before.

**Validation** says whether the bound recipe fits the line:
- `Fits` or `DoesNotFit`;
- the check that said so;
- one finding per thing that does not hold, e.g. "Filling: ContainerType = syringe is not covered
  by Filling".

**Checking a binding by following its references.** Because every link is a model reference, the
check needs no names that agree by convention. It walks the chain of 3.2 and requires:
- that the step's process requires a capability the resource offers;
- that this skill realizes it;
- that its properties cover the product's values;
- that each bound input exists and takes a value within its unit and limits;
- that every step the recipe runs, including those of the sequences it calls, is bound.

Building the reference models refuses a process AAS whose Validation is not what the check finds.

Fig. `bpmn-levels` shows the three levels as BPMN pools:
- the recipe;
- the process on the line, a lane per resource;
- a composite skill opened, a lane per component.

The planner draws both levels, a product's recipe and a module's composite skill, in one notation.
That is possible because they share the step elements.

### 3.6 Who reads and writes what

*[Authors: Fig. `model-use` as a matrix of activities against submodels, with one paragraph per
group.]*

| Activity | Reads | Writes |
| --- | --- | --- |
| Product design (planner) | Product AAS; offered capabilities | Recipe |
| Binding a recipe (planner) | Product AAS; resources' capabilities and skills | Process AAS |
| Changing a skill (skill editor) | A module's and its components' Skills | Skills; then the derived capabilities |
| Registering a module (`modreg`) | The module spec | Every submodel of the module and its components |
| Reconfiguring online (`modsync`) | Skills, the Control Configuration, the running program | The program (online); `Deployment`; the interface of a new skill; the Control Configuration |
| Running a product (either orchestrator) | Process and resource AASs; Variables (through the time series) | Commands through the DMP or OPC UA; per-order bindings (agents) |

Fig. `bpmn-integration` shows two of these as one BPMN process, a lane per tool:
- **a module plugged in:** registered, its capabilities derived, matched against the products'
  required ones;
- **a new product:** its recipe written, matched, a missing skill composed and built online, the
  recipe bound and validated.

### 3.7 Templates, classes and ontologies

Every submodel of our own is kept the way IDTA keeps its own (in aas-model, `templates/` and
`docs/lab-submodels/`):
- a template (`kind = Template`, with a cardinality per element);
- Python classes generated from it;
- a description of each element.

Tests fail when the classes or the descriptions drift from the template. ARSO's submodels (Skills,
Parameters, Control Configuration) are written from the ontology, so every element we write in them
is declared there. The product's and the process AAS's templates are written by hand until their
ontologies (APSO, AProSO) are remade.

| Submodel | AAS | Template from | Classes |
| --- | --- | --- | --- |
| Skills, Parameters, Control Configuration | Resource | ARSO | generated |
| Variables (with Coordinates) | Resource | aas-model | hand-written |
| Production Sequence 2.0, 4.0 (proposed) | Product | the planner (2.0); ours (4.0) | generated |
| Process Parameters, extension | Product | IDTA 02031-1, extended | generated |
| Process Information, Bindings, Validation | Process | ours | generated |

---

## 4 Use cases

We use two cases that stress the models in different ways:
- **pharmaceutical filling on a physical modular line:** one product family, the order fixed by GMP,
  modules reconfigured online;
- **remanufacturing of an EV battery pack in a simulated disassembly cell:** a deep product
  hierarchy, a partial order, joints, and a decision on a measured condition.

The same templates and tools serve both. Only the instances differ.

### 4.1 Pharmaceutical filling on a modular line

**The line** (Fig. `submodel-references-pharma`):
- a planar transport table (B&R ACOPOS 6D) with three shuttles;
- four modules (filling, stoppering, capping, inspection) and two robots for loading and unloading;
- each module a Raspberry Pi running its IEC 61499 program in FORTE, with an OPC UA server.

The filling module has a linear axis, a pump and a scale, each a component AAS with its primitives.
Its composite Dispensing runs MoveAxis, Dispense, Home and Weigh.

**The products** are a 2 mL vial, a 1 mL prefilled syringe and a 3 mL cartridge. Each is a product
AAS with:
- its bill of material;
- the processes Filling, Stoppering, Capping and Inspection with its values (container type, grasp
  diameter, fill volume);
- the capabilities those processes require;
- its recipe.

GMP fixes the order of the steps, so the recipe is a chain. In the Production Sequence 4.0 it is a
partial block whose `After` relations form a chain (Fig. `production-sequence-pharma`):
- Stoppering makes the press fit of stopper and vial;
- Capping crimps the flip-off seal onto the vial;
- the seal is a bought subassembly with an AAS of its own and no sequence.

Each product has a process AAS on the line, which binds:
- Filling to the filling module's Dispensing, with its Volume taken from the product's FillVolume;
- Stoppering, Capping and Inspection to their modules.

All three fit: the filling module takes vials, syringes and cartridges. Fig. `capability-match`
adds an ampoule, which the module's container types exclude. Its binding would be found not to fit.

**How it is set up:**
1. **Module specs.** Each module is described in a short spec: its components, its skills and the
   meanings of their parameters, and the facts of the machine.
2. **Generated program and AASs.** From the spec, `modreg` generates the module's IEC 61499 program
   and every AAS of the module and its components:
   - the interface description from the program's OPC UA nodes;
   - the mapping, the Variables and the Skills;
   - the capabilities derived from the skills (3.4.3).
3. **Reference models.** The products and their process AASs are written out in full in Python with
   aas-model's classes. They are built and checked by following every binding.
4. **Running the line:**
   - all AASs are published to a BaSyx AAS environment;
   - the DMP serves the delegated Operations and writes the time series into InfluxDB;
   - either orchestrator runs the orders: a centralized one, a FOND policy run as a behaviour tree
     [schwoerer2026fond], or a multi-agent one, product and resource agents bidding for steps;
   - both run a skill the same way: occupy, Execute, start, wait for the end, release.
5. **Reconfiguration.** A skill the product needs and no module offers (filling from the bottom;
   twice the volume) is composed by the HTN planner from the components' capabilities, written into
   the module's Skills as `Described`, and built online by `modsync`. Its capability is offered once
   it is `Built`.

### 4.2 Battery pack remanufacturing

**The product** (Fig. `submodel-references-battery`):
- an EV battery pack returned for remanufacturing: an instance with its serial number;
- its bill of material: housing, cover with twelve screws, HV connector, BMS, busbars, and four
  battery modules;
- each module a subassembly with an AAS of its own (also an instance, with its own serial number
  and, once tested, its own state of health), holding twelve cells of one cell type.

**The recipe** has two archetypes (Fig. `production-sequence-battery`).

*Disassembly* is a partial block:
- UnscrewCover and UnplugHV are ready at the start;
- RemoveBusbars waits for both, RemoveBMS only for UnplugHV;
- the four modules' own Disassembly sequences are called after RemoveBusbars and can run at the
  same time.

Each step breaks the joints it holds:
- the cover's screwed joint;
- the HV plug;
- the four bolted busbar joints.

Each joint's parameters (breakaway torque, screw size, pull force) are those of the step's process
in the pack's Process Parameters. A module's sequence:
1. removes the clipped lid;
2. tests the cells, which gives the module's state of health as an output;
3. decides on it: at 80 % or more, sort the module for reuse; otherwise, for recycling.

*Assembly* closes the pack again. It refers to the same joints instead of defining them twice.

**How it is set up:**
- **What exists.** The product AASs (pack, four modules, cell type) and the pack's process AAS are
  written out in full with aas-model's classes, built and checked like the pharma models (aas-model,
  `aas_model.product_instances`, `scripts/export_precedence_examples.py`).
- **The bindings.** The process AAS binds the steps of the pack's Disassembly sequence and of the
  sequences it calls to the stations of the disassembly cell:
  - the unscrewing station, handed the breakaway torque;
  - the handling station;
  - the test station, handed the discharge current.
- **The cell is simulated.**

*[Authors: the cell's resource AASs (line, unscrewing, handling and test stations) are not written
yet, and the simulator is not built. The process AAS refers to them already and its Validation says
`NotChecked`. Before submitting we need:
- the station AASs, made from specs like the pharma modules;
- a simulated controller per station (FORTE on the PC, as the filling module is simulated today);
- one run by either orchestrator.
If that is not done in time, 4.2 presents the battery case as a modelling case only and says so.]*

The Assembly sequence has no process AAS here. Which cell closes the pack is open.

### 4.3 What each case exercises

| Model feature | Pharma | Battery |
| --- | --- | --- |
| Product hierarchy | product, bought subassembly (the seal) | pack, four subassemblies with sequences of their own, a part type |
| Instances or types | product types | instances (each pack and module its own) |
| Order of steps | a chain (GMP) | a partial order, a subassembly's sequence called |
| Joints | press fit, crimp | screwed, plugged, bolted, clipped; defined in Disassembly, referred to in Assembly |
| Decisions | none (inspection reports, the line decides) | on a measured output (state of health) |
| Archetypes | Assembly | Disassembly and Assembly |
| Resources | physical modules, generated from specs, reconfigured online | simulated stations *[to be built]* |
| Capability matching | container types and volume ranges; an ampoule that does not fit | torque and current ranges |
| Online reconfiguration | a composite skill planned and built online | *[not planned for this case]* |

---

## Still to settle

- **Citations not yet in [paper-references.bib](paper-references.bib):**
  - IDTA 02006, 02011, 02015, 02017, 02027, 02031-1, 02008;
  - ISA-88 (IEC 61512-1);
  - W3C WoT Thing Description;
  - VDI/VDE 2193.
- **The Production Sequence 4.0 is proposed.** The planner does not read it, and the agents read
  only top-level steps ([precedence-graphs.md](precedence-graphs.md), rule 3). If the pharma case is
  run on 2.0, 4.1 has to say that the line runs the chain as a 2.0 sequence and that 4.0 is shown as
  the model.
- **Section numbers** of planning, IEC 61499 and orchestration are placeholders (*[planning]*,
  *[IEC 61499]*).
- **The product subsection** and our 3.2 and 3.5 have to use the same names: Production Sequence,
  step, block, `After`, joint, archetype.
