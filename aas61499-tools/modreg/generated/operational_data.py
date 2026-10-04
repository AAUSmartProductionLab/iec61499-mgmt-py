"""OperationalData — generated from IDTA template."""

from __future__ import annotations

from typing import Any, ClassVar, List, Dict, Optional, TypeAlias
from aas_pydantic import (
    Property, ReferenceElement, Submodel, SubmodelElement, SubmodelElementCollection, SubmodelElementList,
)

class OperationalDataVariable(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "A named variable entry."
    InterfaceReference: Optional[ReferenceElement] = None

# alias so field ``OperationalDataVariable_t`` can name a class of the same id_short
OperationalDataVariable_t: TypeAlias = OperationalDataVariable
class OperationalData(Submodel):
    semantic_id: str = "https://smartproductionlab.aau.dk/ARSO/OperationalData/1/0/Submodel"
    description: str = "Custom \u2014 Runtime variable bindings."
    VERSION: ClassVar[str] = "1"
    REVISION: ClassVar[str] = "0"
    Datapoint: Dict[str, Property] = {}
    OperationalDataVariable: Dict[str, OperationalDataVariable_t] = {}

# ── Resolve forward references (Pydantic circular refs) ──
OperationalDataVariable.model_rebuild()
OperationalData.model_rebuild()
