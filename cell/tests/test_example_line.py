"""The example line (cell/examples): four resources and a product planned on them. The product's
plan is followed into the resources' AASs, from the process over the required and the offered
capability to the skill and its parameters."""
import copy
import io
import json
from pathlib import Path
import sys

import pytest

pytest.importorskip("aas_model")
pytest.importorskip("rdflib")

from basyx.aas.adapter.json import read_aas_json_file           # noqa: E402

from modreg import model                                        # noqa: E402
from modreg.ontology import Blueprint, check as ontology_check  # noqa: E402
from modreg.product import plan_id                              # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
ARSO = Path(__file__).resolve().parents[2] / "ontology" / "ARSO"
BASE = "https://smartproductionlab.aau.dk"
sys.path.insert(0, str(EXAMPLES))

import example_line                                             # noqa: E402
import plan_check                                               # noqa: E402
from plan_check import at, children, resolve                    # noqa: E402


@pytest.fixture(scope="module")
def line():
    return example_line.build()


# The vial's profile, and changes to it -----------------------------------------------------------

def process(profile: dict, name: str) -> dict:
    return profile["process_parameters"]["Processes"]["Process"][name]


def required(profile: dict, capability: str, prop: str) -> dict:
    """The value a required capability asks for."""
    held = profile["capability_description"]["CapabilitySet"]["RequiredCapabilities"]["CapabilityContainer"][capability]
    return held["PropertySet"]["PropertySet"]["PropertyContainer"][prop]["PropertyProperty"]["Value"]


def step(profile: dict, order: int) -> dict:
    return profile["production_sequence"]["Steps"]["Step"][f"Step_{order:04d}"]


def assign(profile: dict, order: int, skill: str, resource: str | None = None) -> None:
    """Give a step to another skill, of another resource if one is named."""
    planned = step(profile, order)
    planned["SkillId"]["value"] = skill
    planned["Skill"]["value"]["key"][-1]["value"] = skill
    if resource:
        planned["Resource"]["value"]["key"][0]["value"] = f"{BASE}/aas/{resource}"
        planned["Skill"]["value"]["key"][0]["value"] = f"{BASE}/aas/{resource}/submodels/Skills"


def planned(change) -> dict:
    """The vial's AAS with ``change`` made to its profile first."""
    profile = copy.deepcopy(example_line.product_profiles()["Vial2mLAAS"])
    change(profile)
    return model.build(profile)


def test_the_line_has_four_resources_and_the_vial(line):
    resources, products = line
    assert list(resources) == ["FillingModuleAAS", "StopperingModuleAAS", "CappingModuleAAS", "InspectionModuleAAS"]
    assert list(products) == ["Vial2mLAAS"]
    vial = products["Vial2mLAAS"]
    assert [s["idShort"] for s in vial["submodels"]] == [
        "Nameplate", "HierarchicalStructures", "ProcessParameters", "CapabilityDescription", "ProductionSequence"]
    # Every AAS is valid as BaSyx reads it.
    for env in [*resources.values(), vial]:
        read_aas_json_file(io.StringIO(json.dumps(env)), failsafe=False)


def test_the_vial_is_described_by_its_profile():
    """The product's description is the pydantic dump of its type, as a module's profile is."""
    profile = example_line.product_profiles()["Vial2mLAAS"]
    assert profile["aas_type"] == "ProductTypeAAS"
    asset = model.validated(profile)
    # The file says nothing its type says anyway, and loses nothing.
    assert model.profile(asset, global_asset_id=profile["global_asset_id"]) == profile
    assert list(asset.hierarchical_structures.EntryNode.Node) == ["Vial", "Liquid", "Stopper", "Cap"]
    assert list(asset.process_parameters.Processes.Process) == ["Filling", "Stoppering", "Capping", "Inspection"]


def test_the_planned_modules_follow_the_resource_ontology(line):
    resources, _ = line
    blueprint = Blueprint(ARSO)
    for name in ("CappingModuleAAS", "InspectionModuleAAS"):
        report = ontology_check(resources[name], blueprint)
        assert report.ok, report.errors


def test_the_plan_can_be_followed_into_the_resources(line):
    resources, products = line
    vial = products["Vial2mLAAS"]
    assert plan_check.check(vial, resources) == []
    envs = [vial, *resources.values()]
    plan = next(s for s in vial["submodels"] if s["idShort"] == "ProductionSequence")
    # The planner finds the plan of a product by this identifier.
    assert plan["id"] == plan_id(vial["assetAdministrationShells"][0]["id"])
    steps = children(at(plan, "Steps"))
    assert [at(s, "Name")["value"] for s in steps] == ["Filling", "Stoppering", "Capping", "Inspection"]
    assert [resolve(envs, at(s, "Skill")["value"])["idShort"] for s in steps] == ["Dispensing", "Stoppering", "Capping", "Inspection"]
    # The fill volume: from the product's parameter to the parameter of the skill.
    binding = children(at(steps[0], "Bindings"))[0]
    assert at(binding, "Name")["value"] == "Volume"
    source = resolve(envs, at(binding, "SourceElement")["value"])
    assert (source["idShort"], float(source["value"])) == ("FillVolume", 2.0)
    skill = resolve(envs, at(steps[0], "Skill")["value"])
    assert at(skill, "Parameters", "Volume") is not None
    # The liquid a filling uses is as much as that parameter says.
    liquid = at(resolve(envs, at(steps[0], "ProcessReference")["value"]), "ProcessBoM", "Liquid")
    assert resolve(envs, at(liquid, "QuantityParameterReference")["value"]) is source
    assert resolve(envs, at(liquid, "MaterialReference")["value"])["idShort"] == "Liquid"


@pytest.mark.parametrize("change, told", [
    (lambda p: required(p, "Filling", "FillVolume").update(value="20.0"), "FillVolume = 20.0 is not covered"),
    (lambda p: process(p, "Filling")["ProductParameters"]["Parameter"]["FillVolume"].update(value="20.0"), "is outside 0.5 to 10.0"),
    (lambda p: required(p, "Filling", "FillVolume")["qualifiers"][0].update(value="L"), "asked in L and offered in mL"),
    (lambda p: process(p, "Filling")["ProductParameters"]["Parameter"]["FillVolume"]["qualifiers"][0].update(value="L"), "is in mL, FillVolume in L"),
    (lambda p: required(p, "Capping", "CapDiameter").update(value="28.0"), "CapDiameter = 28.0 is not covered"),
    (lambda p: required(p, "Inspection", "InspectionMethod").update(value="xray"), "InspectionMethod = xray is not covered"),
    (lambda p: assign(p, 0, "Weigh"), "is not realized by Weigh"),
    (lambda p: step(p, 0)["Bindings"]["Binding"]["Binding_0000"]["Name"].update(value="Speed"), "Dispensing.Speed is not a parameter of the skill"),
    (lambda p: step(p, 0)["Bindings"]["Binding"].update(Binding_0000={"Name": {"value": "Volume"}, "Value": {"value": "12.5"}}),
     "the constant = 12.5 is outside 0.5 to 10.0"),
    (lambda p: assign(p, 1, "Dispensing", "FillingModuleAAS"), "offers no capability with the meaning"),
    (lambda p: assign(p, 2, "Crimping"), "no such skill"),
])
def test_a_plan_that_does_not_fit_is_told(line, change, told):
    resources, _ = line
    found = plan_check.check(planned(change), resources)
    assert any(told in f for f in found), found
