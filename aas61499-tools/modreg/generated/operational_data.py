"""OperationalData - generated from IDTA template.
Source: modreg/templates/OperationalData.json
"""

from __future__ import annotations

from typing import Any, ClassVar, List, Dict, TypeAlias
from aas_pydantic import (
    Property, Submodel, SubmodelElement, SubmodelElementCollection, SubmodelElementList,
)
from pydantic import Field
from aas_pydantic.aas_model import AasIdString

class Datapoint(Property):
    description: str = "A domain-specific measurement or value, represented as an AAS Property."
    value_type: str = "xs:decimal"

class OperationalData(Submodel):
    id_short: AasIdString = "OperationalData"
    semantic_id: str = "https://smartproductionlab.aau.dk/ARSO/OperationalData/1/0/Submodel"
    description: str = "Custom \u2014 what the resource shows as it runs: a data point per value, fed from the interface by the mapping."
    VERSION: ClassVar[str] = "1"
    REVISION: ClassVar[str] = "0"
    Datapoint: Dict[str, Datapoint_t] = Field(default_factory=dict, json_schema_extra={"idta_min_cardinality": 1})

# alias so field ``Datapoint_t`` can name a class of the same id_short
Datapoint_t: TypeAlias = Datapoint
# ── Resolve forward references (Pydantic circular refs) ──
Datapoint.model_rebuild()
OperationalData.model_rebuild()
