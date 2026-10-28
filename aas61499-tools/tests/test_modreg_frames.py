"""Where things are: a module's base, mounts, end effectors and points as coordinates in
its Variables, each relative to another by reference, composed up to the planar table's base."""
import math
from pathlib import Path
import re
import sys

import pytest

from modgen import load
from modgen.spec import Location
from modsync.aasjson import at, children, submodel

from modreg import model, profile as profiles
from modreg.frames import Pose, chain, coordinates, place, relative, where

SPECS = Path(__file__).resolve().parents[2] / "cell" / "modules"
EXAMPLES = SPECS.parent / "examples"
BASE = "https://smartproductionlab.aau.dk"


def close(a, b) -> bool:
    return all(math.isclose(x, y, abs_tol=1e-6) for x, y in zip(a, b))


def test_poses_compose_and_invert():
    turned = Pose.of(100.0, 0.0, 0.0, yaw=90.0)
    point = turned @ Pose.of(10.0, 0.0, 0.0)
    assert close(point.position, (100.0, 10.0, 0.0)) and math.isclose(point.heading, 90.0)
    assert close((turned.inverse() @ point).position, (10.0, 0.0, 0.0))
    tilted = Pose.of(roll=90.0) @ Pose.of(0.0, 0.0, 5.0)                              # about X: Z goes to -Y
    assert close(tilted.position, (0.0, -5.0, 0.0))
    # Roll, then pitch, then yaw about the fixed axes: Rz Ry Rx.
    both = Pose.of(roll=90.0, yaw=90.0) @ Pose.of(0.0, 0.0, 5.0)                     # Z -> -Y -> +X
    assert close(both.position, (5.0, 0.0, 0.0))


def test_a_modules_coordinates_are_where_its_spec_says():
    envs = [model.build(p) for p in profiles.describe_all(load(SPECS / "filling.yaml"), "pi")]
    found = coordinates(envs[0])
    assert list(found) == ["ModuleBase", "LinearAxisMount", "LinearAxis", "Transfer", "Fill"]
    transfer = found["Transfer"]
    assert transfer["semanticId"]["keys"][0]["value"] == f"{BASE}/variables/Coordinate/1/0"
    assert transfer["supplementalSemanticIds"][0]["keys"][0]["value"] == f"{BASE}/semantics/TransferPoint"
    assert at(transfer, "X")["semanticId"]["keys"][0]["value"] == "https://admin-shell.io/idta/cds/xframe/1"
    assert {q["type"]: q["value"] for q in at(transfer, "Yaw")["qualifiers"]} == {"Unit": "deg"}
    spec = load(SPECS / "filling.yaml")
    point = spec.points["Transfer"].location
    assert close(where(envs, "FillingModuleAAS", "Transfer").position, (point.x, point.y, point.z))
    # Not placed yet: the module's base is the root of its own tree.
    assert chain(envs, "FillingModuleAAS", "Transfer")[-1] == ("FillingModuleAAS", "ModuleBase")
    # The needle: its mount is fixed (Z down the stroke), the end effector follows the axis' position.
    needle = found["LinearAxis"]
    assert at(needle, "ZSource")["value"]["keys"][-1]["value"] == "LinearAxis_ActualPosition"
    mount = where(envs, "FillingModuleAAS", "LinearAxisMount")
    at_fill = mount @ Pose.of(z=40.0)                                    # the axis 40 mm down: in the vial
    assert close(at_fill.position, where(envs, "FillingModuleAAS", "Fill").position)
    # No point is a part: the bill of material has the components only.
    nodes = children(at(submodel(envs[0], "HierarchicalStructures"), "EntryNode"))
    assert [n["idShort"] for n in nodes] == ["LinearAxis", "Pump", "Scale"] and all("Frame" not in str(n) for n in nodes)


def test_a_module_put_on_the_table_reports_where_its_base_is():
    envs = [model.build(p) for p in profiles.describe_all(load(SPECS / "filling.yaml"), "pi")]
    table = {"assetAdministrationShells": [{"idShort": "T", "id": "urn:t", "assetInformation": {}}],
             "submodels": [{"idShort": "Variables", "id": "urn:t/submodels/Variables", "submodelElements": [
                 {"idShort": "Measurements", "modelType": "SubmodelElementCollection", "value": [
                     {"idShort": "Coordinates", "modelType": "SubmodelElementCollection", "value": [
                         {"idShort": "TableBase", "modelType": "SubmodelElementCollection", "value": []}]}]}]}]}
    placed = place(envs[0], "ModuleBase", ("urn:t", "TableBase"), Location(x=240.0, y=720.0, rz=180.0))
    assert coordinates(envs[0])["ModuleBase"] != coordinates(placed)["ModuleBase"]          # a copy
    world = [table, placed]
    pose = where(world, "FillingModuleAAS", "Transfer")                       # the module turned to face in
    assert close(pose.position, (240.0, 660.0, 0.0)) and math.isclose(abs(pose.heading), 0.0, abs_tol=1e-6)
    assert close(relative(world, ("T", "TableBase"), ("FillingModuleAAS", "Transfer")).position, pose.position)
    with pytest.raises(KeyError):
        where(world, "FillingModuleAAS", "Nowhere")


@pytest.fixture(scope="module")
def line_envs():
    """The example line's AASs: the table, the line and its resources (cell/examples/example_line.py)."""
    sys.path.insert(0, str(EXAMPLES))
    try:
        import example_line
        resources, _ = example_line.build()
        return [example_line.table(), example_line.line(resources), *resources.values()]
    finally:
        sys.path.remove(str(EXAMPLES))


def test_every_coordinate_of_the_line_is_in_one_tree(line_envs):
    """Rooted at the table's base: no other root, no circle."""
    roots = {chain(line_envs, env["assetAdministrationShells"][0]["idShort"], name)[-1]
             for env in line_envs for name in coordinates(env)}
    assert roots == {("PlanarTableAAS", "TableBase")}


def test_the_stations_are_the_simulated_tables(line_envs):
    """The stations of planar-controller/tests/line_scenario.py (X, Y, Rz on the table), from the
    modules' bases on the table, their transfer points and the line's own pick and place points."""
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
