"""The second module: Stoppering planned from the stoppering module's AAS is the module's own skill
(head down on the vial, press, head up again), and that skill passes the check."""
from pathlib import Path

from modgen import load
from modsync.described import described

from modplan.check import check
from modplan.plan import plan
from modplan.read import read

from modreg import model, profile as profiles

SPECS = Path(__file__).resolve().parents[2] / "cell" / "modules"


def test_stoppering_is_planned_as_the_module_does_it():
    envs = [model.build(p) for p in profiles.describe_all(load(SPECS / "stoppering.yaml"), "pi")]
    domain = read(envs[0], envs[1:])
    steps = plan(domain, "Stoppering", {})
    assert [(domain.capabilities[s.capability].skill, s.args) for s in steps] == [
        ("MoveAxis", {"Position": 40.0}), ("PressStopper", {}), ("Home", {})]
    assert check(domain, described(envs[0], envs[1:]).composites["Stoppering"]) == []
