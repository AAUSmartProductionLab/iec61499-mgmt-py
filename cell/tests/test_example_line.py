"""The example line (cell/examples): four resources and a product planned on them. The product's
plan is followed into the resources' AASs, from the process over the required and the offered
capability to the skill and its parameters."""
import io
import json
from pathlib import Path
import sys

import pytest
import yaml

pytest.importorskip("aas_model")
pytest.importorskip("rdflib")

from basyx.aas.adapter.json import read_aas_json_file           # noqa: E402

from modreg.ontology import Blueprint, check as ontology_check  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
ARSO = Path(__file__).resolve().parents[2] / "ontology" / "ARSO"
sys.path.insert(0, str(EXAMPLES))

import example_line                                             # noqa: E402
import product_aas                                              # noqa: E402
from product_aas import at, children, resolve                   # noqa: E402

VIAL = EXAMPLES / "vial-2ml.yaml"


@pytest.fixture(scope="module")
def line():
    return example_line.build()


def planned(line, change) -> dict:
    """The vial's AAS with ``change`` made to its description first."""
    resources, _ = line
    spec = yaml.safe_load(VIAL.read_text(encoding="utf-8"))
    change(spec)
    template = next(s for s in resources["FillingModuleAAS"]["submodels"] if s["idShort"] == "Nameplate")
    return product_aas.build(spec, resources, template)


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


def test_the_planned_modules_follow_the_resource_ontology(line):
    resources, _ = line
    blueprint = Blueprint(ARSO)
    for name in ("CappingModuleAAS", "InspectionModuleAAS"):
        report = ontology_check(resources[name], blueprint)
        assert report.ok, report.errors


def test_the_plan_can_be_followed_into_the_resources(line):
    resources, products = line
    vial = products["Vial2mLAAS"]
    assert product_aas.check(vial, resources) == []
    envs = [vial, *resources.values()]
    plan = next(s for s in vial["submodels"] if s["idShort"] == "ProductionSequence")
    # The planner finds the plan of a product by this identifier.
    assert plan["id"] == product_aas.plan_id(vial["assetAdministrationShells"][0]["id"])
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


@pytest.mark.parametrize("change, told", [
    (lambda d: d["processes"]["Filling"]["parameters"]["FillVolume"].update(value=20.0), "FillVolume = 20.0 is not covered"),
    (lambda d: d["processes"]["Filling"]["parameters"]["FillVolume"].update(value=20.0), "is outside 0.5 to 10.0"),
    (lambda d: d["processes"]["Filling"]["parameters"]["FillVolume"].update(unit="L"), "asked in L and offered in mL"),
    (lambda d: d["processes"]["Capping"]["parameters"]["CapDiameter"].update(value=28.0), "CapDiameter = 28.0 is not covered"),
    (lambda d: d["processes"]["Inspection"]["parameters"]["InspectionMethod"].update(value="xray"), "InspectionMethod = xray is not covered"),
    (lambda d: d["sequence"][0].update(skill="Weigh"), "is not realized by Weigh"),
    (lambda d: d["sequence"][0].update(bind={"Speed": "FillVolume"}), "Dispensing.Speed is not a parameter of the skill"),
    (lambda d: d["sequence"][1].update(resource="FillingModuleAAS", skill="Dispensing"), "offers no capability with the meaning"),
    (lambda d: d["sequence"][2].update(skill="Crimping"), "no such skill"),
])
def test_a_plan_that_does_not_fit_is_told(line, change, told):
    resources, _ = line
    found = product_aas.check(planned(line, change), resources)
    assert any(told in f for f in found), found

