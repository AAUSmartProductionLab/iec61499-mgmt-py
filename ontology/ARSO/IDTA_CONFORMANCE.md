# ARSO vs. IDTA submodel templates

Comparison of the ARSO ontology against the IDTA submodel templates and PDFs in
`Generation/Context_Builder/context/submodels/SMTs/`. Cardinalities quoted from
the templates are the `SMT/Cardinality` qualifiers carried in the template JSON.

Scope: ARSO only (ARSO_AAS.ttl + Modules/), with its AAS v3.1 and CSS imports.
APSO is out of scope.

Written in the AAS generation project (ARSO_Ontology_AAS_Generation) and copied here with the
ontology. Its builder, converter (`aas_to_rdf.py`), `semantic_ids.py`, the UI's `semanticIds.ts`,
the SHACL files `arso-rules.shacl.ttl` and `shapes.generated.shacl.ttl` and the templates above
are that project's, not this repository's; its pushed ARSO is 0.7 (0.8 in a working copy), this
folder's 0.14.
Here the AASs are built and checked by `modreg` (`modreg check`), which the notes below mark where
it differs. Counts as of 31 Oct (named classes and `arso:semanticId` values per file).

## Coverage

| ARSO module | IDTA source | Classes | `arso:semanticId` | Status |
| --- | --- | --- | --- | --- |
| `nameplate.ttl` | 02006-3-0 | 35 | 40 | Complete |
| `hierarchical-structures.ttl` | 02011-1-1 | 9 | 8 | Complete |
| `aid.ttl` | 02017-1-1 | 49 | 40 (was 4) | Filled in; AID 1.2 and aas-model's action extension since 19 Oct |
| `capabilities.ttl` | 02020 | 28 | 30 (was 5) | Filled in; constraints since 0.11 |
| `technical-data.ttl` | 02003 | 26 | 26 (was 0) | Filled in; now built |
| `aimc.ttl` | 02027 | 15 | 15 | New; built |
| `skills.ttl` (was `control-component.ttl`) | 02015 (not supplied) | 49 | 34 | ARSO's own Skills submodel; began from 02015 |
| `variables.ttl` (was `operational-data.ttl` until 0.13) | none: aas-model's Variables, with IDTA 02008 time series and IDTA 02075 frame ids inside | 17 | 17 | n/a |
| `control-configuration.ttl` | none (ARSO-specific) | 18 | 2 | Since 0.10 the schema of the integrator's record, outside the AAS |
| `parameters.ttl` | none (ARSO-specific) | 5 | 1 | n/a |

## Added to the ontology

`arso:semanticId` is multi-valued and the converter reads every value, so these
additions let an externally authored, IDTA-conformant document be typed without
changing how the pipeline's own documents are typed.

- **`aid.ttl` — 28 classes.** The submodel gained the 1/1 template id beside its
  1/0 one. Element classes gained their W3C WoT / IDTA ids (`td#title`,
  `td#hasForm`, `hypermedia#hasTarget`, the `modbus#` / `mqtt#` / OPC UA
  `WoT-Binding/` terms, and the IDTA `PropertyDefinition` / `ExternalDescriptor`
  ids).
- **`capabilities.ttl` — 20 classes**, all from
  `https://admin-shell.io/idta/CapabilityDescription/`. `CapabilitySetSMC` and
  `CapabilityContainerSMC` keep their `smartfactory.de` ids and accept both.
- **`technical-data.ttl` — 26 classes** gained their IDTA 02003 ECLASS IRDIs.
  The module previously carried no annotations at all, so nothing could be typed
  as a TechnicalData class.
- **`aimc.ttl` — new module** for IDTA 02027 (MappingConfigurations, Sources,
  Sinks). `ARSO_AAS.ttl` imports it and adds `arso:hasTechnicalDataSubmodel` /
  `arso:hasAIMCSubmodel` with at-most-one restrictions.
- **`arso-rules.shacl.ttl`** — AIMC requires AID; an AIMC `InterfaceReference`
  must resolve to an AID interface and each `Source` to an AID property.

## Where ARSO is deliberately stricter

Requirements ARSO enforces that the templates do not. These are intentional and
should stay; they are listed so the delta is visible.

1. **Nameplate address fields.** `AddressInformationSMC` requires Street,
   ZipCode, CityTown and NationalCode. IDTA 02006-3-0 ships `AddressInformation`
   as an *empty* SMC and delegates its contents to IDTA 02002, so the template
   states no inner cardinality at all.
2. **Nameplate submodel is mandatory.** `ARSO_AAS.ttl` requires exactly one
   `DigitalNameplateSubmodel` per module AAS (`arso:ResourceAAS`; a component's
   and a system's AAS at most one, since 0.7); IDTA 02006-3-0 has no
   submodel-level cardinality qualifier.
3. **HierarchicalStructures submodel is mandatory.** ARSO requires exactly one
   of a module and of a system (not of a component); the IDTA 02011-1-1
   template marks it `ZeroToOne`.
4. **At least one interface.** `AIDSubmodel` requires `some InterfaceSMC`; every
   `InterfaceTemplateFor*` in IDTA 02017-1-1 is `ZeroToMany`.
5. **Cross-submodel reference targets.** The SPARQL rules in
   `arso-rules.shacl.ttl` require Skill, Capability, Variables, Parameters
   and AIMC references to resolve inside the same AAS. No IDTA template
   expresses cross-submodel constraints. (Those rules predate ARSO 0.11, by
   which `CapabilityRealizedBy` may name a skill in a component's AAS, and
   0.13, by which a coordinate's `RelativeTo` may name one in another AAS.)
6. **Flattened Skills.** `skills.ttl` (until 26 Oct `control-component.ttl`) began from IDTA 02015 CCType
   and keeps none of its containers but `Errors`: the skills are the submodel's own elements, and an
   error is a property whose value is its code (0.9); see the design note in that file.
7. **AIMC sources are AID properties only.** IDTA 02027 lets a Source reference
   any interface element; ARSO rejects actions and events. Sinks are unchecked,
   as IDTA allows any submodel element there.

## Where ARSO is looser than the template

1. **`contentType`.** IDTA 02017-1-1 marks it `One` inside `EndpointMetadata`;
   `EndpointMetadataSMC` does not require it.
2. **No upper bounds on optional Nameplate elements.** Most are `ZeroToOne` in
   the template; ARSO adds `max 1` only for `AddressInformation`, `Markings` and
   `AssetSpecificProperties`.
3. **`CapabilityComposedOf` is `TwoToMany`** in IDTA 02020; ARSO places no
   cardinality on it.

## Open divergences

1. **`FormsSMC` uses idShort `"Forms"`; IDTA 02017-1-1 uses `forms`.** The
   builder emits `"Forms"` too, so the pipeline is self-consistent, but a
   conformant third-party AID submodel would never match. A second
   `arso:idShort` cannot fix it: the converter reads only `idshorts[0]`
   (`aas_to_rdf.py`, `_StructuralRules`), and rdflib does not order multiple
   values. The ontology and builder must change together, or the converter must
   match a set of idShorts. (In this folder `FormsSMC` takes both idShorts, and
   `modreg check` matches either; `modreg` writes `forms`.)
2. **`semantic_ids.py` still emits the `smartfactory.de` ids** for
   CapabilitySet/CapabilityContainer. IDTA 02020 defines both; ARSO accepts either.
3. **`CapabilityRealizedBy` is wrapped in an SML.** IDTA 02020 places repeated
   `CapabilityRealizedBy` RelationshipElements directly under
   `CapabilityRelations`. (`modreg` writes `RealizedBy` there, as IDTA does.)
4. **`TechnicalManufacturerNameMLP` is modelled as a MultiLanguageProperty.** IDTA
   02003 and the builder both emit `ManufacturerName` as a `Property`.
5. **Legacy AID idShorts with no IDTA counterpart:** `modv_address`,
   `opc_node_id` and `MqvTopicProperty`. IDTA 02017-1-1 uses `modv_entity` /
   `modv_function` / `modv_type`, `uav_browsePath`, and carries the MQTT topic
   in `href`. `FormsAddressingShape` and the OPC UA builder both depend on
   `opc_node_id`, so this is a coordinated change.
6. **HierarchicalStructures `SameAs` is emitted as a ReferenceElement.** IDTA
   02011-1-1 models it as a RelationshipElement, and ARSO's `SameAsRelationship`
   subclasses `aas:RelationshipElement`, so the emitted node is typed with a
   class its model type contradicts.
7. **Nameplate optional elements.** The builder emits them without semanticIds
   (so ARSO never types them), emits `ManufacturerProductFamily` as a Property
   where IDTA uses an MLP, and accepts `ManufacturerArticleNumber`, which is not
   an IDTA 02006 element. It ignores the IDTA optional elements
   `ProductArticleNumberOfManufacturer`, `ManufacturerProductRoot`,
   `ManufacturerProductType`, `FirmwareVersion`, `UniqueFacilityIdentifier`,
   `CompanyLogo`, `Markings` and `AssetSpecificProperties`.
8. **Variables (until 0.13 OperationalData).** Not an IDTA template: aas-model's
   Variables, live values as Properties (their meaning a supplemental semanticId) and
   State, Measurements and Log holding IDTA 02008 time series as SMCs instead of
   submodels of their own. The Coordinates in Measurements carry IDTA 02075's frame ids
   on their six values. `modreg` writes only the time series and the coordinates, no
   live values (28 Oct). The AAS generation project's builder emits a collection per
   variable around an InterfaceReference, which ARSO no longer declares.
9. **Generated shapes are stale.** `shapes.generated.shacl.ttl` predates the
   TechnicalData annotations and the AIMC module, so their OWL restrictions
   (for example exactly one `GeneralInformation` or `MappingConfigurations`)
   are not enforced until it is regenerated. Regenerating may also surface item 8.

## Resolved

- **`technical-data.ttl` was inert** — now annotated, built, inverted and editable.
- **No AIMC module** — added with builder, parser, SHACL rules and UI.
- **HierarchicalStructures relationships** carried
  `.../HierarchicalStructures/Relationship/1/0`, which IDTA 02011 does not
  define; the builder now emits the `HasPart` / `IsPartOf` ids.
- **`SkillInterfaceRefTargetShape`** targeted `arso:CCInterfaceReferenceRef`, a
  class that does not exist, so it never fired; it now targets
  `arso:SkillInterfaceReferenceRef`.
- **`aas_to_rdf.py`** emitted `aas:Property/valueType` for a Range instead of
  `aas:Range/valueType`, failing every Range's MinCount shape.
- **UI protocol binding ids** in `semanticIds.ts` had drifted from
  `semantic_ids.py`.

## Not modelled, intentionally

- IDTA 02006-3-0's `ArbitraryProperty` / `ArbitraryMLP` / `ArbitraryFile`
  (`https://admin-shell.io/SMT/General/Arbitrary*`) are generic extension slots
  for vendor content, not real elements.
- IDTA 02003's sample gives `TechnicalPropertyAreas` children idShorts such as
  `ECLASS`, which AASd-120 forbids inside a list. The pipeline follows the
  template instead: one positional area collection holding named sections.
