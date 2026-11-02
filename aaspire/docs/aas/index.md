# AAS: describing products, processes and resources

<span class="pillar aas">AAS</span> Everything in AASPIRE reads and writes Asset Administration Shells.
This pillar fixes what they hold: the types every AAS is an instance of, the ontologies every AAS is
checked against, and the meaning of each element.

## Three kinds of AAS

The split follows ISA-88's recipe levels, which pharmaceutical batch production already uses:

| AAS | ISA-88 | One per | Holds | Changes when | Owner |
| --- | --- | --- | --- | --- | --- |
| **Product** | General recipe | product, and each part with a recipe of its own | What the product is and needs: bill of material, process parameters, the capabilities its steps require, the recipe. No equipment is named | the product changes | the product designer |
| **Process** | Master recipe | product and line | The recipe bound to one line: per step the resource, the skill and what each input is handed; whether it fits | the line is reconfigured | the line engineer |
| **Resource** | (equipment) | line, module, component | What it offers and how it is called, what its skills are made of, its live values and where it is | the vendor delivers it; tools change it online | the vendor |

Why the process AAS is separate from the product AAS: a reconfiguration changes the resource AASs
and at most the process AAS, never the product; one product on two lines is two process AASs and
one product AAS; and each owner has one AAS. The agents later bind the steps per order, and the
recipe stays as it is.

## How an AAS is written

An AAS is never written by hand as JSON. It is a **profile**: the pydantic dump of its type in
[aas-model](aas-model.md), without what the type fixes anyway. The registration service builds the
full AAS from the profile, checks it against the [ontologies](ontologies.md) and publishes it. There
are no description formats of the lab's own beside the AAS types.

## What a resource's AAS holds

| Submodel | Holds | Read by |
| --- | --- | --- |
| Nameplate | What the asset is (line, module, component) | the ontology check |
| Hierarchical Structures | Its parts: a line's modules, a module's components | everyone, to find the parts |
| Capability Description | What it offers, with ranges, each capability realized by a skill; a module's also holds its components' capabilities with their constraints | matching, the agents' bids, [modplan](../planning/modplan.md) |
| Skills | Each skill as its commands (Start, Stop, Abort, Reset), each an Operation whose variables are the parameters and results; a composite skill also its steps; `RuleSet` and `Deployment` | [modlink](../integration/modlink.md), [modsync](../reconfiguration/modsync.md), the Skill Editor |
| Asset Interfaces Description | The OPC UA endpoint and the browse path of every action and property | modlink, the DMP |
| Asset Interfaces Mapping Configuration | Which interface element carries which data, which action an Operation calls | modlink, the DMP |
| Variables | The state, measurements and log as time series (the values are in InfluxDB, not in the AAS); coordinates | the DMP, the agents |

The Skills submodel says **what is wanted**; with `Deployment` it says whether the running program
carries a skill out (`Built`) or the AAS only describes it (`Described`). What was built in detail,
instance by instance, is the integrator's record, kept beside the AAS.

## The parts

| Part | What | State |
| --- | --- | --- |
| [aas-model](aas-model.md) | The lab's pydantic AAS model: the types of the three AASs and their submodels, made from templates | built; the lab's types on the user's fork until its pull request is merged |
| [Ontologies](ontologies.md) | ARSO, the blueprint of the resource AAS, beside the product, process and link ontologies and the vocabulary | built (ARSO 0.14) |
| skill-model | Skills, flows and parameters as every tool reads them | today `modgen.spec` and parts of modsync and modplan; a package of its own planned |
| aas-generator | From spec sheets to a profile (an LLM pipeline with SHACL validation) | a repository of its own |

Read further: [aas-models.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/aas-models.md)
(every element, as built), [ppr-model.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/ppr-model.md)
(the model and its applications), [aas-examples.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/aas-examples.md)
(the example line's AASs with class diagrams).
