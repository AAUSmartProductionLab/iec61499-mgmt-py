# Journal paper on the models: what goes in

Started on 28 Oct 2026, for the authors, and split in two on 3 Nov:
- **this file:** the models' journal paper;
- **[orchestration-paper.md](orchestration-paper.md):** the orchestration journal paper, with IEC 61499
  and online reconfiguration, the planners, FOND and behaviour trees, the agents, and the comparison of
  orchestrators.

The CIRP CMS paper ([paper-outline.md](paper-outline.md)) is the module-level mechanism: restructuring
a running module through its AAS.

Three files carry this paper:
- **[journal-method.md](journal-method.md):** the method as blueprints, with the joints J1 to J7 as
  relations and the constraints by scope; a draft of our parts of section 3; what to settle with the
  colleagues;
- **[journal-rationale.md](journal-rationale.md):** every design decision against the alternatives,
  and what real systems demand of the models;
- **[journal-evaluation.md](journal-evaluation.md):** the showcase, and how the two cases are built
  and evaluated, E1 to E8.

Add to it whenever a change or a design consideration belongs here. Each consideration found while
coding goes first into [design-log.md](design-log.md), tagged *Journal*.

## Scope (decided on 3 Nov)

The models:
- the product, process and resource blueprints;
- their ontologies and constraints;
- the design considerations for using them in real systems.

A small showcase around them, in a deliberately limited scope, shows that they serve:
- **plug and produce integration:** discovery, registration and the check against the blueprint;
- **planning:** matching required against offered capabilities, and binding a recipe into a process
  AAS;
- **execution:** a minimal executor that follows the process AAS through the AAS API alone.

Not in this paper, only cited: how the modules' controllers are built (IEC 61499), online
reconfiguration, the planning of new skills, the agents and the centralized orchestrator.

## Content

| Topic | What we have | Where it is written up |
| --- | --- | --- |
| **Product, process, resource** | ISA-88 recipe levels across product, process and resource AAS; matching by meaning (supplemental ids); three ids, three jobs. Built as aas-model's types; reference models of three products (vial, syringe, cartridge) and their process AASs on the line, checked by following every binding; a capability property listing the containers a module takes | [ppr-model.md](ppr-model.md), [aas-examples.md](aas-examples.md), DD 3.5, 3.6, aas-model's `docs/lab-aas.md` |
| **Skills and capabilities** | A skill as its commands, each with its interface reference, its Operation and the steps it runs; offered capabilities (IDTA 02020) derived from the skills, `CapabilityRealizedBy` a model reference to the skill. The elements for reconfiguration and planning are part of the models and counted, their use is the orchestration paper's | [aas-models.md](aas-models.md) section 2, DD 3.2 to 3.4, aas-model's `docs/lab-submodels/Skills.md` |
| **The recipe as a partial order** | The Production Sequence 4.0 (proposed): `partial` blocks with `After`, connections in the steps that make or break them, one sequence per sequence type; examples of a battery pack and the vial, built and checked | [precedence-graphs.md](precedence-graphs.md), aas-model's `docs/lab-submodels/ProductionSequence4.md` |
| **The AAS as the configuration of its own connection** | A module's AAS is what the DMP (aas-camel-dmp) runs: an Operation invoked at the AAS server is delegated to the DMP, which calls the module's OPC UA method as the AIMC maps it and answers with the method's reply; the module's values are observed over OPC UA and written as rows of the time series the Variables name (InfluxDB), never as live values in the AAS. Checked end to end against a simulated module | [design-log.md](design-log.md) (28 Oct), [tooling.md](tooling.md) section 6, `cell/tests/test_dmp_live.py` |
| **The ontologies and checks** | ARSO, APSO, AProSO (APrSO in the paper) and the link ontology PPRL with its SHACL rules; the projection from AAS JSON to RDF; `modreg check`, the plan check, the sequence check | [ontology/README.md](../ontology/README.md), [journal-method.md](journal-method.md) sections 3.2 and 3.6 |
| **Locations** | Coordinates in Variables as a tree of transforms rooted at the table's base. Probably out: not the paper's argument | [locations-and-layout.md](locations-and-layout.md) |

## What is checked today

The reference models, built and checked by following every reference
(`aas-model/scripts/export_precedence_examples.py`):
- **battery:** 7 AASs, 30 submodels, 195 references; the only ones that do not resolve point into the
  four stations not yet modelled; 20 steps run;
- **pharma:** 4 AASs, 38 references, 4 steps.

The plan for the evaluation is in [journal-evaluation.md](journal-evaluation.md).

## Related work beyond the colleagues' section 2

All in [paper-references.bib](paper-references.bib) unless said otherwise:
- **Skills and CSS:** pedersen2016robot, koecher2020formal, css2022, css2025, dorofeev2018skill,
  dorofeev2019agile, dorofeev2019evaluating, sidorenko2024bt, koecher2022model.
- **BPMN for skills and processes:** koecher2022bpmn models the recipe as BPMN service tasks naming
  capabilities, bound to skills when a run starts; the skill itself is a state machine. Ours draws
  both levels, a product's recipe and a module's composite skill, in one BPMN notation, as a view of a
  block-structured flow. The point for this paper: BPMN as notation and exchange format, not as the
  model; well-structured BPMN as the part that maps to our blocks.
- **Not yet in the file:** Lindorfer and Froschauer, INDIN 2019: BPMN skill workflows with meta-model
  rules.

## Candidate figures (1 Nov)

The pages of [figures/journal-figures.drawio](figures/journal-figures.drawio), each exported to
`paper/journal/figures/<page>.pdf`, for the authors to choose from. Most are drawn 960 px wide (two
columns), with the names and values of the example line (`cell/examples`, `cell/modules`). Since
2 Nov each figure is to become generic, with a `-battery` page (remanufacturing, simulated) and a
`-pharma` page (the example line) beside it; `submodel-references` is the first. Two new figures are
proposed in [journal-method.md](journal-method.md), section 2: `blueprints` and `ontology-layers`.

| Page | What it shows |
| --- | --- |
| `ppr-overview` | Product, process and resource AAS around the capability: what each holds, who keeps it, how the process AAS binds the other two, and what the three make possible |
| `submodel-references` | Generic, full page: product, subassembly and part AASs, the process AAS, line, module and component AASs as trees, every reference between them drawn (capability, skill, interface description, mapping configuration, variables, parameters). `-battery`: a pack remanufactured in a simulated disassembly cell; `-pharma`: the vial on the example line |
| `production-sequence` | Proposed, generic: the product's Production Sequence as a partial order (a `partial` block, `After` per step), the joints in the steps that make or break them, one sequence per archetype, the subassembly's own sequence called; the same steps as a precedence graph, the joints over the BoM. `-battery`: the pack taken apart, the modules at once, a decision on state of health; `-pharma`: the vial, a chain. Described in [precedence-graphs.md](precedence-graphs.md) |
| `product-bom` | The three products' bills of material, each part with its quantity and the process that uses it (workpiece or incorporated) |
| `resource-bom` | The line's bill of material: modules, table and shuttles, components, each with its own AAS |
| `skill-hierarchy` | Per module: the offered capability, the composite realizing it, its steps, the primitives per component, the capability each realizes and its constraints (the vocabulary's and the module's) |
| `ppr-map` | The vial's parts, its recipe, required against offered capability, skill, module and components, column by column; each column a binding of the process AAS |
| `capability-match` | The filling module's offer against the three products, property by property, and an ampoule the container type excludes |
| `isa88-levels` | ISA-88's recipes, procedural elements and equipment against the AASs and skills |
| `bpmn-levels` | Recipe, process on the line (a lane per resource) and Dispensing opened (a lane per component) as three BPMN pools |
| `bpmn-integration` | A module plugged in and a new product as one BPMN process, a lane per tool, with the AASs each task reads and writes |
| `model-use` | Which activity reads and writes which submodel |

## Open questions

- **What to settle with the colleagues, and what to decide among us:** [journal-method.md](journal-method.md),
  sections 5 and 6.
- **Composites of composites:** inlined today; whether a composite's step may call another composite.
