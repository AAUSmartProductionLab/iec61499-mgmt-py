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

class RelativeTo(ReferenceElement):
    id_short: AasIdString = "RelativeTo"
    semantic_id: str = "https://smartproductionlab.aau.dk/ARSO/OperationalData/Coordinate/RelativeTo/1/0"
    description: str = "The coordinate this one is relative to (a ModelReference to its SMC, in this AAS or another)."

class X(Property):
    id_short: AasIdString = "X"
    semantic_id: str = "https://admin-shell.io/idta/cds/xframe/1"
    description: str = "The translation along the parent's X axis (IDTA 02075 xframe)."
    value_type: str = "xs:double"

class Y(Property):
    id_short: AasIdString = "Y"
    semantic_id: str = "https://admin-shell.io/idta/cds/yframe/1"
    description: str = "The translation along the parent's Y axis (IDTA 02075 yframe)."
    value_type: str = "xs:double"

class Z(Property):
    id_short: AasIdString = "Z"
    semantic_id: str = "https://admin-shell.io/idta/cds/zframe/1"
    description: str = "The translation along the parent's Z axis (IDTA 02075 zframe)."
    value_type: str = "xs:double"

class Roll(Property):
    id_short: AasIdString = "Roll"
    semantic_id: str = "https://admin-shell.io/idta/cds/rxframe/1"
    description: str = "The rotation about the parent's X axis, applied first (IDTA 02075 rxframe)."
    value_type: str = "xs:double"

class Pitch(Property):
    id_short: AasIdString = "Pitch"
    semantic_id: str = "https://admin-shell.io/idta/cds/ryframe/1"
    description: str = "The rotation about the parent's Y axis, applied second (IDTA 02075 ryframe)."
    value_type: str = "xs:double"

class Yaw(Property):
    id_short: AasIdString = "Yaw"
    semantic_id: str = "https://admin-shell.io/idta/cds/rzframe/1"
    description: str = "The rotation about the parent's Z axis, applied last (IDTA 02075 rzframe)."
    value_type: str = "xs:double"

class CoordinateSource(ReferenceElement):
    semantic_id: str = "https://smartproductionlab.aau.dk/ARSO/OperationalData/Coordinate/Source/1/0"
    description: str = "The data point whose value that value of the coordinate is: a coordinate that moves (an end effector along its axis, a shuttle on the table)."

class Coordinate(SubmodelElementCollection):
    semantic_id: str = "https://smartproductionlab.aau.dk/ARSO/OperationalData/Coordinate/1/0"
    description: str = "A pose relative to the coordinate RelativeTo names: X, Y, Z in mm and Roll, Pitch, Yaw in degrees about the parent's fixed X, then Y, then Z axis (R = Rz(Yaw) Ry(Pitch) Rx(Roll), as ROS's RPY)."
    RelativeTo: Optional[RelativeTo_t] = None
    X: X_t
    Y: Y_t
    Z: Z_t
    Roll: Roll_t
    Pitch: Pitch_t
    Yaw: Yaw_t
    CoordinateSource: Dict[str, CoordinateSource_t] = {}

class Coordinates(SubmodelElementCollection):
    id_short: AasIdString = "Coordinates"
    semantic_id: str = "https://smartproductionlab.aau.dk/ARSO/OperationalData/Coordinates/1/0"
    description: str = "Where the resource and its points are: one coordinate each, relative to another by reference (a tree of transforms rooted at the planar table's base)."
    Coordinate: Dict[str, Coordinate_t] = Field(default_factory=dict, json_schema_extra={"idta_min_cardinality": 1})

class Measurements(SubmodelElementCollection):
    id_short: AasIdString = "Measurements"
    semantic_id: str = "https://smartproductionlab.aau.dk/ARSO/OperationalData/Measurements/1/0"
    description: str = "The measurement series of the resource (docs/state-and-parameters.md, section 3); for now its coordinates."
    Coordinates: Optional[Coordinates_t] = None

class OperationalData(Submodel):
    id_short: AasIdString = "OperationalData"
    semantic_id: str = "https://smartproductionlab.aau.dk/ARSO/OperationalData/1/0/Submodel"
    description: str = "Custom \u2014 what the resource shows as it runs: a data point per value, fed from the interface by the mapping."
    VERSION: ClassVar[str] = "1"
    REVISION: ClassVar[str] = "0"
    Datapoint: Dict[str, Datapoint_t] = {}
    Measurements: Optional[Measurements_t] = None

# alias so field ``RelativeTo_t`` can name a class of the same id_short
RelativeTo_t: TypeAlias = RelativeTo
# alias so field ``X_t`` can name a class of the same id_short
X_t: TypeAlias = X
# alias so field ``Y_t`` can name a class of the same id_short
Y_t: TypeAlias = Y
# alias so field ``Z_t`` can name a class of the same id_short
Z_t: TypeAlias = Z
# alias so field ``Roll_t`` can name a class of the same id_short
Roll_t: TypeAlias = Roll
# alias so field ``Pitch_t`` can name a class of the same id_short
Pitch_t: TypeAlias = Pitch
# alias so field ``Yaw_t`` can name a class of the same id_short
Yaw_t: TypeAlias = Yaw
# alias so field ``CoordinateSource_t`` can name a class of the same id_short
CoordinateSource_t: TypeAlias = CoordinateSource
# alias so field ``Coordinate_t`` can name a class of the same id_short
Coordinate_t: TypeAlias = Coordinate
# alias so field ``Coordinates_t`` can name a class of the same id_short
Coordinates_t: TypeAlias = Coordinates
# alias so field ``Datapoint_t`` can name a class of the same id_short
Datapoint_t: TypeAlias = Datapoint
# alias so field ``Measurements_t`` can name a class of the same id_short
Measurements_t: TypeAlias = Measurements
# ── Resolve forward references (Pydantic circular refs) ──
Datapoint.model_rebuild()
RelativeTo.model_rebuild()
X.model_rebuild()
Y.model_rebuild()
Z.model_rebuild()
Roll.model_rebuild()
Pitch.model_rebuild()
Yaw.model_rebuild()
CoordinateSource.model_rebuild()
Coordinate.model_rebuild()
Coordinates.model_rebuild()
Measurements.model_rebuild()
OperationalData.model_rebuild()
