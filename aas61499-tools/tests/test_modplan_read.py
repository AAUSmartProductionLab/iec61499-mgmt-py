"""The planning domain read from a module's AAS alone (G3): it is the domain the design states
(``test_modplan.filling``), and the planner and the checker give the same answers on it."""
from pathlib import Path
import sys

import pytest

from modgen import load
from modgen.spec import Composite
from modsync.described import described

from modplan.check import check
from modplan.plan import plan, reach
from modplan.read import read

from modreg import model, profile as profiles

sys.path.insert(0, str(Path(__file__).parent))
from test_modplan import AXIS, CHECKED, HOMED, TARED, filling as written                      # noqa: E402

SPECS = Path(__file__).resolve().parents[2] / "cell" / "modules"


@pytest.fixture(scope="module")
def envs() -> list[dict]:
    return [model.build(p) for p in profiles.describe_all(load(SPECS / "filling.yaml"), "pi")]


@pytest.fixture(scope="module")
def domain(envs):
    return read(envs[0], envs[1:])


def test_the_domain_read_is_the_one_the_design_states(domain):
    expected = written()
    assert domain.rest == expected.rest == {HOMED: True, AXIS: 0.0, TARED: True}
    assert sorted(domain.capabilities) == sorted(expected.capabilities)
    for name, cap in expected.capabilities.items():
        got = domain.capabilities[name]
        assert (got.skill, got.component) == (cap.skill, cap.component), name
        # The same state and the same expressions (a property may be named otherwise: LinearAxisPosition).
        for kind in ("pre", "post", "invariant"):
            said = lambda c_: {(c.var, str(c.expression)) for c in getattr(c_, kind)}       # noqa: E731
            assert said(got) == said(cap), (name, kind)
    assert domain.capabilities["Dosing"].values == {"FillPosition": 40.0}
    dose = domain.capabilities["Dosing"].parameters["Volume"]
    assert (dose.minimum, dose.maximum, dose.default) == (0.5, 10.0, 1.0)              # the default is the skill's
    assert list(domain.capabilities["Filling"].results) == ["FillWeight"]


def test_the_planner_composes_dispensing_from_the_aas(domain):
    steps = plan(domain, "Filling", {"FillVolume": 2.0}, ("FillWeight",))
    assert [(domain.capabilities[s.capability].skill, s.args) for s in steps] == [
        ("MoveAxis", {"Position": 40.0}), ("Dispense", {"FlowRate": 1.0, "Volume": 2.0}), ("Home", {}), ("Weigh", {})]
    assert sorted(s.capability for s in reach(domain, list(domain.rest.items()))) == ["Referencing", "Taring"]


def test_the_checker_reads_the_skills_from_the_aas(domain, envs):
    """Dispensing as its AAS describes it passes; Checked, described the same way, weighs with the
    needle in the vial."""
    spec = described(envs[0], envs[1:])
    assert check(domain, spec.composites["Dispensing"]) == []
    assert [f.step for f in check(domain, Composite(**CHECKED))] == ["Weigh", "Fine", "Again"]
