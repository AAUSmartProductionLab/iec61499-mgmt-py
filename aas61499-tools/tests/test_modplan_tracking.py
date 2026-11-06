"""Planning in time (6 Nov): a requirement that bounds a quantity a formula defines (how deep the needle
is in the liquid) is kept by pairing the step that changes it at a rate (the dose) with one that
moves another state of the formula alongside (the needle rising with the liquid), at rates set so
that the quantity stays as it is. Nothing of it is about filling: the pair, the rates and where the
needle starts follow from the formula, the rates and the bounds the domain states."""
import math
from pathlib import Path
import sys

import pytest

from modgen.spec import Composite, Parallel, Step

from modplan.check import check, timed
from modplan.discover import task
from modplan.domain import Domain
from modplan.lift import flow
from modplan.plan import NoPlan, plan, start_state
from modplan.vocabulary import Vocabulary

sys.path.insert(0, str(Path(__file__).parent))
from test_modplan import AXIS, CONTENT, filling                                       # noqa: E402

SYRINGE = {"InnerDiameter": 6.35, "InnerBottomHeight": 11.0, "RimHeight": 66.0, "MinImmersion": -2.0, "MaxImmersion": 3.0}
AREA = math.pi * 6.35 ** 2 / 4                                                     # mm2, the barrel's cross-section


def bottom_up(base: Domain | None = None) -> Domain:
    """The module's domain with BottomUpFilling, as the vocabulary defines it, as a task."""
    base = base or filling()
    return Domain(base.module, {**base.capabilities, "BottomUpFilling": task(Vocabulary(), "BottomUpFilling")}, base.rest)


def test_filling_from_the_bottom_is_planned_with_the_needle_rising_alongside():
    """1 mL into the 1 mL syringe: the needle 1.5 mm above the barrel's bottom (between the 2 mm the
    product allows above the liquid and the 1 mm the module keeps above the bottom), then the dose with
    the needle rising 31.6 mm at the axis's 12.5 mm/s, the flow rate set to what that keeps up with."""
    domain = bottom_up()
    values = {"FillVolume": 1.0, **SYRINGE}
    steps = plan(domain, "BottomUpFilling", values, ("FillWeight",))
    assert [str(s) for s in steps] == [
        "Positioning(Position=57.5)", "Dosing(FlowRate=0.396, Volume=1.0) with Positioning(Position=25.934)",
        "Referencing()", "Weighing()"]
    assert steps[1].args["FlowRate"] == pytest.approx(12.5 * AREA / 1000, abs=5e-4)
    deep, rising, home, weigh = Composite(execute=flow(domain, steps)).execute
    assert isinstance(rising, Parallel) and [[s.skill for s in b] for b in rising.branches] == [["Dispense"], ["MoveAxis"]]
    start = start_state(domain, "BottomUpFilling", values)
    assert check(domain, Composite(execute=flow(domain, steps)), start=start, task=domain.capabilities["BottomUpFilling"],
                 values=values) == []
    _, took = timed(domain, Composite(execute=flow(domain, steps)), start=start)
    assert took == pytest.approx(57.5 / 12.5 + 1.0 / 0.396 + 25.934 / 12.5 + 0.2, abs=1e-3)


def test_plain_filling_is_planned_as_before():
    """Without the bounds nothing is tracked: the vial is filled as Dispensing does it."""
    domain = bottom_up()
    assert [str(s) for s in plan(domain, "Filling", {"FillVolume": 1.0}, ("FillWeight",))] == [
        "Positioning(Position=40.0)", "Dosing(FlowRate=1.0, Volume=1.0)", "Referencing()", "Weighing()"]


@pytest.mark.parametrize("volume, top", [(0.5, 41.717), (0.75, 33.826)])
def test_less_is_a_shorter_rise(volume, top):
    steps = plan(bottom_up(), "BottomUpFilling", {"FillVolume": volume, **SYRINGE})
    assert steps[1].along[0].args["Position"] == top and steps[1].args["FlowRate"] == 0.396


def test_a_dose_the_pump_cannot_give_is_not_tracked_either():
    """0.25 mL is below the pump's least dose (0.5 mL): no plan, tracked or not (Q4b found it planned)."""
    with pytest.raises(NoPlan):
        plan(bottom_up(), "BottomUpFilling", {"FillVolume": 0.25, **SYRINGE})


def test_the_checker_says_an_argument_beyond_its_range():
    domain = filling()
    skill = Composite(execute=[{"MoveAxis": {"Position": 40.0}, "as": "In"}, {"Dispense": {"Volume": 0.25, "FlowRate": 1.0}}, "Home"])
    assert [str(f) for f in check(domain, skill)] == ["Dispense: Volume = 0.25 is beyond its range (0.5 to 10.0)"]


def test_a_station_raised_too_high_cannot_fill_from_the_bottom():
    """Raised by 5 mm, the barrel's bottom is 64 mm down and the axis reaches 60: the needle cannot get
    within 2 mm of the bottom, so there is no plan (Q4b: the module does not offer it there)."""
    base = filling()
    for name in ("Positioning", "Dosing"):
        base.capabilities[name].values["NestPosition"] = 75.0
    with pytest.raises(NoPlan):
        plan(bottom_up(base), "BottomUpFilling", {"FillVolume": 1.0, **SYRINGE})


def test_with_a_fixed_flow_rate_the_rates_do_not_meet():
    """The axis's speed is fixed; if the pump's flow rate were too, they would have to match."""
    base = filling()
    dosing = base.capabilities["Dosing"]
    dosing.parameters.pop("FlowRate")
    dosing.values["FlowRate"] = 1.0
    with pytest.raises(NoPlan):
        plan(bottom_up(base), "BottomUpFilling", {"FillVolume": 1.0, **SYRINGE})


def test_where_the_needle_starts_follows_from_the_bounds():
    """A narrower band (at most 1.5 mm above the liquid) leaves 57.5 to 58 mm to start from, and the needle
    starts in its middle; a band the bottom clearance leaves no room for (the tip in the liquid from the
    start) has no plan."""
    steps = plan(bottom_up(), "BottomUpFilling", {"FillVolume": 0.5, **SYRINGE, "MinImmersion": -1.5, "MaxImmersion": 1.0})
    assert steps[0].args["Position"] == pytest.approx(57.75)
    with pytest.raises(NoPlan):
        plan(bottom_up(), "BottomUpFilling", {"FillVolume": 0.5, **SYRINGE, "MinImmersion": 0.0, "MaxImmersion": 1.0})


def test_the_pair_is_ordered_by_both_its_parts():
    """The rising dose uses the pump and the axis: Home (the axis) comes after it, never beside it."""
    domain = bottom_up()
    execute = Composite(execute=flow(domain, plan(domain, "BottomUpFilling", {"FillVolume": 1.0, **SYRINGE}))).execute
    assert [type(n).__name__ for n in execute] == ["Step", "Parallel", "Step"] and isinstance(execute[-1], Step)
    assert execute[-1].skill == "Home"
