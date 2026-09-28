# AAS-driven online reconfiguration of IEC 61499 devices: build and modelling plan

Sep 25, 2026 · @Martin Jensen

## Scope and fixed decisions

The CIRP CMS 2027 paper shows that product, process and resource AAS content can drive checked, online reconfiguration of an IEC 61499 filling cell; the full paper is due 18 November 2026 (6 pages).

Working title: *Asset Administration Shell-driven online reconfiguration of IEC 61499 devices for plug-and-produce*.

| Topic | Decision | Status |
| --- | --- | --- |
| Runtime | Eclipse 4diac FORTE 3.x; skills, unit, IO and pattern FBs are compiled types pinned by type hash | Verified on FORTE (release branch, Sept 2026) |
| What changes online | Only the `PROC` subapplication: FB instances, connections, parameter values | Verified: create, connect, write, start, stop, delete inside `PROC.*` while the fixed part runs |
| When it changes | At product changeover, with the unit idle; never mid-batch | Fixed (GMP constraint) |
| AAS server | Eclipse BaSyx V2, accessed only via the standard AAS HTTP API | Fixed |
| AAS framework | Product, process and resource AAS types from the earlier PPR paper; the batch AAS is left to the journal | Fixed |
| Skill description | A skills submodel with parameters, execution states, interface, implementation and a contract | Structure open: extended Control Component or own template (Section 10) |
| Procedure | Restricted BPMN subset stored in the process AAS | Fixed |
| Change classes | Parameter, flow, structural | Fixed |
| Triggers | Product changeover, resource AAS edit, operator BPMN edit, all through one pipeline | Fixed |

Out of scope for CIRP: agents and bidding, planning from contracts, runtime contract monitoring, rebinding to other devices, multi-device orchestration. These are journal material.

## Literature: how others do it, and what we take

No prior work combines skill descriptions with requirements and effects in the AAS, product-driven procedure changes, and checked online IEC 61499 reconfiguration; we reuse most building blocks and add that combination.

### Skill description

| Work | What they do | Our decision |
| --- | --- | --- |
| IDTA 02015/02016 Control Component (2024) | Skill = `Disabled`, `Modes`, `Parameters` (Direction, Type, Values), `Errors`, `Uses`; state-machine profile and interface only per component | **Adapt**: keep this core so CC readers still work; add contract, per-skill execution, binding and implementation |
| [Vieira da Silva et al. 2023](https://arxiv.org/pdf/2307.00827) | Compare the CaSk ontology with AAS submodels; state machine not modelled in the AAS, only `Modes` and `Disabled`; property linked to skill parameter via a `realizedBy` in a `PropertyRelationShips` collection | **Adopt the idea**: that relation is not in the published 02020 v1.0 (checked), so we define it ourselves as `RealizesProperty` |
| BaSys control component (DFKI, 2019 to 2022) | Occupation, execution mode, operation mode, execution state as separate state machines; now moving into VDI/VDE 2190-2 (planned 2027) | **Adopt occupation** as an extension; cite 2190-2 as in preparation |
| [Sidorenko et al. 2021](https://www.sciencedirect.com/science/article/pii/S2351978921002249) | OPC UA model of skill execution as an I4.0-language interaction protocol for active AAS | **Journal**: relevant once agents invoke skills |
| Profanter et al. 2021; Dorofeev and Zoitl 2018 | Skills as OPC UA state machines, invoked by methods; composite skills with the same interface | **Adopt**: procedure facade with the same interface as atomic skills |
| Dorofeev et al. 2021 | Skill behaviour as IEC 61499 adapter service sequences inside the application; future work: host it in the AAS | **Replace**: behaviour and contract live in the skills submodel |
| SMIA (2025) | Capability/skill ontology plus AAS; AID reused for actions via HTTP parameters | **Similar**: confirms the AID action gap; we bind per command to AID actions |
| Huang et al. 2026 (MTP) | MTP service mapped to service-interface FBs, MTP state model to an ECC | **Compatible**: execution profile may be "MTP service"; MTP modules fit the same skills submodel |
| SkiNet (2022); Köcher formal capability and skill model | Skills with preconditions, invariants and effects; verification by Petri nets or SMT | **Adopt lightweight**: structured conditions and a forward check, no model checking |

### Procedure description and generation

| Work | What they do | Our decision |
| --- | --- | --- |
| Köcher et al. 2022 | BPMN of capabilities, bound to skills at execution time, run in Camunda outside the controller | **Adapt**: BPMN kept, but translated into the controller, not executed externally |
| Lindorfer and Froschauer 2019; Spitzer et al. 2020 | BPMN-based ADAPT workflows with rule-based validation, custom engine; FORTE listed as future work | **Adopt the validation idea**; our rules come from skill contracts |
| Wiesmayr et al. 2026 | Compares BPMN, SysML and IEC 61499 modelling; transformation to subapplications named as possibility | **Realise** this transformation |
| Dorofeev et al. 2021 | Textual sequence (sequence, parallel, repeat) generated into one basic FB | **Reject monolithic ECC**: network of pattern instances instead (no state explosion, changeable online) |
| Terzimehić et al. 2021 | Recipe plus topology to a generated IEC 61499 orchestration application; repeat counts compiled in | **Reject compiled counts**: loop counts and branch conditions are parameters |
| [Wu and Dai 2023](https://ieeexplore.ieee.org/document/10312288/) | ISA-88 procedural and physical models mapped onto IEC 61499 with MTP | **Read before writing the translation rules**; likely closest mapping precedent |
| Jhunjhunwala et al. 2023 (one-line pattern) | Recipe as a message interpreted by fixed FBs | **Alternative noted**: interpretation instead of generation; our P1/P2 changes behave like it, P3 stays structural |
| AAS capability to PDDL (2026) | Plans generated from AAS capability models, not executed | **Journal**: plans could enter our pipeline as procedures |

### Reconfiguration and AAS integration

| Work | What they do | Our decision |
| --- | --- | --- |
| [Huang et al. 2026](https://zbc.uz.zgora.pl/repozytorium/Content/96456/download/) | IEC 61499 as MTP orchestration layer; whole layer replaced online via MTP file (96 ms vs 504 ms); commands to running FBs queued | **Differ**: AAS-derived minimal delta, guard on process state, contract check (their future work) |
| Prenzel and Steinhorst 2021 | Delta to operations, dependency graph, ordered execution; state handling left to the developer | **Adopt ordering**; state handled by quiescent states at changeover |
| Lepuschitz et al. 2011 | Agent reconfigures its IEC 61499 control via management services (under 100 ms); control rejects unsafe requests | **Adopt principle**: fixed unit keeps interlocks whatever the procedure says |
| Lv, Zhang and Dai 2021 | AAS metamodel mapped to IEC 61499 models; management commands mapped to AAS API; component manager swaps pre-modelled FBs | **Differ**: template-level mapping; change derived from product and process content |
| Gampig et al. 2021; Wenger et al. 2018 | FB library for AAS access from FORTE; PLC reads its configuration from the AAS | **Optional**: pull design for parameters; we push via management commands |
| Terzimehić et al. 2018 | Deployment configurations stored in the AAS; runtime type library as constraint | **Adopt**: type library check against `types.json` and record in the AAS |
| [Justmann et al. 2024](https://ieeexplore.ieee.org/document/10710837/) | OPC UA FX plus AAS plus capability/skill/service model for automated reconfiguration of real-time communication | **Journal**: multi-device communication |

Better ideas we considered and set aside for CIRP: behaviour trees instead of BPMN (less familiar to operators and MES), an interpreter FB instead of generated networks (less transparent per product), and full model checking (too heavy for a changeover check).

## Model specification: resource AAS

The resource AAS of the filling cell needs ten submodels; seven come from IDTA templates and three (Skills, Operational data, Control configuration) are ours, and only four of them are read or written during reconfiguration.

| Submodel | Template | Elements we fill | Role in reconfiguration | Our extension |
| --- | --- | --- | --- | --- |
| Digital Nameplate | IDTA 02006-3-0 | Manufacturer, product designation, serial number | Identity only | None |
| Technical Data | IDTA 02003 | Dosing volume range, accuracy, needle stroke, cycle time | Source of the physical limits that capability properties point to | None |
| Hierarchical Structures | IDTA 02011 | `EntryNode` cell, `ArcheType` OneDown, `HasPart` to units and equipment modules | Tells which unit and runtime host which skill (ISA-88 physical model) | None |
| Capability Description | IDTA 02020 v1.0 | `CapabilityContainer` per capability (LiquidDosing, Stoppering, Inspection); `PropertyContainer` with `PropertyRange` (DosingVolume 0.1 to 2.0 mL); `CapabilityRealizedBy` to the skill | **Feasibility**: product 02031 values checked against ranges; capability to skill link | None; property-to-parameter link lives on the skill side |
| **Skills** | Ours, compatible with IDTA 02015/02016 core | See Section 5 | **Core**: parameters, contract, execution states, binding, implementation; composite skill written back after each change | Contract, execution, interface, implementation, `RealizesProperty` |
| Asset Interfaces Description | IDTA 02017 v1.1 | One OPC UA interface for FORTE's facades: endpoint, properties for states, parameters and state variables | **Binding**: where each command, state and parameter is reachable | Actions per skill command (AID 1.1 leaves actions out of scope) |
| Asset Interfaces Mapping Configuration | IDTA 02027 | Source AID property to sink Operational data element | Mirrors live values into the AAS; input to the DataBridge generator | None |
| **Operational data** | Ours, following your earlier diagram | State variables (`Needle`, `VialPresent`, `Filled`, `Stoppered`, `Checked`, `DoorClosed`), unit PackML state, occupation (owner, since) | **Contract vocabulary**; shown to operators; the guard reads the same values directly over OPC UA | Occupation owner and timestamp |
| Software Nameplate | IDTA 02007 | FORTE version and build, type-library version, hash of `types.json` | Identifies the exact build the type hashes refer to | None |
| **Control configuration** | Ours | See Section 5 | **Reflection**: active procedure, deployed network hash, change log | New |

What the published templates cannot express, checked against their JSON: 02020 has no relation from a capability property to a skill parameter (only `SameProperty` and `CapabilityRealizedBy`); the Control Component skill has no execution states, binding or implementation reference; AID 1.1 has no actions; AIMC maps only towards the AAS.

Semantic IDs: IDTA template IDs for standard elements; lab IRIs under `https://smartproductionlab.aau.dk/` from your ontology for our own elements, skills, state variables and capability types. The resource AAS keeps your global asset ID pattern (`…/Resource/CPPM/DispensingSystem/…`) and uses AAS version and revision fields for model changes.

## Model specification: process AAS and product AAS

The process AAS is the master recipe for one product on one cell, versioned and approved; the product AAS only supplies values and requirements, so no procedure information is duplicated between them.

### Process AAS (one per product × cell, one AAS version per recipe version)

| Submodel | Template | Elements we fill | Role in reconfiguration |
| --- | --- | --- | --- |
| Recipe header | Ours (small) | `Status` (Draft, Approved, Retired), `ProductRef`, `ResourceRef`, `ApprovedBy`, `ApprovedAt`; version and revision in the AAS administrative information | Lets the manager find the right recipe at changeover and refuse drafts |
| **Procedure** | Ours | BPMN file, task bindings, `Assumes`, derived contract, validation report, generated artifact (see Section 5) | **Core input** to diff, check and translation |

Operator edits never change an approved version in place: `publish-procedure` stores the edited BPMN as a new draft version, the check runs, and approval switches `Status`.

### Product AAS (from your PPR framework; only the parts reconfiguration reads)

| Submodel | Template | Elements we fill | Role in reconfiguration |
| --- | --- | --- | --- |
| Process Parameters Type | IDTA 02031-1 | `Processes` → `Process`: `ProcessId`, `ProcessName`, `PlannedProcessTime`, `ProductParameters` (FillVolume in mL, DosingCycles, InspectionRequired) | **Values** bound to task parameters: parameter changes |
| Bill of processes | Ours (earlier paper) | Required processes, their order, reference to a required capability each | Feasibility: every required process realised by a skill of the target cell |
| Required capabilities | IDTA 02020 used as "required" (idShort `RequiredCapabilities` plus a qualifier) | Capability plus `PropertyRange` or value (FillVolume 1.0 mL) | Range check against the resource's provided capabilities |
| Digital Nameplate, BoM (02011) | IDTA | As in your framework | Not read during reconfiguration |

Batch information, production plan and executed processes (02031-2) stay in the batch AAS for the journal.

### How a changeover finds its models

1. The trigger names the next product; the manager reads its 02031 values and required capabilities.
2. It looks up the approved process AAS whose `ProductRef` and `ResourceRef` match (registry plus a search on the recipe header).
3. It diffs that procedure against the active one recorded in the resource's control configuration, then continues with check, translation and activation.

### Model instances for the paper

| Instance | Content |
| --- | --- |
| Products A to E | 02031 values: fill volume 0.5 or 1.0 mL, dosing cycles 1 or 2, inspection yes or no |
| Process versions | v1 fill once; v2 fill in a loop (count as parameter); v3 with inspection; v4 two steps reordered by an operator; faulty drafts for the mutation study |
| Resource | The filling cell with skills MoveDown, Dose, MoveUp, Stopper, Inspect |

## Our own submodel templates

Four templates carry everything the reconfiguration needs; elements marked CC keep the idShort and semantic ID of IDTA 02015 so Control Component readers still understand them, whichever way Section 10's decision goes.

### Skills (resource AAS)

| Element | AAS type, cardinality | Content, filling-cell example | CC |
| --- | --- | --- | --- |
| `Skill` | SMC, 1..\* | One per atomic or composite skill: `Dose` | yes |
| `Disabled` | Property bool, 1 | false | yes |
| `Kind` | Property enum, 1 | Atomic or Composite |  |
| `RealizesCapability` | ReferenceElement, 0..\* | → 02020 capability LiquidDosing |  |
| `Modes` | SMC, 1 | Production | yes |
| `Parameters/Parameter` | SMC, 0..\* | `V`: `Direction` In, `Type` LREAL | yes |
|  `Range`, `Unit` | Range, Property, 0..1 | 0.1 to 2.0, mL |  |
|  `RealizesProperty` | RelationshipElement, 0..1 | parameter → capability property DosingVolume |  |
|  `ChangeableIn` | SML of Property, 0..1 | Idle, Complete |  |
|  `Binding` | ReferenceElement, 1 | → AID property `Dose/V` |  |
| `Contract/Requires` | SML of Condition, 0..\* | `Needle = Down`, `VialPresent = true` |  |
| `Contract/Ensures` | SML of Effect, 0..\* | `Filled += V` |  |
| `Contract/Invariant` | SML of Condition, 0..\* | `DoorClosed = true` |  |
| `Contract/Occupies` | SML of ReferenceElement, 0..\* | → equipment DosingPump (02011 entity) |  |
| `Execution` | SMC, 1 | `Profile` ISA-TR88/PackML (IRI); `Commands` Start, Hold, Unhold, Stop, Reset, Abort; `QuiescentStates` Idle, Complete, Stopped, Aborted |  |
| `Errors` | SMC, 1 | Error references | yes |
| `Uses` | SMC, 1 | Composite only: references to used skills | yes |
| `Interface` | SMC, 1 | Per command → AID action; state → AID property |  |
| `Implementation` | SMC, 1 | `FBType` SK\_Dose, `TypeHash`, `InstancePath` EM\_Filler.Dose, `Runtime` reference; composite only: `DerivedFrom` → process AAS version |  |

A Condition is a small SMC: `Variable` (reference to a state variable), `Operator` (=, ≠, <, ≤, >, ≥), `Value`. An Effect has `Variable`, `Assign` (:= or +=) and either `Value` or `ValueFromParameter`. References instead of text formulas mean no parser is needed and every variable is guaranteed to exist.

### Procedure (process AAS)

| Element | AAS type, cardinality | Content |
| --- | --- | --- |
| `Model` | File, 1 | BPMN XML of the subset; `ModelHash` beside it |
| `ProfileVersion` | Property, 1 | Version of the BPMN subset profile the file conforms to |
| `TaskBindings/TaskBinding` | SMC, 1..\* | `TaskId` (BPMN id), `Skill` reference, `ParameterMappings`: skill parameter ← 02031 element, constant or expression |
| `ControlParameters` | SML, 0..\* | Loop counts and branch conditions by BPMN id, sourced like parameter mappings: these become parameter changes |
| `Assumes` | SML of Condition, 1 | Start state: `VialPresent = true`, `Needle = Up` |
| `DerivedContract` | SMC, 0..1 | Written by the checker: `Requires`, `Ensures`, `FreeParameters` |
| `Validation` | SMC, 0..1 | `Status` (Passed, Rejected, NotChecked), `CheckedAt`, `CheckedAgainst` (skill versions and type hashes), `Violations` (task, condition, actual value) |
| `Artifact` | SMC, 0..1 | `TargetRuntime`, generated network file, `NetworkHash`, `GeneratorVersion` |

### Control configuration (resource AAS)

| Element | AAS type, cardinality | Content |
| --- | --- | --- |
| `Runtimes/Runtime` | SMC, 1..\* | `Name`, management endpoint (host:61499), reference to Software Nameplate, `TypeLibrary` (file `types.json`) and its hash |
| `ActiveProcedure` | SMC, 1 | Process AAS reference and version, `NetworkHash`, `ActivatedAt`, `BootFileHash` |
| `ChangeLog/Change` | SML of SMC, 0..\* | Time, `Trigger` (ProductChangeover, ResourceEdit, OperatorEdit), from and to references, `ChangeClass` (Parameter, Flow, Structural), command count, duration in ms, `Result` (Applied, Rejected, RolledBack), `VerifiedAt` |

### State variables (resource AAS, in Operational data)

| Variable | Values | Bound to |
| --- | --- | --- |
| `Needle` | Up, Down | AID property and state-observer output of `UNIT_Observer` |
| `VialPresent` | true, false | Same pattern |
| `Filled` | real, mL | Same pattern |
| `Stoppered`, `Checked` | true, false | Same pattern |
| `DoorClosed` | true, false | Same pattern |
| `UnitState` | PackML states | Unit facade |
| `Occupation` | `Owner`, `Since` | Unit coordinator |

## Standard unit structure and skill pattern

Every unit has the same fixed structure: two unit-level state machines (PackML and occupation) govern everything and never change, atomic skills follow one standard logical description and one implementation pattern, and a composite skill is a procedure over atomic skills behind the same interface.

### Unit anatomy

| Element | Per unit | Role | Changes online |
| --- | --- | --- | --- |
| Unit PackML state machine | 1 | Governs the whole unit: start, hold, stop, abort, complete | No |
| Unit modes | 1 | Production, Maintenance, Manual (PackML unit modes) | No |
| Occupation state machine | 1 | Decides whose commands the unit accepts | No |
| Skill gates and status chain | 1 per skill | Each skill composite's gate decides whose commands it accepts (procedure while the unit runs; occupation owner outside Production); the chain through the equipment module aggregates Busy/Held/Running for the unit | With the skill |
| State observer | 1 | Owns the sensors and computes the state variables (`Needle`, `VialPresent`, …) | No |
| Atomic skills | n | One equipment function each, a composite FB (`SK_*`) that owns its actuator IO | Instances in the `EM_Filler` subapplication can be added or rewired while the unit is quiescent; types are compiled |
| Composite skill: procedure facade plus `PROC` | 1 active | Product-specific sequence of atomic skills | Only the `PROC` contents |

### The two unit state machines

**PackML** (ISA-TR88.00.02, OPC 30050) with states Stopped, Resetting, Idle, Starting, Execute, Completing, Complete, Holding, Held, Unholding, Suspending, Suspended, Unsuspending, Stopping, Aborting, Aborted, Clearing, and commands Reset, Start, Stop, Hold, Unhold, Suspend, Unsuspend, Abort, Clear.

**Occupation**, after the BaSys control-component concept: Free, Occupied (owner and since), Priority (an operator overrides the owner) and Local (manual at the machine, all remote commands refused), with commands Occupy, Release and Prioritize. Keep the names aligned with VDI/VDE 2190-2 once it appears.

| Unit state | Skill commands accepted | Parameter writes | Reconfiguration |
| --- | --- | --- | --- |
| Idle, Stopped, Complete, Aborted | Only in Maintenance or Manual mode, only from the occupation owner | Allowed where `ChangeableIn` permits | Allowed when occupation is Free; the manager occupies the unit first |
| Starting, Execute, Completing | Only from the procedure (skill `CALL` port) | Refused | Deferred until a quiescent state |
| Holding, Held, Unholding, Suspending, Suspended, Unsuspending | Unit control holds or resumes the active skills | Refused | Deferred |
| Stopping, Aborting, Clearing | Unit control drives all skills to Stopped or Aborted | Refused | Deferred |

Unit Hold, Stop and Abort propagate to every skill of the equipment module (unit control fan-out; the status chain reports back when all have settled). A skill error leads to unit Hold if recoverable and Abort if safety-relevant, as declared per error in the skills submodel.

### Atomic skills: logical description

An atomic (primitive) skill is the smallest commandable function of one piece of equipment: it starts and ends in a safe state, makes no sequencing decisions and occupies a fixed set of equipment.

Its logical description is its `Skill` entry in the skills submodel (Section 5): parameters with ranges, `Requires`, `Ensures`, `Invariant`, `Occupies`, errors and execution profile. All atomic skills use the same reduced PackML machine: Idle → Starting → Execute → Completing → Complete → Resetting → Idle, plus Holding, Held, Unholding, Stopping, Stopped, Aborting, Aborted. Quiescent states are Idle, Complete, Stopped and Aborted.

### Atomic skills: implementation pattern for every `SK_*` type

| Rule | What the implementation must do | Where the AAS describes it |
| --- | --- | --- |
| Interface | Uniform composite interface: `CALL(P1..P4)` → `DONE`/`FAILED(CallError)`, unit control and status, cell sample, status chain; OPC UA object with one method per command | `Interface`, `Parameters` |
| Start guard | On Start, evaluate `Requires` on the observer outputs; if false, raise PreconditionViolated and stay Idle | `Contract/Requires` |
| Parameter latching | Copy parameters at Start; accept writes only in `ChangeableIn` states | `Parameters` |
| Scope | Drive only its own equipment; never call another skill | `Contract/Occupies` |
| Completion | Complete when the observer confirms `Ensures`, not after a fixed time; a watchdog raises Timeout | `Contract/Ensures`, `Errors` |
| Invariant | Monitor during Execute; on violation, Abort with the documented safe reaction | `Contract/Invariant` |
| Safe states | Hold, Stop and Abort each end in a defined safe equipment state | `Execution` |
| Facade | OPC UA object per skill (state, command methods, parameters), described in the AID | `Interface` |
| Identity | Compiled type; its type hash equals the AAS value | `Implementation` |
| Conformance test | Generated from the contract: Start with `Requires` true → Complete with `Ensures` true; `Requires` false → refused; Hold, Unhold, Abort reach the right states | Whole skill entry |

The start guard is the runtime mirror of the model-based check; the skill gates and the observer's `Safe` stay independent of both.

### Composite skills

A composite skill is the procedure facade plus the `PROC` subapplication. It exposes the same interface and reduced PackML machine as an atomic skill, has `Kind` Composite, lists its atomic skills in `Uses`, and gets a derived contract after each reconfiguration.

Composition rules: atomic skills are called only through their `CALL` port; parallel branches must occupy disjoint equipment; at most K branches run in parallel; for CIRP, one level of nesting (composites of atomic skills only). The unit's Start and Complete map onto the facade's Start and Completed, so unit Execute means the procedure is running.

This is the structure that the BaSys control component and the forthcoming VDI/VDE 2190-2 aim to standardise; names follow PackML and the IDTA Control Component wherever those define one.

## IEC 61499 control structure and translation rules

Only the `PROC` subapplication changes at runtime; everything below it is compiled once, pinned by type hash, and never restarted by a reconfiguration.

### Layers on the FORTE resource

| Layer | Contents | Types | Changes online |
| --- | --- | --- | --- |
| Procedure facade | Composite skill with a stable PackML interface over OPC UA | Facade FB (skill library) | No; only its AAS description is regenerated |
| `PROC` subapplication | One pattern instance per BPMN element, named `PROC.<bpmnId>` | `P_Call`, `P_Loop`, `P_Choice`, `P_Fork`, `P_Join`, `P_Wait` | **Yes**: instances, connections, parameter values |
| Unit coordinator | Unit PackML state machine, occupation, OPC UA unit facade, **state observer** | `FC_Unit`, `FC_Occupation`, `UNIT_Facade`, `UNIT_Observer` | No |
| Atomic skills (`EM_Filler` subapplication) | Composite per skill: shared `SKILL_PackML` and `SKILL_Gate`, contract block `SL_*`, watchdog, OPC UA facade, own actuator IO; status chain | `SK_MoveDown`, `SK_Dose`, `SK_MoveUp`, `SK_Stopper`, `SK_Inspect` | Instances and chain only, while the unit is quiescent |
| Equipment and IO | IO primitives inside the skills and the observer; backend per instance: simulated, GPIO (`IX`/`QX` + `GPIOChip` on the Pi) or Modbus (simulator) | `IO_DO`, `IO_DI`, `IO_AI` | No |

### Translation rules (AAS content to IEC 61499)

| AAS content | IEC 61499 artifact | Management commands |
| --- | --- | --- |
| Skill `Implementation` (type, hash) | Existing skill FB instance in the fixed part | None; checked with `QUERY FBType` against `types.json` |
| BPMN task + `TaskBinding` | `P_Call` instance connected to the skill's `CALL`/`DONE`/`FAILED` port | `CREATE FB Type="P_Call#<hash>"`, `CREATE Connection` |
| Skill parameter mapping | `P_Call` inputs `P1`..`P4` (index from the parameter's order in the skills submodel) | `WRITE` |
| Sequence flow | Event connection between pattern instances | `CREATE Connection` |
| Exclusive gateway + condition | `P_Choice`, condition as a parameter | `CREATE FB`, `WRITE` condition |
| Parallel gateway | `P_Fork` and `P_Join`; rejected if more than K branches | `CREATE FB`, `CREATE Connection` |
| Loop (`loopCardinality`) | `P_Loop` around the body, count as a parameter | `WRITE` count |
| Timer event | `P_Wait`, duration as a parameter | `WRITE` |
| Error boundary event | Error output of `P_Call` to a handler path | `CREATE Connection` |
| Start and end events | Facade `Start` and `Completed` | Fixed wiring |

Every generated FB carries its BPMN id as an attribute, so the diff and the operator's error messages point back to BPMN elements.

### Reconfiguration cycle

1. **Trigger**: product changeover, resource AAS edit, or a new approved procedure version.
2. **Semantic diff** on the procedure's intermediate representation: *parameter* (same graph, new values), *flow* (same nodes, new edges), *structural* (nodes added or removed).
3. **Check**: parameter values against `Range` and `ChangeableIn`, then the contract forward check from `Assumes`; a failure writes the violations to `Validation` and stops.
4. **Guard**: facade and every skill touched by the old or new procedure in a quiescent state, unit unoccupied, and `Assumes` confirmed with live values read over OPC UA; the manager then occupies the unit.
5. **Apply** in dependency order: STOP affected instances, delete their connections, DELETE them; then CREATE with type hash, WRITE, CREATE connections, START.
6. **Verify**: `QUERY FB` and `QUERY Connection` must equal the expected network; release the occupation.
7. **Record**: update `ActiveProcedure` and `ChangeLog`, regenerate the composite skill's derived contract, rewrite the device boot file (fixed part plus current `PROC`).

## Software architecture

Five parts with a life outside this project become git submodules; everything specific to the filling cell or the experiments is a plain folder in the project repo `iec61499-aas-reconfig`. Until the interfaces settle, the five parts live as packages in the project repo and are split out with `git filter-repo`, keeping their history, once they are stable (at the latest after submission).

| Path | Kind | Contents | Language, licence |
| --- | --- | --- | --- |
| `ext/iec61499-skill-lib` | Submodule | PackML skill base, skill gate and status chain; unit building blocks (occupation, state observer); IO primitives; pattern FBs; procedure facade; OPC UA facades | 4diac types and exported C++, EPL-2.0 |
| `ext/iec61499-mgmt-py` | Submodule | Management-protocol client: commands, response parsing, boot files, ordered delta, type-hash checks; integration tests against a FORTE container | Python, Apache-2.0 |
| `ext/ppr-aas-templates` | Submodule | Templates Skills, Procedure, Control configuration, Recipe header, Operational data; YAML sources to AAS JSON and AASX; `ppr_aas` reader | YAML and Python (BaSyx Python SDK), CC-BY-4.0 and Apache-2.0 |
| `ext/ppr-ontology` | Submodule | IRIs for skills, state variables, capability and process types, change classes; SHACL later | Turtle, CC-BY-4.0 |
| `ext/aas61499-tools` | Submodule | The pipeline as one Python package (subpackages below) | Python, Apache-2.0 |
| `cell/control` | Folder | `SK_*` with their `SL_*` contracts, `UNIT_Observer`, 4diac system project with the fixed application | 4diac |
| `cell/models` | Folder | YAML sources of products A to E, process versions, the resource | YAML |
| `cell/sim` | Folder | `sim_filling.py`, trace oracle, shoot-through detector | Python |
| `runtime` | Folder | FORTE Dockerfile and CMake preset; CI job that queries every type and writes `types.json` | CMake, Docker |
| `deploy` | Folder | docker-compose for BaSyx, FORTE, simulator, manager; generated DataBridge configuration | YAML |
| `experiments` | Folder | Scenario runner, mutation study, timing runs, figures and tables for the paper | Python |

### Subpackages of `aas61499-tools`

| Subpackage | Responsibility |
| --- | --- |
| `bpmn` | Parse BPMN XML, check it against the subset profile |
| `ir` | Procedure intermediate representation (JSON schema), built from BPMN plus task bindings |
| `translate` | Translation rules: representation to expected FB network and boot-file fragment |
| `diff` | Semantic diff of two representations and change classification |
| `contracts` | Forward check, derived contract, violation report, mutation generator |
| `deploy` | Delta from the expected networks, ordered application, verification, boot-file rewrite (uses `iec61499-mgmt-py`) |
| `aas_client` | Standard AAS HTTP API (Part 2) only, so BaSyx stays swappable |
| `events` | MQTT subscriber turning BaSyx repository events into triggers |
| `bridge` | AID and AIMC to DataBridge configuration |
| `manager` | The cycle of Section 6 and the CLI: `changeover`, `publish-procedure`, `verify`, `status` |

### Interfaces between repositories

1. **`types.json`** from `runtime`: the types, hashes and interfaces that really exist in the FORTE build.
2. **Submodel templates plus `ppr_aas`**: no tool parses AAS JSON itself.
3. **Procedure representation schema** in `aas61499-tools/ir`: the checker and the diff see only this, never BPMN.

### BaSyx deployment

| Container | Configuration |
| --- | --- |
| AAS Environment | Loads AASX from `cell/models` output; MQTT events on; MongoDB backend; operation delegation for `Reconfigure` and `PublishProcedure` to the manager |
| AAS registry and submodel registry | Lookup of product, process and resource AAS |
| MongoDB, Mosquitto | Persistence and event broker |
| DataBridge | Generated configuration: FORTE OPC UA facades to Operational data |
| AAS Web UI | Operators view state and trigger operations |
| FORTE, simulator, manager | FORTE from `runtime`, the fixed application from its boot file |

## Build plan

Nine work packages fit the 7½ weeks to the full-paper deadline on Nov 18, 2026; the critical path is runtime → skill library → cell control → translator → manager → experiments.

| WP | Weeks (2026) | Deliverable | Acceptance test |
| --- | --- | --- | --- |
| 1 Repos and runtime | 28 Sep to 2 Oct | Repos, CI, FORTE container with one custom FB, `types.json` job | `QUERY FBType` lists the custom type with its hash; the live tests pass against the build |
| 2 Skill library | 28 Sep to 9 Oct | Adapters, PackML skill base, pattern FBs, procedure facade | Each pattern FB driven through its events by the mgmt client gives the expected outputs |
| 3 Cell control | 5 to 16 Oct | `SK_*`, `UNIT_Observer`, unit and occupation state machines, OPC UA facades; hand-built `PROC` | Simulator trace equals the expected coil sequence; no shoot-through; fill once → fill twice rewired online; a skill added to `EM_Filler` online |
| 4 Models | 12 to 23 Oct | Templates as YAML, `ppr_aas` reader, instances, BaSyx running, AID and AIMC, DataBridge generator | All AAS load into BaSyx; reader round-trips; live state variables visible in the Web UI |
| 5 Translator and diff | 19 to 30 Oct | BPMN subset profile, parser, representation, translation rules, network and boot-file output, diff | Generated networks for v1 to v3 deploy and behave like the hand-built ones; the four versions are classified correctly |
| 6 Contracts | 26 Oct to 6 Nov | Forward check, derived contract, mutation generator | Valid versions pass; each faulty draft is rejected with the right task and condition |
| 7 Manager | 2 to 6 Nov | Full cycle with guard, occupation, verification, record, boot file; triggers from MQTT, CLI and operation delegation | Every scenario runs from AAS edits alone; the AAS record equals `QUERY` after each change; a restart restores the active procedure |
| 8 Experiments | 9 to 13 Nov | Scenario runs (30 each), mutation study, analytic network-size table | Tables and figures generated by `experiments/` from a clean checkout |
| 9 Writing | Method from 26 Oct; results 9 to 18 Nov | Six-page paper | Submitted; project repo tagged `cirp-cms-2027-submission` |

If WP6 slips, the paper shows three or four illustrative rejected edits instead of the mutation study; nothing else depends on it.

## Evaluation plan

The evaluation measures four things only this approach can show (disturbance-free activation, checked edits, AAS–runtime consistency, linear network size) and deliberately leaves out effort against manual reprogramming, Dorofeev's evaluation.

### Scenarios

| Scenario | Trigger | Expected class | Expected result |
| --- | --- | --- | --- |
| Product A → B: fill volume 0.5 → 1.0 mL | Product changeover | Parameter | `WRITE` only |
| Product B → C: dosing cycles 1 → 2 | Product changeover | Parameter (loop count) | `WRITE` only |
| Product C → D: inspection required | Product changeover | Structural | Instances and connections added |
| Recipe v3 → v4: two steps reordered | Operator BPMN edit | Flow | Connections only |
| Dose range narrowed to 0.1 to 0.8 mL | Resource AAS edit | Rejection of product B | No deployment; violation recorded |
| Dose before MoveDown; MoveUp deleted | Operator BPMN edit | Rejected | No deployment; task and condition named |

### Metrics and baselines

| Metric | How measured | Baseline |
| --- | --- | --- |
| Activation time | Trigger to running, 30 runs per scenario, median and spread; localhost and, if available, controller hardware reported separately | Full redeployment of the resource (what the 4diac IDE does) |
| Management commands | Count per scenario and change class | Full redeployment |
| Disturbance of the fixed part | Skill and unit state traces, instance identity before and after, simulator trace | Full redeployment restarts all instances |
| Fault detection | Mutation study: every single edit of v3 (swap neighbours, delete, duplicate, insert a skill); contract verdict vs simulator outcome; precision and recall | Structure-only check (types and connections valid) |
| Consistency | `QUERY FB` and `QUERY Connection` equal the AAS record after each change and after a restart | None needed; target 100% |

### Analytic comparison (no experiment needed)

| Parallel skills n | Monolithic ECC states / transitions (Dorofeev 2021) | Pattern network instances / event connections |
| --- | --- | --- |
| 2 | 4 / 4 | 4 / 6 |
| 4 | 16 / 32 | 6 / 10 |
| 8 | 256 / 1024 | 10 / 18 |

The network column assumes n-way fork and join pattern FBs; with 2-input primitives the growth is still linear.

## Open decisions and risks

Six decisions need settling before WP4 and WP5 start, the two early technical risks (runtime adapter connections, empty type hashes) are closed.

### Decisions

| Decision | Options | Recommendation | Decide by |
| --- | --- | --- | --- |
| Skills submodel form | Extend IDTA 02015 in place, or own template with a CC-compatible core | Own template, CC core kept, so the paper can present it as one coherent model | Start of WP4 (12 Oct) |
| Parameter passing in `P_Call` | Fixed vector `P1`..`P4` (LREAL), or typed inputs per skill | Fixed vector for CIRP; index taken from parameter order in the skills submodel | WP2 |
| Parameter delivery | Push via management `WRITE`, or pull from the AAS with the FORTE AAS FB library | Push: fewer moving parts, and the change log sees every value | WP2 |
| AID actions | Own extension per OPC 10101, or a CC interface-profile supplement | Agree with your colleague; one extension used everywhere | WP4 |
| Composite skill reflection in CIRP | One sentence, or its own subsection | One sentence; full treatment in the journal | WP9 |
| Translation-rule precedents | Write rules now, or first read Wu and Dai 2023 and Zhu et al. 2023 (ISA-88 to IEC 61499) | Read both first; they are the closest mappings | Before WP5 |

### Risks

| Risk | Early signal | Fallback |
| --- | --- | --- |
| Adapter connections cannot be created or deleted at runtime as needed | Closed | No adapters: `P_Call` is wired to the skill's `CALL`/`DONE`/`FAILED` port with event and data connections |
| Custom types exported from the IDE lack type hashes in FORTE 3.x | Closed | FORTE 3.2 reports `v2:SHA3-512` hashes for every custom type and refuses CREATE with a wrong hash |
| State variables too coarse or too fine | Mutation study shows missed faults or heavy modelling | Report the trade-off as a finding; keep six variables |
| DataBridge needs a lot of generator work | WP4 slips | Manager reads OPC UA directly; DataBridge only for display, or dropped |
| Localhost timings questioned | Reviewers compare with Huang's 96 ms | Report localhost and hardware separately; stress commands and disturbance, not raw time |
| Reviewers see overlap with Huang or Dorofeev | Related-work draft reads as incremental | Lead with the checked, AAS-derived delta and the untouched fixed part; one sentence per prior work on what it lacks |
| Seven and a half weeks is tight | WP3 not done by 16 Oct | Drop the mutation study (WP6 fallback), keep the scenarios |
