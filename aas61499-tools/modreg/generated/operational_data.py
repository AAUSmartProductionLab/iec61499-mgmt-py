"""OperationalData - generated from IDTA template.
Source: modreg/templates/OperationalData.json
"""

from __future__ import annotations

from typing import Any, ClassVar, List, Dict, Optional, TypeAlias
from aas_pydantic import (
    Property, ReferenceElement, Submodel, SubmodelElement, SubmodelElementCollection, SubmodelElementList,
)
from pydantic import Field
from aas_pydantic.aas_model import AasIdString

class Datapoint(Property):
    description: str = "A domain-specific measurement or value, represented as an AAS Property."
    value_type: str = "xs:decimal"

class InterfaceReference(ReferenceElement):
    id_short: AasIdString = "InterfaceReference"
    description: str = "Points to an AID property (.../InteractionMetadata/properties/{key}) in the same AAS (variables_builder.py hardcodes the properties path segment, never actions/events)."

class OperationalDataVariable(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "A named variable entry."
    InterfaceReference: Optional[InterfaceReference_t] = None

class OperationalData(Submodel):
    id_short: AasIdString = "OperationalData"
    semantic_id: str = "https://smartproductionlab.aau.dk/ARSO/OperationalData/1/0/Submodel"
    description: str = "Custom \u2014 Runtime variable bindings."
    VERSION: ClassVar[str] = "1"
    REVISION: ClassVar[str] = "0"
    Datapoint: Dict[str, Datapoint_t] = Field(default_factory=dict, json_schema_extra={"idta_min_cardinality": 1})
    OperationalDataVariable: Dict[str, OperationalDataVariable_t] = {}

# alias so field ``InterfaceReference_t`` can name a class of the same id_short
InterfaceReference_t: TypeAlias = InterfaceReference
# alias so field ``Datapoint_t`` can name a class of the same id_short
Datapoint_t: TypeAlias = Datapoint
# alias so field ``OperationalDataVariable_t`` can name a class of the same id_short
OperationalDataVariable_t: TypeAlias = OperationalDataVariable
# ── Resolve forward references (Pydantic circular refs) ──
Datapoint.model_rebuild()
InterfaceReference.model_rebuild()
OperationalDataVariable.model_rebuild()
OperationalData.model_rebuild()
