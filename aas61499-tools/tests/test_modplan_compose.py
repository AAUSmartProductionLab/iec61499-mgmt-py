"""A planned skill described in the module's AAS and created online (G4), on the stand-in FORTE.

    The same on a real FORTE: test_modplan_live.py.
"""
from pathlib import Path
import sys

import pytest

from modgen import load
from modsync.aasjson import at, submodel
from modsync.described import described
from modsync.desired import reconfigure

from modplan.compose import compose
from modplan.plan import NoPlan

sys.path.insert(0, str(Path(__file__).parent))
from test_modsync import FakeForte, filling                                          # noqa: E402
from test_modsync_desired import aas                                                 # noqa: E402

SPECS = Path(__file__).resolve().parents[2] / "cell" / "modules"


@pytest.fixture(scope="module")
def delivered() -> tuple[dict, list[dict]]:
    return aas(load(SPECS / "filling.yaml"), "pi")


def test_a_planned_skill_is_described_as_the_editor_saves_one(delivered):
    module, components = delivered
    composed = compose(module, components, "Filling", {"FillVolume": 2.0}, ("FillWeight",), name="PlannedFilling")
    skill = at(submodel(composed.module, "Skills"), "PlannedFilling")
    assert at(skill, "Deployment")["value"] == "Described" and at(skill, "Start", "InterfaceReference") is None
    made = described(composed.module, components).composites["PlannedFilling"]
    assert [(s.name, s.skill, s.bind) for s in made.execute] == [
        ("MoveAxis", "MoveAxis", {"Position": 40.0}), ("Dispense", "Dispense", {"FlowRate": 1.0, "Volume": 2.0}),
        ("Home", "Home", {}), ("Weigh", "Weigh", {})]
    assert made.results == {"FillWeight": "Weigh.Weight"}                   # what the scale measured
    assert [s.skill for s in made.stop] == ["Home"]                          # stopped as the module's skills are
    assert submodel(module, "Skills") is not submodel(composed.module, "Skills")   # the AAS given is left as it was


def test_a_planned_skill_is_created_online(delivered):
    module, components = delivered
    composed = compose(module, components, "Filling", {"FillVolume": 2.0}, ("FillWeight",), name="PlannedFilling")
    done, after = reconfigure(FakeForte(filling()), "pi", 61499, composed.module, components)
    assert done[0].startswith("create PlannedFilling: ") and after.differences.empty, done


def test_a_result_the_capability_cannot_give_is_refused(delivered):
    module, components = delivered
    with pytest.raises(NoPlan, match="no result Nothing"):
        compose(module, components, "Filling", {"FillVolume": 2.0}, ("Nothing",))
