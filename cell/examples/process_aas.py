"""The process AAS of a product on a line (ISA-88's master recipe), a draft: the bindings of the
product's recipe to the resources of the line, made from what the planner keeps in the product's
Production Sequence today. When the planner writes them here instead (docs/next-steps.md, F6),
the product's recipe names no equipment.

    Process Information   the product, the line, the recipe it binds and its revision, a status
    Bindings              per step of the recipe: the step, the resource, the skill, and what each
                          input of the skill is handed (a process parameter of the product, or a
                          constant), with the input itself
    Validation            what the plan check found

Every link is a model reference, so it is followed from here into the product's AAS and the
resources' AASs. The elements of a binding are the planner's (the same semantic ids as in
Production Sequence); the submodels' own ids are drafts until AProSO is remade (F5).
"""
from __future__ import annotations

from plan_check import at, children, shell_of

BASE = "https://smartproductionlab.aau.dk"
SEQUENCE = f"{BASE}/ProductionSequence"          # the planner's elements, as in a skill's steps
DRAFT = {"ProcessInformation": f"{BASE}/ProcessInformation/1/0/Submodel",
         "Bindings": f"{BASE}/ProcessBindings/1/0/Submodel",
         "Validation": f"{BASE}/ProcessValidation/1/0/Submodel"}


def semantic(value: str) -> dict:
    return {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": value}]}


def element(model_type: str, id_short: str, meaning: str | None, **fields) -> dict:
    return {"idShort": id_short, "modelType": model_type, **({"semanticId": semantic(meaning)} if meaning else {}), **fields}


def prop(id_short: str, value, meaning: str | None = None, value_type: str = "xs:string") -> dict:
    return element("Property", id_short, meaning, valueType=value_type, value=str(value))


def ref(id_short: str, keys: list[tuple[str, str]] | list[dict], meaning: str | None = None) -> dict:
    keys = [k if isinstance(k, dict) else {"type": k[0], "value": k[1]} for k in keys]
    return element("ReferenceElement", id_short, meaning, value={"type": "ModelReference", "keys": keys})


def smc(id_short: str, value: list[dict], meaning: str | None = None) -> dict:
    return element("SubmodelElementCollection", id_short, meaning, value=value)


def keys_of(reference_element: dict) -> list[dict]:
    return [dict(k) for k in reference_element["value"]["keys"]]


def binding(step: dict, recipe_id: str) -> dict:
    """What a step of the recipe is bound to: the resource, the skill, and per input of the skill
    what it is handed, with a reference to the input (a variable of the skill's Start)."""
    node, skill = at(step, "NodeId")["value"], keys_of(at(step, "Skill"))
    handed = []
    for i, given in enumerate(children(at(step, "Bindings"))):
        name, source = at(given, "Name")["value"], at(given, "SourceElement")
        handed.append(smc(f"Binding_{i:04d}", [
            prop("Name", name, f"{SEQUENCE}/Name/1/0"),
            ref("SourceElement", keys_of(source), f"{SEQUENCE}/SourceElement/1/0") if source
            else prop("Value", at(given, "Value").get("value") or "", f"{SEQUENCE}/Value/1/0"),
            ref("InputReference", [*skill, {"type": "SubmodelElementCollection", "value": "Start"},
                                   {"type": "Operation", "value": "Start"}, {"type": "Property", "value": name}],
                f"{SEQUENCE}/InputReference/1/0"),
        ], f"{SEQUENCE}/Binding/1/0"))
    return smc(node, [
        prop("NodeId", node, f"{SEQUENCE}/NodeId/1/0"),
        ref("Step", [("Submodel", recipe_id), ("SubmodelElementCollection", "Steps"),
                     ("SubmodelElementCollection", step["idShort"])], f"{BASE}/ProcessBindings/Step/1/0"),
        ref("Resource", keys_of(at(step, "Resource")), f"{SEQUENCE}/Resource/1/0"),
        ref("Skill", skill, f"{SEQUENCE}/Skill/1/0"),
        prop("ExecutionMode", at(step, "ExecutionMode")["value"], f"{SEQUENCE}/ExecutionMode/1/0"),
        *([smc("Bindings", handed, f"{SEQUENCE}/Bindings/1/0")] if handed else []),
    ], f"{BASE}/ProcessBindings/StepBinding/1/0")


def process(product: dict, line: dict, findings: list[str]) -> dict:
    """The process AAS of ``product`` on ``line``, as an AAS environment; ``findings``: what the plan
    check found (nothing: the plan fits)."""
    made, on = shell_of(product), shell_of(line)
    name = f"{made['idShort'].removesuffix('AAS')}On{on['idShort'].removesuffix('AAS')}"
    aas_id = f"{BASE}/aas/{name}AAS"
    recipe = next(s for s in product["submodels"] if s["idShort"] == "ProductionSequence")
    submodels = [
        {"idShort": "ProcessInformation", "id": f"{aas_id}/submodels/ProcessInformation", "kind": "Instance",
         "modelType": "Submodel", "semanticId": semantic(DRAFT["ProcessInformation"]), "submodelElements": [
             ref("Product", [("AssetAdministrationShell", made["id"])], f"{BASE}/ProcessInformation/Product/1/0"),
             ref("Line", [("AssetAdministrationShell", on["id"])], f"{BASE}/ProcessInformation/Line/1/0"),
             ref("Recipe", [("Submodel", recipe["id"])], f"{BASE}/ProcessInformation/Recipe/1/0"),
             prop("RecipeRevision", at(recipe, "Revision")["value"], f"{BASE}/ProcessInformation/RecipeRevision/1/0",
                  "xs:nonNegativeInteger"),
             prop("Status", "Draft", f"{BASE}/ProcessInformation/Status/1/0")]},
        {"idShort": "Bindings", "id": f"{aas_id}/submodels/Bindings", "kind": "Instance", "modelType": "Submodel",
         "semanticId": semantic(DRAFT["Bindings"]),
         "submodelElements": [binding(step, recipe["id"]) for step in children(at(recipe, "Steps"))]},
        {"idShort": "Validation", "id": f"{aas_id}/submodels/Validation", "kind": "Instance", "modelType": "Submodel",
         "semanticId": semantic(DRAFT["Validation"]), "submodelElements": [
             prop("Result", "DoesNotFit" if findings else "Fits", f"{BASE}/ProcessValidation/Result/1/0"),
             prop("CheckedBy", "plan_check", f"{BASE}/ProcessValidation/CheckedBy/1/0"),
             {"idShort": "Findings", "modelType": "SubmodelElementList", "semanticId": semantic(f"{BASE}/ProcessValidation/Findings/1/0"),
              "typeValueListElement": "Property", "valueTypeListElement": "xs:string",
              "value": [{"modelType": "Property", "valueType": "xs:string", "value": f} for f in findings]}]},
    ]
    shell = {
        "idShort": f"{name}AAS", "id": aas_id, "modelType": "AssetAdministrationShell",
        "description": [{"language": "en", "text": f"The process of {made['idShort']} on {on['idShort']}: its recipe "
                                                   "bound to the line's resources (draft)"}],
        "assetInformation": {
            "assetKind": "Type", "globalAssetId": f"{BASE}/assets/{name}", "assetType": f"{BASE}/Process",
            # Found from the product and from the line by their asset ids.
            "specificAssetIds": [{"name": "product", "value": made["assetInformation"]["globalAssetId"]},
                                 {"name": "line", "value": on["assetInformation"]["globalAssetId"]}]},
        "submodels": [{"type": "ModelReference", "keys": [{"type": "Submodel", "value": s["id"]}]} for s in submodels],
    }
    return {"assetAdministrationShells": [shell], "submodels": submodels}
