"""Where things are (docs/locations-and-layout.md): the coordinates in the Variables of a line's AASs
(aas-model's ``Measurements/Coordinates``), composed along their references.

A coordinate (Measurements/Coordinates/<name>) is a pose relative to the coordinate its RelativeTo
names, in this AAS or another: a translation X, Y, Z in mm and rotations Roll, Pitch, Yaw in degrees
about the parent's fixed X, then Y, then Z axis, so the rotation is Rz(Yaw) Ry(Pitch) Rx(Roll), as
ROS's RPY. The references make a tree rooted at the planar table's base (a coordinate without
RelativeTo): a module's base is relative to it, the module's points and mounts to the module's base,
an end effector to its mount. A coordinate that moves names the variable each moving value is
(XSource ... YawSource); its values here are the latest known.

    where(envs, "FillingModuleAAS", "Transfer")                     # in the root's frame (the table's)
    relative(envs, ("PlanarTableAAS", "TableBase"), ("FillingModuleAAS", "Transfer"))
    place(env, "ModuleBase", ("PlanarTableAAS", "TableBase"), Location(x=240.0, y=720.0, rz=180.0))
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import math

from aas_model.submodel_templates.coordinates import VAR_RELATIVE_TO as RELATIVE_TO
from modsync.aasjson import at, children, submodel

VALUES = ("X", "Y", "Z", "Roll", "Pitch", "Yaw")
UNITS = {"X": "mm", "Y": "mm", "Z": "mm", "Roll": "deg", "Pitch": "deg", "Yaw": "deg"}


@dataclass(frozen=True)
class Pose:
    """A rigid transform as a 4x4 matrix, row by row."""
    m: tuple[tuple[float, float, float, float], ...]

    @classmethod
    def of(cls, x=0.0, y=0.0, z=0.0, roll=0.0, pitch=0.0, yaw=0.0) -> Pose:
        a, b, c = (math.radians(v) for v in (roll, pitch, yaw))
        ca, sa, cb, sb, cc, sc = math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(c), math.sin(c)
        # Rz(c) Ry(b) Rx(a)
        r = ((cc * cb, cc * sb * sa - sc * ca, cc * sb * ca + sc * sa),
             (sc * cb, sc * sb * sa + cc * ca, sc * sb * ca - cc * sa),
             (-sb, cb * sa, cb * ca))
        return cls(((*r[0], x), (*r[1], y), (*r[2], z), (0.0, 0.0, 0.0, 1.0)))

    def __matmul__(self, other: Pose) -> Pose:
        return Pose(tuple(tuple(sum(self.m[i][k] * other.m[k][j] for k in range(4)) for j in range(4)) for i in range(4)))

    def inverse(self) -> Pose:
        r = [[self.m[j][i] for j in range(3)] for i in range(3)]                     # the transpose
        t = [-sum(r[i][k] * self.m[k][3] for k in range(3)) for i in range(3)]
        return Pose(tuple((*r[i], t[i]) for i in range(3)) + ((0.0, 0.0, 0.0, 1.0),))

    @property
    def position(self) -> tuple[float, float, float]:
        return tuple(round(self.m[i][3], 6) for i in range(3))

    @property
    def heading(self) -> float:
        """The rotation about Z, in degrees (what a shuttle's Yaw is)."""
        return round(math.degrees(math.atan2(self.m[1][0], self.m[0][0])), 6)


IDENTITY = Pose.of()


def _env(envs: list[dict], key: str) -> dict:
    """The environment of the AAS named (idShort), identified (id) or of the asset (globalAssetId)
    ``key``, or of the AAS one of whose submodels has the id ``key``."""
    for env in envs:
        shell = env["assetAdministrationShells"][0]
        if key in (shell["idShort"], shell["id"], shell["assetInformation"].get("globalAssetId")) \
                or any(s.get("id") == key for s in env.get("submodels", [])):
            return env
    raise KeyError(f"no AAS {key}")


def coordinates(env: dict) -> dict[str, dict]:
    """The coordinates of an AAS, by name."""
    found = at(submodel(env, "Variables") or {}, "Measurements", "Coordinates")
    return {c["idShort"]: c for c in children(found)} if found else {}


def pose_of(coordinate: dict) -> Pose:
    value = lambda name: float((at(coordinate, name) or {}).get("value") or 0.0)          # noqa: E731
    return Pose.of(*(value(name) for name in VALUES))


def parent_of(coordinate: dict) -> tuple[str, str] | None:
    """What a coordinate is relative to: (the id of the submodel it is in, its name); None: a root."""
    ref = at(coordinate, "RelativeTo")
    keys = ((ref or {}).get("value") or {}).get("keys") or []
    if not keys:
        return None
    return keys[0]["value"], keys[-1]["value"]


def chain(envs: list[dict], aas: str, name: str) -> list[tuple[str, str]]:
    """The coordinate (``aas``, ``name``) and those it is relative to, up to the root."""
    env, found = _env(envs, aas), []
    while True:
        here = (env["assetAdministrationShells"][0]["idShort"], name)
        if here in found:
            raise ValueError(f"the coordinates are relative to each other in a circle: {found + [here]}")
        coordinate = coordinates(env).get(name)
        if coordinate is None:
            raise KeyError(f"{here[0]} has no coordinate {name}")
        found.append(here)
        parent = parent_of(coordinate)
        if parent is None:
            return found
        env, name = _env(envs, parent[0]), parent[1]


def where(envs: list[dict], aas: str, name: str) -> Pose:
    """The pose of the coordinate ``name`` of the AAS ``aas`` in the frame of its tree's root (the
    planar table's base)."""
    pose = IDENTITY
    for at_aas, at_name in chain(envs, aas, name):
        pose = pose_of(coordinates(_env(envs, at_aas))[at_name]) @ pose
    return pose


def relative(envs: list[dict], frame: tuple[str, str], point: tuple[str, str]) -> Pose:
    """The pose of ``point`` in the frame of ``frame``, both (AAS, coordinate): a module's point in
    the planar table's frame, say. Both must be in the same tree."""
    if chain(envs, *frame)[-1] != chain(envs, *point)[-1]:
        raise ValueError(f"{frame} and {point} are not in one tree of coordinates")
    return where(envs, *frame).inverse() @ where(envs, *point)


def place(env: dict, name: str, parent: tuple[str, str] | None, location) -> dict:
    """A copy of ``env`` with its coordinate ``name`` at ``location`` (with x, y, z, rx, ry, rz)
    relative to ``parent`` (the id of the AAS it is in and its name): how a module reports where it
    has been put."""
    env = copy.deepcopy(env)
    coordinate = coordinates(env)[name]
    for value, given in zip(VALUES, (location.x, location.y, location.z, location.rx, location.ry, location.rz)):
        at(coordinate, value)["value"] = repr(float(given))
    coordinate["value"] = [e for e in coordinate["value"] if e.get("idShort") != "RelativeTo"]
    if parent is not None:
        coordinate["value"].insert(0, {
            "idShort": "RelativeTo", "modelType": "ReferenceElement",
            "semanticId": {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": RELATIVE_TO}]},
            "value": {"type": "ModelReference", "keys": [
                {"type": "Submodel", "value": f"{parent[0]}/submodels/Variables"},
                {"type": "SubmodelElementCollection", "value": "Measurements"},
                {"type": "SubmodelElementCollection", "value": "Coordinates"},
                {"type": "SubmodelElementCollection", "value": parent[1]}]}})
    return env
