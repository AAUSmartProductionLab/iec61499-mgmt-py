# Journal paper: the method, as blueprints

Rewritten on 2 Nov 2026, for the authors. The colleagues' introduction and related work frame the
method in a new way:
- as AAS blueprints, one per asset class;
- closing seven joints between IDTA templates (J1 to J7);
- answering RQ1 to RQ3, with RQ4 left to the cases.

This version rebuilds the method around that frame. The first version of this file, from the same
day, had most of the content in another order. Its resource and process parts are folded in here,
and its use cases have moved to the evaluation file.

Three files belong together:
- **this one:** the concept, the structure of sections 3 to 6, a draft of our parts of section 3,
  and what has to be settled with the colleagues;
- **[journal-rationale.md](journal-rationale.md):** every design decision, set against the
  alternatives in the literature and in technology. It serves the method and the discussion;
- **[journal-evaluation.md](journal-evaluation.md):** how the two cases are built and evaluated,
  experiment by experiment.

Conventions:
- Text in *[Authors: ...]* is a note for us, not paper text.
- Citation keys are those of the paper's bib file. A key written *[cite: ...]* is not in it yet.
- Figures are pages of [figures/journal-figures.drawio](figures/journal-figures.drawio), named by
  page. Two of the figures proposed here are new.

## 1. The method in one page

**What it has to answer.** Section 2 ends with seven joints, relations between IDTA templates that
no template defines, and four research questions. The method answers three of them:
- **RQ1:** how the three kinds of shell are composed from templates, and how much has to be added;
- **RQ2:** which additions close the joints, so that a new module can be planned and invoked from its
  AAS alone;
- **RQ3:** how constraints across submodels and shells are stated and checked.

It answers all three with one construct, the blueprint, and one procedure for building it.

**A blueprint** states, for one asset class (product, process, resource):
1. **Composition:** which submodels a shell of the class holds, each with a multiplicity. Each is an
   IDTA template as published, an IDTA template with additions, or a template of ours.
2. **Structure:** what each element is, as a class of the class's structure ontology (APSO, APrSO,
   ARSO). An element is recognised by its semanticId; the class says what it must, may and may not
   contain.
3. **Relations:** which element states which relation between the concepts of the PPR and CSS
   models. Examples: a capability realised by a skill, a skill invoked through an action, a step bound
   to a skill, an input taking a product's value. The relations belong to one abstract ontology over
   the three structure ontologies (contribution 2).
4. **Constraints:** what must hold of these elements and relations, within a submodel, within a
   shell, and across shells (contribution 3).

A submodel template does this for one submodel. A blueprint does it for a whole shell and its links
to other shells.

**Four ideas the method rests on.**
1. **A joint is a reference that no template states, or states without a target.** Each joint of
   section 2 is a relation that one template would have to state about an element of another. No
   template does, or one does with a reference whose target is not defined (02020's
   `CapabilityRealizedBy`). A blueprint closes a joint in four moves:
   - it chooses the element that states the relation;
   - it fixes the class of the element's target;
   - it makes the element a model reference, which any AAS client resolves;
   - it states the constraint the reference must satisfy.

   Every addition inside an IDTA template is one of these moves. The templates of our own answer
   questions that no template answers: what a skill is, what is bound, where the time series are. The
   four moves are also how a blueprint for another asset class would be built (3.1).
2. **Meaning finds, reference binds.** Two mechanisms link the shells:
   - **A shared meaning** lets a tool find what could fit. It is a supplemental semantic id from one
     vocabulary: every capability that means Filling, every input that means FillVolume.
   - **A model reference** records what was chosen: this step is carried out by this skill, this
     input takes that parameter.

   Matching uses meanings, so it stays open to modules nobody has seen. Binding uses references, so
   it can be checked.
3. **One step on every level.** Three things are made of the same step, a node that runs something
   and hands its inputs values:
   - a product's recipe, whose steps run processes;
   - a composite skill, whose steps run component skills;
   - a process binding, which binds a step of the recipe to a module's skill.

   J4 (a product value handed to a skill's input) and J6 (a composite handing values to a component
   skill) are therefore one constraint at two levels, and one checker serves both. The hierarchies
   match as well: product, subassembly and part on one side; line, module and component on the
   other.
4. **The domains differ in candidates, not in structure.**
   - Where the product is specified in advance (pharma), each step has one validated binding, fixed
     before the batch starts.
   - Where its condition is found during processing (battery remanufacturing), a step has several
     validated candidates. The run chooses among them once the condition is known.

   The blueprint is the same in both. Only the number of candidates per step differs, and when the
   choice is made. This is the hypothesis RQ4 tests.

**The levels.**

| Level | What it says | Examples | Checked by |
| --- | --- | --- | --- |
| AAS metamodel (IEC 63278, IDTA Part 1) | What any shell can hold | – | Metamodel verifiers, the AAS Test Engines [otto2025test] |
| Blueprint (this paper) | What a product, process or resource shell holds and how its elements relate | The resource blueprint | Its constraints |
| Type AAS (assetKind Type) | One kind of asset | The 2 mL vial; the vial on the filling line | Against its blueprint |
| Instance AAS (assetKind Instance) | One asset | A returned pack with its serial number; the filling module on the line | Against its blueprint |

A blueprint governs type and instance shells alike. Some of its constraints apply to instances only:
a measured condition, an execution record.

*[Authors: the introduction calls blueprints "type-level models". Define this once in 3.1 as the
level above the type AAS, or say "class-level", so that readers do not take it for assetKind Type.
The product subsection's "maintained once as a type-level AAS" means the type AAS.]*

**The seven joints are seven relations.**

| Joint (section 2) | Relation | Stated by (blueprint, element) | Constraint (3.6) |
| --- | --- | --- | --- |
| J1 Offered capability to the skill that realises it | `css:isRealizedBySkill` | Resource: Capability Description, `CapabilityRealizedBy`, a model reference to a skill | C05, C14 |
| J2 Skill to the action that calls it | `pprl:invokedThrough` (to add) | Resource: Skills, a command's `InterfaceReference` to an AID action; AIMC, the command's Operation mapped onto that action | C06, C07 |
| J3 Required against offered capability | `pprl:matches`, `pprl:matchesProperty` | Product and resource: meanings, values and ranges of the two capabilities. Process: `Validation` records the verdict | C17, C20 |
| J4 Product value to skill parameter | `pprl:takesValueFrom`, `css:isRealizedBySkillParameter` | Process: Bindings, an input binding's `SourceElement` and `InputReference` | C18, C19 |
| J5 Step to resource and skill | `pprl:boundTo`, `pprl:executedBy` | Process: Bindings, a step binding's `Step`, `Resource` and `Skill` | C16, C21 |
| J6 Module skill to the component skills it runs | `pprl:usesSkill`, `pprl:handedFrom` | Resource: Skills, a command's `Steps` (`Skill`, `Bindings`, `Order`, blocks) | C12, C13 |
| J7 Connection in the product to the step that breaks it | `pprl:joins`, `pprl:releasedBy` (to add) | Product: the connection (an ARE between two BoM entities) and the step that makes or breaks it | C09 |

**Principles.** Each principle points at its decision in
[journal-rationale.md](journal-rationale.md).

| # | Principle | What it means | Decision |
| --- | --- | --- | --- |
| P1 | Reuse, then extend, then add | An IDTA template as published where it suffices. Additions where it nearly suffices, never a changed or removed element. A template of ours only where none exists. Every added element carries our semanticId, so a reader can tell standard from addition | M2 |
| P2 | One owner and one reason to change per shell | The product designer, the line engineer, the vendor | M1 |
| P3 | References bind, meanings find | Idea 2 | M3, M4 |
| P4 | Derive what can be derived | Offered capabilities from skills; resource shells from the module's description; planning domains from capability constraints | M5, M12 |
| P5 | Descriptions in the AAS, data beside it | No live values in the shell; time series are named, not copied; build records stay with the integrator | M10, M11 |
| P6 | Check where information changes hands | At registration (vendor to integrator), at binding (line engineer), and at every change during a run (orchestrator) | O5 |
| P7 | Neutral to the orchestrator | The blueprints say what is needed, offered and bound, not how the line is controlled | X7 |

## 2. The structure of sections 3 to 6

The paper's skeleton (as pasted): 3.1 Blueprint Design, 3.2 Ontology Mapping, 3.3 Product
Description, then Process and Resource Description; 4 Case Studies; 5 Results; 6 Conclusion. Proposed:

| § | Title | Answers | Content | Figure | Who |
| --- | --- | --- | --- | --- | --- |
| 3 | Method | RQ1–RQ3 | One paragraph: blueprints, relations, constraints | – | us |
| 3.1 | Blueprint design | RQ1 | The four parts; the procedure; three origins; references and meanings; the levels | `blueprints` (new: section 2's `fig-joints` redrawn with every joint closed) | us, merged with the colleagues' text |
| 3.2 | Ontology mapping | RQ2, RQ3 | PPRL over CSS and the three structure ontologies; the projection; the joints as relations | `ontology-layers` (new, small) or a table | us |
| 3.3 | Product blueprint | RQ1, J7 | The colleagues' subsection | `product-bom`, `production-sequence` | colleagues |
| 3.4 | Resource blueprint | RQ1; J1, J2, J6 | Composition; what it can do; how it is called; how the call reaches the asset; where its data goes | `skill-hierarchy`, `capability-match` | us |
| 3.5 | Process blueprint | RQ1; J3, J4, J5 | What is bound; candidates; values to inputs; whether it fits; what happened | `ppr-map` (or `isa88-levels`) | us |
| 3.6 | Constraints and conformance | RQ3 | Four scopes; the catalogue C01 to C21; who checks when | a table | us |
| 4 | Case studies | RQ4 | | | |
| 4.1 | Pharmaceutical filling | | The physical line; its shells; scenarios P1 to P5 | `submodel-references-pharma` | us |
| 4.2 | Battery disassembly | | REVAMP in Plant Simulation; its shells; the dynamics; the coupling; scenarios B1 to B4 | `submodel-references-battery`, `production-sequence-battery` | colleagues and us |
| 4.3 | Evaluation design | RQ1–RQ4 | Experiments E1 to E7, their metrics and baselines | – | us |
| 5 | Results | RQ1–RQ4 | One subsection per RQ | Tables; one heatmap | all |
| 6 | Discussion | | Decisions against related work; joint coverage of the reviewed works; limits; threats to validity | the decisions table, the coverage table | all |
| 7 | Conclusion | | | | |

How we got to this structure:
- **Resource before process.** The skeleton lists the process first. But the process blueprint binds
  the other two, so with the resource first, J4 and J5 can be described in terms the reader already
  knows. If the authors keep the skeleton's order, 3.5 has to refer forward to skills and their
  inputs.
- **A blueprint subsection per asset class, the joints across them.** Each joint is described once,
  in the subsection where its element is, and named there by number. The table of joints in 3.2
  points to all of them.
- **Design decisions inline, the comparison in the discussion.** Each element we add gets one
  sentence in section 3: what it is instead of, and who does it the other way. The full table of
  decisions against the related work goes into section 6, which is where reviewers look for "how is
  this different".
- **Generic figures in section 3, the cases' figures in section 4,** as planned before.
- **The two new figures.**
  - `blueprints` is the method's key figure. It is section 2's `fig-joints` in the same layout, with
    each of the seven arrows labelled by the element that closes it, and each submodel tagged by its
    origin (IDTA, IDTA+, ours). The reader sees the joints open in section 2 and closed in section 3.
  - `ontology-layers` is optional. It can also be a sentence and a table.
- **Too many figures.** We recommend `ppr-map` over `isa88-levels` and dropping `bpmn-integration`.
  The measured read and write matrix of E1 replaces `model-use` in section 5.

**Scope.** The introduction makes this paper about the blueprints and their checking. Planning (the
HTN planner against standard planners) and the comparison of the two orchestrators answer none of
RQ1 to RQ4. We recommend:
- they appear only as users of the blueprints in the cases: they read and write the shells, which is
  part of RQ1's four phases;
- the comparison of the orchestrators becomes a paper of its own.

[journal-paper.md](journal-paper.md) still lists both as content; its scope note now points here.

## 3. How each blueprint subsection is written

**The same five parts in each,** so that the product, resource and process subsections read alike,
whoever writes them:
1. **Role and owner:** what the shell stands for, at which ISA-88 level, who keeps it and when it
   changes. One paragraph.
2. **Composition:** a table with the submodel, its template, its multiplicity, its origin (IDTA as
   published, IDTA extended, ours) and the joints it closes.
3. **The elements that close joints:** per joint, the element, its target, and why the template has
   no such element. Only elements we add are described; IDTA's elements are cited, not described.
4. **Constraints:** the constraints of 3.6 this blueprint carries, by number.
5. **What it leaves out:** and where that information lives instead.

Write element names in typewriter font (`CapabilityRealizedBy`). Use the metamodel's names for kinds
(Submodel, SMC, SML, Property, ReferenceElement, RelationshipElement, AnnotatedRelationshipElement,
Operation).

**Terms all authors use:**

| Term | Means | Not to be confused with |
| --- | --- | --- |
| Blueprint | What every shell of an asset class holds and how its elements relate: composition, structure, relations, constraints | A submodel template (one submodel); a type AAS (one kind of asset) |
| Origin | As published, extended, or ours | |
| Joint, J1 to J7 | A relation between templates that no template defines | A connection between two parts (see A7 in section 5) |
| Connection | A mechanical joint between two parts of a product (screw, plug, press fit), an ARE | |
| Step | A node of a recipe or of a composite skill: it runs a process or a skill, and hands its inputs values | |
| Block | A step that holds steps: parallel, decision, conditional, partial | |
| Recipe | The product's steps for one sequence type (Production Sequence, or the colleagues' BoP; A2) | |
| Binding, candidate | A step bound to a resource and a skill, with its inputs' values. A step may have several, each a candidate | |
| Required and offered capability | An 02020 capability with the role Required (product) or Offered (resource) | Skill |
| Skill: primitive, composite, module control | What a resource carries out, in Skills | Capability |
| Command | Start, Stop, Abort or Reset of a skill | |
| Meaning | A supplemental semantic id from the vocabulary | The semanticId (what an element is in its template) |
| Record | Executed Processes in an instance AAS (3.5) | The call log in a resource's Variables |
| Sequence type | Assembly or Disassembly (A11) | 02011's ArcheType (Full, OneDown, OneUp) |

## 4. Draft of section 3

### 3.1 Blueprint design

To merge with the colleagues' two paragraphs.

A blueprint defines, for one asset class, what every shell of the class holds and how its elements
relate to each other and to the shells of the other classes. It has four parts (Fig. `blueprints`):
- **a composition:** the submodels, each with a multiplicity;
- **a structure:** a class of the class's structure ontology for every element;
- **relations:** the elements that state relations of the abstract ontology;
- **constraints:** what must hold of them.

**How a blueprint is built.** We built the three blueprints by one procedure. It would serve another
asset class as well:
1. **List the questions** that engineering, integration, planning and execution ask of a shell of the
   class. For a resource: what it is, what it can do, how that is called, and where its data goes
   (Section 2.3).
2. **Take the IDTA template that answers each question.** Where a template nearly answers it, add
   elements. Where none does, write a template of our own, in IDTA's form: cardinality qualifiers,
   semantic ids, an element table.
3. **For each question that spans two templates, name the relation,** the element that states it, and
   the class of its target. That element becomes a model reference, and the relation one of the
   abstract ontology (3.2).
4. **State what must hold** of the relation as a constraint (3.6).

Steps 3 and 4 close the joints of Section 2.

**Three origins.** A submodel of a blueprint has one of three origins:
- **an IDTA template as published,** recognised by its official semanticId;
- **an IDTA template with additions.** An addition is one of three things:
  - an element or qualifier, carrying a semanticId of ours;
  - a target for a reference that the template leaves open;
  - a use that the template announces but does not yet describe.

  The template's own elements are never changed or removed. A reader that knows the template ignores
  the additions; a reader that knows the blueprint finds them;
- **a template of ours,** where no template exists.

Table 1 lists the submodels of the three blueprints by origin, and Section 5 counts their elements
(RQ1).

**References and meanings.**
- **References.** Every link that a tool follows is a model reference, held by a ReferenceElement or
  a RelationshipElement. Any AAS client resolves it through the AAS API, and a constraint can follow
  it.
- **Meanings.** Every element that is compared with another by what it means carries a supplemental
  semantic id from one domain vocabulary. Its primary semanticId stays the template's.

The two ids have two jobs: the primary id says what an element is in its template, the supplemental
id what it means in the domain. The individual (this skill, this step) is named by its own id and by
the references to it, never by a semantic id.

**Each shell on its own, and the set together.** Each shell is serialised and checked against its own
blueprint, on its own. The constraints between shells are checked on the set that a process AAS
links: one product with its subassemblies, and one line with its modules and components.

*[Authors: on the colleagues' paragraphs, before merging.*
- *"An ordered set of submodels": a shell's submodels are a set; the metamodel gives their order no
  meaning.*
- *"Exclusively through typed ReferenceElement entries": RelationshipElements carry references too
  (`CapabilityRealizedBy`, a connection as an ARE). Better: "through model references, held by
  ReferenceElements and RelationshipElements".*
- *"Allowing the shells to be serialized and validated independently": true of each shell against
  its own blueprint; the constraints between shells need the shells they link.*
- *"Domain-specific extensions": name the three origins instead.*
- *"Figure ???" is `blueprints`.*
- *"Developed and evaluated iteratively in two domains": keep it, and say which additions came from
  which case. E6 counts them.]*

### 3.2 Ontology mapping

The blueprints are stated in OWL and checked with SHACL. Three layers of ontology take part (Fig.
`ontology-layers`):
- **Imported.** The RDF ontology of the AAS metamodel [cite: IDTA AAS RDF], and the CSS reference
  model [koecher2023reference, plattform2025cssplus], which gives the concepts: product, process,
  resource, capability, skill, property, skill parameter.
- **Structure, one ontology per asset class.** APSO (product), APrSO (process) and ARSO (resource)
  [jensen2026ontology]. A class of these ontologies types the elements that carry one semanticId,
  and its restrictions say what such an element must, may and may not hold. Each ontology describes
  one kind of shell and loads on its own.
- **Relations.** An abstract ontology over the three, the PPR link ontology (PPRL). It imports the
  three structure ontologies and CSS, and states what lies between them:
  - which CSS concept an element describes;
  - the relations between those concepts that CSS leaves open.

A domain vocabulary gives the meanings: capabilities and their properties, skill types and the
capability each contributes, and commands. Elements refer to it by supplemental semantic ids.

**Why a separate link ontology.** The relations that matter for plug and produce run between asset
classes: a product's step requires a capability that a resource offers. Stated in APSO or ARSO, they
would make each structure ontology import the others, and a vendor could not check a module's shell
without loading the product's ontology. So each structure ontology stays about its own class, and
PPRL holds only what lies between them.

**The mapping is a projection.** A shell is turned into RDF in three passes:
1. Every element is written in the terms of the AAS metamodel and, by its semanticId, typed as a
   class of its structure ontology.
2. Every element that stands for a CSS concept gets an individual of that concept
   (`pprl:describes`). These are the elements with a meaning: a capability, a property, a skill, a
   parameter, a step.
3. The references become the relations of PPRL and CSS, by rules kept next to the ontology as SPARQL
   CONSTRUCT queries.

The relations are never written down twice: they are made from the references the shells already
hold, every time a check runs.

**Derived relations.** OWL property chains give each step its candidates:
- a step's candidate resources provide a capability that matches one it requires
  (`css:requiresCapability` ∘ `pprl:matches` ∘ `pprl:providedBy`);
- its candidate skills realise such a capability.

Whether two capabilities match depends on comparing numbers, which OWL cannot do. So the matcher
asserts `pprl:matches`, and a constraint checks the assertion (C17).

Table 2 is section 1's table of joints, with each relation's domain and range and the projection rule
that makes it.

*[Authors:*
- *PPRL 0.2 states J1 and J3 to J6. J2 is a rule of ARSO today, inside one shell. J7 is APSO's
  (`jointFirstEntity`, `IsDisassembleBy`). PPRL 0.3 should state both, so that every joint is one
  relation of one ontology (D6).*
- *The projection covers the resource shells' Skills and Capability Description. The product's and
  the process's shells are still to project (D6).*
- *The introduction says APrSO, the repository AProSO (A7).]*

### 3.3 Product blueprint (the colleagues)

What 3.4 to 3.6 rely on from this subsection:
- **The recipe's steps.** Each has a `NodeId` and a path through its blocks, which a binding names, and
  the recipe has a `Revision`, which a binding records.
- **Each step refers to its process.** The process is in Process Parameters (IDTA 02031-1), with the
  product's values and their meanings and units. It refers to its required capability (IDTA 02020,
  role Required).
- **The order is a partial order** (A2).
- **Each connection is made or broken by a step that refers to it** (J7, A1).
- **A subassembly with a shell of its own** is a part of the bill of material that names its asset
  id. A call step refers to the subassembly's own sequence.
- **A returned product has an instance AAS** derived from its type AAS. It holds its condition, and
  its record (3.5).

What still differs between the colleagues' draft and the models we built is in section 5.

### 3.4 Resource blueprint

**Role.** A resource AAS says:
- what a resource is;
- what it can do;
- how that is called;
- where its data goes.

The vendor writes it, or it is generated from the module's description. The integrator's tools
change it online when a skill is added. A line is made of modules, and a module of components. Each
has a shell of its own, and its asset type says which of the three it is (Fig. `resource-bom`). A
component is a part of a module that acts: an axis, a pump, a scale. It holds only its skills, the
primitives, and has no interface of its own, since its module carries its skills out.

**Table R1. The resource blueprint.** Multiplicities are ARSO's.

| Submodel | Template | Line | Module | Component | Origin | Joints |
| --- | --- | --- | --- | --- | --- | --- |
| Nameplate | IDTA 02006-3 | 0..1 | 1 | 0..1 | as published | – |
| Hierarchical Structures | IDTA 02011-1 | 1 | 1 | – | as published | finds the parts' shells (J6) |
| Capability Description | IDTA 02020 | – | 0..1 | – | extended | J1, J3 |
| Skills | ours (ARSO) | – | 0..1 | 1 | ours | J2, J6 |
| Asset Interfaces Description | IDTA 02017 | – | 0..1 | – | extended | J2 |
| Asset Interfaces Mapping Configuration | IDTA 02027 | – | 0..1 | – | extended | J2 |
| Variables | ours, with IDTA 02008 time series | – | 0..1 | – | ours | (record) |
| Parameters | ours (ARSO) | 0..1 | 0..1 | 0..1 | ours | – |
| Technical Data | IDTA 02003 | – | 0..1 | 0..1 | as published (planned) | – |

The optional submodels depend on each other (C05 to C07):
- an offered capability needs Skills;
- a built skill's command needs the AID;
- a mapping needs the AID.

**What it can do (J1, J3).** A module's Capability Description (IDTA 02020 [idtaCapability]) holds its
offered capabilities. Their properties are values, ranges, or lists of the values the module takes,
such as the container types a filling module accepts. We give one element of the template a target,
and add two qualifiers:
- **`CapabilityRealizedBy` gets a target.** It is a RelationshipElement whose second element is a
  model reference to a skill, in the module's Skills or in one of its components'. The template points
  it at "a Skill implementation, not defined in this Submodel template" [idtaCapability]. Ours has a
  defined target, so it can be followed and checked (J1).
- **Offered capabilities are derived, not written.**
  - Which capability: from the skill types a composite's steps run. The vocabulary says that Dispense
    contributes Filling.
  - Its properties: from the parameters' meanings and limits, and from the steps' constants.
  - The facts of the machine, such as the container types, are stated once.

  Derived elements carry the qualifier `Derived`, so a new derivation replaces only what it derived.
- **A capability whose skill is only described,** not yet built, carries
  `Availability = AfterReconfiguration`. A planner then sees what the line could do after a change.

Every property carries its meaning, as a supplemental semantic id, and its unit; matching compares
these (J3). A module also lists its components' capabilities with the role NotAssigned. Each carries,
as 02020 BasicConstraint expressions, the precondition, postcondition and invariant of the primitive
that realises it. New composite skills are planned from these.

**How it is called (J2, J6).** No published template describes a skill with its parameters, the
commands that call it and what it runs. IDTA's Control Component templates [idtaCCType, idtaCCInstance]
give a skill:
- one Operation;
- a list of the skills it uses;
- parameters whose data type is a free string.

Our Skills submodel replaces them (Fig. `skill-hierarchy`):

```
Skills
├── {Skill}                       semanticId .../skill; kind and type as supplemental ids
│   ├── Deployment                Built | Described
│   ├── Start, Stop, Abort, Reset the commands
│   │   ├── InterfaceReference    → the AID action that calls it               (J2)
│   │   ├── {Operation}           in: Session, parameters; out: Accepted, ErrorID, results
│   │   └── Steps                 of a composite: what the command runs        (J6)
│   ├── Conditions                of a primitive: Precondition, Postcondition, Invariant
│   └── Completion                of a primitive: After, Timeout
├── RuleSet                       the rules the module's program follows
└── Errors                        the codes an ErrorID can carry
```

- **A skill is its commands.** A skill is a state machine that is started, stopped, aborted and
  reset, and each command is called and answers on its own. So a skill holds up to four commands,
  each with three parts:
  - an `InterfaceReference` to the action of the module's interface that calls it (J2);
  - an Operation, the call's signature. Its variables are the protocol (`Session` in; `Accepted` and
    `ErrorID` out) and the skill's parameters and results. Each parameter has its unit, limits and
    default as qualifiers and its meaning as a supplemental semantic id;
  - for a composite, the `Steps` the command runs (J6).
- **Three kinds,** told apart by a supplemental id rather than by structure, so one reader finds them
  all:
  - **primitive:** one function block that moves one component, described in the component's shell;
  - **composite:** a module-level skill whose steps run primitives;
  - **module control:** the module's own commands (occupy, release, reset, start, stop).

  A second supplemental id gives the skill's type, a class of the vocabulary.
- **A composite's steps are a recipe's steps** (idea 3). They use the same elements, with the same
  idShorts and semantic ids:
  - `NodeId`, `Kind` and `Order`;
  - `Skill`, a model reference to the primitive the step runs;
  - `Bindings`: for each input of that primitive, a constant or a variable of the command's own
    Operation;
  - `Outputs`;
  - parallel, decision and conditional blocks.

  These close J6: the module's skill names the component skills it runs, in order, with what each is
  handed. Where the Control Component templates list the skills used, ours give their order and their
  values.
- **Conditions and Completion.** A primitive states its precondition, postcondition and invariant as
  expressions over the module's state variables, and when it is complete. They are the run-time form
  of the capability constraints that skills are planned from.
- **Deployment and RuleSet.**
  - `Deployment` says whether the module's program carries the skill out (`Built`) or the skill is
    only described (`Described`).
  - `RuleSet` names the rules by which skills map to the program, so that a tool knows it can read the
    program back and build a described skill.

**How the call reaches the asset (J2).** Three submodels share the work:
- the Asset Interfaces Description (IDTA 02017 [idtaAID]) holds how to reach things;
- Skills holds what they mean;
- the Mapping Configuration (IDTA 02027 [idtaAIMC]) joins the two.

The two templates leave the call itself open:
- AID "focuses on monitoring purposes" and leaves the detailed definition of actions out of scope
  [idtaAID].
- AIMC is meant to map in both directions, but of version 1.0 it says: "In this version only a
  unidirectional mapping from asset to AAS is considered" [idtaAIMC].

We add to both:
- **AID actions.** Every method of the module's OPC UA server is an AID action, with its input and
  output schemas in call order. It carries the command and the skill it carries out as supplemental
  semantic ids.
- **AIMC from AAS to asset.** A command's Operation may be a mapping's source, with the interface
  action as its sink. 02027 calls for this direction ("a (bidirectional) mapping") but leaves it out
  of version 1.0.

An Operation invoked at the AAS server is then delegated to a runtime that calls the action as the
mapping says and answers with the action's reply (Section 4: the data management platform). Nothing
outside the shell says how a skill is called, so plugging in a module needs no code (RQ2).

**Where its data goes.** A module keeps no live value in its shell. Its Variables submodel (ours,
built on IDTA 02008 time series [cite: idtaTimeSeries]) names, per group of values that change
together, a time series and the database table its rows are in:
- the module's state;
- each skill's state and results;
- the measurements;
- a log with one row per call of a command: who called it, with what, and how it ended.

The mapping writes the rows, and a reader asks the database for the latest value or a span. An
execution record refers to the call's row in the log (3.5).

**Settings.** Parameters (ours) holds a resource's settings that are not a skill's: a value, its unit,
and the interface property it is written through. They change when the resource is set up. A skill's
parameters change with every call, so they stay in its Operation. What was built on the controller
(block instances, type hashes, a change log) is the integrator's record, kept outside the shell. The
shell keeps only `RuleSet` and each skill's `Deployment`.

**Constraints.** C01 to C04 (structure); C05 to C07, C10, C11 (within the shell); C12 to C14 (across
the shells of a module and its components); C16 to C19 (across classes).

**What it leaves out, and where that lives instead:**
- a skill's current state and results: in Variables' time series;
- which block of the program is which skill: in the integrator's record;
- which capability a skill realises: the capability refers to its skill, never the other way, so
  only one direction has to be kept;
- when a skill runs: the orchestrators decide.

### 3.5 Process blueprint

**Role.** A process AAS binds one product's recipe to one line. For each step it says:
- which resource and which skill carry the step out;
- what each input of the skill is handed;
- whether the whole fits.

It is ISA-88's master recipe [iec61512part1]. The product AAS holds the general recipe, which names no
equipment. The line engineer keeps the process AAS, and it changes when the line is reconfigured or
the product moves to another line.

Most implementations keep plans in the product's shell [jungbluth2022dynamic, sakurada2025agentbased,
dasilva2026modular]. Keeping them out of it has three consequences:
- a reconfiguration changes the resource shells and at most the process shell, never the product's;
- one product on two lines is one product shell and two process shells;
- an orchestrator that chooses a station per unit changes a choice, not the recipe.

**Table P1. The process blueprint.**

| Submodel | Template | Multiplicity | Origin | Joints |
| --- | --- | --- | --- | --- |
| Process Information | ours | 1 | ours | J5 (the recipe and its revision) |
| Bindings | ours | 1 | ours | J4, J5 |
| Validation | ours | 1 | ours | J3 |
| Executed Processes, in the product's instance AAS | IDTA 02031-2 | 0..1 | extended (proposed, D2) | record |

**What is bound.** Process Information holds three references and two properties:
- the product's shell;
- the line's shell;
- the recipe, the product's sequence of one sequence type;
- the recipe's revision the bindings were made for. A binding names steps of the recipe, so a newer
  recipe can leave it pointing at a step that is gone (C21);
- a status: Draft, Approved or Withdrawn.

The shell names the product's and the line's assets as specific asset ids, so the processes of a
product, or of a line, can be found by asset id.

**Steps to resources and skills (J5).** Bindings holds a step binding per step of the recipe, named by
the step's `NodeId` (with a suffix where a step has several):
- `Step`, a model reference to the step, through its blocks;
- `Resource`, the resource's shell;
- `Skill`, the skill in that resource's Skills;
- `ExecutionMode`: by a resource's skill, or manual.

A step may have more than one step binding. Each is a candidate, validated like the others, and the
run chooses one (idea 4). On the pharmaceutical line each step has one, approved with the process. In
remanufacturing a step has as many as the cell has stations that can do it, and the unit's condition
decides between them.

**Values to inputs (J4).** For each input of the skill that is handed something, an input binding
gives:
- `Name`, the input's name;
- either a constant (`Value`), or a `SourceElement`: a model reference to a parameter in the product's
  Process Parameters [idtaProcessParamsType];
- `InputReference`, a reference to the input itself, a variable of the skill's Start Operation.

The meaning both carry is how the binding was found: the vial's FillVolume and the input Volume of
Dispensing both mean FillVolume. The reference records what was chosen. An input without a binding
runs with its default, and an input without a default has to be bound (C19). Values are handed over
before execution, in the shell, rather than in messages at run time [sakurada2025agentbased], so they
are checked before anything moves.

**Whether it fits (J3).** Validation holds:
- the verdict: Fits or DoesNotFit, or NotChecked while a resource is missing;
- the check that gave it;
- one finding per thing that does not hold, such as "Filling: ContainerType = ampoule is not covered
  by Filling".

The matching itself still runs in a tool, but everything around it is in the models:
- its criterion is a constraint of the blueprint (C17);
- its inputs are in the shells;
- its verdict is in the process shell, and a stored verdict that differs from a recomputed one is
  itself a violation (C20).

The match is thereby a fact of the models, which anyone can recompute.

**What happened (proposed, D2).** The record of a run goes into the shell of the unit that was made or
taken apart: the product's instance AAS, derived from its type AAS. We reuse IDTA's Executed Processes
[idtaProcessParamsInstance]. Per run, and per executed process, it records:
- the values as executed;
- start and end;
- status and result;
- stages and errors.

It names no resource and no skill, so we add four references to each executed process:
- the step binding that was used;
- the resource;
- the skill;
- the call's row in the resource's log.

A unit's history then reads from its own shell, through the process shell, to the module that acted
and the logged call. A deviation, such as a unit taken to the manual station, is an entry in the
record, not a new recipe, as a deviation in a GMP batch record is [iec61512part4].

**Constraints.** C16 to C21 (across classes).

**What it leaves out:**
- when a step runs, and on which shuttle: the orchestrators decide, and transport is chosen at run
  time;
- the order of the steps: that is the recipe's;
- the control strategy, centralized or by agents (P7).

### 3.6 Constraints and conformance

A shell **conforms** to its blueprint when the constraints of its class hold on it alone. A set of
shells is **consistent** when the constraints between them hold on the set. The constraints have four
scopes (Table C):

| Scope | What is checked | Stated as | Constraints |
| --- | --- | --- | --- |
| 1 Submodel | Presence and multiplicity of submodels and elements; model types, value types and allowed values; semantic ids. These are the OWL restrictions of the structure ontologies | SHACL shapes generated from them | C01 to C04 |
| 2 Shell | Every reference that joins two submodels of one shell resolves to an element of the class its relation names, and the two agree. These are the dependencies that a template cannot state [jensen2026ontology] | SHACL with SPARQL constraints | C05 to C11 |
| 3 Shells of one class | A module and its components; a product and its subassemblies | SHACL with SPARQL constraints | C12 to C15 |
| 4 Across classes | The relations of PPRL between product, process and resource shells | SHACL with SPARQL constraints over the projected graph | C16 to C21 |

The checks run where information changes hands (P6):
- a resource shell when it registers;
- a process shell when it is bound, and again when a resource it binds changes;
- an instance at every change during a run, such as a measured condition or a choice among
  candidates.

Section 5 tests which modelling errors each scope detects (RQ3).

**Table C. The constraints.** The last column says what checks each one today.
- *Plan check* is `modreg.plancheck`.
- *Sequence check* is `aas-model/scripts/export_precedence_examples.py`.
- *ARSO rules* are the SPARQL rules of the generation project (IDTA_CONFORMANCE.md, item 5).

| # | Scope | Must hold | Joint | Checked today |
| --- | --- | --- | --- | --- |
| C01 | 1 | A shell holds the submodels its blueprint requires, and no more of each than allowed (a module: one Nameplate, one Hierarchical Structures, at most one of each other) | – | `modreg check` (resource shells) |
| C02 | 1 | Every element has the model type, multiplicity and value type its class states | – | `modreg check`; aas-model's classes when building |
| C03 | 1 | Allowed values: `Kind`, `Deployment`, `Status`, `Result`, `ExecutionMode`, the sequence type | – | in part, by the classes |
| C04 | 1 | Every element is described by the blueprint (strict mode); every meaning is a term of the vocabulary; no semantic id names a single element | – | `modreg check --strict` (resource shells); the meanings not yet |
| C05 | 2 | Every offered capability is realised by a skill of this resource | J1 | ARSO rules (from before skills could be a component's) |
| C06 | 2 | Every command of a built skill has an `InterfaceReference` to an action of this shell's AID | J2 | ARSO rules |
| C07 | 2 | The AIMC maps that command's Operation onto that same action; every mapping's source and sink resolve | J2 | ARSO rules (sources and sinks); "the same action" not yet |
| C08 | 2 | In a partial block, `After` names siblings only, there is no cycle, and `Order` respects `After`; at most one sequence per sequence type | – | sequence check (AFTER, CYCLE, ORDER); `Product` |
| C09 | 2 | Each connection between two parts of the shell's BoM is made or broken by exactly one step of each sequence type present; each connection a step names exists | J7 | sequence check (JOINT, TWICE), in part |
| C10 | 2 | A built skill's commands have their interface; a capability realised by a described skill is `AfterReconfiguration`; derived elements carry `Derived` | J1 | not yet |
| C11 | 2 | Every field of a time series shows, by its meaning, a variable or property of this shell; every series names its table | – | not yet |
| C12 | 3 | A composite step's `Skill` is a skill of this module or of one of its components | J6 | PPRL `UsesDownward`, on the example |
| C13 | 3 | Each binding of a composite step names an input of that skill's Start, and a constant or a variable of the command's Operation, within the input's limits and in its unit | J6 | `modplan check` |
| C14 | 3 | A capability realised by a component's skill names a component of this module | J1 | not yet |
| C15 | 3 | A call step's sequence is the sequence of a subassembly of the same sequence type, and the subassembly is a part of the BoM | – | sequence check (BROKEN), in part |
| C16 | 4 | Every step the bound recipe runs, including those of the sequences it calls, has at least one step binding. Its `Step` resolves into the recipe, its `Resource` is part of the bound line, and its `Skill` is a skill of that resource | J5 | plan check; sequence check (UNBOUND, BROKEN) |
| C17 | 4 | The bound skill realises an offered capability with the step's required meaning or a narrower one, whose properties cover every required value in the same unit | J3 | plan check; PPRL `BoundSkillIsCandidate` |
| C18 | 4 | Each input binding's `InputReference` is an input of the bound skill's Start, and its `SourceElement` resolves to a product parameter. Units agree, and the value lies within the input's limits | J4 | plan check |
| C19 | 4 | Every input of the bound skill that has no default is bound | J4 | not yet |
| C20 | 4 | The stored Validation is what the check finds | J3 | building the reference models |
| C21 | 4 | `RecipeRevision` is the recipe's `Revision` | J5 | not yet |

Two things to change before the evaluation (D5):
- **Most constraints of scopes 2 to 4 are Python today.** For RQ3's "formalised", they should become
  SHACL shapes over the projection. The Python checks then serve as the reference that the shapes must
  agree with on every mutant of E4.
- **Some constraints are not checked yet:** C10, C11, C14, C19 and C21.

## 5. To settle with the colleagues

Each item ends with our recommendation. The first five decide whether 3.3 and 3.5 fit together.

- **A1. Where the connections live.**
  - The colleagues' draft puts them in the BoM, as AREs between entities, and the BoP's steps refer to
    them (`affectedJoint`, `affectedEntity`).
  - Our Production Sequence 4.0 defines them in the step that breaks them, and keeps Hierarchical
    Structures a plain tree of parts. That was the user's choice of 2 Nov.

  **Recommendation: take the colleagues' placement.** A connection is a fact of the product's
  structure, and it exists once, whatever the sequence type. Section 2's J7 also reads "a joint in the
  product". Our 4.0 then keeps only references in a step's `Joints`, as its Assembly sequence already
  does. This reverses our choice, so it needs the user's go. Its price: Hierarchical Structures is
  extended, by an addition, which 02011 allows.
- **A2. One recipe, as a partial order.** The colleagues' BoP and our Production Sequence are two
  descriptions of the same thing. The draft calls the BoP "an ordered list of process steps", but the
  battery case needs a partial order: the modules come out in parallel, and the agents call for
  proposals on every ready step. APSO's `ProcessOrder` relations already are a partial order.
  **Recommendation:** one element set under one name, partially ordered. The process AAS binds its
  steps by `NodeId` and path.
- **A3. Where a connection's parameters live.**
  - The colleagues: `JointParams` in the BoM.
  - Us: the process's parameters in Process Parameters (IDTA 02031-1), from where they reach the
    skill's inputs (J4).

  **Recommendation:** the values a step needs (torque, force) go into Process Parameters. The BoM's
  `JointParams` keeps the design data (screw size, standard). Each value is written once.
- **A4. Required capabilities.** APSO has a Requirements module of its own; Section 2 states
  requirements as 02020 required capabilities. **Recommendation:** 02020 with the role Required, which
  each process refers to.
- **A5. Condition.** The colleagues' `ConditionInfo` is optional and filled in during processing.
  **Recommendation:**
  - reuse the Digital Battery Passport's condition part where it fits (state of health, remaining
    capacity [idtaDBPCondition]), and add only the connection's condition (a seized or corroded
    screw);
  - a required capability's properties take their values from it (`takesValueFrom`), so that
    checking the candidates again uses it (journal-evaluation.md, section 4).
- **A6. Type and instance.** "The blueprint ... is maintained once as a type-level AAS; only the
  instance AAS is enriched" mixes the blueprint with the type AAS. **Recommendation:** "the type AAS
  is maintained once; each returned product gets an instance AAS derived from it, which holds its
  measured condition and its record."
- **A7. Names.**
  - "Joint" means both J1 to J7 and a screwed connection, so J7 reads "a joint in the product must
    lead to a disassembly step". **Recommendation:** keep "joint" for the mechanical kind, the
    domain's word, and call J1 to J7 "seams" (S1 to S7), or "links".
  - APrSO (introduction) or AProSO (repository): pick one. APrSO reads better beside APSO.
- **A8. "Type-level":** see section 1.
- **A9. "Exclusively ReferenceElements"** in 3.1: see the note there.
- **A10. The battery system.** Our example pack (a cover with twelve screws, an HV connector, a BMS,
  busbars and four modules on three stations) was drawn for the figures. The case is the colleagues'
  REVAMP truck battery: housing, cover and modules, screw, plug and form-fit connections, and four
  stations (the robot cells for cover removal and module disconnection, a manual station, a sorting
  station). **Recommendation:** remake our example shells and the `-battery` figure pages from REVAMP's
  bill of material and station list.
- **A11. `ArcheType`.** The colleagues' BoM carries 02011's `ArcheType` (Full, OneDown, OneUp), and our
  4.0 uses the same idShort for Assembly or Disassembly. **Recommendation:** rename ours
  `SequenceType`.

## 6. To decide among us

- **D1. Several step bindings per step, as candidates.** Hardly a change to the template, which already
  allows any number of step bindings:
  - a step binding is named by its step's `NodeId`, so a second candidate takes a suffix
    (`UnscrewCover_2`);
  - its `NodeId` property, which may repeat, names the step;
  - the plan check and Validation judge each candidate.

  **Recommended:** it is what idea 4 and the battery case need.
- **D2. The record:** IDTA 02031-2 Executed Processes in the product's instance AAS, with four added
  references. **Recommended:** it is needed for E5 and for the battery case, and it reuses IDTA instead
  of adding a template.
- **D3. The order of sections:** product, resource, process. **Recommended** (section 2).
- **D4. Scope:** planning and the comparison of orchestrators stay out; the orchestrators appear only
  as users. **Recommended** (section 2).
- **D5. The constraints as SHACL.** Port the plan check and the sequence check to SHACL-SPARQL over the
  projection, and add C10, C11, C14, C19 and C21. **Recommended:** RQ3 claims they are formalised.
- **D6. PPRL 0.3:**
  - `invokedThrough` (J2);
  - the connection relations (J7);
  - the projection of the product and process shells.

  **Recommended.**
- **D7. APSO and APrSO remade from the templates as built** (F5 in [next-steps.md](next-steps.md)),
  with the colleagues for APSO. **Recommended:** section 3.2 claims one structure ontology per class.
- **D8. A small fix:** Validation's template lists Fits and DoesNotFit, while the battery example uses
  NotChecked. Add NotChecked to the template.
