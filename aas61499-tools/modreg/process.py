"""A product's process AAS on a line (ISA-88's master recipe), from the bindings the process sequence
planner writes into the product's recipe: per step, the module that carries it out, its skill and
what each input of the skill is handed (a process parameter of the product, or a constant).

The product's AAS is the general recipe and names no equipment; the process AAS binds it to one line.
Until the planner writes the process AAS itself, the planner's bindings in the recipe are where this
reads them; the registration service writes the process AAS after the planner saves
(``POST /process/<product>``). Its Validation is the plan check's result (``plancheck``).

The process AAS of the reference products (``cell/examples/processes``) is the same, written out by hand.
"""
from __future__ import annotations

import re

from aas_model.constants import BASE_URL
from aas_model.process_template import Process
from aas_model.submodel_templates.process import bindings as b, process_information as pi, validation as v
from aas_pydantic import Key, ModelReference

from . import model
from .plancheck import at, check_process, children, shell_of

# What a step of the planner's recipe is; other elements (parallel blocks, decisions, calls) hold steps.
STEP = "step"
# The asset type of a line: aas-model's ProductionSystem.
SYSTEM = f"{model.RESOURCE}/System"


class NotBound(ValueError):
    """The recipe cannot be bound: no step names a module, or no line holds the modules it names."""


def reference(*keys: tuple[str, str]) -> ModelReference:
    """A model reference along ``keys``: (type, value) pairs."""
    return ModelReference(key=tuple(Key(type_=kind, value=value) for kind, value in keys))


def keys_of(element: dict | None) -> tuple[tuple[str, str], ...]:
    """The keys of a ReferenceElement's reference as (type, value) pairs."""
    return tuple((k["type"], k["value"]) for k in ((element or {}).get("value") or {}).get("keys", []))


def short(env: dict) -> str:
    """An AAS's idShort without its ``AAS``: what its process AAS is named after."""
    return shell_of(env)["idShort"].removesuffix("AAS")


def recipe_of(product: dict) -> dict:
    found = next((sm for sm in product["submodels"] if sm["idShort"] == "ProductionSequence"), None)
    if found is None:
        raise NotBound(f"{shell_of(product)['idShort']} has no recipe (Production Sequence)")
    return found


def steps_of(recipe: dict) -> list[tuple[tuple[tuple[str, str], ...], dict]]:
    """Every step of the recipe, in order, with the path of keys to it from the recipe: the steps of
    its Steps, and those in its parallel blocks, decisions and branches, found at any depth."""
    found = []

    def walk(element: dict, path: tuple[tuple[str, str], ...]):
        for child in children(element):
            if child.get("modelType") != "SubmodelElementCollection":
                continue
            here = (*path, ("SubmodelElementCollection", child["idShort"]))
            if (at(child, "Kind") or {}).get("value", STEP) == STEP and at(child, "NodeId") is not None:
                found.append((here, child))
            else:
                walk(child, here)

    walk(at(recipe, "Steps") or {}, (("SubmodelElementCollection", "Steps"),))
    return found


def modules_bound(product: dict) -> list[str]:
    """The AASs (ids) the recipe's steps are bound to, in the order they first appear."""
    found = []
    for _, step in steps_of(recipe_of(product)):
        resource = keys_of(at(step, "Resource"))
        if resource and resource[0][1] not in found:
            found.append(resource[0][1])
    return found


def line_for(product: dict, lines: list[dict], resources: dict[str, dict]) -> dict:
    """The line of the recipe: the one production system that holds every module the recipe is
    bound to (its Hierarchical Structures name each module's asset)."""
    by_id = {shell_of(env)["id"]: env for env in resources.values()}
    wanted = modules_bound(product)
    if not wanted:
        raise NotBound(f"no step of {shell_of(product)['idShort']}'s recipe is bound to a module yet")
    unknown = [aas for aas in wanted if aas not in by_id]
    if unknown:
        raise NotBound(f"the recipe is bound to {unknown}, which the AAS server does not hold")
    assets = {shell_of(by_id[aas])["assetInformation"]["globalAssetId"] for aas in wanted}
    fitting = [line for line in lines if assets <= members(line)]
    if len(fitting) != 1:
        held = [shell_of(line)["idShort"] for line in fitting] or "none"
        raise NotBound(f"one line has to hold every module the recipe is bound to ({len(wanted)}); found {held}")
    return fitting[0]


def members(line: dict) -> set[str]:
    """The assets a line's Hierarchical Structures name, at any depth."""
    found = set()

    def walk(element: dict):
        if element.get("modelType") == "Entity" and element.get("globalAssetId"):
            found.add(element["globalAssetId"])
        for child in element.get("statements") or element.get("submodelElements") or []:
            walk(child)

    for sm in line["submodels"]:
        if sm["idShort"] == "HierarchicalStructures":
            walk(sm)
    return found


def process_of(product: dict, line: dict, resources: dict[str, dict], status: str = "Draft") -> dict:
    """The process AAS (an environment) of ``product`` on ``line``: a step binding per bound step of
    the recipe, and the plan check's result as its Validation. A step without a module is left
    unbound; the plan check names it."""
    recipe = recipe_of(product)
    product_id, line_id = shell_of(product)["id"], shell_of(line)["id"]
    id_short = f"{short(product)}On{short(line)}AAS"
    steps = {}
    for path, step in steps_of(recipe):
        resource, skill = keys_of(at(step, "Resource")), keys_of(at(step, "Skill"))
        if not resource or not skill:
            continue
        inputs = {}
        for i, given in enumerate(children(at(step, "Bindings"))):
            name = (at(given, "Name") or {}).get("value", "")
            source, constant = keys_of(at(given, "SourceElement")), (at(given, "Value") or {}).get("value", "")
            inputs[f"Binding_{i:04d}"] = b.InputBinding(
                id_short=f"Binding_{i:04d}", Name=b.Name(value=name),
                SourceElement=b.SourceElement(value=reference(*source)) if source else None,
                Value=b.Value(value=constant) if not source and constant != "" else None,
                # The input itself: a variable of the Operation of the skill's Start command (ARSO).
                InputReference=b.InputReference(value=reference(
                    *skill, ("SubmodelElementCollection", "Start"), ("Operation", "Start"), ("Property", name))))
        node = at(step, "NodeId")["value"]
        key = re.sub(r"\W", "_", node)
        key = key if key[:1].isalpha() else f"Step_{key}"
        steps[key] = b.ProcessStepBinding(
            id_short=key, NodeId=b.NodeId(value=node),
            Step=b.BoundStep(value=reference(("Submodel", recipe["id"]), *path)),
            Resource=b.Resource(value=reference(*resource)), Skill=b.BoundSkill(value=reference(*skill)),
            ExecutionMode=b.ExecutionMode(value=(at(step, "ExecutionMode") or {}).get("value") or "station"),
            Bindings=b.InputBindings(Binding=inputs) if inputs else None)

    def built(validation: v.Validation) -> dict:
        asset = Process(
            id_short=id_short, id=f"{BASE_URL}/aas/{id_short}",
            description=f"The process of {shell_of(product)['idShort']} on {shell_of(line)['idShort']}: its recipe bound to the line's modules",
            specific_asset_ids={"product": shell_of(product)["assetInformation"]["globalAssetId"],
                                "line": shell_of(line)["assetInformation"]["globalAssetId"]},
            process_information=pi.ProcessInformation(
                id_short="ProcessInformation",
                Product=pi.Product(value=reference(("AssetAdministrationShell", product_id))),
                Line=pi.Line(value=reference(("AssetAdministrationShell", line_id))),
                Recipe=pi.Recipe(value=reference(("Submodel", recipe["id"]))),
                RecipeRevision=pi.RecipeRevision(value=(at(recipe, "Revision") or {}).get("value") or "0"),
                Status=pi.Status(value=status)),
            bindings=b.ProcessBindings(id_short="Bindings", StepBinding=steps),
            validation=validation)
        model.inject_ids(asset)
        return model.environment(asset, f"{BASE_URL}/assets/{id_short.removesuffix('AAS')}")

    # The plan check follows the bindings as written; its result is the Validation.
    findings = check_process(product, built(v.Validation(id_short="Validation", Result=v.Result(value="DoesNotFit"),
                                                         CheckedBy=v.CheckedBy(value="plan_check"))), resources)
    return built(v.Validation(
        id_short="Validation", Result=v.Result(value="DoesNotFit" if findings else "Fits"),
        CheckedBy=v.CheckedBy(value="plan_check"),
        Findings=v.Findings(value=[v.FindingsItem(value=finding) for finding in findings])))
