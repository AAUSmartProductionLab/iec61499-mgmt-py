"""ProcessParameters — generated from IDTA template."""

from __future__ import annotations

from typing import Any, ClassVar, List, Dict, Optional, TypeAlias
from aas_pydantic import (
    MultiLanguageProperty, Property, ReferenceElement, Submodel, SubmodelElement, SubmodelElementCollection, SubmodelElementList,
)

class ProcessId(Property):
    semantic_id: str = "https://admin-shell.io/idta/ProcessParameters/ProcessId/1/0"
    description: str = "Describes the ID of the process"
    value_type: str = "xs:string"

class ProcessName(Property):
    semantic_id: str = "https://admin-shell.io/idta/ProcessParameters/ProcessName/1/0"
    description: str = "Describes the Name of the Process"
    value_type: str = "xs:string"

class ProcessDescription(MultiLanguageProperty):
    semantic_id: str = "https://admin-shell.io/idta/ProcessParameters/ProcessDescription/1/0"
    description: str = "Describes the process."

class PlannedProcessTime(Property):
    semantic_id: str = "https://admin-shell.io/idta/ProcessParameters/PlannedProcessTime/1/0"
    description: str = "Planned processing time for process execution (without set-up time)"
    value_type: str = "xs:duration"

class ProductParameters(SubmodelElementCollection):
    semantic_id: str = "https://admin-shell.io/idta/ProcessParameters/ProductParameters/1/0"
    description: str = "Mandatory product parameters for process execution"
    Parameter: Dict[str, Property] = {}

class ProcessParameters_process_parameters(SubmodelElementCollection):
    semantic_id: str = "https://admin-shell.io/idta/ProcessParameters/ProcessParameters/1/0"
    description: str = "Mandatory process parameters for process execution"
    Parameter: Dict[str, Property] = {}

class ResourceParameters(SubmodelElementCollection):
    semantic_id: str = "https://admin-shell.io/idta/ProcessParameters/ResourceParameters/1/0"
    description: str = "Mandatory resource parameters for process execution"
    Parameter: Dict[str, Property] = {}

class MaterialReference(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProcessParameters/MaterialUse/MaterialReference/1/0"
    description: str = "The material: an entity of the bill of material."

class Role(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProcessParameters/MaterialUse/Role/1/0"
    description: str = "workpiece, incorporated or output."
    value_type: str = "xs:string"

class Quantity(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProcessParameters/MaterialUse/Quantity/1/0"
    description: str = "How much of the material."
    value_type: str = "xs:double"

class Unit(Property):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProcessParameters/MaterialUse/Unit/1/0"
    description: str = "The unit of the quantity."
    value_type: str = "xs:string"

class QuantityParameterReference(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProcessParameters/MaterialUse/QuantityParameterReference/1/0"
    description: str = "The parameter that gives the quantity, instead of a fixed one."

# alias so field ``MaterialReference_t`` can name a class of the same id_short
MaterialReference_t: TypeAlias = MaterialReference
# alias so field ``Role_t`` can name a class of the same id_short
Role_t: TypeAlias = Role
# alias so field ``Quantity_t`` can name a class of the same id_short
Quantity_t: TypeAlias = Quantity
# alias so field ``Unit_t`` can name a class of the same id_short
Unit_t: TypeAlias = Unit
# alias so field ``QuantityParameterReference_t`` can name a class of the same id_short
QuantityParameterReference_t: TypeAlias = QuantityParameterReference
class MaterialUse(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProcessParameters/MaterialUse/1/0"
    description: str = "Lab extension: one material the process uses or makes."
    MaterialReference: MaterialReference_t
    Role: Role_t
    Quantity: Optional[Quantity_t] = None
    Unit: Optional[Unit_t] = None
    QuantityParameterReference: Optional[QuantityParameterReference_t] = None

# alias so field ``MaterialUse_t`` can name a class of the same id_short
MaterialUse_t: TypeAlias = MaterialUse
class ProcessBoM(SubmodelElementCollection):
    semantic_id: str = "https://admin-shell.io/idta/ProcessParameters/ProcessBoM/1/0"
    description: str = "Describes the products or semi-finished products to be involved in the process"
    MaterialUse: Dict[str, MaterialUse_t] = {}

class RequiredCapability(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ProcessParameters/RequiredCapability/1/0"
    description: str = "Lab extension: the Required capability the process needs, in the Capability Description of the same AAS."

# alias so field ``ProcessId_t`` can name a class of the same id_short
ProcessId_t: TypeAlias = ProcessId
# alias so field ``ProcessName_t`` can name a class of the same id_short
ProcessName_t: TypeAlias = ProcessName
# alias so field ``ProcessDescription_t`` can name a class of the same id_short
ProcessDescription_t: TypeAlias = ProcessDescription
# alias so field ``PlannedProcessTime_t`` can name a class of the same id_short
PlannedProcessTime_t: TypeAlias = PlannedProcessTime
# alias so field ``ProductParameters_t`` can name a class of the same id_short
ProductParameters_t: TypeAlias = ProductParameters
# alias so field ``ResourceParameters_t`` can name a class of the same id_short
ResourceParameters_t: TypeAlias = ResourceParameters
# alias so field ``ProcessBoM_t`` can name a class of the same id_short
ProcessBoM_t: TypeAlias = ProcessBoM
# alias so field ``RequiredCapability_t`` can name a class of the same id_short
RequiredCapability_t: TypeAlias = RequiredCapability
class Process(SubmodelElementCollection):
    semantic_id: str = "https://admin-shell.io/idta/ProcessParameters/Process/1/0"
    description: str = "The processes to be executed are described individually in the SMC Process."
    ProcessId: ProcessId_t
    ProcessName: ProcessName_t
    ProcessDescription: ProcessDescription_t
    PlannedProcessTime: PlannedProcessTime_t
    ProductParameters: ProductParameters_t
    ProcessParameters: ProcessParameters_process_parameters
    ResourceParameters: ResourceParameters_t
    ProcessBoM: ProcessBoM_t
    RequiredCapability: Optional[RequiredCapability_t] = None

# alias so field ``Process_t`` can name a class of the same id_short
Process_t: TypeAlias = Process
class Processes(SubmodelElementCollection):
    semantic_id: str = "https://admin-shell.io/idta/ProcessParameters/Processes/1/0"
    description: str = "Provides all the necessary parameters of processes in a structured form that are required to manufacture a product"
    Process: Dict[str, Process_t] = {}

# alias so field ``Processes_t`` can name a class of the same id_short
Processes_t: TypeAlias = Processes
class ProcessParameters(Submodel):
    semantic_id: str = "https://admin-shell-io/idta/SubmodelTemplate/ProcessParameters/1/0"
    description: str = "The Submodel provides all the necessary parameters in a structured form that are required for the manufacture of any product"
    VERSION: ClassVar[str] = "1"
    REVISION: ClassVar[str] = "0"
    Processes: Processes_t

# ── Resolve forward references (Pydantic circular refs) ──
ProcessId.model_rebuild()
ProcessName.model_rebuild()
ProcessDescription.model_rebuild()
PlannedProcessTime.model_rebuild()
ProductParameters.model_rebuild()
ProcessParameters_process_parameters.model_rebuild()
ResourceParameters.model_rebuild()
MaterialReference.model_rebuild()
Role.model_rebuild()
Quantity.model_rebuild()
Unit.model_rebuild()
QuantityParameterReference.model_rebuild()
MaterialUse.model_rebuild()
ProcessBoM.model_rebuild()
RequiredCapability.model_rebuild()
Process.model_rebuild()
Processes.model_rebuild()
ProcessParameters.model_rebuild()
