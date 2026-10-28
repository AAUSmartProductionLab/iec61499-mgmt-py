# The product, process and resource model

The model the work proceeds by, decided on 26 Oct 2026 ([decisions.md](decisions.md)): which AASs
there are, what each holds, which ontology each element is tied to and by which id, which
application reads and writes what, and how a product's need becomes a change of an IEC 61499
program. Each part says whether it is built. What the AASs built today hold, element by element, is
in [aas-models.md](aas-models.md); the plan is in [next-steps.md](next-steps.md), section F.

Figures (draw.io; open them at app.diagrams.net or in the draw.io desktop app, and edit them there):

| File | Page | Shows |
| --- | --- | --- |
| [figures/ppr-models.drawio](figures/ppr-models.drawio) | Models and ontologies | The three AASs with their submodels and references, and the ontologies their ids point into |
| | Applications | Which application reads and writes which AAS, and which acts on the running module |
| [figures/reconfiguration-pipeline.drawio](figures/reconfiguration-pipeline.drawio) | Reconfiguration pipeline | From a product's recipe through a changed skill to a changed IEC 61499 program, and back to the plan |
| [figures/skill-hierarchies.drawio](figures/skill-hierarchies.drawio) | Hierarchies | The line's, a module's and its components' AASs as the web UI's tree shows them: the bill of material names the module and its components; Dispensing's steps run the components' primitives |
| | Recipe to process | The product's, the line's and the modules' AASs feed a process sequence (one card per step: what comes from which AAS); kept as the process AAS, whose rows are coloured by where they come from |
| | Hierarchies (paper), Recipe to process (paper) | The same two, cut down for the paper: no title, only the rows the argument needs |
| [figures/module-tools.drawio](figures/module-tools.drawio) | Tools and FORTE | The tools (spec, modgen, 4diac project, build, deployment, AAS, modsync, modlink) above the filling module's program drawn as its function block network (as in the module architecture figure): the INIT chain, Dispensing with its wiring, and create, read, update and delete on it (the boot file; DoubleDose created online and appended; a step's constant written; deleting only by a new boot file); the OPC UA nodes the blocks serve |
| | Tools and FORTE (paper) | The same, as small cards and Dispensing's network with the online change |
| | Production system | The line as it stands, drawn isometrically (the ACOPOS 6D table and its shuttles, the four stations each with a Pi running FORTE, the Kuka robots at loading and unloading, the vial filled, stoppered and capped on its way), the inside of the filling module (the Pi, its program, the equipment on GPIO and PWM, its ports), and the server: the AAS environment with the product, process and resource AASs, the web UI, modreg, modsync, modlink, the transport control, and the agents and time series database still planned |
| | Concept (isometric) | The idea in four layers floating above each other, drawn isometrically: the assets (the line), control (a Pi with FORTE per module, the transport controller), information (the AAS server with the product, process and resource AASs) and the applications (planner, skill editor, modreg, modsync, modlink, agents); dashed lines say what connects them |
| | Layers (computers) | The line and five layers above it, drawn isometrically: the digital assets (each module's parts with their kind and IO, wired to its Pi; the robots and the transport); behaviour in IEC 61499 (FORTE per module, Dispensing's function block network, the PackML state machine, a skill's state machine); the AAS models and orchestration (a resource AAS, the product's recipe bound to the modules, agents; the AAS server, modreg, modsync, the orchestrator, the time series); the HMIs, MES, planning and scheduling (ERP, MES, planner, scheduling, skill editor, HMI, a schedule and the HMI sketched). The programs as the computers they run on |
| | Layers (programs) | The same, with each program drawn as its window standing on its layer |
| | Layers (illustrated) | The same layers drawn further: the stations open in front and reach over the vial with their tools, shuttles with black rims, names on signs above the stations; the programs as windows with the server they run on at the side; the agents as a product and miniature modules, the AASs as stacks, people at the planner and the HMI; the HMI with a state machine and buttons per module, a trend and alarms. Only the lines that matter, along x, y and z |
| | Layers (slide) | The same layers for a slide: a few objects with a word or two on each, the layers apart, big cards naming them on the right |
| [figures/mapping.drawio](figures/mapping.drawio) | AAS skill to IEC 61499, Flow kinds as blocks, The AAS as the target | Dispensing's AAS elements beside the blocks, values and connections they are (numbered to match), with its OPC UA nodes and the names that join them; each kind of step as its pattern of library blocks, and groups of conditions as chains; modsync's loop from the AAS and the running program to the commands, the check and the record ([mapping.md](mapping.md)) |
| [figures/slides.drawio](figures/slides.drawio) | 01 to 19, 06b | One figure per slide of [presentation/presentation.md](presentation/presentation.md): 16:9 pages, big type, few elements, no title of their own; 01 is the line alone, for the title slide; 06b the layers across a whole slide, drawn dimetrically so each layer is a long shelf |

They follow the style of the module architecture figure (Arial, grey panels, white cards, rounded
pills, small blue tags, dashed for what is not built yet).

## 1. Three kinds of AAS

The split follows ISA-88's recipe levels, which pharmaceutical batch production already uses:

| ISA-88 | AAS | One per | Holds | Changes when | Owner | Ontology | Built |
| --- | --- | --- | --- | --- | --- | --- | --- |
| General recipe | **Product AAS** | Product, and each part with a recipe of its own | What the product is, the processes it needs with their parameters and materials, the capabilities they require, the recipe (steps, order, conditions), no equipment named | The product changes | Product designer | APSO | Yes, but the recipe still holds the bindings |
| Master recipe | **Process AAS** | Product and line | The recipe bound to one line: each step's resource, skill and parameter bindings, and the plan check's result | The line is reconfigured, or the product moves to another line | Line engineer | AProSO | No |
| (equipment) | **Resource AAS** | Line, module, component | What it offers and how it is called, what its skills are made of, what was built, what it does | The vendor delivers it; the integrator's tools change it online | Vendor | ARSO | Yes |
| Control recipe, batch record | Order, product instance | Order; vial | How many, which run; what was done to each vial | Every order | The executor (agents) | APSO, PPRL | After the paper |

Why the process AAS is separate from the product AAS:

1. A reconfiguration changes the resource AAS and at most the process AAS. The product AAS is not
   touched: the product stays the same, the line adapts.
2. One product on two lines is two process AASs and one product AAS.
3. The agents later replace only the bindings, per order; the recipe stays.
4. Each owner has one AAS: product designer, line engineer, vendor.

**The planner fills the process AAS.** The process sequence planner (a module of the BaSyx web UI)
takes the recipe from the product AAS, matches each step's required capability against the offered
capabilities of the resources, binds the step to a skill (by the matching or by hand) with its
parameters, and writes these bindings into the process AAS. Today it keeps them in the product's
Production Sequence; they move with the planner change (F6).

## 2. The submodels

Template "ours" means a submodel template of our own (section 6). Since 28 Oct the types of the three
AASs, the templates and their classes are in aas-model (branch `lab-ppr-models`: `Product`,
`Process`, `Module`, `Component`, `ProductionSystem`; its `docs/lab-aas.md`), and the example line's
are the lab's reference models: three products and their processes written out in Python
(`cell/examples/products`, `cell/examples/processes`), the modules built from their specs
([aas-examples.md](aas-examples.md)).

**Product AAS**

| Submodel | Template | Holds | Built |
| --- | --- | --- | --- |
| Nameplate | IDTA 02006 | What the product is | Yes |
| Hierarchical Structures | IDTA 02011 | The bill of material: parts with quantities, each part's AAS by its asset id | Yes |
| Process Parameters | IDTA 02031 + our extension | The processes with product, process and resource parameters, the materials each uses (`MaterialUse`), a reference to the capability each requires | Yes |
| Capability Description | IDTA 02020, role Required | The capabilities the processes require, with values or acceptable ranges | Yes |
| Production Sequence | ours (the planner's, 2.0) | The recipe: steps that run processes, calls of sub-recipes, parallel, decision and optional flows, conditions | Yes; the reference products' name no equipment, the planner still writes bindings into it (F6) |

**Process AAS** (built since 28 Oct: aas-model's `Process` with templates of its own; one per
reference product on the example line, `cell/examples/processes`, checked by `plan_check.check_process`.
No ontology yet. Its asset is the process; it carries the product's and the line's asset ids as
specific asset ids, so it is found from either)

| Submodel | Template | Holds |
| --- | --- | --- |
| Process Information | ours | The product and the line (references to their AASs), the recipe it binds and its revision, status; approval to come |
| Bindings | ours | Per step of the product's recipe (by its `NodeId`): the step, the resource, the skill (references), and per input of the skill what it is handed (a process parameter of the product or a constant) with a reference to the input itself; the elements are the planner's (Production Sequence ids). To come: the candidates the matching found |
| Validation | ours | The plan check's result (`Result`, `Findings`); when and by whom to come |

**Resource AAS** (a module; a line has Hierarchical Structures of its modules, a component its Skills)

| Submodel | Template | Holds | Built |
| --- | --- | --- | --- |
| Nameplate | IDTA 02006 | What the resource is | Yes |
| Hierarchical Structures | IDTA 02011 | Its parts: a line's modules, a module's components | Yes |
| Capability Description | IDTA 02020, role Offered | What it offers, with ranges, each capability realized by a skill; derived from the skills (section 5) | Yes, derived since 26 Oct |
| Skills | ours (ARSO) | Each skill as its commands, directly in the submodel; the Start's variables are the parameters with limits; a composite's steps; the error codes | Yes |
| Asset Interfaces Description | IDTA 02017 (+ aas-model's actions) | The OPC UA endpoint and every action and property | Yes |
| Asset Interfaces Mapping Configuration | IDTA 02027 | Which interface element feeds which data, which action an Operation calls | Yes |
| Variables | aas-model's (ARSO 0.14; Operational Data until 0.13) | Live values as Properties (their meaning a supplemental id), and `State`, `Measurements` and `Log` holding IDTA 02008 time series as SMCs; the coordinates in `Measurements` | Data points and coordinates; series planned ([state-and-parameters.md](state-and-parameters.md)) |
| (in Skills) `RuleSet`, `Deployment` | ours (ARSO 0.10) | The rule set the program is built by; per module level skill, `Built` or `Described`. What was built in detail (instances, block types, hashes, the change log) is the integrator's record outside the AAS ([control-configuration.md](control-configuration.md)) | Yes, since 27 Oct |
| Parameters | ours | The resource's settings (microsteps, speed, timeouts) | Planned |
| Technical Data | IDTA 02003 | Fixed facts (screw lead, motor current) | Planned |

## 3. Ontologies and ids

Three layers:

| Layer | What | Tied to the AAS by |
| --- | --- | --- |
| Domain vocabulary (`ontology/Vocabulary`) | What things mean: capabilities of two kinds (process: a product can require it; auxiliary: it serves other skills), properties, commands, skill types with the capability each contributes (built 26 Oct); variables and states, equipment and product kinds (to do). Classes below CSS, aligned to VDI 2206, VDI 3682, IEC 61360, PackML | `supplementalSemanticId` |
| PPRL | Relations between individuals (`hasPart`, `hasSubProcess`, `requiresCapability`, `matches`, `isRealizedBySkill`, `usesSkill`, `boundTo`, `takesValueFrom`, ...) and rules (derived candidates, derived capabilities) | Made from the references the AASs hold, by the projection (section 4) |
| APSO, AProSO, ARSO | What each element of an AAS is, one ontology per kind of AAS, with the restrictions it must satisfy | `semanticId`: a class names the semantic id of the elements it describes (`arso:semanticId`) |

**Three ids, three jobs** (decided 26 Oct):

| Id | Says | Points into |
| --- | --- | --- |
| `semanticId` | What the element is in its template | APSO, AProSO, ARSO (and IDTA's ids) |
| `supplementalSemanticId` | What it means in the domain | The vocabulary: `lab:Filling`, `lab:FillVolume`, a skill type, a command, a state |
| The element's own id or reference | Which individual it is (this skill, this step) | Nothing: the projection names the individual by it |

State on 26 Oct, from the 305 ids the example line's 15 AASs carry: the template ids of the
resource AAS and the vocabulary's capabilities and properties are in an ontology; the product side
(Process Parameters, MaterialUse, the plan's own fields), skill types, variables, most commands and
states, and the lab's `apex` state ids are in none; about half the ids name one element rather than
a concept (`.../skills/Dispensing/Execute/NeedleDown/Position`) and are to be moved out (`modlink`
joins a data point to its variable by such an id; that join changes with them). APSO and AProSO
describe a Bill of Process and a process AAS nothing builds and carry no semantic ids: they are
remade like ARSO, from the submodels above.

## 4. Hierarchies and relations

The hierarchies are not written twice: the projection (AAS JSON to RDF) makes them from references
the AASs already hold, and the vocabulary's class hierarchy adds the kinds.

| Hierarchy | From | Relation |
| --- | --- | --- |
| Equipment: line, module, component | Hierarchical Structures of the resources | `pprl:hasPart` |
| Product: product, parts | Hierarchical Structures of the product | `pprl:hasPart` |
| Process: recipe, steps, sub-recipes | Production Sequence (steps, calls) | `pprl:hasSubProcess`, `directlyPrecedes` |
| Skill: composite, steps, primitive | Skills (`Step/Skill`) | `pprl:usesSkill` |
| Capability to skill | Capability Description (`CapabilityRealizedBy`) | `css:isRealizedBySkill` |
| Process to capability | Process Parameters (`RequiredCapability`) | `css:requiresCapability` |
| Values | A binding's source, a parameter's meaning | `pprl:takesValueFrom`, `css:isRealizedBySkillParameter` |
| Step to resource and skill | Process AAS, Bindings | `pprl:executedBy`, `boundTo` |

The projection runs in three passes: type each element by its `semanticId` (as `modreg check` does
for ARSO today), create an individual for each element with a `supplementalSemanticId`
(`pprl:describes`), turn the references into the relations above (rules kept in PPRL as data). One
projection serves the checks, the matching and the derivation; the AAS generation project's
converter and `modreg`'s check become one. **Built 26 Oct** for the resource AASs' Skills,
Capability Description and Control Configuration (`modreg/projection.py`, rules in
`ontology/PPRL/projection`, `modreg graph` writes the graph); the product side, Hierarchical
Structures and the process AAS are still to do.

## 5. Capabilities derived from skills

A module's offered capabilities follow from its skills and the vocabulary, so they are derived and
written into the Capability Description, not typed by hand:

| Part of a capability | Example | From |
| --- | --- | --- |
| Which capability | Filling | The skill types its steps run (the vocabulary says Dispense contributes Filling); for a new skill made from an existing one, that one's |
| Properties a parameter sets | FillVolume 0.5 to 10 mL | The parameter's meaning and limits (`css:isRealizedBySkillParameter`) |
| Properties a step's constant sets | FlowRate 1.0 mL/s | The constant and its meaning |
| Facts of the machine | ContainerType vial, GraspDiameter, AbsoluteFillError | Not from the skill: stated once per module (later its Technical Data); the vocabulary lists which a capability needs |

**Built 26 Oct.** The rule is `ontology/PPRL/derivation/10-capabilities.rq`, run on the projection
(`modreg/derive.py`). What a parameter means is stated on a primitive's parameter (the spec's
`meaning`, written as its supplemental semantic id); a module level skill's parameter inherits it
through the step it is handed to. Derived elements carry the qualifier `Derived`, so a derivation
replaces only what it derived; facts and capabilities written by hand stay, and a container keeps
its name (two skills offering one capability: `<Capability>_<Skill>`). A described skill that is
not built yet (`Deployment = Described`, since 27 Oct; before, no instance in the Control Configuration) offers its capability with
`Availability = AfterReconfiguration`. Written by `modreg profile` (the module spec's
`capabilities` keep only the facts of the machine; a capability no skill offers is refused), by
`modsync record` (with the components' AASs) and by `POST /capabilities/<shell>` of `modreg serve`,
which the skill editor is to call after saving. Still to do: the skill editor calling it, the
planner showing the availability. Aggregates (DoubleDose fills twice the Volume) need a rule of
their own and come later.

## 6. Submodel templates of our own

In aas-model since 28 Oct: the templates (`templates/`), the pydantic classes made from them
(`scripts/lab_generate.py`) and a description of every submodel, its purpose and reasons by hand and
its elements in the form of IDTA's specifications written from the template (`docs/lab-submodels/`,
`scripts/lab_docs.py`). `modreg generate` writes ARSO's templates from the ontology into aas-model.

| Template | Ontology | Template and classes | Element description |
| --- | --- | --- | --- |
| Skills, Control Configuration, Parameters | ARSO | Yes, from the ontology | Yes |
| Variables (with the coordinates) | ARSO 0.14 describes aas-model's | aas-model's own classes | Yes (`docs/lab-aas.md`) |
| Production Sequence (the recipe) | APSO (remade) | Copied from the planner (2.0) | Yes |
| Process Parameters extension | APSO (remade) | Yes | Yes |
| Process Information, Bindings, Validation | AProSO (remade) | Yes, written by hand | Yes |

## 7. The applications

| Application | Reads | Writes | Acts on the module | Built |
| --- | --- | --- | --- | --- |
| Process sequence planner (web UI module) | Product AAS; offered capabilities and skills of the resources | The recipe (product AAS), the bindings (process AAS) | – | Yes; the process AAS is planned |
| Skill editor (web UI plugin) | A module's Skills and its components' | The module's Skills | – | Yes; its fixes not committed; calling the derivation after saving is to do |
| `modreg` | Specs, profiles, the ontologies | Every AAS (built, checked, registered); derived capabilities | – | Yes |
| `modsync` | Skills, the integrator's record, the running program | `Deployment`, the interface of a new skill, the record, the boot file | Creates, writes, verifies (management protocol) | Yes |
| `modlink`, HMI | Interface description, mapping, Skills | – | Occupies, calls skills (OPC UA) | Yes; the HMI moves into the web UI (C5), later the AAS alone (C6) |
| Agents | Process and resource AAS | Bindings per order | Through `modlink` and `modsync` | After the paper |

## 8. The pipeline

From [figures/reconfiguration-pipeline.drawio](figures/reconfiguration-pipeline.drawio):

| # | Step | Application | Built |
| --- | --- | --- | --- |
| 1 | The product's recipe: processes, parameters, required capabilities | Planner | Yes |
| 2 | Match required against offered: offered now, offered after a reconfiguration, not offered | Planner | Yes; "after a reconfiguration" is in the AAS (`Availability`), the planner does not show it yet |
| 3 | Not offered: change a skill (a new one from an existing one, a limit, a constant) | Skill editor | Yes |
| 4 | Derive the capabilities from the changed skills | `modreg` (`serve`, `profile`), `modsync record` | Yes; the skill editor does not call it yet |
| 5 | Compare the Skills with the running program; check; guard | `modsync` | Yes |
| 6 | Apply online: instances, values, connections by the module rules; INIT | `modsync`, FORTE | Yes |
| B2 | Or, as the baseline: a new boot file and a restart | `pi.py`, FORTE | No (B2) |
| 7 | Verify by reading the program back | `modsync` | Yes |
| 8 | Record: `Deployment`, the new skill's interface, the integrator's record, the boot file | `modsync` | Yes |
| 9 | Match again, bind in the process AAS, run: occupy, Start over OPC UA | Planner, `modlink` | Matching and running yes; the process AAS no |

Steps 5 to 8 against B2 are what the evaluation times (B1, B2).

## 9. Before and after the paper

| Before 18 Nov | After |
| --- | --- |
| Skill types in the vocabulary, each with the capability it contributes (done 26 Oct) | Variables and states (aligned with the lab's `apex` ids), equipment and product kinds, DIN 8580 and VDI 2860 |
| The projection of Skills and Capability Description (done 26 Oct) | The projection of everything else |
| Capabilities derived from skills, written back (done 26 Oct); the skill editor calling it and "after a reconfiguration" in the planner (to do, web UI) | APSO and AProSO remade; templates and element descriptions for all our submodels |
| The figures and this model as the paper's overview | The process AAS and the planner writing into it; per-instance ids moved out |
