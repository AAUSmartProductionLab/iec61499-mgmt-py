"""ControlConfiguration — generated from IDTA template."""

from __future__ import annotations

from typing import Any, ClassVar, List, Dict, Optional, TypeAlias
from aas_pydantic import (
    Property, ReferenceElement, Submodel, SubmodelElement, SubmodelElementCollection, SubmodelElementList,
)

class Runtime(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "The controller runtime: Name, ManagementEndpoint, Resource."
    Name: Optional[Property] = None
    ManagementEndpoint: Optional[Property] = None
    Resource: Optional[Property] = None

class Differences(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One Property per difference between the running program and its source."
    CCfgDifference: Dict[str, Property] = {}

class CCfgType(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One function block type in use."
    Name: Optional[Property] = None
    Hash: Optional[Property] = None

# alias so field ``CCfgType_t`` can name a class of the same id_short
CCfgType_t: TypeAlias = CCfgType
class Types(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "The function block types in use, each with Name and Hash as the runtime reports them."
    CCfgType: Dict[str, CCfgType_t] = {}

class CCfgInstance(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One block of the program, named like its instance path with underscores."
    InstancePath: Optional[Property] = None
    FBType: Optional[Property] = None
    TypeHash: Optional[Property] = None
    Skill: Optional[ReferenceElement] = None

# alias so field ``CCfgInstance_t`` can name a class of the same id_short
CCfgInstance_t: TypeAlias = CCfgInstance
class Instances(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "The blocks of the program that are the resource's skills and the steps of their commands: which block, of which type, is which skill."
    CCfgInstance: Dict[str, CCfgInstance_t] = {}

class ActiveProcedure(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "Reference to the Process AAS (and version) whose procedure is active, with NetworkHash, BootFileHash, ActivatedAt."
    pass

class CCfgChange(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "One reconfiguration record."
    pass

class ChangeLog(SubmodelElementList):
    semantic_id: str = ""
    description: str = "One Change SMC per reconfiguration: Time, Trigger, ChangeClass (a pprl:ChangeClass IRI), From, To, Result, Duration."
    item_type: ClassVar = CCfgChange
    value: List[CCfgChange] = []

# alias so field ``Runtime_t`` can name a class of the same id_short
Runtime_t: TypeAlias = Runtime
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
class ControlConfiguration(Submodel):
    semantic_id: str = "https://smartproductionlab.aau.dk/ARSO/ControlConfiguration/1/0/Submodel"
    description: str = "Custom \u2014 what runs on the resource's controller and how it got there."
    VERSION: ClassVar[str] = "1"
    REVISION: ClassVar[str] = "0"
    Runtime: Optional[Runtime_t] = None
    Rules: Optional[Property] = None
    ModuleSpec: Optional[Property] = None
    Target: Optional[Property] = None
    Generator: Optional[Property] = None
    ProgramDigest: Optional[Property] = None
    ReadAt: Optional[Property] = None
    SyncState: Property
    Differences: Optional[Differences_t] = None
    Types: Optional[Types_t] = None
    Instances: Optional[Instances_t] = None
    ActiveProcedure: Optional[ActiveProcedure_t] = None
    ChangeLog: Optional[ChangeLog_t] = None

# ── Resolve forward references (Pydantic circular refs) ──
Runtime.model_rebuild()
Differences.model_rebuild()
CCfgType.model_rebuild()
Types.model_rebuild()
CCfgInstance.model_rebuild()
Instances.model_rebuild()
ActiveProcedure.model_rebuild()
CCfgChange.model_rebuild()
ChangeLog.model_rebuild()
ControlConfiguration.model_rebuild()
