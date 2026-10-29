"""modreg.process: a product's process AAS on a line, from the bindings the process sequence planner
writes into the product's recipe; the reference vial on the example line, bound as the planner binds it."""
import copy
from pathlib import Path
import sys

import pytest

pytest.importorskip("aas_model")

from modreg.plancheck import at, children, resolve, shell_of  # noqa: E402
from modreg.process import NotBound, line_for, process_of  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BASE = "https://smartproductionlab.aau.dk"
# Step of the vial's recipe -> (module, skill, its inputs: (name, the process parameter it takes, or a constant))
BOUND = {
    "Filling": ("FillingModuleAAS", "Dispensing", [("Volume", "FillVolume", None)]),
    "Stoppering": ("StopperingModuleAAS", "Stoppering", []),
    "Capping": ("CappingModuleAAS", "Capping", []),
    "Inspection": ("InspectionModuleAAS", "Inspection", []),
}


@pytest.fixture(scope="module")
def line():
    sys.path.insert(0, str(ROOT / "cell" / "examples"))
    try:
        import example_line
        resources, products = example_line.build()
        return resources, products, example_line.line(resources)
    finally:
        sys.path.remove(str(ROOT / "cell" / "examples"))


def ref(*keys):
    return {"type": "ModelReference", "keys": [{"type": t, "value": v} for t, v in keys]}


def element(kind, id_short, value):
    return {"modelType": kind, "idShort": id_short, "value": value, **({"valueType": "xs:string"} if kind == "Property" else {})}


def planned(product: dict, bound: dict) -> dict:
    """The product as the planner leaves it: each step of its recipe given its module, skill and inputs."""
    product = copy.deepcopy(product)
    recipe = next(sm for sm in product["submodels"] if sm["idShort"] == "ProductionSequence")
    for step in children(at(recipe, "Steps")):
        name = at(step, "NodeId")["value"]
        if name not in bound:
            continue
        module, skill, inputs = bound[name]
        module_id = f"{BASE}/aas/{module}"
        process = at(step, "ProcessReference")["value"]["keys"]
        bindings = [element("SubmodelElementCollection", f"Binding_{i:04d}", [
            element("Property", "Name", input_name),
            element("Property", "Value", constant or ""),
            *([element("ReferenceElement", "SourceElement", ref(
                *[(k["type"], k["value"]) for k in process], ("SubmodelElementCollection", "ProductParameters"),
                ("Property", parameter)))] if parameter else []),
        ]) for i, (input_name, parameter, constant) in enumerate(inputs)]
        step["value"] += [
            element("ReferenceElement", "Resource", ref(("AssetAdministrationShell", module_id))),
            element("Property", "SkillId", skill),
            element("ReferenceElement", "Skill", ref(("Submodel", f"{module_id}/submodels/Skills"), ("SubmodelElementCollection", skill))),
            element("Property", "ExecutionMode", "station"),
            *([element("SubmodelElementCollection", "Bindings", bindings)] if bindings else []),
        ]
    return product


def submodel(env, id_short):
    return next(sm for sm in env["submodels"] if sm["idShort"] == id_short)


def test_the_planners_bindings_make_the_process_aas_of_the_product_on_its_line(line):
    resources, products, system = line
    product = planned(products["Vial2mLAAS"], BOUND)
    found = line_for(product, [system], resources)
    assert shell_of(found)["idShort"] == "FillingLineAAS"
    env = process_of(product, found, resources)
    shell = shell_of(env)
    assert shell["idShort"] == "Vial2mLOnFillingLineAAS" and shell["id"] == f"{BASE}/aas/Vial2mLOnFillingLineAAS"
    information = submodel(env, "ProcessInformation")
    assert at(information, "Product")["value"]["keys"][0]["value"] == f"{BASE}/aas/Vial2mLAAS"
    assert at(information, "Line")["value"]["keys"][0]["value"] == f"{BASE}/aas/FillingLineAAS"
    assert at(information, "Status")["value"] == "Draft"
    # Per step its binding, every reference resolving: the step of the recipe, the skill, its input.
    envs = [product, env, *resources.values()]
    bindings = submodel(env, "Bindings")
    assert [b["idShort"] for b in children(bindings)] == list(BOUND)
    filling = at(bindings, "Filling")
    assert at(resolve(envs, at(filling, "Step")["value"]), "NodeId")["value"] == "Filling"
    assert resolve(envs, at(filling, "Skill")["value"])["idShort"] == "Dispensing"
    volume = at(filling, "Bindings", "Binding_0000")
    assert resolve(envs, at(volume, "InputReference")["value"])["idShort"] == "Volume"
    assert resolve(envs, at(volume, "SourceElement")["value"])["idShort"] == "FillVolume"
    # The plan check followed them: the recipe fits the line.
    validation = submodel(env, "Validation")
    assert at(validation, "Result")["value"] == "Fits" and children(at(validation, "Findings")) == []


def test_what_does_not_fit_is_the_validation_and_a_recipe_without_bindings_is_refused(line):
    resources, products, system = line
    # Filling bound to the stoppering module: it does not offer what filling requires; a step unbound.
    wrong = {**{k: v for k, v in BOUND.items() if k != "Inspection"}, "Filling": ("StopperingModuleAAS", "Stoppering", [])}
    env = process_of(planned(products["Vial2mLAAS"], wrong), system, resources)
    validation = submodel(env, "Validation")
    findings = [f["value"] for f in children(at(validation, "Findings"))]
    assert at(validation, "Result")["value"] == "DoesNotFit"
    assert any(f.startswith("Filling:") for f in findings) and "Inspection: not bound" in findings
    with pytest.raises(NotBound, match="no step"):
        line_for(products["Vial2mLAAS"], [system], resources)
