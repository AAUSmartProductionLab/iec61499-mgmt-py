# Ontologies

The ontologies behind the product, process and resource AAS, and the links between them.
The conceptual picture across all layers, including what is not formalised yet, is
in [conceptual-model.md](conceptual-model.md). What the AASs hold as built is in
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
| `APSO/` | APSO 0.2 | Product AAS: BatchInformation, BoM, Requirements, Bill of Process |
| `ARSO/` | ARSO 0.5 | Resource AAS: Nameplate, Hierarchical Structures, AID, AIMC, Skills, Capabilities, Operational Data, Parameters, Technical Data, Control Configuration |
| `AProSO/` | AProSO 0.1 (new) | Process AAS: ProcessInformation, ProcessStructure (process map with flow), CapabilityBindings, Validation, Policy |
| `PPRL/` | PPRL 0.1 (new) | What lies between them: the CSS concept an AAS element describes, process decomposition and order, resource parts, required and offered capabilities and matching, skill composition, occupation, binding, parameter value flow, derived candidates, change classes |

`AAS/` and `CSS/` are unchanged copies of ontologies published by others (the AAS v3.1 RDF
ontology of the IDTA, `https://admin-shell.io/aas/3/1/`; the CSS ontology of Helmut Schmidt
University, `http://www.w3id.org/hsu-aut/css`), kept here so the imports resolve offline; their
own terms apply.

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

**ARSO 0.4 → 0.5** (`ARSO_AAS.ttl`, `Modules/control-component.ttl`, new `Modules/control-configuration.ttl`)
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
  procedure, change log), which modsync writes (as `ControlSoftware` for now).
- Resolved properties `usesSkill`, `occupies`, `realizesProperty`, `realizedBySkill`.

## Checks

The ontologies were the **design guide** only until 2 Oct 2026; since then ARSO is also the
blueprint the registration service checks every resource AAS against (`aas61499-tools/modreg`,
`modreg check <module> --ontology ontology/ARSO`) and the source of the pydantic classes of its
own submodels (`modreg generate`). ARSO stays at 0.5 with two additions for that: Value and Unit
of a parameter entry (`Modules/parameters.ttl`) and the detail properties of Control
Configuration. This folder is a working copy, in the repository for now.

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
(`modreg check <module> --ontology ontology/ARSO`); both modules break no restriction. What
still differs:

1. Elements the check reports as not described: the Web of Things terms the lab's shared model
   writes into the Asset Interfaces Description (key, type, title, observable, unit, op, input
   and output schemas, `uav_browsePath`, `uav_componentOf`), about 380 per module.
2. What ARSO names but does not declare, so the classes are hand-written in `modreg/model.py`:
   the terms of a skill's Contract, the children of a Step and of Implementation, the item types
   of Uses and Occupies.
3. A skill that is not offered has no Operation and no interface action, which ARSO asks of every
   skill; such a skill is not listed, and steps name it by an external reference.
4. Operational Data: ARSO's data point is a decimal Property, so Booleans are 0 or 1.
5. Capabilities, Technical Data and the active procedure and change log of Control
   Configuration are not written yet.
