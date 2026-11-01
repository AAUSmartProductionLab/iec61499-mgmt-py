# Journal paper: what goes in

Started 28 Oct 2026, for the authors. The CIRP CMS paper ([paper-outline.md](paper-outline.md)) keeps
a narrow scope: restructuring a running module through its AAS. This file collects what goes into
the journal paper:
- the modelling of skills and capabilities;
- planning;
- orchestration with multi-agent systems, compared with a centralized orchestrator on the same line;
- what the CIRP paper had no room for.

Add to it whenever a change or a design consideration belongs here. Each consideration found while
coding goes first into [design-log.md](design-log.md), tagged *Journal*.

## Scope, as it stands

A module that describes itself:
- its skills and capabilities in the AAS (ARSO [jensen2026ontology]);
- new composite skills planned from them;
- built online in its IEC 61499 program;
- offered to a line run by either of two orchestrators: centralized (FOND policies run as behaviour
  trees [schwoerer2026fond]) or multi-agent (product agents following their recipes). Only the
  orchestration differs (31 Oct, [framework-plan.md](framework-plan.md) section 1).

The CIRP paper is the module-level mechanism. The journal paper is the models, the planning and the
line.

## Content

| Topic | What we have | Where it is written up |
| --- | --- | --- |
| **The capability model** | One IDTA 02020 Capability Description per module: offered (process) capabilities, a set per component of capabilities realized by primitives, Pre/Post/Invariant as `BasicConstraint` expressions, properties as state variables through `SameProperty`. Kind-level constraints in the vocabulary, integration constraints per module | [skill-planning.md](skill-planning.md) sections 2 to 4, DD 3.9 |
| **Why no planning submodel** | Against AAS2PDDL [nabizada2026capability], Bernhard et al. [bernhard2024leverage] and our own AI-Planning submodel [schwoerer2026fond]. Inside a module: a fixed cast, state as a few values, deletes generated. Execution constraints (occupation) are the shell's business. PDDL/HDDL generated, not modelled. Line level, with relational and uncertain outcomes, keeps a planning model of its own | [skill-planning.md](skill-planning.md) section 7, DD 3.9 |
| **The planner** | HTN with goal regression (GTPyhop): compositions, then existing composites, then generated methods; `+=` in equal doses; lifting to parallel blocks by state and invariants | [skill-planning.md](skill-planning.md) section 6 |
| **Checking and discovery** | Checker for hand-written flows (unmet preconditions with the step that fixes them; invariants broken by parallel branches); discovery of capabilities offered after a reconfiguration | [skill-planning.md](skill-planning.md) section 6; `modplan check`, `discover` |
| **Standard planners** | The same domain as numeric PDDL (ENHSP) and HDDL (Aries), validated by unified-planning; the HDDL encoding with values as objects and sums as static facts | `modplan/export.py`, [skill-planning.md](skill-planning.md) section 6 |
| **Runtime conditions** | A primitive's `Conditions` and `Completion` (ARSO 0.11), and their link to the capability constraints through shared data points | [skill-planning.md](skill-planning.md) section 5 |
| **Product, process, resource** | ISA-88 recipe levels across product, process and resource AAS; matching by meaning (supplemental ids); three ids, three jobs. Built as aas-model's types; reference models of three products (vial, syringe, cartridge) and their process AASs on the line, checked by following every binding; a capability property listing the containers a module takes | [ppr-model.md](ppr-model.md), [aas-examples.md](aas-examples.md), DD 3.5, 3.6, aas-model's `docs/lab-aas.md` |
| **Orchestration by agents** | Product and resource agents bidding for process steps (VDI/VDE 2193 over XMPP, SPADE); a product agent per unit ordered; shuttles bid for Transporting like modules, the module's binding proposal held until the product is at its station; custody (who carries a product) as capability constraints in the resources' AASs, Receiving and Releasing, so that no rule of the agents is about shuttles; a capability narrower than its steps contribute (BottomUpFilling, a Filling) declared by the skill written for it, so a product can ask for it; the module's agent creating that skill online on FORTE before it carries the step out (built 30 Oct, on the PC). Still to do: the agent planning the skill itself (A3). FOND policies [schwoerer2026fond] are, since 31 Oct, the other orchestrator of the same line (next row) | [agents.md](agents.md), [design-log.md](design-log.md) (30 Oct), `line-agents/` |
| **One line, two orchestrators** | Planned 31 Oct, with the colleagues. The same resource, product and process AASs, the same IEC 61499 modules (occupation, PackML module state, the skills' state machines) and one way of running a skill (occupy, Execute, start, wait, release), under a centralized orchestrator (FOND-AAS's policy run as a behaviour tree [schwoerer2026fond]) and a multi-agent one; occupation hands the line from one to the other | [framework-plan.md](framework-plan.md) section 1, [design-log.md](design-log.md) (31 Oct) |
| **The AAS as the configuration of its own connection** | A module's AAS is what the DMP (aas-camel-dmp) runs: an Operation invoked at the AAS server is delegated to the DMP, which calls the module's OPC UA method as the AIMC maps it and answers with the method's reply; the module's values are observed over OPC UA and written as rows of the time series the Variables name (InfluxDB), never as live values in the AAS. Generated from the module spec with the program, checked end to end against a simulated module | [design-log.md](design-log.md) (28 Oct), [tooling.md](tooling.md) section 6, `cell/tests/test_dmp_live.py` |
| **Locations** | Coordinates in Variables (aas-model's; ARSO 0.14) as a tree of transforms rooted at the table's base: mounts and end effectors following measured positions, shuttles following the controller, products re-parented at handover; the stations derived from the AASs; the first version as frames on BoM nodes, and why it was replaced | [locations-and-layout.md](locations-and-layout.md), [design-log.md](design-log.md) |

## Evaluation the CIRP paper leaves out

- **Planning against standard planners:** GTPyhop 1 to 2 ms, Aries 41 to 66 ms, ENHSP 282 to 348 ms;
  all valid (`cell/eval/planners.py`).
- **Plan quality** against the engineer's skill:
  - GTPyhop's plan equals Dispensing.
  - Aries returns by MoveAxis(0) instead of Home.
  - ENHSP weighs the empty vial first.
- **Scaling with plan size:** one probe, 1 to 20 doses. GTPyhop 2 to 4 ms, ENHSP about 0.37 s, Aries
  0.08 to 6.8 s on our HDDL encoding. Five-run medians are to do; the method is borrowed from
  [schwoerer2026fond].
- **Modelling effort** (borrowed from [nabizada2026capability], who report 77 AAS elements for one
  action):
  - Filling: 16 constraints (102 AAS elements), of which 4 are written for the module.
  - Stoppering: 9 constraints, 2 written.
  - The HDDL (9 tasks, 17 methods, 5 actions) is generated.
- **Repeatability:** successful runs out of N (borrowed from [schwoerer2026fond]).
- **The cases T1 to T14**, including discovery (T10), a missing scale (T11), a missing integration
  constraint (T12) and filling from the bottom (T13, T14).
- **Agents:** time from a product's request to a module offering a new skill.
- **The two orchestrators on one scenario** (proposed 31 Oct): the same orders and events (a module
  failing, a rush order, a module plugged in) run by both; the time to finish the orders, the reaction
  to the failure, the time until a new module is used, the work to set each up.

## Related work beyond the CIRP paper's 17

All in [paper-references.bib](paper-references.bib):
- **Skills and CSS:** pedersen2016robot, koecher2020formal, css2022, css2025, dorofeev2018skill,
  dorofeev2019agile, dorofeev2019evaluating, sidorenko2024bt, koecher2022model.
- **BPMN for skills and processes:** koecher2022bpmn models the recipe as BPMN service tasks naming
  capabilities, bound to skills when a run starts and run by Camunda outside the machines; the skill
  itself is a state machine. Ours draws both levels, a product's plan and a module's composite skill,
  in one BPMN notation, as a view of a block-structured flow: the plan is carried out by the agents,
  the skill by FORTE, with no engine; the binding is by the agents, not the user; the plan is checked
  before it runs. Drawn freely (a catalog, wiring by hand), the drawing is read back into blocks by a
  validator that names what keeps it from being well structured; only a flow is saved. The point for
  the paper: BPMN as notation and exchange format, not as executor; well-structured BPMN as the part
  that maps to our blocks.
- **Reconfiguration and services:** zoitl2006dynamic, dai2017self, klose2019orchestration (MTP).
- **Planning:** mayr2023skiros2, martin2021plansys2, bennulf2021goal, wally2019production,
  hoeller2020hddl, scala2016interval, godet2022chronicles, blair2009models,
  jarvenpaa2019development.
- **Not yet in the file:**
  - Lindorfer and Froschauer, INDIN 2019: BPMN skill workflows with meta-model rules.
  - Spitzer et al., ETFA 2020: an OPC UA skill interface for PLCs, atomic and composite skills.
  - Stolze et al., ETFA 2024: a proactive AAS through BPMN and the I4.0 language bidding.

- **Agents** (survey of 30 Oct, [agents-literature.md](agents-literature.md), BibTeX in its section 8.2,
  not yet in the bib file): SMIA (Hurtado et al., JII 2025, doi:10.1016/j.jii.2025.100915) as the
  closest system; Lepuschitz et al. (TSMC-C 2011), Zoitl et al. (ETFA 2010), Vallée et al. (TII 2011) for
  agents reconfiguring IEC 61499; Lyu and Brennan (2020, 2025) for SPADE with 4diac; Bernhard et al.
  (2023) and Jungbluth et al. (2022, 2023) for AAS agents with VDI/VDE 2193 bidding and transport; IEEE
  2660.1-2020 and Leitão et al. (OJIES 2023) for the agent-device interface; Smith (1980) for the
  contract net. The contribution against them is in [agents.md](agents.md), section 9: an agent that
  plans and creates a skill online to win a bid.

## Candidate figures (1 Nov)

Eleven pages of [figures/journal-figures.drawio](figures/journal-figures.drawio), each exported to
`paper/journal/figures/<page>.pdf`, for the authors to choose from. All are drawn 960 px wide (two
columns), with the names and values of the example line (`cell/examples`, `cell/modules`).

| Page | What it shows |
| --- | --- |
| `ppr-overview` | Product, process and resource AAS around the capability: what each holds, who keeps it, how the process AAS binds the other two, and what the three make possible |
| `submodel-references` | The vial's, its process's, the line's, the filling module's and the pump's AASs as trees, every reference between them drawn |
| `product-bom` | The three products' bills of material, each part with its quantity and the process that uses it (workpiece or incorporated) |
| `resource-bom` | The line's bill of material: modules, table and shuttles, components, each with its own AAS |
| `skill-hierarchy` | Per module: the offered capability, the composite realizing it, its steps, the primitives per component, the capability each realizes and its constraints (the vocabulary's and the module's) |
| `ppr-map` | The vial's parts, its recipe, required against offered capability, skill, module and components, column by column; each column a binding of the process AAS |
| `capability-match` | The filling module's offer against the three products, property by property, and an ampoule the container type excludes |
| `isa88-levels` | ISA-88's recipes, procedural elements and equipment against the AASs and skills |
| `bpmn-levels` | Recipe, process on the line (a lane per resource) and Dispensing opened (a lane per component) as three BPMN pools |
| `bpmn-integration` | A module plugged in and a new product as one BPMN process, a lane per tool, with the AASs each task reads and writes |
| `model-use` | Which activity reads and writes which submodel |

The page `product-to-process` of [figures/cirp-figures.drawio](figures/cirp-figures.drawio) (one column)
fits here as well.

## Open questions for the journal paper

- **The comparison's place:** the centralized orchestrator is the colleagues' work (FOND-AAS, the BT
  controller); whether the comparison is this paper's or a joint one.
- **Taring:** the plan tares after dispensing from an untared start
  ([skill-planning.md](skill-planning.md) section 9).
- **Composites of composites:** inlined today; whether to keep them as calls.
- **A discovered offer's range under `+=`:** it needs the container's capacity.
- **Decisions in planned skills:** "top up if light".
