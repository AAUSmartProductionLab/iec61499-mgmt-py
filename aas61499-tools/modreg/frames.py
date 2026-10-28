"""Where things are (ARSO 0.12; docs/locations-and-layout.md): the frames along the Hierarchical
Structures of a line's, a module's and its parts' AASs, composed.

A Node's Frame is the pose of its part (or point of interest) in its parent's frame: a translation X,
Y, Z in mm and rotations RX, RY, RZ in degrees about the parent's X, then Y, then Z axis, so the
rotation is Rz Ry Rx (the order is to be checked against IEC 62714's statement of AutomationML's
Frame). Poses compose along the tree: a point of a module in the line's frame is the module's pose in
the line times the point's pose in the module; in the planar table's frame it is that, seen from the
table's pose in the line.

    where(envs, "FillingLineAAS", "FillingModule", "Transfer")                  # in the line's frame
    relative(envs, "FillingLineAAS", ["PlanarTable"], ["FillingModule", "Transfer"])   # in the table's
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from modsync.aasjson import at, children, submodel


@dataclass(frozen=True)
class Pose:
    """A rigid transform as a 4x4 matrix, row by row."""
    m: tuple[tuple[float, float, float, float], ...]

    @classmethod
    def of(cls, x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0) -> Pose:
        a, b, c = (math.radians(v) for v in (rx, ry, rz))
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
        """The rotation about Z, in degrees (what a shuttle's Rz is)."""
        return round(math.degrees(math.atan2(self.m[1][0], self.m[0][0])), 6)


IDENTITY = Pose.of()


def frame_of(node: dict) -> Pose:
    """The pose a Node states (none stated: where its parent is)."""
    frame = at(node, "Frame")
    if frame is None:
        return IDENTITY
    value = lambda name: float((at(frame, name) or {}).get("value") or 0.0)            # noqa: E731
    return Pose.of(value("X"), value("Y"), value("Z"), value("RX"), value("RY"), value("RZ"))


def _env(envs: list[dict], key: str) -> dict:
    """The environment of the AAS named (idShort) or of the asset (globalAssetId) ``key``."""
    for env in envs:
        shell = env["assetAdministrationShells"][0]
        if key in (shell["idShort"], shell["id"], shell["assetInformation"].get("globalAssetId")):
            return env
    raise KeyError(f"no AAS {key}")


def where(envs: list[dict], root: str, *path: str) -> Pose:
    """The pose of the part or point at ``path`` (idShorts of Nodes, one AAS after the other: a
    module of the line, then a point of the module) in the frame of the AAS ``root``."""
    env, pose = _env(envs, root), IDENTITY
    for i, name in enumerate(path):
        entry = at(submodel(env, "HierarchicalStructures"), "EntryNode")
        node = next((n for n in children(entry) if n.get("idShort") == name), None)
        if node is None:
            raise KeyError(f"{env['assetAdministrationShells'][0]['idShort']} has no part or point {name}")
        pose = pose @ frame_of(node)
        if i + 1 < len(path):
            env = _env(envs, node.get("globalAssetId") or "")                       # into the part's own AAS
    return pose


def relative(envs: list[dict], root: str, frame: list[str], path: list[str]) -> Pose:
    """The pose of ``path`` in the frame of ``frame`` (both from ``root``): a module's point in the
    planar table's frame, say."""
    return where(envs, root, *frame).inverse() @ where(envs, root, *path)
