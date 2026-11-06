# Ontologies

<span class="pillar aas">AAS</span> The ontologies behind the product, process and resource AASs and
the links between them, with the vocabulary that says what each AAS element means. ARSO, the
resource ontology, is the blueprint every resource AAS is checked against.

<figure markdown="span">
  [![PPRL on top linking APSO, AProSO and ARSO, which build on the AAS v3.1 ontology; CSS beside PPRL;
  the vocabulary below; on the right what uses them](../figures/ontologies.png)](../figures/ontologies.png)
  <figcaption>One blueprint per AAS type, each checkable on its own; PPRL holds what lies between them;
  the vocabulary gives meanings. The registration service, the class generator and the planner use them.</figcaption>
</figure>

## The ontologies

| Folder | Ontology | Describes |
| --- | --- | --- |
| `ARSO/` | ARSO 0.14 | The resource AAS of a line, a module and a component: Nameplate, Hierarchical Structures, AID, AIMC, Skills, capabilities, Variables. **Authoritative**: the code follows it, not the other way round |
| `APSO/` | APSO 0.2 | The product AAS (to be brought to aas-model's `Product`) |
| `AProSO/` | AProSO 0.1 | The process AAS (to be brought to aas-model's `Process`) |
| `PPRL/` | PPRL 0.2 | What lies between them: a step requires a capability a resource offers, matching, skill composition, bindings |
| `Vocabulary/` | the lab's vocabulary 0.9 | What the AASs' elements mean (their supplemental semantic ids): capabilities, process and auxiliary, and what each kind needs and does; what each is a kind of in DIN 8580 or VDI 2860 |
| `AAS/` | AAS v3.1 | The AAS metamodel as RDF (IDTA's, unchanged) |
| `CSS/` | CSS 2.0.2 | Capabilities, skills and services (Plattform Industrie 4.0; Helmut Schmidt University) |
| `VDI2860/`, `DIN8580/` | VDI 2860 2.0.0, DIN 8580 2.0.0 | The standards' taxonomies of handling functions and of manufacturing processes (Helmut Schmidt University, unchanged) |

**Why a link ontology.** The relations that matter for reconfiguration run between AAS types: a step
of the process requires a capability from the product that a resource offers. Put into APSO or ARSO,
each would import the others, and a product AAS could no longer be checked without the resource
blueprint. So the three stay structural, and PPRL imports all three with CSS.

## How they are used

- **Checking** (`modreg check`, and the registration service on every registration): an AAS as RDF
  against ARSO's shapes, closed: what the ontology does not describe is a finding. A broken restriction
  refuses the registration; `--strict` refuses what is not described too.
- **Generating** (`modreg generate`): ARSO's own submodels as templates, and aas-model's classes from
  them ([aas-model](aas-model.md)).
- **Planning and matching**: the vocabulary says what a kind of capability does to a product, so a
  skill can be [planned](../planning/modplan.md) and a step matched to a resource.

```powershell
python -m modreg check profiles/FillingModuleAAS.json --ontology ontology/ARSO
python -m modreg generate --ontology ontology/ARSO
```

ARSO may be extended for new building blocks and for what a skill's contract, steps and
implementation hold; changes are made with the lab, not to fit the code. After the split the folder
becomes the `ontologies` repository, a Python package with the Turtle files as data.

Read further: the folder's own [README](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/ontology/README.md),
and [ppr-model.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/ppr-model.md), sections 3 and 4.
