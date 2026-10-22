"""modsync project offline: an IDE project of what runs, against the fake FORTE of test_modsync."""
import xml.etree.ElementTree as ET

from modgen import project_dir
from modsync.compare import expected
from modsync.project import write_project
from modsync.sync import inspect

from test_modsync import FakeForte, composed, filling


def written(forte, tmp_path):
    status = inspect(forte, "pi", 61499, [filling()])
    return write_project(forte, "pi", 61499, status, tmp_path)


def positions(path, app):
    root = ET.parse(path).getroot()
    net = next(a for a in root.iter("Application") if a.get("Name") == app).find("SubAppNetwork")
    return {el.get("Name"): (el.get("x"), el.get("y")) for el in net if el.tag in ("FB", "SubApp", "Group")}


def test_a_module_in_step_with_its_spec_gives_the_repositorys_project(tmp_path):
    project = written(FakeForte(filling()), tmp_path)
    assert project.changes == [] and project.unreproduced == []
    assert project.path == tmp_path / "FillingModule"
    assert expected(project.spec, "pi").fbs == filling().app.fbs
    system = project.path / "FillingModule.sys"
    arranged = project_dir("FillingModule") / "FillingModule.sys"
    assert positions(system, "Filling_pi") == positions(arranged, "Filling_pi")      # the layout from the IDE


def test_a_skill_added_online_and_a_changed_value_are_in_the_project(tmp_path):
    forte = FakeForte(composed())                       # DoubleDose was added online
    forte.values["MoveAxis.Position"] = "25.0"           # and an offered primitive given another default
    project = written(forte, tmp_path)
    assert project.unreproduced == []                   # deploying the project gives what runs
    assert any(c.startswith("DoubleDose: a module level skill the spec does not have") for c in project.changes)
    assert "MoveAxis: other parameter values than the spec's" in project.changes
    assert project.spec.skills["MoveAxis"].parameters["Position"].default == 25.0
    system = project.path / "FillingModule.sys"
    placed = positions(system, "Filling_pi")
    kept = positions(project_dir("FillingModule") / "FillingModule.sys", "Filling_pi")
    assert {k: placed[k] for k in kept} == kept and "DoubleDose" in placed
    assert project.spec.targets["pi"].host == "pi"      # the project's device is the one read


def test_a_project_written_again_takes_the_repositorys_layout_and_keeps_its_own_blocks(tmp_path):
    """The repository's layout wins (it may have been arranged since); a skill only the written
    project has keeps the place it was given there."""
    project = written(FakeForte(composed()), tmp_path)
    system = project.path / "FillingModule.sys"
    doc = ET.parse(system)
    net = next(a for a in doc.getroot().iter("Application") if a.get("Name") == "Filling_pi").find("SubAppNetwork")
    for el in net:
        if el.get("Name") in ("Occupation", "DoubleDose"):
            el.set("x", str(float(el.get("x")) + 777))
    doc.write(system, encoding="utf-8", xml_declaration=True)
    moved = positions(system, "Filling_pi")["DoubleDose"]
    written(FakeForte(composed()), tmp_path)
    placed = positions(system, "Filling_pi")
    kept = positions(project_dir("FillingModule") / "FillingModule.sys", "Filling_pi")
    assert placed["Occupation"] == kept["Occupation"] and placed["DoubleDose"] == moved
