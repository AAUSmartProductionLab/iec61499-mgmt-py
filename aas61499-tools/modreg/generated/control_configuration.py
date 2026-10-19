"""ControlConfiguration - generated from IDTA template.
Source: modreg/templates/ControlConfiguration.json
"""

from __future__ import annotations

from typing import Any, ClassVar, List, Dict, Optional, Union, TypeAlias
from aas_pydantic import (
    Property, ReferenceElement, Submodel, SubmodelElement, SubmodelElementCollection, SubmodelElementList,
)
from aas_pydantic.aas_model import AasIdString

class Name(Property):
    id_short: AasIdString = "Name"
    description: str = "Property Name, ManagementEndpoint or Resource of the runtime."
    value_type: str = "xs:string"

class ManagementEndpoint(Property):
    id_short: AasIdString = "ManagementEndpoint"
    description: str = "Property Name, ManagementEndpoint or Resource of the runtime."
    value_type: str = "xs:string"

class Resource(Property):
    id_short: AasIdString = "Resource"
    description: str = "Property Name, ManagementEndpoint or Resource of the runtime."
    value_type: str = "xs:string"

class Runtime(SubmodelElementCollection):
    id_short: AasIdString = "Runtime"
    semantic_id: str = ""
    description: str = "The controller runtime: Name, ManagementEndpoint, Resource."
    Name: Optional[Name_t] = None
    ManagementEndpoint: Optional[ManagementEndpoint_t] = None
    Resource: Optional[Resource_t] = None

class Rules(Property):
    id_short: AasIdString = "Rules"
    description: str = "The IRI of the rule set the resource's program is built by: its shell, the interface of a skill primitive and the pattern of a composite skill."
    value_type: str = "xs:string"

class ModuleSpec(Property):
    id_short: AasIdString = "ModuleSpec"
    description: str = "Property ModuleSpec, Target, Generator (what the program was generated from and by), ProgramDigest (SHA-256 of the generated program: instances, types, connections, values) or ReadAt (when the controller was read)."
    value_type: str = "xs:string"

class Target(Property):
    id_short: AasIdString = "Target"
    description: str = "Property ModuleSpec, Target, Generator (what the program was generated from and by), ProgramDigest (SHA-256 of the generated program: instances, types, connections, values) or ReadAt (when the controller was read)."
    value_type: str = "xs:string"

class Generator(Property):
    id_short: AasIdString = "Generator"
    description: str = "Property ModuleSpec, Target, Generator (what the program was generated from and by), ProgramDigest (SHA-256 of the generated program: instances, types, connections, values) or ReadAt (when the controller was read)."
    value_type: str = "xs:string"

class ProgramDigest(Property):
    id_short: AasIdString = "ProgramDigest"
    description: str = "Property ModuleSpec, Target, Generator (what the program was generated from and by), ProgramDigest (SHA-256 of the generated program: instances, types, connections, values) or ReadAt (when the controller was read)."
    value_type: str = "xs:string"

class ReadAt(Property):
    id_short: AasIdString = "ReadAt"
    description: str = "Property ModuleSpec, Target, Generator (what the program was generated from and by), ProgramDigest (SHA-256 of the generated program: instances, types, connections, values) or ReadAt (when the controller was read)."
    value_type: str = "xs:string"

class SyncState(Property):
    id_short: AasIdString = "SyncState"
    description: str = "InSync (the running program is the one its source generates), Drift (it differs, see Differences), NoProgram, NotRead (described from the source only)."
    value_type: str = "xs:string"

class CCfgDifference(Property):
    description: str = "One difference."
    value_type: str = "xs:string"

class Differences(SubmodelElementCollection):
    id_short: AasIdString = "Differences"
    semantic_id: str = ""
    description: str = "One Property per difference between the running program and its source."
    CCfgDifference: Dict[str, CCfgDifference_t] = {}

class Name_Property(Property):
    id_short: AasIdString = "Name"
    description: str = "Property Name or Hash of a type, as the runtime reports them."
    value_type: str = "xs:string"

class Hash(Property):
    id_short: AasIdString = "Hash"
    description: str = "Property Name or Hash of a type, as the runtime reports them."
    value_type: str = "xs:string"

class CCfgType(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One function block type in use."
    Name: Optional[Union[Name_Property, Name]] = None
    Hash: Optional[Hash_t] = None

class Types(SubmodelElementCollection):
    id_short: AasIdString = "Types"
    semantic_id: str = ""
    description: str = "The function block types in use, each with Name and Hash as the runtime reports them."
    CCfgType: Dict[str, CCfgType_t] = {}

class InstancePath(Property):
    id_short: AasIdString = "InstancePath"
    description: str = "Property InstancePath (the dotted name of the instance), FBType (its qualified IEC 61499 type) or TypeHash (the hash of that type as the runtime reports it)."
    value_type: str = "xs:string"

class FBType(Property):
    id_short: AasIdString = "FBType"
    description: str = "Property InstancePath (the dotted name of the instance), FBType (its qualified IEC 61499 type) or TypeHash (the hash of that type as the runtime reports it)."
    value_type: str = "xs:string"

class TypeHash(Property):
    id_short: AasIdString = "TypeHash"
    description: str = "Property InstancePath (the dotted name of the instance), FBType (its qualified IEC 61499 type) or TypeHash (the hash of that type as the runtime reports it)."
    value_type: str = "xs:string"

class Skill(ReferenceElement):
    id_short: AasIdString = "Skill"
    description: str = "What the block is: a skill (in the Skills submodel of this AAS or of a component), or the step of a command that runs one."

class CCfgInstance(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One block of the program, named like its instance path with underscores."
    InstancePath: Optional[InstancePath_t] = None
    FBType: Optional[FBType_t] = None
    TypeHash: Optional[TypeHash_t] = None
    Skill: Optional[Skill_t] = None

class Instances(SubmodelElementCollection):
    id_short: AasIdString = "Instances"
    semantic_id: str = ""
    description: str = "The blocks of the program that are the resource's skills and the steps of their commands: which block, of which type, is which skill."
    CCfgInstance: Dict[str, CCfgInstance_t] = {}

class ActiveProcedure(SubmodelElementCollection):
    id_short: AasIdString = "ActiveProcedure"
    semantic_id: str = ""
    description: str = "Reference to the Process AAS (and version) whose procedure is active, with NetworkHash, BootFileHash, ActivatedAt."
    pass

class CCfgChange(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One reconfiguration record."
    pass

class ChangeLog(SubmodelElementList):
    id_short: AasIdString = "ChangeLog"
    semantic_id: str = ""
    description: str = "One Change SMC per reconfiguration: Time, Trigger, ChangeClass (a pprl:ChangeClass IRI), From, To, Result, Duration."
    type_value_list_element: str = "SubmodelElementCollection"
    order_relevant: bool = True
    item_type: ClassVar = CCfgChange
    value: List[CCfgChange] = []

class ControlConfiguration(Submodel):
    id_short: AasIdString = "ControlConfiguration"
    semantic_id: str = "https://smartproductionlab.aau.dk/ARSO/ControlConfiguration/1/0/Submodel"
    description: str = "Custom \u2014 what runs on the resource's controller and how it got there."
    VERSION: ClassVar[str] = "1"
    REVISION: ClassVar[str] = "0"
    Runtime: Optional[Runtime_t] = None
    Rules: Optional[Rules_t] = None
    ModuleSpec: Optional[ModuleSpec_t] = None
    Target: Optional[Target_t] = None
    Generator: Optional[Generator_t] = None
    ProgramDigest: Optional[ProgramDigest_t] = None
    ReadAt: Optional[ReadAt_t] = None
    SyncState: SyncState_t
    Differences: Optional[Differences_t] = None
    Types: Optional[Types_t] = None
    Instances: Optional[Instances_t] = None
    ActiveProcedure: Optional[ActiveProcedure_t] = None
    ChangeLog: Optional[ChangeLog_t] = None

# alias so field ``Name_t`` can name a class of the same id_short
Name_t: TypeAlias = Name
# alias so field ``ManagementEndpoint_t`` can name a class of the same id_short
ManagementEndpoint_t: TypeAlias = ManagementEndpoint
# alias so field ``Resource_t`` can name a class of the same id_short
Resource_t: TypeAlias = Resource
# alias so field ``CCfgDifference_t`` can name a class of the same id_short
CCfgDifference_t: TypeAlias = CCfgDifference
# alias so field ``Hash_t`` can name a class of the same id_short
Hash_t: TypeAlias = Hash
# alias so field ``CCfgType_t`` can name a class of the same id_short
CCfgType_t: TypeAlias = CCfgType
# alias so field ``InstancePath_t`` can name a class of the same id_short
InstancePath_t: TypeAlias = InstancePath
# alias so field ``FBType_t`` can name a class of the same id_short
FBType_t: TypeAlias = FBType
# alias so field ``TypeHash_t`` can name a class of the same id_short
TypeHash_t: TypeAlias = TypeHash
# alias so field ``Skill_t`` can name a class of the same id_short
Skill_t: TypeAlias = Skill
# alias so field ``CCfgInstance_t`` can name a class of the same id_short
CCfgInstance_t: TypeAlias = CCfgInstance
# alias so field ``Runtime_t`` can name a class of the same id_short
Runtime_t: TypeAlias = Runtime
# alias so field ``Rules_t`` can name a class of the same id_short
Rules_t: TypeAlias = Rules
# alias so field ``ModuleSpec_t`` can name a class of the same id_short
ModuleSpec_t: TypeAlias = ModuleSpec
# alias so field ``Target_t`` can name a class of the same id_short
Target_t: TypeAlias = Target
# alias so field ``Generator_t`` can name a class of the same id_short
Generator_t: TypeAlias = Generator
# alias so field ``ProgramDigest_t`` can name a class of the same id_short
ProgramDigest_t: TypeAlias = ProgramDigest
# alias so field ``ReadAt_t`` can name a class of the same id_short
ReadAt_t: TypeAlias = ReadAt
# alias so field ``SyncState_t`` can name a class of the same id_short
SyncState_t: TypeAlias = SyncState
# alias so field ``Differences_t`` can name a class of the same id_short
Differences_t: TypeAlias = Differences
# alias so field ``Types_t`` can name a class of the same id_short
Types_t: TypeAlias = Types
# alias so field ``Instances_t`` can name a class of the same id_short
Instances_t: TypeAlias = Instances
# alias so field ``ActiveProcedure_t`` can name a class of the same id_short
ActiveProcedure_t: TypeAlias = ActiveProcedure
# alias so field ``ChangeLog_t`` can name a class of the same id_short
ChangeLog_t: TypeAlias = ChangeLog
# ── Resolve forward references (Pydantic circular refs) ──
Name.model_rebuild()
ManagementEndpoint.model_rebuild()
Resource.model_rebuild()
Runtime.model_rebuild()
Rules.model_rebuild()
ModuleSpec.model_rebuild()
Target.model_rebuild()
Generator.model_rebuild()
ProgramDigest.model_rebuild()
ReadAt.model_rebuild()
SyncState.model_rebuild()
CCfgDifference.model_rebuild()
Differences.model_rebuild()
Name_Property.model_rebuild()
Hash.model_rebuild()
CCfgType.model_rebuild()
Types.model_rebuild()
InstancePath.model_rebuild()
FBType.model_rebuild()
TypeHash.model_rebuild()
Skill.model_rebuild()
CCfgInstance.model_rebuild()
Instances.model_rebuild()
ActiveProcedure.model_rebuild()
CCfgChange.model_rebuild()
ChangeLog.model_rebuild()
ControlConfiguration.model_rebuild()
