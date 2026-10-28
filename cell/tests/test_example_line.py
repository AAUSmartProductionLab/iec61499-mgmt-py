"""The example line (cell/examples), the lab's reference models: the modules, three products and the
process of each on the line. A product's recipe is followed through its process AAS into the
modules' AASs, from the process over the required and the offered capability to the skill and its
parameters."""
import copy
import io
import json
from pathlib import Path
import sys

import pytest

pytest.importorskip("aas_model")
pytest.importorskip("rdflib")

from basyx.aas.adapter.json import read_aas_json_file           # noqa: E402

from aas_model.process_template import Process                   # noqa: E402
from aas_model.product_template import Product, plan_id          # noqa: E402
from modreg.ontology import Blueprint, check as ontology_check  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
ARSO = Path(__file__).resolve().parents[2] / "ontology" / "ARSO"
BASE = "https://smartproductionlab.aau.dk"
sys.path.insert(0, str(EXAMPLES))

import example_line                                             # noqa: E402
import plan_check                                               # noqa: E402
from plan_check import at, children, resolve                    # noqa: E402

PRODUCTS = ["Vial2mLAAS", "PrefilledSyringe1mLAAS", "Cartridge3mLAAS"]


@pytest.fixture(scope="module")
def line():
    return example_line.build()


@pytest.fixture(scope="module")
def processes(line):
    resources, products = line
    return example_line.processes(resources, products)


def submodel(env: dict, id_short: str) -> dict:
    return next(s for s in env["submodels"] if s["idShort"] == id_short)


def test_the_line_has_four_modules_and_makes_three_products(line, processes):
    resources, products = line
    assert list(resources) == ["FillingModuleAAS", "StopperingModuleAAS", "CappingModuleAAS", "InspectionModuleAAS"]
    assert list(products) == PRODUCTS
    assert list(processes) == [f"{name.removesuffix('AAS')}OnFillingLineAAS" for name in PRODUCTS]
    for env in products.values():
        assert [s["idShort"] for s in env["submodels"]] == [
            "Nameplate", "HierarchicalStructures", "ProcessParameters", "CapabilityDescription", "ProductionSequence"]
        assert plan_check.shell_of(env)["assetInformation"]["assetKind"] == "Type"
    # Every AAS is valid as BaSyx reads it.
    for env in [*resources.values(), *products.values(), *processes.values(), *example_line.planar_table()]:
        read_aas_json_file(io.StringIO(json.dumps(env)), failsafe=False)


@pytest.mark.parametrize("make", example_line.PRODUCTS + example_line.PROCESSES, ids=lambda m: m.__name__)
def test_a_product_or_process_written_out_reads_back_from_its_json(make):
    made = make()
    again = type(made).model_validate_json(made.model_dump_json())
    assert json.loads(again.model_dump_json()) == json.loads(made.model_dump_json())
    assert isinstance(made, (Product, Process))


def test_a_recipe_names_no_equipment(line):
    """The product's recipe: the steps in order, each running a process and requiring its capability;
    no resource, skill or binding (those are the process AAS's)."""
    _, products = line
    names = {"Vial2mLAAS": ["Filling", "Stoppering", "Capping", "Inspection"],
             "PrefilledSyringe1mLAAS": ["Filling", "Stoppering", "Inspection"],
             "Cartridge3mLAAS": ["Filling", "Stoppering", "Inspection"]}
    for name, env in products.items():
        recipe = submodel(env, "ProductionSequence")
        # The planner finds the recipe of a product by this identifier.
        assert recipe["id"] == plan_id(plan_check.shell_of(env)["id"])
        steps = children(at(recipe, "Steps"))
        assert [at(s, "Name")["value"] for s in steps] == names[name]
        for step in steps:
            assert {"Resource", "Skill", "SkillId", "Bindings"}.isdisjoint(c["idShort"] for c in children(step))
            process = resolve([env], at(step, "ProcessReference")["value"])
            required = resolve([env], at(process, "RequiredCapability")["value"])
            assert resolve([env], at(at(step, "RequiredCapabilities"), at(step, "Name")["value"])["value"]) is required


def test_the_modules_take_three_kinds_of_container(line):
    """Filling, stoppering and inspection take vials, syringes and cartridges; capping vials only."""
    resources, _ = line
    for name, capability, takes in [("FillingModuleAAS", "Filling", ["vial", "syringe", "cartridge"]),
                                    ("StopperingModuleAAS", "Stoppering", ["vial", "syringe", "cartridge"]),
                                    ("InspectionModuleAAS", "Inspection", ["vial", "syringe", "cartridge"]),
                                    ("CappingModuleAAS", "Capping", ["vial"])]:
        offered = at(submodel(resources[name], "CapabilityDescription"), "OfferedCapabilities", capability,
                     "PropertySet", "ContainerType", "Value")
        listed = [item["value"] for item in offered["value"]] if offered["modelType"] == "SubmodelElementList" else [offered["value"]]
        assert listed == takes, name


def test_the_planned_modules_follow_the_resource_ontology(line):
    resources, _ = line
    blueprint = Blueprint(ARSO)
    for name in ("CappingModuleAAS", "InspectionModuleAAS"):
        report = ontology_check(resources[name], blueprint)
        assert report.ok, report.errors


def test_every_process_fits_the_line(line, processes):
    resources, products = line
    for product, process in zip(products.values(), processes.values()):
        assert plan_check.check_process(product, process, resources) == []
        assert at(submodel(process, "Validation"), "Result")["value"] == "Fits"


def test_the_fill_volume_is_followed_from_the_product_to_the_skill(line, processes):
    resources, products = line
    vial, process = products["Vial2mLAAS"], processes["Vial2mLOnFillingLineAAS"]
    envs = [vial, process, *resources.values()]
    filling = at(submodel(process, "Bindings"), "Filling")
    [binding] = children(at(filling, "Bindings"))
    assert at(binding, "Name")["value"] == "Volume"
    source = resolve(envs, at(binding, "SourceElement")["value"])
    assert (source["idShort"], float(source["value"])) == ("FillVolume", 2.0)
    # It is an input of the skill's Start, and means what the capability's property means.
    volume = resolve(envs, at(binding, "InputReference")["value"])
    assert volume is at(resolve(envs, at(filling, "Skill")["value"]), "Start", "Start", "Volume")
    assert f"{BASE}/semantics/FillVolume" in plan_check.semantic_ids(volume) and plan_check.unit_of(volume) == "mL"
    # The liquid a filling uses is as much as that parameter says.
    step = resolve(envs, at(filling, "Step")["value"])
    liquid = at(resolve(envs, at(step, "ProcessReference")["value"]), "ProcessBoM", "Liquid")
    assert resolve(envs, at(liquid, "QuantityParameterReference")["value"]) is source
    assert resolve(envs, at(liquid, "MaterialReference")["value"])["idShort"] == "Liquid"


# Changes to the vial, its process or the line, and what the plan check tells of them ----------------

def required(env: dict, capability: str, prop: str) -> dict:
    """The value a required capability of the product asks for."""
    return at(submodel(env, "CapabilityDescription"), "RequiredCapabilities", capability, "PropertySet", prop, "Value")


def parameter(env: dict, process: str, name: str) -> dict:
    return at(submodel(env, "ProcessParameters"), "Processes", process, "ProductParameters", name)


def bound(env: dict, step: str) -> dict:
    return at(submodel(env, "Bindings"), step)


def rebind(env: dict, step: str, skill: str, resource: str | None = None) -> None:
    """Give a step to another skill, of another AAS if one is named."""
    keys = at(bound(env, step), "Skill")["value"]["keys"]
    keys[-1]["value"] = skill
    if resource:
        keys[0]["value"] = f"{BASE}/aas/{resource}/submodels/Skills"
        at(bound(env, step), "Resource")["value"]["keys"][0]["value"] = f"{BASE}/aas/{resource}"


def unbind(env: dict, step: str) -> None:
    held = submodel(env, "Bindings")
    held["submodelElements"] = [b for b in held["submodelElements"] if b["idShort"] != step]


@pytest.mark.parametrize("change, told", [
    (lambda v, p: required(v, "Filling", "FillVolume").update(value="20.0"), "FillVolume = 20.0 is not covered"),
    (lambda v, p: parameter(v, "Filling", "FillVolume").update(value="20.0"), "is outside 0.5 to 10.0"),
    (lambda v, p: required(v, "Filling", "FillVolume")["qualifiers"][0].update(value="L"), "asked in L and offered in mL"),
    (lambda v, p: parameter(v, "Filling", "FillVolume")["qualifiers"][0].update(value="L"), "is in mL, FillVolume in L"),
    (lambda v, p: required(v, "Filling", "AbsoluteFillError").update(max="0.01"), "AbsoluteFillError = 0.0 to 0.01 is not covered"),
    (lambda v, p: required(v, "Capping", "CapDiameter").update(value="28.0"), "CapDiameter = 28.0 is not covered"),
    (lambda v, p: required(v, "Capping", "ContainerType").update(value="syringe"), "ContainerType = syringe is not covered"),
    (lambda v, p: required(v, "Inspection", "InspectionMethod").update(value="xray"), "InspectionMethod = xray is not covered"),
    (lambda v, p: rebind(p, "Filling", "Weigh", "FillingScaleAAS"), "FillingScaleAAS offers no capability"),
    (lambda v, p: at(bound(p, "Filling"), "Bindings", "Binding_0000", "Name").update(value="Speed"),
     "Dispensing.Speed is not a parameter of the skill"),
    (lambda v, p: at(bound(p, "Filling"), "Bindings", "Binding_0000", "InputReference")["value"]["keys"][1].update(value="Home"),
     "its InputReference is not that input"),
    (lambda v, p: rebind(p, "Stoppering", "Dispensing", "FillingModuleAAS"), "offers no capability with the meaning"),
    (lambda v, p: rebind(p, "Capping", "Crimping"), "no such skill"),
    (lambda v, p: unbind(p, "Inspection"), "Inspection: not bound"),
])
def test_a_process_that_does_not_fit_is_told(line, processes, change, told):
    resources, products = line
    vial, process = copy.deepcopy(products["Vial2mLAAS"]), copy.deepcopy(processes["Vial2mLOnFillingLineAAS"])
    change(vial, process)
    found = plan_check.check_process(vial, process, {**resources, **example_line.components()})
    assert any(told in f for f in found), found


def test_a_process_whose_validation_is_wrong_is_refused(line, monkeypatch):
    """A process AAS that says it fits, where the plan check finds otherwise, is not built."""
    resources, products = line
    broken = copy.deepcopy(resources)
    offered = at(submodel(broken["FillingModuleAAS"], "CapabilityDescription"), "OfferedCapabilities", "Filling",
                 "PropertySet", "ContainerType", "Value")
    offered["value"] = [item for item in offered["value"] if item["value"] == "vial"]
    with pytest.raises(example_line.ValidationError, match="PrefilledSyringe1mLOnFillingLineAAS"):
        example_line.processes(broken, products)


def test_the_process_aas_binds_the_recipe_to_the_resources_by_reference(line, processes):
    """Each step of the vial's recipe is bound in the process AAS: the step, the resource, the skill,
    and each input of the skill with what it is handed; every link resolves, and an input and the
    product parameter it is handed mean the same."""
    resources, products = line
    process = processes["Vial2mLOnFillingLineAAS"]
    system = example_line.line(resources)
    envs = [process, system, *resources.values(), *example_line.components().values(), *products.values()]
    shell = plan_check.shell_of(process)
    assert shell["assetInformation"]["assetKind"] == "Type"
    assert {a["name"]: a["value"] for a in shell["assetInformation"]["specificAssetIds"]} == {
        "product": f"{BASE}/assets/Vial2mL", "line": f"{BASE}/assets/FillingLine"}
    assert [s["idShort"] for s in process["submodels"]] == ["ProcessInformation", "Bindings", "Validation"]
    information, bindings, validation = process["submodels"]
    assert resolve(envs, at(information, "Recipe")["value"]) is submodel(products["Vial2mLAAS"], "ProductionSequence")
    assert at(information, "Product")["value"]["keys"][0]["value"] == plan_check.shell_of(products["Vial2mLAAS"])["id"]
    assert at(information, "Line")["value"]["keys"][0]["value"] == plan_check.shell_of(system)["id"]
    assert at(validation, "Result")["value"] == "Fits"
    assert [b["idShort"] for b in children(bindings)] == ["Filling", "Stoppering", "Capping", "Inspection"]
    filling = at(bindings, "Filling")
    assert resolve(envs, at(filling, "Step")["value"])["idShort"] == "Step_0000"
    assert resolve(envs, at(filling, "Skill")["value"])["idShort"] == "Dispensing"
    [volume] = children(at(filling, "Bindings"))
    given = resolve(envs, at(volume, "SourceElement")["value"])
    takes = resolve(envs, at(volume, "InputReference")["value"])
    assert (given["idShort"], takes["idShort"]) == ("FillVolume", "Volume")
    assert set(plan_check.semantic_ids(given)) & set(plan_check.semantic_ids(takes))
    for binding in children(bindings):
        for name in ("Step", "Skill"):
            assert resolve(envs, at(binding, name)["value"]) is not None, (binding["idShort"], name)
        for given in children(at(binding, "Bindings")):
            assert resolve(envs, at(given, "InputReference")["value"]) is not None, binding["idShort"]


def test_every_component_has_an_aas_of_its_own_and_the_line_names_its_modules(line):
    """The bill of material of the resources: line -> modules -> components, each part found by its
    asset id; and the hierarchy of skills: a module's skill runs the skills of its components."""
    resources, _ = line
    components = example_line.components()
    assert list(components) == [
        "FillingLinearAxisAAS", "FillingPumpAAS", "FillingScaleAAS", "StopperingLinearAxisAAS", "StopperingPistonAAS",
        "CappingLinearAxisAAS", "CappingCrimperAAS", "InspectionTopCameraAAS", "InspectionSideCameraAAS"]
    blueprint = Blueprint(ARSO)
    kinds = {}
    for name, env in components.items():
        assert ontology_check(env, blueprint).ok, name
        read_aas_json_file(io.StringIO(json.dumps(env)), failsafe=False)
        kinds.setdefault(plan_check.shell_of(env)["assetInformation"]["assetType"].rsplit("/", 1)[-1], []).append(name)
    # What kind a component is, is shared: three axes, with the same two skills.
    assert kinds["LinearAxis"] == ["FillingLinearAxisAAS", "StopperingLinearAxisAAS", "CappingLinearAxisAAS"]
    for name in kinds["LinearAxis"]:
        held = next(s for s in components[name]["submodels"] if s["idShort"] == "Skills")
        assert [s["idShort"] for s in children(held)] == ["Home", "MoveAxis", "Errors"]
    assets = {plan_check.shell_of(env)["assetInformation"]["globalAssetId"]: name for name, env in {**resources, **components}.items()}
    # A module's parts are its components (its points are coordinates) ...
    filling = next(s for s in resources["FillingModuleAAS"]["submodels"] if s["idShort"] == "HierarchicalStructures")
    assert [assets.get(n.get("globalAssetId")) for n in children(at(filling, "EntryNode"))] == [
        "FillingLinearAxisAAS", "FillingPumpAAS", "FillingScaleAAS"]
    # ... and the line's parts are the modules, with the two that are not described yet at its ends,
    # and the planar table they stand around.
    system = example_line.line(resources)
    assert plan_check.shell_of(system)["assetInformation"]["assetType"] == f"{BASE}/Resource/System"
    assert ontology_check(system, blueprint).ok
    nodes = children(at(next(s for s in system["submodels"] if s["idShort"] == "HierarchicalStructures"), "EntryNode"))
    assert [n["idShort"] for n in nodes] == ["LoadingModule", "FillingModule", "StopperingModule", "CappingModule",
                                             "InspectionModule", "UnloadingModule", "PlanarTable"]
    assert [assets.get(n.get("globalAssetId")) for n in nodes][1:5] == list(resources)
    # The steps of a module's skill run skills of its components.
    envs = [*resources.values(), *components.values()]
    dispensing = at(next(s for s in resources["FillingModuleAAS"]["submodels"] if s["idShort"] == "Skills"), "Dispensing")
    ran = [resolve(envs, at(step, "Skill")["value"]) for step in children(at(dispensing, "Start", "Steps"))]
    assert [s["idShort"] for s in ran] == ["MoveAxis", "Dispense", "Home", "Weigh"]
