"""A requirement's bounds over time are kept or refused, never assumed (9 Nov): a bound on something
the module states nothing about, or a formula the checks at the events cannot follow, is refused by
the planner and reported by the checker; a pair whose rates can both be set is planned."""
from pathlib import Path
import sys

import pytest

from modgen.spec import Composite
from modplan.check import check
from modplan.domain import Constraint, Parameter
from modplan.expression import parse
from modplan.plan import NoPlan, plan, start_state

sys.path.insert(0, str(Path(__file__).parent))
from test_modplan import filling                                                    # noqa: E402
from test_modplan_tracking import SYRINGE, bottom_up                                # noqa: E402

VALUES = {"FillVolume": 1.0, **SYRINGE}


def without_formula():
    """The filling module as if its Dosing did not state how deep the needle is in the liquid."""
    base = filling()
    dosing = base.capabilities["Dosing"]
    dosing.invariant[:] = [c for c in dosing.invariant if c.var.meaning != "OutletImmersion"]
    return bottom_up(base)


def test_a_bound_on_what_the_module_never_states_is_refused():
    with pytest.raises(NoPlan, match="OutletImmersion"):
        plan(without_formula(), "BottomUpFilling", VALUES)


def test_the_checker_reports_a_bound_no_step_says_anything_about():
    """Before 9 Nov this plain filling passed as filling from the bottom: the bound was never checked."""
    domain = without_formula()
    skill = Composite(execute=[{"MoveAxis": {"Position": 40.0}}, {"Dispense": {"Volume": 1.0}}, "Home"])
    found = check(domain, skill, start=start_state(domain, "BottomUpFilling", VALUES),
                  task=domain.capabilities["BottomUpFilling"], values=VALUES)
    assert any("no step says what" in f.what and "OutletImmersion" in f.what for f in found)


def test_a_nonlinear_formula_is_refused_when_bounds_are_kept_over_time():
    domain = bottom_up()
    dosing = domain.capabilities["Dosing"]
    dosing.invariant[:] = [Constraint(c.prop, c.var, parse("= ContentVolume * ContentVolume", "Invariant"))
                           if c.var.meaning == "OutletImmersion" else c for c in dosing.invariant]
    with pytest.raises(NoPlan, match="not linear"):
        plan(domain, "BottomUpFilling", VALUES)


def test_when_both_rates_can_be_set_the_dose_follows_the_axis():
    """The axis's Speed a parameter too: the pump's rate is set to follow it, the axis at its default.
    Before 9 Nov such a pair was refused unless the two defaults happened to match."""
    base = filling()
    positioning = base.capabilities["Positioning"]
    positioning.parameters["Speed"] = Parameter(1.0, 25.0, positioning.values.pop("Speed"))
    steps = plan(bottom_up(base), "BottomUpFilling", VALUES)
    paired = next(step for step in steps if step.along)
    assert paired.args["FlowRate"] == pytest.approx(0.396, abs=1e-3)


def test_when_only_the_axis_can_be_set_it_follows_the_dose():
    """The pump's flow rate fixed at 0.5 mL/s and the axis's Speed a parameter: the axis is set to rise
    as fast as the liquid does, 0.5 mL/s over the barrel's 31.67 mm2."""
    base = filling()
    dosing, positioning = base.capabilities["Dosing"], base.capabilities["Positioning"]
    dosing.parameters.pop("FlowRate")
    dosing.values["FlowRate"] = 0.5
    positioning.parameters["Speed"] = Parameter(1.0, 25.0, positioning.values.pop("Speed"))
    steps = plan(bottom_up(base), "BottomUpFilling", VALUES)
    paired = next(step for step in steps if step.along)
    assert paired.along[0].args["Speed"] == pytest.approx(500 / 31.669, abs=1e-2)
