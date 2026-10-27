"""The planner and the checker on the filling module (docs/skill-planning.md, sections 4 and 10).

The domain is written here as the module's Capability Description is to state it: the vocabulary's
constraints of each capability, and what holds on this module (the needle in the vial while the
pump doses, out of it and still while the scale weighs). The module's own skills are the ground
truth: Dispensing (the spec), DoubleDose, Checked and Ready (the tests of rule set 2).
"""
from pathlib import Path

import pytest

from modgen import load
from modgen.spec import Composite, Parallel, Step

from modplan.check import check
from modplan.domain import PRODUCT, Capability, Constraint, Domain, Parameter, Var
from modplan.expression import parse
from modplan.lift import flow
from modplan.plan import NoPlan, Planned, plan, reach

SPECS = Path(__file__).resolve().parents[2] / "cell" / "modules"
AXIS = Var("LinearAxis_ActualPosition", "Position")
HOMED = Var("LinearAxis_Homed", "Referenced")
TARED = Var("Scale", "Tared")
WEIGHT = Var("Scale_Weight", "Weight")
CONTENT, WEIGHED = Var(PRODUCT, "ContentVolume"), Var(PRODUCT, "Weighed")


def said(kind: str, prop: str, var: Var, text: str) -> Constraint:
    return Constraint(prop, var, parse(text, kind))


def filling(dose: float = 10.0, needle_in_vial: bool = True, scale: bool = True) -> Domain:
    """The filling module's domain; ``dose``: the largest dose of the pump."""
    caps = [
        Capability("Referencing", "Referencing", "Home", "LinearAxis",
                   post=[said("Post", "Referenced", HOMED, "= true"), said("Post", "Position", AXIS, "= 0.0")]),
        Capability("Positioning", "Positioning", "MoveAxis", "LinearAxis", parameters={"Position": Parameter(0.0, 60.0, 0.0)},
                   pre=[said("Pre", "Referenced", HOMED, "= true")], post=[said("Post", "Position", AXIS, "given")]),
        Capability("Dosing", "Dosing", "Dispense", "Pump",
                   parameters={"Volume": Parameter(0.5, dose, 1.0), "FlowRate": Parameter(0.1, 5.0, 1.0)},
                   values={"FillPosition": 40.0},
                   pre=[said("Pre", "NeedlePosition", AXIS, "= FillPosition")] if needle_in_vial else [],
                   post=[said("Post", "ContentVolume", CONTENT, "+= Volume"), said("Post", "Weighed", WEIGHED, "= false")],
                   invariant=[said("Invariant", "NeedlePosition", AXIS, "unchanged")]),
    ]
    if scale:
        caps += [
            Capability("Taring", "Taring", "Tare", "Scale", post=[said("Post", "Tared", TARED, "= true")]),
            Capability("Weighing", "Weighing", "Weigh", "Scale",
                       pre=[said("Pre", "Tared", TARED, "= true"), said("Pre", "NeedlePosition", AXIS, "= 0.0")],
                       post=[said("Post", "Weight", WEIGHT, "measured"), said("Post", "Weighed", WEIGHED, "= true")],
                       invariant=[said("Invariant", "NeedlePosition", AXIS, "unchanged")]),
        ]
    caps.append(Capability("Filling", "Filling", "Dispensing", None, parameters={"FillVolume": Parameter(0.5, 10.0)},
                           pre=[said("Pre", "ContentVolume", CONTENT, "= 0.0")],
                           post=[said("Post", "ContentVolume", CONTENT, "= FillVolume")],
                           results={"FillWeight": [said("Pre", "Weighed", WEIGHED, "= true")]}))
    domain = Domain("Filling", {cap.name: cap for cap in caps})
    domain.rest = domain.after([("Home", {}), ("Tare", {})])
    return domain


def skills_of(plan_: list[Planned], domain: Domain) -> list[tuple]:
    return [(domain.capabilities[p.capability].skill, p.args) for p in plan_]


def test_the_rest_state_follows_from_the_reset_procedure():
    """T1: Reset is Home and Tare; from nothing known the planner reaches the same, at once."""
    domain = filling()
    assert domain.rest == {HOMED: True, AXIS: 0.0, TARED: True}
    steps = reach(domain, list(domain.rest.items()))
    assert sorted(s.capability for s in steps) == ["Referencing", "Taring"]
    (both,) = Composite(execute=flow(domain, steps)).execute
    assert isinstance(both, Parallel) and sorted(b[0].skill for b in both.branches) == ["Home", "Tare"]


def test_filling_with_its_weight_is_planned_as_dispensing_is_written():
    """T2: needle down, dispense, home (the needle out of the vial), weigh: the module's Dispensing."""
    domain = filling()
    steps = plan(domain, "Filling", {"FillVolume": 2.0}, ("FillWeight",))
    assert skills_of(steps, domain) == [("MoveAxis", {"Position": 40.0}), ("Dispense", {"Volume": 2.0, "FlowRate": 1.0}),
                                        ("Home", {}), ("Weigh", {})]
    execute = Composite(execute=flow(domain, steps)).execute
    assert all(isinstance(node, Step) for node in execute)
    assert [(s.skill, s.bind) for s in execute] == [(skill, args) for skill, args in skills_of(steps, domain)]


def test_filling_without_its_weight_does_not_weigh():
    """T3: nobody asked for the weight, so nothing is weighed; the needle still goes back up (rest)."""
    domain = filling()
    assert [s for s, _ in skills_of(plan(domain, "Filling", {"FillVolume": 2.0}), domain)] == ["MoveAxis", "Dispense", "Home"]


def test_the_fill_position_comes_from_the_module():
    """T4: the fill position is a value of the module's Dosing; changed there, the plan follows."""
    domain = filling()
    domain.capabilities["Dosing"].values["FillPosition"] = 35.0
    assert skills_of(plan(domain, "Filling", {"FillVolume": 2.0}), domain)[0] == ("MoveAxis", {"Position": 35.0})


def test_a_volume_above_one_dose_is_dosed_twice():
    """T5: with doses of at most 1.0 mL, 2.0 mL is two equal doses, as DoubleDose does it."""
    domain = filling(dose=1.0)
    steps = skills_of(plan(domain, "Filling", {"FillVolume": 2.0}, ("FillWeight",)), domain)
    assert steps == [("MoveAxis", {"Position": 40.0}), ("Dispense", {"Volume": 1.0, "FlowRate": 1.0}),
                     ("Dispense", {"Volume": 1.0, "FlowRate": 1.0}), ("Home", {}), ("Weigh", {})]
    assert [s.name for s in Composite(execute=flow(domain, plan(domain, "Filling", {"FillVolume": 2.0}))).execute] == [
        "MoveAxis", "Dispense", "Dispense_2", "Home"]


def test_without_a_scale_the_weight_cannot_be_had():
    """T11: a module without a scale fills, but cannot give the fill weight."""
    domain = filling(scale=False)
    assert [s for s, _ in skills_of(plan(domain, "Filling", {"FillVolume": 2.0}), domain)] == ["MoveAxis", "Dispense", "Home"]
    with pytest.raises(NoPlan):
        plan(domain, "Filling", {"FillVolume": 2.0}, ("FillWeight",))


def test_without_the_needle_in_the_vial_the_plan_fills_with_the_needle_up():
    """T12: what holds on the module carries the meaning; without it a plan is valid and wrong."""
    domain = filling(needle_in_vial=False)
    assert [s for s, _ in skills_of(plan(domain, "Filling", {"FillVolume": 2.0}), domain)] == ["Dispense"]


def test_a_full_container_is_not_filled():
    domain = filling()
    with pytest.raises(NoPlan, match="ContentVolume"):
        plan(domain, "Filling", {"FillVolume": 2.0}, start={**domain.rest, CONTENT: 1.0})


# The checker ----------------------------------------------------------------------------------

DOUBLE_DOSE = {"parameters": {"Dose": {"unit": "mL", "minimum": 0.5, "maximum": 10.0, "default": 0.5}},
               "execute": [{"MoveAxis": {"Position": 40.0}, "as": "NeedleDown"}, {"Dispense": {"Volume": "Dose", "FlowRate": 1.0}},
                           {"Dispense": {"Volume": "Dose", "FlowRate": 1.0}}, {"MoveAxis": {"Position": 0.0}, "as": "NeedleUp"}, "Weigh"]}
CHECKED = {"parameters": {"Volume": {"unit": "mL", "minimum": 0.5, "maximum": 10.0, "default": 1.0}},
           "execute": [{"MoveAxis": {"Position": 40.0}, "as": "NeedleDown"}, {"Dispense": {"Volume": "Volume", "FlowRate": 1.0}}, "Weigh",
                       {"if": {"operand": "Weigh.Weight", "op": "lt", "value": 2.5},
                        "then": [{"Dispense": {"Volume": 0.5, "FlowRate": 1.0}, "as": "TopUp"}], "else": [{"Weigh": {}, "as": "Fine"}]},
                       {"if": {"operand": "Weigh.Weight", "op": "lt", "value": 1.0}, "then": [{"Weigh": {}, "as": "Again"}]},
                       "Home"]}
READY = {"execute": [{"parallel": [["Home"], ["Tare"]], "as": "Both"}]}


def test_the_modules_skills_pass_the_check_but_checked():
    """T8: Dispensing, DoubleDose and Ready need nothing that does not hold; Checked weighs with the
    needle still in the vial (it was written to try decisions out)."""
    domain = filling()
    assert check(domain, load(SPECS / "filling.yaml").composites["Dispensing"]) == []
    assert check(domain, Composite(**DOUBLE_DOSE)) == []
    assert check(domain, Composite(**READY)) == []
    found = check(domain, Composite(**CHECKED))
    assert [f.step for f in found] == ["Weigh", "Fine", "Again"]
    assert "needs LinearAxis_ActualPosition.Position = 0.0, but it is 40.0" in found[0].what
    assert "Home" in found[0].fix


def test_a_missing_step_is_found_with_the_step_that_makes_it_hold():
    """T6: Dispensing without NeedleDown doses with the needle up; moving it to 40 mm first fixes it."""
    domain = filling()
    skill = load(SPECS / "filling.yaml").composites["Dispensing"]
    without = Composite(**{**skill.model_dump(), "execute": [n.model_dump() for n in skill.execute[1:]]})
    (finding,) = check(domain, without)
    assert finding.step == "Dispense" and "Position = 40.0, but it is 0.0" in finding.what
    assert finding.fix == ("MoveAxis(Position=40.0)",)


def test_weighing_while_the_axis_moves_is_found():
    """T7: Home and Weigh at once: the scale is read while the needle moves."""
    found = check(filling(), Composite(execute=[{"parallel": [["Home"], ["Weigh"]], "as": "Both"}]))
    assert [(f.step, "cannot run at the same time" in f.what) for f in found] == [("Weigh", True)]


def test_a_skill_that_does_not_end_at_rest_is_found():
    found = check(filling(), Composite(execute=[{"MoveAxis": {"Position": 40.0}}]))
    assert [f.step for f in found] == ["end"] and "Home" in found[0].fix
