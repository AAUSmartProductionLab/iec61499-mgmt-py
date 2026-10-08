# The example line: its AASs

Five AASs built to the framework: four resources (filling, stoppering, capping, inspection) and
one product planned on them (a 2 mL vial). Each product's plan is followed into the resources when
they are built; a plan that does not fit is refused. What the submodels are and how they link is
in [aas-models.md](aas-models.md).

This file is written by `python cell/examples/describe.py`. Every AAS is built by `modreg` from a
profile, the pydantic dump of its type: a resource's profile is made from its module spec
(`cell/modules`, `cell/modules/planned`), a product's profile is a file (`cell/examples/Vial2mLAAS.json`).
`python cell/examples/example_line.py --out <folder> --publish <server>` builds the AASs and puts
them on an AAS server.

| AAS | Kind | Submodels |
| --- | --- | --- |
| `FillingModuleAAS` | resource | Nameplate, HierarchicalStructures, AssetInterfacesDescription, Skills, OperationalData, AssetInterfacesMappingConfiguration, ControlConfiguration, CapabilityDescription |
| `StopperingModuleAAS` | resource | Nameplate, HierarchicalStructures, AssetInterfacesDescription, Skills, OperationalData, AssetInterfacesMappingConfiguration, ControlConfiguration, CapabilityDescription |
| `CappingModuleAAS` | resource | Nameplate, HierarchicalStructures, AssetInterfacesDescription, Skills, OperationalData, AssetInterfacesMappingConfiguration, ControlConfiguration, CapabilityDescription |
| `InspectionModuleAAS` | resource | Nameplate, HierarchicalStructures, AssetInterfacesDescription, Skills, OperationalData, AssetInterfacesMappingConfiguration, ControlConfiguration, CapabilityDescription |
| `Vial2mLAAS` | product | Nameplate, HierarchicalStructures, ProcessParameters, CapabilityDescription, ProductionSequence |

## Class diagram: a resource AAS

All four resources have this structure. First what the AAS holds: its submodels and their main
elements.

```mermaid
classDiagram
  direction LR
  class ResourceAAS {
    id, idShort
    globalAssetId
    derivedFrom resource template
  }
  class Nameplate {
    <<IDTA 02006>>
    ManufacturerName
    ManufacturerProductDesignation
    AddressInformation
  }
  class HierarchicalStructures {
    <<IDTA 02011>>
    ArcheType = OneDown
  }
  class Equipment {
    <<Entity>>
    idShort
    description
  }
  class AssetInterfacesDescription {
    <<IDTA 02017>>
  }
  class Interface {
    title
    EndpointMetadata base, security
  }
  class Action {
    title, synchronous
    input, output
    forms href, browse path
    command id: supplemental
  }
  class InterfaceProperty {
    key, title, type, unit
    observable
    forms href, browse path
  }
  class MappingConfiguration {
    <<IDTA 02027>>
  }
  class Mapping {
    Sources, Sinks
    Transformation
  }
  class CapabilityDescription {
    <<IDTA 02020>>
  }
  class Capability {
    meaning: supplemental id
    role = Offered
  }
  class CapabilityProperty {
    Value or Range
    unit
    meaning: supplemental id
  }
  class Skills {
    <<ARSO>>
    Interfaces
    Errors with ErrorCode
  }
  class Skill {
    SemanticId
    Kind = Primitive or Composite
    Operation per command
  }
  class SkillParameter {
    value: deployed
    Unit, Minimum, Maximum, Default
  }
  class Contract {
    Requires
    Ensures or After
    Invariant, Timeout
  }
  class Step {
    InstancePath
    Bindings constant or reference
  }
  class BuildingBlock {
    SemanticId
    Kind = Primitive
    Parameters, Contract
  }
  class Implementation {
    FBType
    TypeHash
    InstancePath
  }
  class ModuleCommands {
    Operation per command
    Methods
    StateReference, OccupiedReference
  }
  class Procedure {
    name Resetting or Stopping
  }
  class OperationalData {
    <<ARSO>>
  }
  class DataPoint {
    value decimal
    meaning: semantic id
  }
  class ControlConfiguration {
    <<ARSO>>
    Rules
    ModuleSpec, Target, Generator
    ProgramDigest
    SyncState, Differences
  }
  class Runtime {
    Name
    ManagementEndpoint
    Resource
  }
  class BlockType {
    Name
    Hash
  }

  ResourceAAS *-- Nameplate
  ResourceAAS *-- HierarchicalStructures
  ResourceAAS *-- AssetInterfacesDescription
  ResourceAAS *-- MappingConfiguration
  ResourceAAS *-- CapabilityDescription
  ResourceAAS *-- Skills
  ResourceAAS *-- OperationalData
  ResourceAAS *-- ControlConfiguration
  HierarchicalStructures *-- "0..*" Equipment
  AssetInterfacesDescription *-- "1" Interface
  Interface *-- "0..*" Action
  Interface *-- "0..*" InterfaceProperty
  MappingConfiguration *-- "1..*" Mapping
  CapabilityDescription *-- "1..*" Capability
  Capability *-- "0..*" CapabilityProperty
  Skills *-- "0..*" Skill
  Skills *-- "0..*" BuildingBlock
  Skills *-- "0..1" ModuleCommands
  Skills *-- "0..*" Procedure
  Skill *-- "0..*" SkillParameter
  Skill *-- "0..1" Contract
  Skill *-- "0..*" Step : Execute, Stop
  Skill *-- "0..1" Implementation
  BuildingBlock *-- "1" Implementation
  Procedure *-- "1..*" Step
  OperationalData *-- "1..*" DataPoint
  ControlConfiguration *-- "0..1" Runtime
  ControlConfiguration *-- "0..*" BlockType

```

Then how those elements refer to each other. Every arrow is a reference stored in the AAS, named
like the element that carries it.

```mermaid
classDiagram
  direction LR
  class Capability
  class CapabilityProperty
  class Skill
  class SkillParameter
  class Step
  class BuildingBlock
  class ModuleCommands
  class Action
  class InterfaceProperty
  class Equipment
  class Mapping
  class DataPoint

  Capability --> Skill : RealizedBy
  SkillParameter --> CapabilityProperty : RealizesProperty
  Skill --> Action : InterfaceReference, Methods
  Skill --> InterfaceProperty : State, Error, Results
  Skill --> Equipment : Occupies
  Skill --> Skill : Uses
  Skill --> BuildingBlock : Uses
  Step --> Skill : Skill
  Step --> BuildingBlock : Skill
  Step --> SkillParameter : Bindings (handed down)
  Step --> InterfaceProperty : StateReference
  ModuleCommands --> Action : Methods
  Mapping --> InterfaceProperty : Source
  Mapping --> DataPoint : Sink
  Mapping --> Skill : Source (its Operation)
  Mapping --> Action : Sink
```

## Class diagram: a product AAS

The classes marked as another AAS are in the resource AAS above; the dashed arrows are links that
are followed by meaning or by name, not by a stored reference.

```mermaid
classDiagram
  direction LR
  class ProductAAS {
    id, idShort
    globalAssetId
    assetKind = Type
  }
  class Nameplate {
    <<IDTA 02006>>
    ManufacturerProductDesignation
  }
  class HierarchicalStructures {
    <<IDTA 02011>>
    ArcheType = OneDown
  }
  class Part {
    <<Entity>>
    Quantity
    QuantityUnit
  }
  class ProcessParameters {
    <<IDTA 02031>>
  }
  class Process {
    ProcessId, ProcessName
    ProcessDescription
    PlannedProcessTime
    ProcessParameters
    ResourceParameters
  }
  class MaterialUse {
    <<lab extension>>
    Role
    Quantity, Unit
  }
  class ProductParameter {
    value, unit
    meaning: semantic id
  }
  class CapabilityDescription {
    <<IDTA 02020>>
  }
  class RequiredCapability {
    meaning: supplemental id
    role = Required
  }
  class RequiredProperty {
    Value, unit
    meaning: supplemental id
  }
  class ProductionSequence {
    <<planner template 2.0>>
    PlanSchema, Revision
    SequenceId, Name, Role
    Subject
  }
  class Step {
    NodeId, Kind, Name, Order
    SkillId
    ExecutionMode
  }
  class Binding {
    Name: skill parameter
    Value: constant if no source
  }
  class ResourceAAS {
    <<another AAS>>
  }
  class Skill {
    <<in the resource AAS>>
  }
  class SkillParameter {
    <<in the resource AAS>>
  }
  class OfferedCapability {
    <<in the resource AAS>>
  }

  ProductAAS *-- Nameplate
  ProductAAS *-- HierarchicalStructures
  ProductAAS *-- ProcessParameters
  ProductAAS *-- CapabilityDescription
  ProductAAS *-- ProductionSequence
  HierarchicalStructures *-- "0..*" Part
  ProcessParameters *-- "1..*" Process
  Process *-- "0..*" ProductParameter : ProductParameters
  Process *-- "0..*" MaterialUse : ProcessBoM
  CapabilityDescription *-- "0..*" RequiredCapability
  RequiredCapability *-- "0..*" RequiredProperty
  ProductionSequence *-- "0..*" Step
  Step *-- "0..*" Binding

  MaterialUse --> Part : MaterialReference
  MaterialUse --> ProductParameter : QuantityParameterReference
  Process --> RequiredCapability : RequiredCapability
  Step --> Process : ProcessReference
  Step --> ResourceAAS : Resource
  Step --> Skill : Skill
  Binding --> ProductParameter : SourceElement
  Binding ..> SkillParameter : Name
  RequiredCapability ..> OfferedCapability : matches (same meaning, values covered)
  OfferedCapability --> Skill : RealizedBy
```

## The resources

Read upwards: a primitive occupies equipment, a module level skill runs primitives and building
blocks in order, and a capability is realized by a module level skill.

### FillingModuleAAS

`https://smartproductionlab.aau.dk/aas/FillingModuleAAS`, asset `https://smartproductionlab.aau.dk/assets/FillingModule`. Built: its program is generated and runs on FORTE (against the simulator; the hardware is not wired yet).

```mermaid
flowchart BT
  subgraph EQ_FillingModuleAAS["Equipment (Hierarchical Structures)"]
    FillingModuleAASLinearAxis["LinearAxis"]
    FillingModuleAASPump["Pump"]
    FillingModuleAASScale["Scale"]
  end
  subgraph PR_FillingModuleAAS["Skill primitives (Skills, kind Primitive)"]
    FillingModuleAASHome["Home"]
    FillingModuleAASMoveAxis["MoveAxis"]
    FillingModuleAASDispense["Dispense"]
    FillingModuleAASTare["Tare"]
    FillingModuleAASWeigh["Weigh"]
  end
  subgraph CO_FillingModuleAAS["Module level skills (Skills, kind Composite)"]
    FillingModuleAASDispensing["Dispensing"]
  end
  subgraph CA_FillingModuleAAS["Capabilities (Capability Description, offered)"]
    FillingModuleAAScapFilling(["Filling"])
  end
  FillingModuleAASHome -- occupies --> FillingModuleAASLinearAxis
  FillingModuleAASMoveAxis -- occupies --> FillingModuleAASLinearAxis
  FillingModuleAASDispense -- occupies --> FillingModuleAASPump
  FillingModuleAASTare -- occupies --> FillingModuleAASScale
  FillingModuleAASWeigh -- occupies --> FillingModuleAASScale
  FillingModuleAASDispensing -- "1" --> FillingModuleAASMoveAxis
  FillingModuleAASDispensing -- "2" --> FillingModuleAASDispense
  FillingModuleAASDispensing -- "3" --> FillingModuleAASMoveAxis
  FillingModuleAASDispensing -- "4" --> FillingModuleAASWeigh
  FillingModuleAAScapFilling -- realized by --> FillingModuleAASDispensing
```

| Skill | Kind | Parameters | Equipment | Sequence |
| --- | --- | --- | --- | --- |
| Occupy | access control | – | – | – |
| Release | access control | – | – | – |
| Home | Primitive | – | LinearAxis | – |
| MoveAxis | Primitive | Position = 0.0 mm | LinearAxis | – |
| Dispense | Primitive | Volume = 1.0 mL, FlowRate = 1.0 mL/s | Pump | – |
| Tare | Primitive | – | Scale | – |
| Weigh | Primitive | – | Scale | – |
| Dispensing | Composite | Volume = 1.0 mL | LinearAxis, Pump, Scale | MoveAxis (Position = 40.0) → Dispense (FlowRate = 1.0, Volume ← Volume) → MoveAxis (Position = 0.0) → Weigh |

- **Capability Filling** (`https://smartproductionlab.aau.dk/semantics/Filling`), realized by Dispensing: ContainerType vial; GraspDiameter 6.0 to 30.0 mm; FillVolume 0.5 to 10.0 mL; AbsoluteFillError 0.05 mL.
- **Module:** commands Reset, Start, Stop, Abort, Clear; access control Occupy, Release; procedures: Resetting (Home → Tare), Stopping (Home).
- **Interface:** OPC UA at `opc.tcp://localhost:4840`, 31 actions and 46 properties; 46 data points; 32 mappings.
- **Control Configuration:** rules `https://smartproductionlab.aau.dk/rules/module/1`, spec `cell/modules/filling.yaml`, sync state NotRead.

### StopperingModuleAAS

`https://smartproductionlab.aau.dk/aas/StopperingModuleAAS`, asset `https://smartproductionlab.aau.dk/assets/StopperingModule`. Built: its program is generated and runs on FORTE (against the simulator; the hardware is not wired yet).

```mermaid
flowchart BT
  subgraph EQ_StopperingModuleAAS["Equipment (Hierarchical Structures)"]
    StopperingModuleAASPiston["Piston"]
    StopperingModuleAASPlunger["Plunger"]
    StopperingModuleAASStopperArm["StopperArm"]
  end
  subgraph PR_StopperingModuleAAS["Skill primitives (Skills, kind Primitive)"]
    StopperingModuleAASLowerPiston["LowerPiston"]
    StopperingModuleAASRaisePiston["RaisePiston"]
    StopperingModuleAASExtendPlunger["ExtendPlunger"]
    StopperingModuleAASRetractPlunger["RetractPlunger"]
    StopperingModuleAASMoveArm["MoveArm"]
  end
  subgraph CO_StopperingModuleAAS["Module level skills (Skills, kind Composite)"]
    StopperingModuleAASStoppering["Stoppering"]
  end
  subgraph CA_StopperingModuleAAS["Capabilities (Capability Description, offered)"]
    StopperingModuleAAScapStoppering(["Stoppering"])
  end
  StopperingModuleAASLowerPiston -- occupies --> StopperingModuleAASPiston
  StopperingModuleAASRaisePiston -- occupies --> StopperingModuleAASPiston
  StopperingModuleAASExtendPlunger -- occupies --> StopperingModuleAASPlunger
  StopperingModuleAASRetractPlunger -- occupies --> StopperingModuleAASPlunger
  StopperingModuleAASMoveArm -- occupies --> StopperingModuleAASStopperArm
  StopperingModuleAASStoppering -- "1" --> StopperingModuleAASLowerPiston
  StopperingModuleAASStoppering -- "2" --> StopperingModuleAASMoveArm
  StopperingModuleAASStoppering -- "3" --> StopperingModuleAASMoveArm
  StopperingModuleAASStoppering -- "4" --> StopperingModuleAASExtendPlunger
  StopperingModuleAASStoppering -- "5" --> StopperingModuleAASRetractPlunger
  StopperingModuleAASStoppering -- "6" --> StopperingModuleAASRaisePiston
  StopperingModuleAAScapStoppering -- realized by --> StopperingModuleAASStoppering
```

| Skill | Kind | Parameters | Equipment | Sequence |
| --- | --- | --- | --- | --- |
| Occupy | access control | – | – | – |
| Release | access control | – | – | – |
| LowerPiston | Primitive | – | Piston | – |
| RaisePiston | Primitive | Duration = 2.0 s | Piston | – |
| ExtendPlunger | Primitive | Duration = 10.0 s | Plunger | – |
| RetractPlunger | Primitive | Duration = 6.5 s | Plunger | – |
| MoveArm | Primitive | Angle = 120.0 deg, Settle = 2.0 s | StopperArm | – |
| Stoppering | Composite | – | Piston, StopperArm, Plunger | LowerPiston → MoveArm (Angle = 1.0) → MoveArm (Angle = 121.0) → ExtendPlunger → RetractPlunger → RaisePiston |

- **Capability Stoppering** (`https://smartproductionlab.aau.dk/semantics/Stoppering`), realized by Stoppering: ContainerType vial; GraspDiameter 6.0 to 30.0 mm; StopperDiameter 6.0 to 20.0 mm.
- **Module:** commands Reset, Start, Stop, Abort, Clear; access control Occupy, Release; procedures: Resetting (MoveArm → MoveArm → RetractPlunger → LowerPiston → RaisePiston).
- **Interface:** OPC UA at `opc.tcp://localhost:4840`, 31 actions and 55 properties; 55 data points; 32 mappings.
- **Control Configuration:** rules `https://smartproductionlab.aau.dk/rules/module/1`, spec `cell/modules/stoppering.yaml`, sync state NotRead.

### CappingModuleAAS

`https://smartproductionlab.aau.dk/aas/CappingModuleAAS`, asset `https://smartproductionlab.aau.dk/assets/CappingModule`. **Planned only:** described from a spec; there is no program and no hardware behind it yet.

```mermaid
flowchart BT
  subgraph EQ_CappingModuleAAS["Equipment (Hierarchical Structures)"]
    CappingModuleAASCapFeeder["CapFeeder"]
    CappingModuleAASCrimpHead["CrimpHead"]
  end
  subgraph PR_CappingModuleAAS["Skill primitives (Skills, kind Primitive)"]
    CappingModuleAASFeedCap["FeedCap"]
    CappingModuleAASLowerHead["LowerHead"]
    CappingModuleAASCrimp["Crimp"]
    CappingModuleAASRaiseHead["RaiseHead"]
  end
  subgraph CO_CappingModuleAAS["Module level skills (Skills, kind Composite)"]
    CappingModuleAASCapping["Capping"]
  end
  subgraph CA_CappingModuleAAS["Capabilities (Capability Description, offered)"]
    CappingModuleAAScapCapping(["Capping"])
  end
  CappingModuleAASFeedCap -- occupies --> CappingModuleAASCapFeeder
  CappingModuleAASLowerHead -- occupies --> CappingModuleAASCrimpHead
  CappingModuleAASCrimp -- occupies --> CappingModuleAASCrimpHead
  CappingModuleAASRaiseHead -- occupies --> CappingModuleAASCrimpHead
  CappingModuleAASCapping -- "1" --> CappingModuleAASFeedCap
  CappingModuleAASCapping -- "2" --> CappingModuleAASLowerHead
  CappingModuleAASCapping -- "3" --> CappingModuleAASCrimp
  CappingModuleAASCapping -- "4" --> CappingModuleAASRaiseHead
  CappingModuleAAScapCapping -- realized by --> CappingModuleAASCapping
```

| Skill | Kind | Parameters | Equipment | Sequence |
| --- | --- | --- | --- | --- |
| Occupy | access control | – | – | – |
| Release | access control | – | – | – |
| FeedCap | Primitive | – | CapFeeder | – |
| LowerHead | Primitive | – | CrimpHead | – |
| Crimp | Primitive | Duration = 1.5 s | CrimpHead | – |
| RaiseHead | Primitive | – | CrimpHead | – |
| Capping | Composite | – | CapFeeder, CrimpHead | FeedCap → LowerHead → Crimp → RaiseHead |

- **Capability Capping** (`https://smartproductionlab.aau.dk/semantics/Capping`), realized by Capping: ContainerType vial; GraspDiameter 6.0 to 30.0 mm; CapDiameter 13.0 to 20.0 mm.
- **Module:** commands Reset, Start, Stop, Abort, Clear; access control Occupy, Release; procedures: Resetting (RaiseHead), Stopping (RaiseHead).
- **Interface:** OPC UA at `opc.tcp://localhost:4840`, 27 actions and 31 properties; 31 data points; 28 mappings.
- **Control Configuration:** rules `https://smartproductionlab.aau.dk/rules/module/1`, spec `cell/modules/planned/capping.yaml`, sync state NotRead.

### InspectionModuleAAS

`https://smartproductionlab.aau.dk/aas/InspectionModuleAAS`, asset `https://smartproductionlab.aau.dk/assets/InspectionModule`. **Planned only:** described from a spec; there is no program and no hardware behind it yet.

```mermaid
flowchart BT
  subgraph EQ_InspectionModuleAAS["Equipment (Hierarchical Structures)"]
    InspectionModuleAASCamera["Camera"]
  end
  subgraph PR_InspectionModuleAAS["Skill primitives (Skills, kind Primitive)"]
    InspectionModuleAASIlluminate["Illuminate"]
    InspectionModuleAASCapture["Capture"]
  end
  subgraph CO_InspectionModuleAAS["Module level skills (Skills, kind Composite)"]
    InspectionModuleAASInspection["Inspection"]
  end
  subgraph CA_InspectionModuleAAS["Capabilities (Capability Description, offered)"]
    InspectionModuleAAScapInspection(["Inspection"])
  end
  InspectionModuleAASIlluminate -- occupies --> InspectionModuleAASCamera
  InspectionModuleAASCapture -- occupies --> InspectionModuleAASCamera
  InspectionModuleAASInspection -- "1" --> InspectionModuleAASIlluminate
  InspectionModuleAASInspection -- "2" --> InspectionModuleAASCapture
  InspectionModuleAAScapInspection -- realized by --> InspectionModuleAASInspection
```

| Skill | Kind | Parameters | Equipment | Sequence |
| --- | --- | --- | --- | --- |
| Occupy | access control | – | – | – |
| Release | access control | – | – | – |
| Illuminate | Primitive | Settle = 0.2 s | Camera | – |
| Capture | Primitive | – | Camera | – |
| Inspection | Composite | – | Camera | Illuminate → Capture |

- **Capability Inspection** (`https://smartproductionlab.aau.dk/semantics/Inspection`), realized by Inspection: ContainerType vial; GraspDiameter 6.0 to 30.0 mm; InspectionMethod vision.
- **Module:** commands Reset, Start, Stop, Abort, Clear; access control Occupy, Release; procedures: none.
- **Interface:** OPC UA at `opc.tcp://localhost:4840`, 19 actions and 19 properties; 19 data points; 20 mappings.
- **Control Configuration:** rules `https://smartproductionlab.aau.dk/rules/module/1`, spec `cell/modules/planned/inspection.yaml`, sync state NotRead.

## The product

### Vial2mLAAS

`https://smartproductionlab.aau.dk/aas/Vial2mLAAS`, asset `https://smartproductionlab.aau.dk/assets/Vial2mL`.

```mermaid
flowchart LR
  subgraph S_Filling["Step 1"]
    pFilling["process Filling"] -- requires --> cFilling(["Filling"])
    cFilling -. offered by .-> sFilling["FillingModuleAAS<br/>skill Dispensing"]
  end
  subgraph S_Stoppering["Step 2"]
    pStoppering["process Stoppering"] -- requires --> cStoppering(["Stoppering"])
    cStoppering -. offered by .-> sStoppering["StopperingModuleAAS<br/>skill Stoppering"]
  end
  S_Filling --> S_Stoppering
  subgraph S_Capping["Step 3"]
    pCapping["process Capping"] -- requires --> cCapping(["Capping"])
    cCapping -. offered by .-> sCapping["CappingModuleAAS<br/>skill Capping"]
  end
  S_Stoppering --> S_Capping
  subgraph S_Inspection["Step 4"]
    pInspection["process Inspection"] -- requires --> cInspection(["Inspection"])
    cInspection -. offered by .-> sInspection["InspectionModuleAAS<br/>skill Inspection"]
  end
  S_Capping --> S_Inspection
```

Bill of material (Hierarchical Structures):

| Part | Name | Quantity |
| --- | --- | --- |
| Vial | Glass vial 2R | 1.0 piece |
| Liquid | Demo liquid | 2.0 mL |
| Stopper | Rubber stopper 13 mm | 1.0 piece |
| Cap | Crimp cap 13 mm | 1.0 piece |

Processes (Process Parameters) and what they require (Capability Description):

| Process | Planned time | Product parameters | Materials | Required capability |
| --- | --- | --- | --- | --- |
| Filling | PT10S | ContainerType = vial, GraspDiameter = 16.0 mm, FillVolume = 2.0 mL | Vial (workpiece, 1.0 piece), Liquid (incorporated, FillVolume) | `https://smartproductionlab.aau.dk/semantics/Filling` |
| Stoppering | PT5S | ContainerType = vial, GraspDiameter = 16.0 mm, StopperDiameter = 13.0 mm | Stopper (incorporated, 1.0 piece) | `https://smartproductionlab.aau.dk/semantics/Stoppering` |
| Capping | PT5S | ContainerType = vial, GraspDiameter = 16.0 mm, CapDiameter = 13.0 mm | Cap (incorporated, 1.0 piece) | `https://smartproductionlab.aau.dk/semantics/Capping` |
| Inspection | PT3S | ContainerType = vial, GraspDiameter = 16.0 mm, InspectionMethod = vision | – | `https://smartproductionlab.aau.dk/semantics/Inspection` |

The plan (Production Sequence, `production-sequence/2.0`):

| Order | Step | Resource | Skill | Bound |
| --- | --- | --- | --- | --- |
| 1 | Filling | FillingModuleAAS | Dispensing | Volume ← FillVolume |
| 2 | Stoppering | StopperingModuleAAS | Stoppering | – |
| 3 | Capping | CappingModuleAAS | Capping | – |
| 4 | Inspection | InspectionModuleAAS | Inspection | – |
