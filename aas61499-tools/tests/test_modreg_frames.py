"""Where things are (ARSO 0.12, H1 and H2): a module's parts and points with their frames in its AAS,
a line's modules in the line's, and a point in any frame the tree reaches."""
import math
from pathlib import Path
import re
import sys

import pytest

from modgen import load
from modsync.aasjson import at, children, submodel

from modreg import model, profile as profiles
from modreg.frames import Pose, relative, where

SPECS = Path(__file__).resolve().parents[2] / "cell" / "modules"
EXAMPLES = SPECS.parent / "examples"
BASE = "https://smartproductionlab.aau.dk"


def close(a, b) -> bool:
    return all(math.isclose(x, y, abs_tol=1e-6) for x, y in zip(a, b))


def test_poses_compose_and_invert():
    turned = Pose.of(100.0, 0.0, 0.0, rz=90.0)
    point = turned @ Pose.of(10.0, 0.0, 0.0)
    assert close(point.position, (100.0, 10.0, 0.0)) and math.isclose(point.heading, 90.0)
    assert close((turned.inverse() @ point).position, (10.0, 0.0, 0.0))
    tilted = Pose.of(rx=90.0) @ Pose.of(0.0, 0.0, 5.0)                                # about X: Z goes to -Y
    assert close(tilted.position, (0.0, -5.0, 0.0))


def test_a_modules_parts_and_points_are_where_its_spec_says():
    envs = [model.build(p) for p in profiles.describe_all(load(SPECS / "filling.yaml"), "pi")]
    entry = at(submodel(envs[0], "HierarchicalStructures"), "EntryNode")
    nodes = {n["idShort"]: n for n in children(entry)}
    transfer = nodes["Transfer"]
    assert transfer["entityType"] == "CoManagedEntity"
    assert transfer["supplementalSemanticIds"][0]["keys"][0]["value"] == f"{BASE}/semantics/TransferPoint"
    frame = at(transfer, "Frame")
    assert at(frame, "X")["semanticId"]["keys"][0]["value"] == "https://admin-shell.io/idta/cds/xframe/1"
    assert {q["type"]: q["value"] for q in at(frame, "RZ")["qualifiers"]} == {"Unit": "deg"}
    spec = load(SPECS / "filling.yaml")
    point = spec.points["Transfer"].location
    assert close(where(envs, "FillingModuleAAS", "Transfer").position, (point.x, point.y, point.z))


@pytest.fixture(scope="module")
def line_envs():
    """The example line's AAS and its resources' (cell/examples/example_line.py)."""
    sys.path.insert(0, str(EXAMPLES))
    try:
        import example_line
        resources, _ = example_line.build()
        return [example_line.line(resources), *resources.values()]
    finally:
        sys.path.remove(str(EXAMPLES))


def test_a_point_of_a_module_in_the_planar_tables_frame(line_envs):
    """The filling module's transfer point, where a shuttle stands to have its vial filled, in the
    frame of the table the shuttle moves on: the shuttle's MoveToPosition target."""
    pose = relative(line_envs, "FillingLineAAS", ["PlanarTable"], ["FillingModule", "Transfer"])
    line_module = where(line_envs, "FillingLineAAS", "FillingModule")
    line_table = where(line_envs, "FillingLineAAS", "PlanarTable")
    expected = line_table.inverse() @ line_module @ where(line_envs, "FillingModuleAAS", "Transfer")
    assert close(pose.position, expected.position) and math.isclose(pose.heading, expected.heading)
    with pytest.raises(KeyError):
        where(line_envs, "FillingLineAAS", "FillingModule", "Nowhere")


def test_the_stations_are_the_simulated_tables(line_envs):
    """The stations of planar-controller/tests/line_scenario.py (X, Y, Rz on the table), from the
    line's layout, its own pick and place points and the modules' transfer points."""
    scenario = SPECS.parents[1] / "planar-controller" / "tests" / "line_scenario.py"
    if not scenario.is_file():
        pytest.skip("the planar-controller submodule is needed")
    stated = dict(re.findall(r'"(\w+)": \(([-0-9., ]+)\)', scenario.read_text(encoding="utf-8").split("STATIONS = {")[1].split("}")[0]))
    sys.path.insert(0, str(EXAMPLES))
    try:
        import example_line
        found = example_line.stations(line_envs)
    finally:
        sys.path.remove(str(EXAMPLES))
    assert found == {name: tuple(float(v) for v in pose.split(",")) for name, pose in stated.items()}
