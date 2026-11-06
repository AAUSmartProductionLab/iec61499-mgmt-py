"""The constraint language's formulas (6 Nov): linear in what the capabilities change, so that a
condition that holds at the ends of a stretch of constant rates holds all along it; and how long a
capability runs, from its rates or its skill's Completion."""
import math

import pytest

from modplan.domain import PRODUCT, Capability, Constraint, Domain, Parameter, Var
from modplan.expression import Formula, parse

AXIS = Var("LinearAxis_ActualPosition", "Position")
CONTENT, DIAMETER = Var(PRODUCT, "ContentVolume"), Var(PRODUCT, "InnerDiameter")
IMMERSION = Var(PRODUCT, "OutletImmersion")
DEPTH = "LinearAxisPosition - NestPosition + InnerBottomHeight + 1000 * ContentVolume / (pi * InnerDiameter * InnerDiameter / 4)"


def test_a_formula_is_parsed_with_its_names_and_value():
    e = parse(f"= {DEPTH}", "Invariant")
    assert isinstance(e.operand, Formula) and e.named is None
    assert e.names == ("LinearAxisPosition", "NestPosition", "InnerBottomHeight", "ContentVolume", "InnerDiameter")
    values = {"LinearAxisPosition": 57.5, "NestPosition": 70.0, "InnerBottomHeight": 11.0, "ContentVolume": 0.5, "InnerDiameter": 6.35}
    surface = 59.0 - 500.0 / (math.pi * 6.35 ** 2 / 4)
    assert e.operand.value(values.get) == pytest.approx(57.5 - surface)
    assert e.operand.value({**values, "ContentVolume": None}.get) is None        # a value not known
    assert str(e) == f"= {DEPTH}" and parse(str(e)) == e                          # written back as read


@pytest.mark.parametrize("text, value", [("= -2.0", -2.0), ("<= 2 * (3 - 1)", 4.0), ("> -Gap", -1.5), (">= 1e3 / 4", 250.0)])
def test_numbers_signs_and_brackets(text, value):
    e = parse(text, "Pre")
    found = e.operand if isinstance(e.operand, float) else e.operand.value({"Gap": 1.5}.get)
    assert found == value


@pytest.mark.parametrize("text", ["= 2 +", "= (Volume", "= Volume ^ 2", "= 3 Volume", "+= ", "~ 2"])
def test_what_is_not_a_formula_is_refused(text):
    with pytest.raises(ValueError):
        parse(text, "Post")


def test_a_one_name_operand_is_still_a_name():
    assert parse(">= FillPosition").named == "FillPosition"
    assert parse("= pi").operand.value({}.get) == math.pi                        # pi is a constant, not a property


def test_linear_in_what_changes_and_nothing_else_is_refused():
    """The diameter times itself is a constant (nothing changes it); the content times itself is not."""
    immersion = Capability("Dosing", "Dosing", "Dispense", "Pump", post=[Constraint("ContentVolume", CONTENT, parse("+= Volume"))],
                           invariant=[Constraint("OutletImmersion", IMMERSION, parse(f"= {DEPTH}", "Invariant"))],
                           variables={"LinearAxisPosition": AXIS, "InnerDiameter": DIAMETER, "ContentVolume": CONTENT})
    assert Domain("Filling", {"Dosing": immersion}).nonlinear() == []
    squared = Capability("Dosing", "Dosing", "Dispense", "Pump", post=[Constraint("ContentVolume", CONTENT, parse("+= Volume"))],
                         invariant=[Constraint("OutletImmersion", IMMERSION, parse("= ContentVolume * ContentVolume"))])
    (finding,) = Domain("Filling", {"Dosing": squared}).nonlinear()
    assert "not linear in ContentVolume" in finding


def test_a_capability_runs_as_long_as_its_rates_or_its_completion_say():
    move = Capability("Positioning", "Positioning", "MoveAxis", "LinearAxis", parameters={"Position": Parameter(0.0, 60.0, 0.0)},
                      values={"Speed": 12.5}, post=[Constraint("Position", AXIS, parse("given"))], rates={AXIS: "Speed"})
    assert move.duration({AXIS: 10.0}, {"Position": 35.0}) == 2.0               # 25 mm at 12.5 mm/s
    assert move.duration({}, {"Position": 35.0}) is None                        # from where it is not known
    dose = Capability("Dosing", "Dosing", "Dispense", "Pump", parameters={"Volume": Parameter(0.5, 10.0, 1.0), "FlowRate": Parameter(0.1, 5.0, 1.0)},
                      post=[Constraint("ContentVolume", CONTENT, parse("+= Volume"))], rates={CONTENT: "FlowRate"},
                      after=parse("= Volume / FlowRate"))
    assert dose.duration({CONTENT: 0.0}, {"Volume": 2.0, "FlowRate": 0.5}) == 4.0
    tare = Capability("Taring", "Taring", "Tare", "Scale", after=parse("= 2.0"))
    assert tare.duration({}, {}) == 2.0
    assert Capability("Referencing", "Referencing", "Home", "LinearAxis").duration({}, {}) is None
