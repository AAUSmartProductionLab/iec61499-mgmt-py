"""Parameters - generated from IDTA template.
Source: modreg/templates/Parameters.json
"""

from __future__ import annotations

from typing import Any, ClassVar, List, Dict, Optional, TypeAlias
from aas_pydantic import (
    Property, ReferenceElement, Submodel, SubmodelElement, SubmodelElementCollection, SubmodelElementList,
)
from pydantic import Field
from aas_pydantic.aas_model import AasIdString

class InterfaceReference(ReferenceElement):
    id_short: AasIdString = "InterfaceReference"
    description: str = "Points to an AID property (.../InteractionMetadata/properties/{key}) in the same AAS (parameters_builder.py hardcodes the properties path segment, never actions/events)."

class Value(Property):
    id_short: AasIdString = "Value"
    description: str = "The parameter's value as deployed; its valueType is the parameter's type (added 2 Oct 2026 for the registration service)."
    value_type: str = "xs:string"

class Unit(Property):
    id_short: AasIdString = "Unit"
    description: str = "The unit of the value (added 2 Oct 2026)."
    value_type: str = "xs:string"

class ParameterEntry(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "A named parameter entry."
    InterfaceReference: Optional[InterfaceReference_t] = None
    Value: Optional[Value_t] = None
    Unit: Optional[Unit_t] = None

class Parameters(Submodel):
    id_short: AasIdString = "Parameters"
    semantic_id: str = "https://smartproductionlab.aau.dk/ARSO/Parameters/1/0/Submodel"
    description: str = "Custom \u2014 Static configuration parameters."
    VERSION: ClassVar[str] = "1"
    REVISION: ClassVar[str] = "0"
    ParameterEntry: Dict[str, ParameterEntry_t] = Field(default_factory=dict, json_schema_extra={"idta_min_cardinality": 1})

# alias so field ``InterfaceReference_t`` can name a class of the same id_short
InterfaceReference_t: TypeAlias = InterfaceReference
# alias so field ``Value_t`` can name a class of the same id_short
Value_t: TypeAlias = Value
# alias so field ``Unit_t`` can name a class of the same id_short
Unit_t: TypeAlias = Unit
# alias so field ``ParameterEntry_t`` can name a class of the same id_short
ParameterEntry_t: TypeAlias = ParameterEntry
# ── Resolve forward references (Pydantic circular refs) ──
InterfaceReference.model_rebuild()
Value.model_rebuild()
Unit.model_rebuild()
ParameterEntry.model_rebuild()
Parameters.model_rebuild()
