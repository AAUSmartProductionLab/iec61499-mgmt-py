# Ontologies

The ontologies behind the product, process and resource AAS, and the links between them.
The model the work proceeds by (26 Oct) is [docs/ppr-model.md](../docs/ppr-model.md); the
conceptual picture of 30 Sep, not kept up to date, is in [docs/archive/conceptual-model.md](../docs/archive/conceptual-model.md).
What the AASs hold as built is in
[docs/aas-models.md](../docs/aas-models.md); the first target structures (30 Sep) are in
[docs/archive](../docs/archive/aas-implementation-plan.md).

```
                          PPRL  (links, on CSS; + PPRL-rules.shacl.ttl)
              ┌─────────────┼──────────────┐
            APSO          AProSO          ARSO         one blueprint per AAS type, each
          (product)      (process)     (resource)      checkable on its own
              └─────────────┼──────────────┘
                   AAS v3.1 ontology           CSS (Plattform I4.0 capabilities, skills, services)
```

| Folder | Ontology | What it describes |
| --- | --- | --- |
| `AAS/` | AAS v3.1 RDF ontology | The metamodel (unchanged) |
| `CSS/` | CSS 2.0.2 | Capability, Skill, Service reference model (updated from 2.0.1 on 30 Sep 2026: fixes the domain of `behaviorConformsTo`) |
| `VDI2860/`, `DIN8580/` | HSU's VDI 2860 2.0.0 and DIN 8580 2.0.0 | The standards' taxonomies of handling functions (VDI 2860) and manufacturing processes (DIN 8580), as ontology design patterns of Helmut Schmidt University: what the lab's capabilities are kinds of (vocabulary 0.9) |
| `APSO/` | APSO 0.2 | Product AAS: BatchInformation, BoM, Requirements, Bill of Process. Not the product AAS that is built (aas-model's `Product`, [docs/ppr-model.md](../docs/ppr-model.md)); to be remade from it (F5 in [docs/next-steps.md](../docs/next-steps.md)) |
| `ARSO/` | ARSO 0.14 | Resource AAS of a line, a module and a component: Nameplate, Hierarchical Structures, AID, AIMC, Skills, Capabilities, Variables (aas-model's, with the coordinates; Operational Data until 0.13), Parameters, Technical Data, Control Configuration (since 0.10 the schema of the integrator's record, outside the AAS). The templates of its own submodels and their classes are in aas-model (`templates/arso`) |
| `AProSO/` | AProSO 0.1 (30 Sep) | Process AAS: ProcessInformation, ProcessStructure (process map with flow), CapabilityBindings, Validation, Policy. Not the process AAS that is built since 28 Oct (aas-model's `Process`: Process Information, Bindings, Validation); to be remade from it (F5) |
| `PPRL/` | PPRL 0.2 | What lies between them: the CSS concept an AAS element describes, process decomposition and order, resource parts, required and offered capabilities and matching, skill composition, occupation, binding, parameter value flow, derived candidates, change classes; since 0.2 (28 Oct) what a capability needs, does and keeps, for planning (`pre`, `post`, `invariant`, `ProductProperty`); since 30 Oct `writtenFor`, the narrower capability a composite skill was written for. `projection.ttl` and `projection/*.rq`: how an AAS becomes RDF and which individuals and relations its elements describe (`modreg graph`, `aas61499-tools/modreg/projection.py`) |
| `Vocabulary/` | Lab vocabulary 0.9 | What the elements of the AASs mean (their supplemental semantic ids): capabilities, of two kinds (process: a product can require it; auxiliary: it serves other skills), their properties and, since 0.2 (28 Oct), what each needs, does and keeps; since 0.3 the meanings of a module's points of interest, since 0.4 Transporting and the planar table's Flyway, since 0.5 what a coordinate is of, since 0.6 (30 Oct) BottomUpFilling and Transporting's targets, since 0.7 (30 Oct) custody: Receiving, Releasing, Holding, HeldBy, Occupancy, Capacity, since 0.8 CrimpPosition, since 0.9 (6 Nov) the capabilities placed below DIN 8580 and VDI 2860 (`capabilities.ttl`); the commands and kinds of a skill (`commands.ttl`); the skill types of the components, the capability each contributes and the one of its component it realizes (`skills.ttl`) |

`AAS/`, `CSS/`, `VDI2860/` and `DIN8580/` are unchanged copies of ontologies published by others
(the AAS v3.1 RDF ontology of the IDTA, `https://admin-shell.io/aas/3/1/`; the CSS ontology of
Helmut Schmidt University, `http://www.w3id.org/hsu-aut/css`; HSU's VDI 2860 and DIN 8580 ontology
design patterns, `http://www.w3id.org/hsu-aut/VDI2860` and `.../DIN8580`, MIT, converted from OWL/XML
to Turtle with their triples unchanged), kept here so the imports resolve offline; their own terms
apply.

**What the capabilities are kinds of (vocabulary 0.9).** A lab capability class is also a subclass
of the class of the standard it is a kind of: what changes the product of DIN 8580 (Filling and
Dosing are pouring, 4.2.1; Stoppering and Pressing press fitting, 4.3.4; Crimping joining by forming
sheet metal, 4.5.2; Capping joining), what moves or checks it of VDI 2860 (Positioning; Transporting
as conveying; Weighing as measuring; Imaging and Inspection as checking). The standards' classes
state no constraints, so a class inherits nothing that planning reads; the lab's split into process
and auxiliary capabilities (what a product can require, what serves other skills) stays its own and
runs across both standards. Not placed: Referencing and Taring, Receiving and Releasing (custody;
VDI 2860's holding and releasing are clamping), Loading, Unloading, Unpacking and Packing. VDI 3682
(formalised process description) was read too: its states, inputs and outputs say what our pre- and
postconditions say, with no time or rates, so it is not imported.

## Why a link ontology rather than more in APSO and ARSO

The relations that matter for reconfiguration run *between* AAS types (a process step of the
process AAS requires a capability from the product AAS that a resource AAS offers). Putting them
in APSO or ARSO would make each import the others, and a product AAS could no longer be checked
without loading the resource blueprint. So APSO, ARSO and AProSO stay structural (one AAS type
each, as ARSO already was for its own cross-submodel links), and PPRL imports all three plus CSS.
CSS already has most of the vocabulary (`requiresCapability`, `providesCapability`,
`isRealizedBySkill`, `isRealizedBySkillParameter`, `controls`, `hasInput`/`hasOutput`); PPRL adds
what it leaves open: `hasSubProcess`, `directlyPrecedes`/`precedes`, `refines`, `hasPart`,
`RequiredCapability`/`OfferedCapability`, `matches`, `matchesProperty`, `takesValueFrom`,
`usesSkill`, `occupies`, `boundTo` (inverse of `css:controls`), `executedBy`, and the derived
`candidateResource` and `candidateSkill` (property chains).

## Changes to the existing ontologies (30 Sep 2026)

All additions are optional, so existing instances stay valid; the originals are in the user's
own copy.

**APSO 0.1 → 0.2** (`APSO_AAS.ttl`, `modules/bill_of_process.ttl`)
- The Bill of Process is a tree: `ProcessStructure` gets `subProcesses` (same content rules as
  `Processes`); `Process` is a leaf.
- A leaf may have a `RequiredCapability`: an IDTA 02020 CapabilityContainer (role Required),
  reusing ARSO's capabilities module so required and offered capabilities share one structure.
  A constraint property points to the process parameter it takes its value from with 02020
  `SameProperty`.
- `Consumes` and `Produces` relationships from a process to BoM entities (`css:hasInput`,
  `css:hasOutput`); until now only `IsDisassembleBy` linked BoM and BoP.
- `sequenceNumber` is optional (was mandatory); `ProcessOrder` (a partial order, so parallel
  steps are possible) is the general form and may now order structures too.
- Resolved properties `hasSubProcess`, `consumes`, `produces`, `hasRequiredCapability`.

**ARSO 0.4 → 0.5** (`ARSO_AAS.ttl`, `Modules/control-component.ttl` (since 26 Oct `Modules/skills.ttl`: the Skills submodel is its own template, no longer IDTA's Control Component Type), new `Modules/control-configuration.ttl`)
- **Scope fix:** the restrictions ARSO stated on every `aas:AssetAdministrationShell` (exactly one
  Nameplate, exactly one Hierarchical Structures, represents exactly one `css:Resource`, ...) now
  apply to a new class `arso:ResourceAAS`. Loaded together with APSO they would otherwise have
  claimed every product shell represents a resource. The JSON-to-RDF projection has to type
  resource shells as `arso:ResourceAAS` (e.g. from `derivedFrom .../aas/templates/resource`,
  which the lab's configs carry).
- Optional reconfiguration elements per skill: `Kind`, `Parameters`, `RealizesProperty`,
  `Contract`, `Uses`, `Execute`/`Stop` sequences of `Step`s, `Occupies`, `StateReference`,
  `Implementation`. ARSO's flattening had dropped per-skill parameters and IDTA 02015's `Uses`;
  these bring back what matching, composition and checking need.
- A Control Configuration submodel (runtime, sync state, differences, type hashes, active
  procedure, change log), which modsync writes (first as `ControlSoftware`, its semantic id is
  still accepted).
- Resolved properties `usesSkill`, `occupies`, `realizesProperty`, `realizedBySkill`.

**ARSO 0.5 → 0.8** (6 to 19 Oct; the details are in [docs/aas-models.md](../docs/aas-models.md),
section 2)
- 0.7 (8 Oct): a skill is its commands (Start, Stop, Abort, Reset), each with its interface
  reference, an Operation whose variables are the parameters and results, and the steps it runs;
  `Kind`, `Parameters`, `Uses`, the `Execute`/`Stop` lists, `Occupies` and the rest of 0.5's
  per-skill elements are gone. A line, a module and a component are each an AAS, told apart by
  the asset type (`arso:SystemAAS`, `arso:ResourceAAS`, `arso:ComponentAAS`).
- 0.8 (9 Oct): the steps are a flow in the elements of the process planner's Production Sequence;
  a skill's kind (Primitive, Composite, ModuleControl) is a supplemental semantic id; the
  module's own commands are skills of the kind ModuleControl, and the Module submodel is gone.
- 19 Oct (still 0.8, additions only): the AID of IDTA 02017 version 1.2, and the action, event
  and property terms of aas-model's AID extension (`.../aid/ActionDefinition/1/0`,
  `synchronous`, `input`, `output`, `uav_componentOf`, `readOnly`).

**ARSO 0.8 → 0.12** (26 to 28 Oct; the version notes are in `ARSO_AAS.ttl`)
- 0.9: the Skills submodel is ARSO's own template; 0.10: what was built leaves the AAS
  (`RuleSet`, `Deployment`).
- 0.11: a primitive's `Contract` becomes `Conditions` (Precondition, Postcondition, Invariant)
  and `Completion` (After, Timeout), the run-time form of what its capability states for planning
  ([docs/skill-planning.md](../docs/skill-planning.md)).
- 0.12: a Node of Hierarchical Structures may say where its part is in its parent's frame
  (`Frame`: AutomationML's frame attribute with IDTA 02075's ids); a co-managed Node with a meaning
  is a point of interest ([docs/locations-and-layout.md](../docs/locations-and-layout.md)). Gone
  with 0.13.

**ARSO 0.13 and 0.14** (28 Oct)
- 0.13: where things are is a coordinate in Operational Data (`Measurements/Coordinates`), relative
  to another coordinate by reference: a tree rooted at the planar table's base. The `Frame` of 0.12
  and the point Nodes are gone; Hierarchical Structures is a bill of material again.
- 0.14: aas-model's Variables replace Operational Data (`Modules/variables.ttl`, was
  `operational-data.ttl`): time series in `State`, `Measurements` and `Log`, the coordinates in
  `Measurements`. ARSO's own templates and their classes are aas-model's (`templates/arso`).

## Checks

The ontologies were the **design guide** only until 2 Oct 2026; since then ARSO is also the
blueprint the registration service checks every resource AAS against (`aas61499-tools/modreg`,
`modreg check <module> --ontology ontology/ARSO`) and the source of the templates of its own
submodels, from which aas-model makes their classes (`modreg generate`). On 2 Oct that was ARSO 0.5
with two additions (Value and Unit of a parameter entry, `Modules/parameters.ttl`, and the detail
properties of Control Configuration); ARSO has changed with the code since and is at 0.14. This
folder is a working copy, in the repository for now.

`checks/test_ontology.py` keeps the design guide itself consistent: every file parses, every `owl:imports` resolves to a file here, the
whole set plus the worked example (`PPRL/examples/filling-line.ttl`: the HGH vial on the filling
and stoppering modules) is consistent under OWL RL, the reasoner derives the candidate skill and
resource of each step, and the SHACL rules pass on the example and catch seven kinds of mistakes
(a composite using a sibling module's skill, occupying another module's equipment, a binding to
a skill that is no candidate, a cycle or a cross-level order, a leaf with two capabilities, a
parent with a capability).

```powershell
python -m pytest ontology/checks
```

## The resource AAS that is built, against ARSO

`modreg` (in `aas61499-tools/`) builds a module's AAS in ARSO's structure and checks it
(`modreg check <module> --ontology ontology/ARSO`); both modules break no restriction (checked
31 Oct). What still differs:

1. Elements the check reports as not described: the Web of Things terms the lab's shared model
   writes into the Asset Interfaces Description (a property's key, type, title, observable and
   unit, an action's title, `uav_browsePath` on every form), 299 in the filling module and 217 in
   the stoppering module (31 Oct). The rest of an action (`synchronous`, the input and output
   schemas, `uav_componentOf`) is declared since 19 Oct.
2. ~~What ARSO names but does not declare, so the classes are hand-written in `modreg/model.py`:
   the children of a Step and of Implementation, the item types of Uses and Occupies.~~ Gone:
   Implementation, Uses and Occupies with 0.7; since 28 Oct the classes are aas-model's, made from
   ARSO's templates.
3. ~~A skill that is not offered has no Operation and no interface action, which ARSO asks of
   every skill; such a skill is not listed, and steps name it by an external reference.~~ Since
   0.7 a command's `InterfaceReference` is optional: a skill that is not offered has its Operation
   and no action. No module of the line has one.
4. Variables (Operational Data until 0.13): a module's value is a decimal field of a time series
   (the AAS holds no value), so Booleans are 0 or 1.
5. Technical Data is not written yet. (Capabilities are written since 26 Oct, derived from the
   skills; the Control Configuration left the AAS with 0.10.)
