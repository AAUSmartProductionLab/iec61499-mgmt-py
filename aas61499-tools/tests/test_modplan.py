"""The planner and the checker on the filling module (docs/skill-planning.md, sections 4 and 10).

The domain is written here as the module's Capability Description is to state it: the vocabulary's
constraints of each capability, and what holds on this module (the needle in the vial while the
pump doses, out of it and still while the scale weighs). The module's own skills are the ground
truth: Dispensing (the spec), DoubleDose, Checked and Ready (the tests of rule set 2).
"""
import copy
import math
from pathlib import Path

import pytest

from modgen import load
from modgen.spec import Composite, Parallel, Step

from modplan.check import check, timed
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


IMMERSION = Var(PRODUCT, "OutletImmersion")
# What the product states of its container (vocabulary 0.10): a 2R vial and the 1 mL syringe, as the
# oracle of Q4 has them (cell/eval/process_model.py), heights above the face it stands on in the nest.
VIAL_2R = {Var(PRODUCT, "InnerDiameter"): 14.0, Var(PRODUCT, "InnerBottomHeight"): 1.0, Var(PRODUCT, "RimHeight"): 35.0}
SYRINGE = {Var(PRODUCT, "InnerDiameter"): 6.35, Var(PRODUCT, "InnerBottomHeight"): 11.0, Var(PRODUCT, "RimHeight"): 66.0}
IMMERSED = "= LinearAxisPosition - NestPosition + InnerBottomHeight + 1000 * ContentVolume / (pi * InnerDiameter * InnerDiameter / 4)"


def filling(dose: float = 10.0, needle_in_vial: bool = True, scale: bool = True) -> Domain:
    """The filling module's domain; ``dose``: the largest dose of the pump. The axis moves at 12.5
    mm/s, the pump at its flow rate, the scale takes its Completion's time (vocabulary 0.10)."""
    geometry = {var.meaning: var for var in VIAL_2R}
    caps = [
        Capability("Referencing", "Referencing", "Home", "LinearAxis", values={"Speed": 12.5},
                   post=[said("Post", "Referenced", HOMED, "= true"), said("Post", "Position", AXIS, "= 0.0")], rates={AXIS: "Speed"}),
        Capability("Positioning", "Positioning", "MoveAxis", "LinearAxis", parameters={"Position": Parameter(0.0, 60.0, 0.0)},
                   values={"NestPosition": 70.0, "BottomClearance": 1.0, "Speed": 12.5},
                   pre=[said("Pre", "Referenced", HOMED, "= true")], post=[said("Post", "Position", AXIS, "given")],
                   invariant=[said("Invariant", "Position", AXIS, "<= NestPosition - InnerBottomHeight - BottomClearance")],
                   rates={AXIS: "Speed"}, variables=dict(geometry)),
        Capability("Dosing", "Dosing", "Dispense", "Pump",
                   parameters={"Volume": Parameter(0.5, dose, 1.0), "FlowRate": Parameter(0.1, 5.0, 1.0)},
                   values={"FillPosition": 40.0, "NestPosition": 70.0, "InsertDepth": 5.0},
                   pre=[said("Pre", "NeedlePosition", AXIS, ">= FillPosition")] if needle_in_vial else [],
                   post=[said("Post", "ContentVolume", CONTENT, "+= Volume"), said("Post", "Weighed", WEIGHED, "= false")],
                   invariant=[said("Invariant", "NeedlePosition", AXIS, ">= NestPosition - RimHeight + InsertDepth"),
                              said("Invariant", "OutletImmersion", IMMERSION, IMMERSED)],
                   rates={CONTENT: "FlowRate"}, after=parse("= Volume / FlowRate"), variables={**geometry, "LinearAxisPosition": AXIS}),
    ]
    if scale:
        caps += [
            Capability("Taring", "Taring", "Tare", "Scale", post=[said("Post", "Tared", TARED, "= true")], after=parse("= 2.0")),
            Capability("Weighing", "Weighing", "Weigh", "Scale",
                       pre=[said("Pre", "Tared", TARED, "= true"), said("Pre", "NeedlePosition", AXIS, "= 0.0")],
                       post=[said("Post", "Weight", WEIGHT, "measured"), said("Post", "Weighed", WEIGHED, "= true")],
                       invariant=[said("Invariant", "NeedlePosition", AXIS, "unchanged")], after=parse("= 0.2")),
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
    assert finding.step == "Dispense" and "Position >= 40.0, but it is 0.0" in finding.what
    assert finding.fix == ("MoveAxis(Position=40.0)",)


def test_weighing_while_the_axis_moves_is_found():
    """T7: Home and Weigh at once, the needle 20 mm down: the scale is read while the needle moves.
    From home, Home does not move the needle, and nothing is said (in time, 6 Nov)."""
    domain, both = filling(), Composite(execute=[{"parallel": [["Home"], ["Weigh"]], "as": "Both"}])
    found = check(domain, both, start={**domain.rest, AXIS: 20.0})
    assert ("Weigh", "keeps LinearAxis_ActualPosition.Position while Home changes it: they cannot run at the same time") in [
        (f.step, f.what) for f in found]
    assert check(domain, both) == []


BOTTOM_UP = {"parameters": {"Volume": {"unit": "mL", "minimum": 0.5, "maximum": 10.0, "default": 1.0}},
             "execute": [{"MoveAxis": {"Position": 58.0}, "as": "NeedleDeep"},
                         {"parallel": [[{"Dispense": {"Volume": "Volume", "FlowRate": 0.7}}],
                                       [{"MoveAxis": {"Position": 40.0}, "as": "NeedleRise"}]], "as": "Rising"},
                         "Home", "Weigh"]}


def test_filling_from_the_bottom_keeps_the_needle_in_the_container():
    """T13: the needle starts deep and rises while the pump doses; it stays at the fill position or
    deeper, so Dosing's invariant holds while the axis moves."""
    assert check(filling(), Composite(**BOTTOM_UP)) == []


def test_a_needle_that_rises_out_of_the_container_while_dosing_is_found():
    """T14: in a 2R vial (its rim 35 mm down, the needle 5 mm below it), rising to 30 mm takes the
    needle out of the container before the dose is in. Without the product, nothing is known of where
    its rim is, and nothing is said."""
    above = copy.deepcopy(BOTTOM_UP)
    above["execute"][1]["parallel"][1][0]["MoveAxis"]["Position"] = 30.0
    above["execute"][1]["parallel"][0][0]["Dispense"]["FlowRate"] = 0.5          # 2 s; the needle passes 40 mm at 1.44 s
    domain = filling()
    (finding,) = check(domain, Composite(**above), start={**domain.rest, **VIAL_2R})
    assert finding.step == "Dispense" and finding.what.endswith(">= 40.0 while NeedleRise changes it")
    assert check(domain, Composite(**above)) == []


def test_in_time_a_dose_that_is_in_before_the_needle_leaves_is_kept():
    """At 0.7 mL/s the dose of 1 mL is in after 1.43 s; rising from 58 mm at 12.5 mm/s, the needle passes
    40 mm at 1.44 s: the bound held all the time the pump ran. Without the speed the checker could only
    take the move's end (30 mm) and refuse it: nine of Q4a's refusals were so (6 Nov)."""
    above = copy.deepcopy(BOTTOM_UP)
    above["execute"][1]["parallel"][1][0]["MoveAxis"]["Position"] = 30.0
    domain = filling()
    assert check(domain, Composite(**above), start={**domain.rest, **VIAL_2R}) == []
    slow = filling()
    slow.capabilities["Positioning"].rates = {}                                     # no speed: not in time
    assert [f.step for f in check(slow, Composite(**above), start={**slow.rest, **VIAL_2R})] == ["Dispense"]


def test_a_skill_takes_as_long_as_its_steps_in_time():
    """Dispensing: 3.2 s down at 12.5 mm/s, 1 s to dose 1 mL, 3.2 s home, 0.2 s to weigh; the bottom-up
    skill's rising dose takes as long as its longer branch."""
    domain = filling()
    _, took = timed(domain, load(SPECS / "filling.yaml").composites["Dispensing"])
    assert took == pytest.approx(3.2 + 1.0 + 3.2 + 0.2)
    _, took = timed(domain, Composite(**BOTTOM_UP))
    assert took == pytest.approx(58 / 12.5 + max(1 / 0.7, 18 / 12.5) + 40 / 12.5 + 0.2)


def test_how_deep_the_needle_is_in_the_liquid_is_kept_as_the_requirement_says():
    """BottomUpFilling of 1 mL into the syringe: the needle 1.5 mm above the barrel's bottom (57.5 mm down)
    and rising with the liquid keeps the tip within 2 mm above and 3 mm below the surface. A needle that
    stays deep goes 30 mm under; one that rises too fast leaves the liquid."""
    domain, task = filling(), _bottom_up()
    bounds = {"MinImmersion": -2.0, "MaxImmersion": 3.0}
    rise = 1000 / (math.pi * 6.35 ** 2 / 4)                                       # 31.6 mm for 1 mL
    flow = 12.5 * (math.pi * 6.35 ** 2 / 4) / 1000                               # the flow rate the axis's speed keeps up with
    tracked = {"execute": [{"MoveAxis": {"Position": 57.5}, "as": "NeedleDeep"},
                           {"parallel": [[{"Dispense": {"Volume": 1.0, "FlowRate": round(flow, 6)}}],
                                         [{"MoveAxis": {"Position": round(57.5 - rise, 6)}, "as": "NeedleRise"}]], "as": "Rising"},
                           "Home", "Weigh"]}
    start = {**domain.rest, **SYRINGE, CONTENT: 0.0}
    assert check(domain, Composite(**tracked), start=start, task=task, values=bounds) == []
    deep = {"execute": [{"MoveAxis": {"Position": 57.5}, "as": "NeedleDeep"}, {"Dispense": {"Volume": 1.0, "FlowRate": 0.4}}, "Home", "Weigh"]}
    (finding,) = check(domain, Composite(**deep), start=start, task=task, values=bounds)
    assert finding.step == "Dispense" and "BottomUpFilling keeps OutletImmersion <= 3.0, but it comes to 30.076" in finding.what
    fast = copy.deepcopy(tracked)
    fast["execute"][1]["parallel"][0][0]["Dispense"]["FlowRate"] = round(flow / 2, 6)
    (finding,) = check(domain, Composite(**fast), start=start, task=task, values=bounds)
    assert "OutletImmersion >= -2.0, but it comes to" in finding.what and finding.step == "Dispense"
    assert check(domain, Composite(**deep), start=start) == []                    # no requirement: nothing to keep


def test_the_needle_does_not_go_into_the_bottom():
    """In the syringe, 59 mm down is its bottom; the needle stays 1 mm above it."""
    domain = filling()
    (finding,) = check(domain, Composite(execute=[{"MoveAxis": {"Position": 59.5}, "as": "TooDeep"}, "Home"]),
                       start={**domain.rest, **SYRINGE})
    assert finding.step == "TooDeep" and finding.what == "keeps LinearAxis_ActualPosition.Position <= 58.0, but it comes to 59.5"


def _bottom_up() -> Capability:
    """BottomUpFilling as the vocabulary defines it: Filling, and the tip kept near the surface."""
    from modplan.discover import task
    from modplan.vocabulary import Vocabulary
    return task(Vocabulary(), "BottomUpFilling")


def test_a_skill_that_does_not_end_at_rest_is_found():
    found = check(filling(), Composite(execute=[{"MoveAxis": {"Position": 40.0}}]))
    assert [f.step for f in found] == ["end"] and "Home" in found[0].fix
