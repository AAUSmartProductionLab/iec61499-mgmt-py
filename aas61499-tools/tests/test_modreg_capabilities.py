"""The capabilities a module's planner reads (ARSO 0.11; docs/skill-planning.md, section 4): a set
per component with the capabilities its primitives realize, and the constraints of every capability,
as the vocabulary and the module spec state them."""
from pathlib import Path

import pytest
import yaml

from modgen import load
from modgen.spec import ModuleSpec
from modsync.aasjson import at, children, submodel

from modreg import model, profile as profiles
from modreg.capabilities import state_point

SPECS = Path(__file__).resolve().parents[2] / "cell" / "modules"
BASE = "https://smartproductionlab.aau.dk"


def resolve(envs: list[dict], reference: dict) -> dict | None:
    """The element a model reference names, in one of the environments."""
    keys = reference["keys"]
    for env in envs:
        found = next((s for s in env["submodels"] if s["id"] == keys[0]["value"]), None)
        for key in keys[1:] if found else ():
            found = next((c for c in children(found) if c.get("idShort") == key["value"]), None)
        if found is not None:
            return found
    return None


def constraints(container: dict) -> dict[str, tuple[str, str, str]]:
    """idShort -> (kind, the property it is about, the expression)."""
    found = {}
    for record in children(at(container, "CapabilityRelations", "ConstraintSet")):
        (relation,) = children(at(record, "ConstraintPropertyRelations"))
        found[record["idShort"]] = (at(record, "PropertyConditionalType")["value"], relation["second"]["keys"][-2]["value"],
                                    at(record, "BasicConstraint")["value"])
    return found


@pytest.fixture(scope="module")
def filling() -> list[dict]:
    return [model.build(p) for p in profiles.describe_all(load(SPECS / "filling.yaml"), "pi")]


def test_each_component_has_the_capabilities_its_primitives_realize(filling):
    module = filling[0]
    description = submodel(module, "CapabilityDescription")
    sets = {s["idShort"]: [c["idShort"] for c in children(s)] for s in children(description)}
    assert sets == {"OfferedCapabilities": ["Filling"], "LinearAxis": ["Referencing", "Positioning"],
                    "Pump": ["Dosing"], "Scale": ["Taring", "Weighing"]}
    dosing = at(description, "Pump", "Dosing")
    capability = at(dosing, "Capability")
    assert {q["type"]: q["value"] for q in capability["qualifiers"]} == {"CapabilityRoleQualifier/NotAssigned": "true"}
    assert capability["supplementalSemanticIds"][0]["keys"][0]["value"] == f"{BASE}/semantics/Dosing"
    # Realized by the pump's primitive, in the pump's AAS.
    (realized,) = [r for r in children(at(dosing, "CapabilityRelations")) if r["idShort"] == "RealizedBy"]
    skill = resolve(filling, realized["second"])
    assert skill["idShort"] == "Dispense" and realized["second"]["keys"][0]["value"].endswith("FillingPumpAAS/submodels/Skills")


def test_a_capability_says_what_it_needs_does_and_keeps(filling):
    """The vocabulary's (Dosing adds to the content, the vial is no longer weighed) and the module's
    (the needle in the vial, and still)."""
    dosing = at(submodel(filling[0], "CapabilityDescription"), "Pump", "Dosing")
    assert sorted(constraints(dosing).values()) == [
        ("Invariant", "LinearAxisPosition", ">= FillPosition"), ("Post", "ContentVolume", "+= Volume"),
        ("Post", "Weighed", "= false"), ("Pre", "LinearAxisPosition", ">= FillPosition")]
    assert at(dosing, "PropertySet", "FillPosition", "Value")["value"] == "40.0"
    volume = at(dosing, "PropertySet", "Volume", "Value")
    assert (volume["modelType"], volume["min"], volume["max"]) == ("Range", "0.5", "10.0")
    assert volume["supplementalSemanticIds"][0]["keys"][0]["value"] == f"{BASE}/semantics/Volume"   # a dose
    weighing = at(submodel(filling[0], "CapabilityDescription"), "Scale", "Weighing")
    assert sorted(constraints(weighing).values()) == [
        ("Invariant", "LinearAxisPosition", "unchanged"), ("Post", "Weighed", "= true"), ("Post", "Weight", "measured"),
        ("Pre", "LinearAxisPosition", "= 0.0"), ("Pre", "Tared", "= true")]
    offered = at(submodel(filling[0], "CapabilityDescription"), "OfferedCapabilities", "Filling")
    assert sorted(constraints(offered).values()) == [("Post", "ContentVolume", "= FillVolume"), ("Pre", "ContentVolume", "= 0.0")]


def test_a_state_of_the_module_names_its_data_point(filling):
    """The axis's position is one state, whichever capability names it: the data point it is."""
    module = filling[0]
    description = submodel(module, "CapabilityDescription")
    points = {}
    for path_ in (("LinearAxis", "Positioning", "PropertySet", "Position"), ("LinearAxis", "Referencing", "PropertySet", "Position"),
                  ("Pump", "Dosing", "PropertySet", "LinearAxisPosition"), ("Scale", "Weighing", "PropertySet", "LinearAxisPosition")):
        same = at(description, *path_, "SameProperty")
        points[path_] = resolve(filling, same["second"])["idShort"]
    assert set(points.values()) == {"LinearAxis_ActualPosition"}
    assert resolve(filling, at(description, "Scale", "Weighing", "PropertySet", "Weight", "SameProperty")["second"])["idShort"] == "Scale_Weight"
    # The scale's Tared has no data point (it is the scale's state); ContentVolume is the product's.
    assert at(description, "Scale", "Taring", "PropertySet", "Tared", "SameProperty") is None
    assert at(description, "Pump", "Dosing", "PropertySet", "ContentVolume", "SameProperty") is None


def test_a_condition_on_a_state_no_item_publishes_is_refused():
    data = yaml.safe_load((SPECS / "filling.yaml").read_text(encoding="utf-8"))
    data["skills"]["Dispense"]["capability"]["precondition"] = {"Scale.Tared": "= true"}
    with pytest.raises(ValueError, match="Scale publishes no Tared"):
        profiles.describe(ModuleSpec.model_validate(data), "pi")
    spec = load(SPECS / "filling.yaml")
    assert (state_point(spec, "LinearAxis", "Referenced"), state_point(spec, "Scale", "Weight"), state_point(spec, "Pump", "Volume")) == (
        "LinearAxis_Homed", "Scale_Weight", None)
