# aas-model

<span class="pillar aas">AAS</span> The lab's shared AAS model in Python (pydantic): the types every
product, process and resource AAS of the lab is an instance of, their submodels, and the generator
that makes the classes from submodel templates.

<figure markdown="span">
  [![The product, process and resource AAS types side by side with their submodels, and below the five
  steps from a template to a published AAS](../figures/aas-model.png)](../figures/aas-model.png)
  <figcaption>The three types and their submodels (top), and how a type is made and used (bottom):
  templates, aas-model's generator, the classes, a profile, the AAS.</figcaption>
</figure>

## The types

| Type | Asset kind and type | Submodels |
| --- | --- | --- |
| `Product` | Type, `.../Product` | Nameplate, Hierarchical Structures (the bill of material), Process Parameters (IDTA 02031), Capability Description (required), Production Sequence (the recipe) |
| `Process` | Type, `.../Process` | Process Information, Bindings, Validation |
| `Module` | Instance, `.../Resource/Module` | Nameplate, Hierarchical Structures (its components), Asset Interfaces Description (one OPC UA server), Asset Interfaces Mapping Configuration, Skills, Capability Description (offered), Variables |
| `Component` | Instance, `.../Resource/Component/<Kind>` | Skills: its primitives, which its module carries out |
| `ProductionSystem` | Instance, `.../Resource/System` | Hierarchical Structures (its modules); Variables with the coordinates |

`Module`, `Component` and `ProductionSystem` are aas-model's `Resource` with the resource ontology's
submodels added (decided 19 October 2026: the lab's modules are resources in the
product-process-resource sense). A submodel a kind does not have is left out.

What the lab changed in the IDTA templates:

- **Capability Description (IDTA 02020):** a capability is realized by a skill of the same AAS or a
  component's (a model reference), a property is the module's variable it is (`SameAs`), a
  constraint is an expression (`BasicConstraint`).
- **Asset Interfaces Description:** OPC UA, with aas-model's own actions and events.
- **Skills, Parameters:** ARSO's own submodels, which have no IDTA template; their templates are
  generated from the ontology.

## From a template to an AAS

1. **Templates** (JSON): IDTA's, the lab's and ARSO's, with semanticIds, idShorts and cardinalities.
2. **Generator** (`scripts/lab_generate.py`): pydantic classes from each template.
3. **Classes**: `aas_model.submodel_templates.*` and the types above.
4. **Profile**: an AAS as the pydantic dump of its type, without what the type says anyway. A vendor
   writes it, or a tool makes it (`modreg profile` from a module spec).
5. **AAS**: built from the profile by the [registration service](../integration/registration.md),
   checked against the [ontologies](ontologies.md), published to the AAS server.

ARSO's own templates are generated from the ontology into aas-model, so the ontology, the templates
and the classes cannot drift apart:

```powershell
git submodule update --init aas-model           # the checkout (not --recursive)
python -m modreg generate --ontology ontology/ARSO
```

A test fails when the committed templates no longer match the ontology.

## Where it is

- The submodule `aas-model/` and the `registration` extra of the Python project follow the user's
  fork (`MartinJensen37/aas-model`, branch `lab-ppr-models`) until its pull request to
  [aas-model](https://github.com/tristan-schwoerer/aas-model) is merged; a test checks that both point
  at the same commit.
- Its own documentation: `docs/lab-aas.md` (the lab's types) and `docs/lab-submodels/` (a page per
  submodel) in aas-model.
- aas-model loads the MQTT message schemas from the lab's GitHub pages when it is imported, unless
  `MQTT_SCHEMAS_DIR` names a local copy.

```powershell
python -m pip install -e ".[registration]"      # aas-model, the BaSyx SDK, rdflib
python -m modreg profile filling --target pi    # profiles/: the filling module's and its components'
python -m modreg build profiles/FillingModuleAAS.json   # aas/: the AAS the profile describes
```
