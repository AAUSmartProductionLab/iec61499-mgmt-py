"""Parameters — generated from IDTA template."""

from __future__ import annotations

from typing import Any, ClassVar, List, Dict, Optional, TypeAlias
from aas_pydantic import (
    Property, ReferenceElement, Submodel, SubmodelElement, SubmodelElementCollection, SubmodelElementList,
)

class ParameterEntry(SubmodelElementCollection):
    semantic_id: str = ""
    description: str = "A named parameter entry."
    InterfaceReference: Optional[ReferenceElement] = None
    Value: Property
    Unit: Optional[Property] = None

# alias so field ``ParameterEntry_t`` can name a class of the same id_short
ParameterEntry_t: TypeAlias = ParameterEntry
class Parameters(Submodel):
    semantic_id: str = "https://smartproductionlab.aau.dk/ARSO/Parameters/1/0/Submodel"
    description: str = "Custom \u2014 Static configuration parameters."
    VERSION: ClassVar[str] = "1"
    REVISION: ClassVar[str] = "0"
    ParameterEntry: Dict[str, ParameterEntry_t] = {}

# ── Resolve forward references (Pydantic circular refs) ──
ParameterEntry.model_rebuild()
Parameters.model_rebuild()
