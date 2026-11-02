# Journal paper: the design decisions, against the alternatives

Written on 2 Nov 2026, for the authors. It collects every decision behind the blueprints:
- what was chosen;
- what it was chosen instead of, and who does it that way;
- why;
- what it costs.

It serves two places in the paper:
- **Section 3:** one sentence where each element is introduced, naming the alternative and its source;
- **Section 6 (discussion):** a table of the main decisions (section 5 here), and a table of how far
  each reviewed work closes the joints (section 6 here).

The method is in [journal-method.md](journal-method.md), the evaluation in
[journal-evaluation.md](journal-evaluation.md). The settled decisions of the CIRP paper, mostly about
the module in IEC 61499, are in [design-decisions.md](design-decisions.md), and the day-by-day reasons
in [design-log.md](design-log.md).

Citation keys are those of the paper's bib file. A key written *[cite: ...]* is not in it yet.

The decisions fall into four kinds, and the paper should keep them apart:
- **M, the blueprints:** normative. They are the contribution, and another implementation would have
  to follow them.
- **O, the ontologies and the checks:** normative. They are how conformance is defined and checked.
- **X, what is deliberately left out:** scope. A reviewer asks for these, so they are stated.
- **T, technologies:** our implementation, replaceable. Each could be swapped without changing a
  blueprint.

## 1. The blueprints (M)

**M1. A process AAS of its own: the master recipe.**
- **Instead of:**
  - a plan submodel in the product's shell: a production plan whose steps refer to a module's skills
    [jungbluth2022dynamic]; a manufacturing plan with state, schedule, operation and resource per step
    [sakurada2025agentbased]; active steps [dasilva2026modular]; a bill of process [shi2026cognitive];
  - a plan negotiated at run time and not stored [stolze2024realizing, arm2021automated];
  - orders kept outside the AAS [nguyen2025aas].

  The closest are a process AAS with steps and the capabilities they need [alonso2024aas], and product,
  process and resource shells in an agentic architecture [li2026agentic].
- **Why:**
  - ISA-88 separates the general recipe (what the product needs) from the master recipe (on which
    equipment) [iec61512part1], and regulated batch production already works so;
  - each shell has one owner;
  - a reconfiguration leaves the product's shell untouched;
  - one product on two lines is two process shells;
  - a binding is checked before anything runs;
  - the record of a run has something to refer to.
- **Price:**
  - one more shell to keep consistent with the product's, hence the recipe's revision (C21) and the
    constraints C16 to C21;
  - finding the process of a product needs its asset id, held as a specific asset id.
- **In the paper:** 3.5.

**M2. Reuse, then extend, then add.**
- **Instead of:** submodels of one's own where templates exist (most works of Table tab:coverage); an
  extension of the metamodel [nguyen2025aas]; copying a template and changing it.
- **Why:**
  - a reader that knows an IDTA template still reads ours;
  - every addition is told apart by its semanticId;
  - no element of a template is changed or removed;
  - the share of additions is measurable (RQ1).
- **Price:**
  - our AID, AIMC and Capability Description carry additions that an IDTA reader ignores;
  - to become standard, the three additions must go to IDTA: the target of `CapabilityRealizedBy`,
    AID actions with schemas, and AIMC from AAS to asset.
- **In the paper:** 3.1, Table 1.

**M3. Every link a tool follows is a model reference.**
- **Instead of:**
  - links by name or idShort convention;
  - an external reference to a target the template does not define (02020's `CapabilityRealizedBy`
    [idtaCapability]);
  - links held in an ontology beside the AAS, reached through semantic identifiers [hurtado2025smia],
    or declarative mappings between submodels and an ontology [vieiradasilva2023mapping].
- **Why:**
  - any AAS client resolves a model reference through the AAS API;
  - a constraint can follow it;
  - the projection turns it into a relation (3.2);
  - nothing outside the shells has to be kept in step.
- **Price:**
  - ids must be stable, so we derive them from asset ids;
  - a reference into another shell needs that shell on the same server, or a registry that finds it.
- **In the paper:** 3.1.

**M4. Three ids, three jobs.**
- **What:**
  - the semanticId says what an element is in its template;
  - a supplemental semantic id says what it means in the domain;
  - the element's own id, or a reference to it, names the individual.
- **Instead of:**
  - the domain meaning as the semanticId, which is common: a capability's IRI as its semanticId;
  - matching by idShort;
  - a semanticId per element, which names no concept (half of the ids of our own first models did,
    26 Oct).
- **Why:**
  - a template's validator and a domain's matcher each find what they need in one place;
  - matching does not depend on names, so two parties name their elements as they like.
- **Price:**
  - tools seldom read supplemental ids;
  - the vocabulary needs an owner, and alignment with ECLASS and IEC CDD where they cover a property
    [guentner2023industrial].
- **In the paper:** 3.1.

**M5. Offered capabilities are derived from skills.**
- **Instead of:** capabilities written by hand (all reviewed works), or held only in an ontology
  [hurtado2025smia]. Alonso et al. let a module's capabilities be "inherited from the assets that
  compound the module" [alonso2024aas]. That is the same idea one level up, from parts rather than from
  skills.
- **Why:**
  - an offer and the skill behind it cannot drift apart: a new skill without a capability, or a
    changed limit the capability does not follow;
  - a skill that is only described offers its capability "after reconfiguration", which is the answer a
    product-driven change needs.
- **Price:**
  - the rules of derivation live in the vocabulary (which skill type contributes which capability);
  - the facts of the machine (container types) are still stated by hand.
- **In the paper:** 3.4.

**M6. A Skills submodel of our own: a skill is its commands.**
- **Instead of:**
  - IDTA's Control Component templates [idtaCCType, idtaCCInstance], used as they are by
    [sakurada2025agentbased]. They give a skill one Operation and a list of used skills, a parameter's
    type is a free string, and its meaning "should be added via a capability Submodel";
  - skills as delegated operations bound to a service [li2026agentic];
  - skills in an ontology [hurtado2025smia];
  - skill submodels of their own [sidorenko2023mas4ai, dasilva2026modular];
  - an OPC UA SkillType [koecher2023reference];
  - OPC UA programs [dorofeev2018skill].
- **Why:**
  - J2 needs an interface reference per command, since Stop and Abort are called through other
    actions than Start;
  - J6 needs the steps a command runs, in order, with their values;
  - a client calls commands, so that is what a skill is made of;
  - a parameter carries its unit, limits, default and meaning in the Operation it is passed by.
- **Price:** not an IDTA template. It is input for a revision of the Control Component templates.
- **In the paper:** 3.4.

**M7. One step format for recipes and composite skills.**
- **Instead of:**
  - BPMN for processes, run by an engine, with state machines for skills [koecher2022bpmn];
  - composition by a superior PackML state machine [schaefer2022industrial];
  - composition of capabilities only [barth2023mtp].
- **Why:**
  - one reader, one editor and one checker serve both (J4 and J6 are one constraint at two levels);
  - the hierarchy of line, module and component mirrors that of product, subassembly and part.
- **Price:**
  - flows are block-structured: well-structured BPMN only, read back into blocks;
  - partial blocks are allowed in a product's recipe but not inside a module's skills, since an
    IEC 61499 program runs blocks.
- **In the paper:** 3.4, idea 3 in 3.1.

**M8. Each skill has a small state machine; PackML runs once, for the module.**
- **Instead of:** a harmonised state machine per skill, often PackML [koecher2023reference,
  isaTR88PackML, opcPackML].
- **Why:**
  - a skill is called, runs and ends, like a node of a behaviour tree, so Idle, Running, Stopping,
    Succeeded, Failed and Aborted suffice;
  - one machine for every skill means one way to call any of them;
  - Start, Stop, Abort and Reset answer at once with `Accepted` and `ErrorID`.
- **Price:** a client that expects PackML per skill has to map.
- **In the paper:** one sentence in 3.4; the module side is the CIRP paper's.

**M9. The interface is described for acting, not only for monitoring.**
- **Instead of:**
  - AID as published, which "focuses on monitoring purposes" [idtaAID], and AIMC 1.0, of which IDTA
    says "In this version only a unidirectional mapping from asset to AAS is considered" [idtaAIMC];
  - AID extended for properties only [hurtado2025smia];
  - calls configured outside the shell, as runtimes need them today. FA³ST builds asset connections from
    AID and AIMC, but "if you need write access or if you want to call operations in the Asset" they are
    configured in its own file [cite: fa3st]. BaSyx's DataBridge is configured by its own route and
    consumer files [cite: basyx-databridge].
- **Why:** J2 closes in the shell. An Operation invoked at the AAS server is delegated, and the runtime
  calls the action the mapping names, so nothing outside the shell says how a skill is called. That is
  what "invoked from its AAS alone" (RQ2) means.
- **Price:**
  - it depends on the server delegating Operations, and on a runtime that executes AIMC in this
    direction (T2);
  - a call through the server is slower than a direct OPC UA call, so the agents also call directly
    (T6).
- **In the paper:** 3.4.

**M10. No live values in the AAS: Variables names time series.**
- **Instead of:** properties kept current by a mapping, which is the usual use of AID and AIMC
  [vaz2025automated, idtaAIMC] and how the lab's earlier stations worked; values read over OPC UA only.
- **Why:**
  - values change fast (a position while an axis moves);
  - written into the AAS server, they load it with writes nobody reads there, and it keeps no history;
  - a time series keeps every row, including one per command call, which the record refers to.
- **Price:** a reader needs the database as well as the AAS. The series' shape follows IDTA 02008, so
  the database is named in IDTA's terms.
- **In the paper:** 3.4.

**M11. The AAS says what is wanted; the integrator records what was built.**
- **Instead of:** the build record in the AAS (our own Control Configuration until 27 Oct).
- **Why:**
  - the shell is what a vendor delivers;
  - instances, type hashes and change logs change with every build and are read by the integrator's
    tools only;
  - the shell keeps what clients read: `RuleSet` and each skill's `Deployment`.
- **Price:** two places to read for the whole picture.
- **In the paper:** one sentence in 3.4.

**M12. Planning constraints go into 02020; there is no planning submodel.**
- **Instead of:**
  - planning submodels that mirror PDDL [nabizada2026capability];
  - an AI-planning submodel of our own [cite: schwoerer2026fond];
  - transition constraints between capabilities only [plattform2025cssplus].
- **Why:**
  - 02020's property constraints already state preconditions, postconditions and invariants;
  - a module's Capability Description is then its whole planning domain;
  - PDDL and HDDL are generated from it, so the blueprint does not depend on a planner.
- **Price:** the constraints say only what 02020's `BasicConstraint` expressions can say.
- **In the paper:** one sentence in 3.4, if planning stays out (D4).

**M13. Alternatives come from matching, not from OR nodes in the recipe.**
- **What:** a step names the capability it requires, and any offer that covers it is a candidate.
- **Instead of:** AND/OR graphs of alternatives, common in disassembly planning; alternative processes
  listed in the recipe.
- **Why:**
  - the product designer says what is needed, not by which equipment;
  - a module that is plugged in and offers the capability becomes an alternative without anyone editing
    the recipe.
- **Price:** an alternative that changes the plan's structure (drill, then extract) still needs a
  decision block in the recipe.
- **In the paper:** 3.5, and the battery case.

**M14. Validated candidates per step; the run chooses, and the record says which (proposed, D1).**
- **Instead of:** one binding fixed per step (a validated line); free binding at run time by
  negotiation [stolze2024realizing, sakurada2025agentbased].
- **Why:**
  - one structure covers both domains: one candidate in pharma, several in remanufacturing (idea 4);
  - every choice the run can make has been checked before;
  - a deviation is an entry in the record, not a new recipe, which is GMP's practice [iec61512part4].
- **Price:** candidates must be checked again for each unit whose values differ from the type's.
- **In the paper:** 3.5.

**M15. The record reuses IDTA 02031-2 Executed Processes, in the product's instance AAS (proposed,
D2).**
- **Instead of:**
  - records of one's own: an execution log [jensen2026service], a traceability link [alonso2024aas];
  - records outside the AAS;
  - 02027's own example 2, an AIMC in the product's shell that maps a machine's data into it
    [idtaAIMC], which would bring live data into the product's shell (against M10).
- **Why:**
  - IDTA's template has per run and per executed process what a record needs: the values as executed,
    start and end, status, result, stages and errors;
  - the record travels with the unit, as a batch record [iec61512part4] and a battery passport
    [idtaDBPCondition] do.
- **Price:** four added references (step binding, resource, skill, the logged call), because the
  template names no resource.
- **In the paper:** 3.5.

**M16. A component has a shell of its own.**
- **Instead of:**
  - all skills in the module's shell;
  - components as nodes of the module's bill of material only.
- **Why:**
  - a component of a type offers the same primitives in every module that has it (every linear axis
    offers `MoveAxis` and `Home`);
  - its skills are therefore described with it, once per type, and a module composes them;
  - J6's target is a skill in a component's shell.
- **Price:** more shells: a module with three axes has three component shells.
- **In the paper:** 3.4.

**M17. A recipe is a partial order (with the colleagues, A2).**
- **Instead of:**
  - a list of steps;
  - nested sequence and parallel blocks, which express only series-parallel orders (our own Production
    Sequence 2.0).
- **Why:**
  - a disassembly order is often not series-parallel: in our example pack, the busbars come off after
    the cover and the HV plug, the BMS after the HV plug only;
  - a product agent can call for proposals on every step that is ready, not only the next.
- **Price:**
  - a reader that knows only `Order` must still get a valid order, so `Order` must respect `After`
    (C08);
  - edges only between siblings.
- **In the paper:** 3.3 (the colleagues).

## 2. The ontologies and the checks (O)

**O1. One structure ontology per asset class, and one link ontology over them.**
- **Instead of:**
  - one ontology of the whole production system [eichenwald2024production];
  - SHACL shapes that "mainly check for mandatory properties" [bader2019semantic];
  - comparison with a reference AAS, without "dependencies between submodels and cross-references"
    [ellwein2026settheoretic];
  - the AAS Test Engines: the metamodel and, so far, two templates [otto2025test].
- **Why:**
  - a vendor checks a module's shell without loading the product's ontology;
  - relations between classes live in one place (PPRL);
  - the concepts are CSS's, not ours [koecher2023reference].
- **Price:** three structure ontologies and a link ontology to keep in step with the templates. Two of
  the structure ontologies (APSO, APrSO) still have to be remade from the templates as built (D7).
- **In the paper:** 3.2.

**O2. Constraints in SHACL, closed world; concepts in OWL, open world.**
- **Instead of:**
  - matching and checking by OWL reasoning, which needs closing axioms [koecher2023reference];
  - checks as code in each tool.
- **Why:**
  - a shell is a closed document, and SHACL is the W3C standard for checking closed data;
  - its shapes are generated from the OWL restrictions;
  - SPARQL constraints follow references across shells;
  - OWL stays for what it does well: the candidate relations as property chains.
- **Price:**
  - the projection to RDF must follow every template version;
  - numeric comparisons (ranges, limits) live in SPARQL, not in OWL.
- **In the paper:** 3.2, 3.6.

**O3. The relations are projected from the references, never stored twice.**
- **Instead of:** individuals and relations kept in an ontology beside the AAS and synchronised with it.
- **Why:** the shells stay the only source, and the graph is rebuilt for every check.
- **Price:** the projection rules are maintained with the templates.
- **In the paper:** 3.2.

**O4. Matching by meaning and coverage: deterministic, and recorded.**
- **Instead of:**
  - OWL satisfiability of class expressions [koecher2023reference];
  - rules over a process taxonomy [jarvenpaa2018product, jarvenpaa2023semantic];
  - language models [shi2026cognitive, dasilva2026llm];
  - a matchmaking service outside the AAS [nguyen2025aas].
- **Why:**
  - the same shells always give the same verdict;
  - each finding says what does not fit and why;
  - the verdict is stored and can be recomputed (C20).
- **Price:**
  - it needs the shared vocabulary;
  - it compares values, ranges and lists of values. Geometry and other physical feasibility are not
    covered.
- **In the paper:** 3.5, 3.6.

**O5. Checks where information changes hands.**
- **What:** at registration, at binding, and at every change during a run.
- **Instead of:** checking only when a file is read (the metamodel), or finding a fault when a step
  fails.
- **Why:**
  - a fault found when a module registers costs nothing;
  - the same fault found during a batch can stop the line.
- **In the paper:** 3.6.

## 3. What the blueprints deliberately leave out (X)

| # | Left out | Where it is instead | Why |
| --- | --- | --- | --- |
| X1 | The commercial service of CSS: cost, delivery time | Out of scope, as section 2 says | No implementation examples to build on [koecher2023reference] |
| X2 | Scheduling: when a step runs | The orchestrators | A schedule changes with every order; the blueprints describe what does not |
| X3 | Transport: which shuttle carries a product | Chosen at run time; shuttles offer Transporting like modules | It depends on traffic the line engineer cannot foresee |
| X4 | Live values | Time series named in Variables (M10) | |
| X5 | The build record | The integrator's record (M11) | |
| X6 | Planning models in PDDL or HDDL | Generated from 02020 (M12) | |
| X7 | The control strategy: centralised or by agents | The orchestrators read the same shells | Plug and produce must not depend on who orchestrates (P7) |
| X8 | Diagram layouts (BPMN) | Not stored: the shell keeps the flow | A second, presentational model beside the flow |

## 4. Technologies (T): our implementation, replaceable

| # | Chosen | Instead of | Why | Replaceable by |
| --- | --- | --- | --- | --- |
| T1 | AAS (IEC 63278) with IDTA templates | AutomationML, for engineering exchange [schleipen2009threeview]; OPC UA information models; MTP for process modules [vdivde2658] | A standard digital twin over the life cycle, with a REST API, registries and templates for capabilities and interfaces [iec63278, sakurada2025tenyears]. OPC UA stays the run-time interface, described by the AID | – (the paper's premise) |
| T2 | Eclipse BaSyx: the AAS environment with Operation delegation, registries, discovery, MQTT events, the web UI [cite: basyx] | FA³ST [cite: fa3st]; the AASX Server | Operation delegation and the lab's existing stack and web UI fork | Any AAS server that delegates Operations |
| T3 | The data management platform (aas-camel-dmp, on Apache Camel) runs AID and AIMC both ways: an Operation becomes the OPC UA method's call; values become rows of InfluxDB | BaSyx DataBridge, own route files [cite: basyx-databridge]; FA³ST, own configuration for writing and operations [cite: fa3st] | The shell is the configuration of its own connection (M9) | Any runtime that executes AIMC from AAS to asset |
| T4 | IEC 61499 on Eclipse 4diac FORTE, one Raspberry Pi per module [cite: iec61499, 4diac] | IEC 61131-3 PLCs; ROS 2; PackML stations over MQTT (our predecessor, AP2030-UNS) | Distributed, event-driven control whose standard management interface creates instances and connections while the program runs, so a described skill is built online; open source; an OPC UA server built in | For the blueprints: any controller that serves the skills' commands |
| T5 | OPC UA methods for the commands; OPC UA multicast discovery (LDS-ME) [cite: opcua-part12] | OPC UA programs [dorofeev2018skill]; PackML tags over MQTT; MTP services [vdivde2658] | Each command answers at once, accepted or refused with an error; any OPC UA client calls it; a module announces itself | Any protocol the AID can describe |
| T6 | Agents: SPADE over XMPP (Prosody), VDI/VDE 2193 messages [cite: spade, vdivde2193] | JADE with FIPA-ACL; SARL agents with Kafka at the DFKI SmartFactory ([agents-literature.md](agents-literature.md)); SMIA [hurtado2025smia] | Python like the rest of the tools; XMPP gives each agent an address, presence and delivery; VDI/VDE 2193 is the I4.0 language of the AAS community. SMIA is the closest system but uses its own FIPA-ACL dialect and an OWL capability model instead of 02020 | Any agent platform |
| T7 | Centralised: a FOND policy planned from the shells, run as a behaviour tree (the colleagues) [cite: schwoerer2026fond] | BPMN engines [koecher2022bpmn, nguyen2025aas]; orchestration by a language model [li2026agentic] | Handles outcomes that are not known in advance; a behaviour tree executes and monitors | Any orchestrator that reads the shells |
| T8 | HTN with goal regression (GTPyhop) for a module's new skills; PDDL and HDDL generated for ENHSP and Aries | A flat PDDL problem over the line | Small, local domains with the integrator's methods; 1 to 2 ms per plan | Any planner (the domain is generated) |
| T9 | OWL 2 and SHACL, with rdflib and pySHACL | JSON Schema; aas-core's metamodel verification | Constraints across shells are paths in a graph | Any SHACL engine |
| T10 | Python classes generated from the templates (aas-model, aas_pydantic) | The AASX Package Explorer; hand-written JSON | Templates, classes, descriptions and examples checked together in the tests; the example shells written out in full | Any SDK |
| T11 | InfluxDB for the time series | TimescaleDB (our predecessor's); values in the AAS | The lab's stack; the series is named in IDTA 02008's terms | Any time-series database |
| T12 | Siemens Plant Simulation for the battery cell (the colleagues) | A cell simulated in FORTE, as the pharma modules are on the PC; other discrete-event tools | The REVAMP demonstrator's model exists in it; stochastic conditions; an industrial tool | Any discrete-event simulator |

## 5. A table for the paper's discussion

The main decisions, condensed for section 6. Each row is one of the entries above.

| Decision | Usual alternative | Why ours | Price |
| --- | --- | --- | --- |
| A process AAS per product and line, the master recipe (M1) | Plan in the product AAS [jungbluth2022dynamic, sakurada2025agentbased, dasilva2026modular]; negotiated at run time [stolze2024realizing] | The product's shell does not change with the line; the binding is checked before it runs | One more shell; revision tracking |
| Reuse, then extend, then add (M2) | Own submodels for what templates cover; metamodel extension [nguyen2025aas] | IDTA readers still read it; additions are measurable | Three additions to bring to IDTA |
| Links as model references, meanings as supplemental ids (M3, M4) | Names; external references; links in an ontology beside the AAS [hurtado2025smia] | Resolvable with the AAS API; matching independent of names | Stable ids; a governed vocabulary |
| Offers derived from skills (M5) | Offers written by hand | No drift between offer and implementation | Rules in the vocabulary |
| Skills as commands with interface reference, Operation and steps (M6) | Control Component templates [idtaCCType, idtaCCInstance] | Closes J2 and J6 | Not an IDTA template |
| One step format on every level (M7) | BPMN for processes, state machines for skills [koecher2022bpmn] | One checker for J4 and J6 | Block-structured flows only |
| The interface for acting: AID actions, AIMC from AAS to asset (M9) | AID for monitoring [idtaAID]; calls configured outside the AAS [cite: fa3st] | Invoked from its AAS alone | Depends on Operation delegation |
| No live values in the AAS (M10) | Properties kept current [vaz2025automated] | No write load; history; a call log | A database beside the AAS |
| Validated candidates, chosen at run time and recorded (M14) | One fixed binding; free negotiation | One structure for both domains | Checks per unit |
| The record in IDTA 02031-2 (M15) | Own execution logs [jensen2026service] | Reuse; it travels with the unit | Four added references |
| Structure ontology per class plus a link ontology, SHACL across shells (O1, O2) | Mandatory-property shapes [bader2019semantic]; metamodel tests [otto2025test]; reference comparison [ellwein2026settheoretic] | Constraints between submodels and shells | A projection to maintain |
| Matching by meaning and coverage, recorded (O4) | OWL [koecher2023reference]; language models [shi2026cognitive, dasilva2026llm] | Deterministic and explained | Needs the shared vocabulary |

## 6. How far the reviewed works close the joints

A first pass, from section 2's own text only, for the authors to check against each paper before it
is used. A cell is left as "?" where section 2 does not say.

Legend:
- ● closed by an element in the AAS;
- ◐ handled outside the AAS, or only at run time;
- ○ open;
- – not addressed.

| Work | J1 | J2 | J3 | J4 | J5 | J6 | J7 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Jungbluth et al. [jungbluth2022dynamic] | ? | ◐ OPC UA skills | ◐ agents | ? | ● plan steps refer to a module's skills | ? | – |
| Sidorenko et al. [sidorenko2023mas4ai] | ? | ◐ AID, own skills | ◐ agents | ? | ◐ agent planning | ? | – |
| Alonso et al. [alonso2024aas] | ? | ? | ◐ orchestrator | ? | ◐ process steps | ? | – |
| Strakošová et al. [strakosova2024popan, strakosova2024bipan] | – | ○ no interface | – | ○ no parameters | ◐ | – | ● network edges with directions |
| Hurtado et al. [hurtado2025smia] | ◐ ontology | ◐ AID extended | ◐ ontology | ? | ◐ negotiation | ? | – |
| Nguyen et al. [nguyen2025aas] | ? | ◐ BPMN over AAS operations | ◐ service | ? | ◐ BPMN | ? | – |
| Sakurada et al. [sakurada2025agentbased] | ? | ○ in the templates; agents invoke | ◐ negotiation | ◐ messages | ● plan in the product AAS | ○ used skills only | – |
| Shi et al. [shi2026cognitive] | ? | – | ◐ language model | ? | ◐ bill of process | ? | – |
| Li et al. [li2026agentic] | ? | ◐ delegated operations | ◐ language model | ? | ◐ language model | ? | ? (the passport's dismantling data are documents) |
| Jensen et al. [jensen2026service] | ? | ◐ AID data access | ? | ? | ◐ execution plan | ? | – |
| Da Silva et al. [dasilva2026llm] | ? | – | ◐ language model | – | – | – | – |
| Da Silva et al. [dasilva2026modular] | ? | ? | ◐ negotiation | ◐ messages | ◐ active steps | ? | – |
| Nabizada et al. [nabizada2026capability] | ? | ? | ◐ PDDL | ? | ◐ planning | ? | – |
| This paper | ● | ● | ● the criterion and the verdict | ● | ● | ● | ● with the colleagues |

*[Authors: section 2 already reads the table "by row" and "by column". This table is the same reading
per joint, and is probably the clearest single argument for RQ2. Fill in the "?" cells from the
papers, or merge the columns into Table tab:coverage.]*
