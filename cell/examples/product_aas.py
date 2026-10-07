"""The AAS of a product, from a product description (``vial-2ml.yaml``), and the check that it
fits the resources it is planned on.

A product AAS holds what the process planner reads (see docs/aas-models.md):

- **Nameplate** (IDTA 02006): what the product is.
- **Hierarchical Structures** (IDTA 02011): its bill of material.
- **Process Parameters** (IDTA 02031): the processes it needs, each with the product's values, the
  materials it uses and the capability it requires.
- **Capability Description** (IDTA 02020, role Required): those capabilities with their values.
- **Production Sequence** (the planner's template, 2.0): the plan, each step assigned to a skill
  of a resource, with what is bound to the skill's parameters.

``check`` follows every link from the plan into the resources' AASs, the way an executor would.
"""
from __future__ import annotations

import base64
import copy

BASE = "https://smartproductionlab.aau.dk"
VOCABULARY = f"{BASE}/semantics"
IEC61360 = "https://admin-shell.io/DataSpecificationTemplates/DataSpecificationIEC61360/3/0"
PROCESS_PARAMETERS = "https://admin-shell-io/idta/SubmodelTemplate/ProcessParameters/1/0"      # the template's spelling
CAPABILITY_DESCRIPTION = "https://admin-shell.io/idta/SubmodelTemplate/CapabilityDescription/1/0"
HIERARCHICAL_STRUCTURES = "https://admin-shell.io/idta/HierarchicalStructures/1/1/Submodel"
PRODUCTION_SEQUENCE = f"{BASE}/SubmodelTemplate/ProductionSequence/2/0"
REQUIRED_CAPABILITY = f"{BASE}/ProcessParameters/RequiredCapability/1/0"
SMC = "SubmodelElementCollection"


def pp(name: str) -> str:
    return f"https://admin-shell.io/idta/ProcessParameters/{name}/1/0"


def cap(name: str) -> str:
    return f"https://admin-shell.io/idta/CapabilityDescription/{name}/1/0"


def seq(name: str) -> str:
    return f"{BASE}/ProductionSequence/{name}/1/0"


def external(value: str) -> dict:
    return {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": value}]}


def model(*keys: tuple[str, str]) -> dict:
    return {"type": "ModelReference", "keys": [{"type": t, "value": v} for t, v in keys]}


def shell_reference(aas_id: str) -> dict:
    return model(("AssetAdministrationShell", aas_id))


def text(value) -> str:
    return str(value).lower() if isinstance(value, bool) else str(value)


def unit_specification(name: str, unit: str) -> list[dict]:
    """The unit the standard way (IEC 61360), where the planner's matching reads it."""
    return [{"dataSpecification": external(IEC61360),
             "dataSpecificationContent": {"modelType": "DataSpecificationIec61360", "unit": unit,
                                          "preferredName": [{"language": "en", "text": name}]}}]


def prop(id_short: str, value, semantic: str | None = None, value_type: str | None = None, unit: str | None = None,
         supplemental: str | None = None) -> dict:
    number = isinstance(value, (int, float)) and not isinstance(value, bool)
    found = {"modelType": "Property", "idShort": id_short, "valueType": value_type or ("xs:double" if number else "xs:string"),
             "value": text(value)}
    if semantic:
        found["semanticId"] = external(semantic)
    if supplemental:
        found["supplementalSemanticIds"] = [external(supplemental)]
    if unit:
        found["embeddedDataSpecifications"] = unit_specification(id_short, unit)
    return found


def collection(id_short: str, children: list[dict], semantic: str | None = None) -> dict:
    found = {"modelType": SMC, "idShort": id_short, "value": children}
    if semantic:
        found["semanticId"] = external(semantic)
    return found


def reference(id_short: str, value: dict, semantic: str | None = None) -> dict:
    found = {"modelType": "ReferenceElement", "idShort": id_short, "value": value}
    if semantic:
        found["semanticId"] = external(semantic)
    return found


def submodel(id_: str, id_short: str, semantic: str, elements: list[dict]) -> dict:
    return {"modelType": "Submodel", "kind": "Instance", "id": id_, "idShort": id_short,
            "semanticId": external(semantic), "submodelElements": elements}


def plan_id(aas_id: str) -> str:
    """The planner finds a product's plan by this identifier."""
    return f"{BASE}/sm/process-plan/{base64.urlsafe_b64encode(aas_id.encode()).decode().rstrip('=')}"


# What an AAS environment holds ------------------------------------------------------------------

def children(element: dict | None) -> list[dict]:
    """The elements an element holds; none for an element that is not there."""
    element = element or {}
    held = element.get("submodelElements") or element.get("statements") or element.get("value")
    return [c for c in held if isinstance(c, dict) and "modelType" in c] if isinstance(held, list) else []


def at(element: dict | None, *path: str) -> dict | None:
    for step in path:
        element = next((c for c in children(element) if c.get("idShort") == step), None)
    return element


def semantic_ids(element: dict) -> list[str]:
    refs = [element.get("semanticId"), *element.get("supplementalSemanticIds", [])]
    return [r["keys"][0]["value"] for r in refs if r and r.get("keys")]


def resolve(envs: list[dict], ref: dict | None) -> dict | None:
    """The submodel element a model reference names, in any of the environments."""
    keys = (ref or {}).get("keys") or []
    if not keys or keys[0]["type"] != "Submodel":
        return None
    node = next((s for env in envs for s in env["submodels"] if s["id"] == keys[0]["value"]), None)
    for key in keys[1:]:
        node = at(node, key["value"]) if node else None
    return node


def shell_of(env: dict) -> dict:
    return env["assetAdministrationShells"][0]


# Building ---------------------------------------------------------------------------------------

def nameplate(template: dict, aas_id: str, spec: dict) -> dict:
    """The nameplate the resources carry, with the product's own designation."""
    plate = copy.deepcopy(template)
    plate["id"] = f"{aas_id}/submodels/Nameplate"
    for element in plate["submodelElements"]:
        if element["idShort"] == "ManufacturerProductDesignation":
            element["value"] = [{"language": "en", "text": spec.get("designation") or spec["name"]}]
        elif element["idShort"] == "URIOfTheProduct":
            element["value"] = f"{BASE}/assets/{spec['product']}"
    return plate


def build(spec: dict, resources: dict[str, dict], nameplate_template: dict) -> dict:
    """The AAS environment of the product ``spec`` describes; ``resources``: the environments of
    the resources its plan names, by the idShort of their shell."""
    name = spec["product"]
    aas_id = f"{BASE}/aas/{name}AAS"
    sm = lambda id_short: f"{aas_id}/submodels/{id_short}"                           # noqa: E731

    parts = [{"modelType": "Entity", "idShort": part, "entityType": "CoManagedEntity",
              "displayName": [{"language": "en", "text": about.get("name", part)}],
              "statements": [prop("Quantity", about.get("quantity", 1), f"{VOCABULARY}/Quantity"),
                             prop("QuantityUnit", about.get("unit", "piece"), f"{VOCABULARY}/QuantityUnit")]}
             for part, about in spec.get("parts", {}).items()]
    bom = submodel(sm("HierarchicalStructures"), "HierarchicalStructures", HIERARCHICAL_STRUCTURES, [
        {"modelType": "Entity", "idShort": "EntryNode", "entityType": "SelfManagedEntity",
         "globalAssetId": f"{BASE}/assets/{name}", "displayName": [{"language": "en", "text": spec["name"]}],
         "semanticId": external("https://admin-shell.io/idta/HierarchicalStructures/EntryNode/1/0"), "statements": parts},
        prop("ArcheType", "OneDown", "https://admin-shell.io/idta/HierarchicalStructures/ArcheType/1/0")])

    processes, required = [], []
    for process, about in spec["processes"].items():
        parameters = [prop(p, v["value"], f"{VOCABULARY}/{p}", unit=v.get("unit")) for p, v in about.get("parameters", {}).items()]
        capability = {
            "modelType": "Capability", "idShort": "Capability", "semanticId": external(cap("Capability")),
            "supplementalSemanticIds": [external(f"{VOCABULARY}/{about['requires']}")],
            "displayName": [{"language": "en", "text": about["requires"]}],
            "qualifiers": [{"type": "CapabilityRoleQualifier/Required", "kind": "ValueQualifier", "valueType": "xs:boolean",
                            "value": "true", "semanticId": external(cap("CapabilityRoleQualifier/Required"))}]}
        values = [collection(p, [prop("Value", v["value"], "https://admin-shell.io/idta/CapabilityPropertyType/Property/1/0",
                                      unit=v.get("unit"), supplemental=f"{VOCABULARY}/{p}")], cap("PropertyContainer"))
                  for p, v in about.get("parameters", {}).items()]
        required.append(collection(process, [capability, collection("PropertySet", values, cap("PropertySet"))],
                                   cap("CapabilityContainer")))
        materials = [reference(m, model(("Submodel", bom["id"]), ("Entity", "EntryNode"), ("Entity", m)))
                     for m in about.get("materials", [])]
        processes.append(collection(process, [
            prop("ProcessId", process, pp("ProcessId")), prop("ProcessName", process, pp("ProcessName")),
            {"modelType": "MultiLanguageProperty", "idShort": "ProcessDescription", "semanticId": external(pp("ProcessDescription")),
             "value": [{"language": "en", "text": about.get("description", process)}]},
            collection("ProductParameters", parameters, pp("ProductParameters")),
            collection("ProcessParameters", [], pp("ProcessParameters")),
            collection("ResourceParameters", [], pp("ResourceParameters")),
            collection("ProcessBoM", materials, pp("ProcessBoM")),
            reference("RequiredCapability", model(("Submodel", sm("CapabilityDescription")), (SMC, "RequiredCapabilities"),
                                                  (SMC, process), ("Capability", "Capability")), REQUIRED_CAPABILITY),
        ], pp("Process")))
    parameters_sm = submodel(sm("ProcessParameters"), "ProcessParameters", PROCESS_PARAMETERS,
                             [collection("Processes", processes, pp("Processes"))])
    capabilities = submodel(sm("CapabilityDescription"), "CapabilityDescription", CAPABILITY_DESCRIPTION,
                            [collection("RequiredCapabilities", required, cap("CapabilitySet"))])

    steps = []
    for order, step in enumerate(spec["sequence"]):
        process = step["process"]
        resource = shell_of(resources[step["resource"]])
        skills = next(s["id"] for s in resources[step["resource"]]["submodels"] if s["idShort"] == "Skills")
        bindings = [collection(f"Binding_{i:04d}", [
            prop("Name", parameter, seq("Name")), prop("Value", "", seq("Value")),
            reference("SourceAas", shell_reference(aas_id), seq("SourceAas")),
            reference("SourceElement", model(("Submodel", parameters_sm["id"]), (SMC, "Processes"), (SMC, process),
                                             (SMC, "ProductParameters"), ("Property", source)), seq("SourceElement")),
        ], seq("Binding")) for i, (parameter, source) in enumerate(step.get("bind", {}).items())]
        steps.append(collection(f"Step_{order:04d}", [
            prop("NodeId", process, seq("NodeId")), prop("Kind", "step", seq("Kind")), prop("Name", process, seq("Name")),
            prop("Order", order, seq("Order"), "xs:nonNegativeInteger"),
            reference("ProcessOwner", shell_reference(aas_id), seq("ProcessOwner")),
            reference("ProcessReference", model(("Submodel", parameters_sm["id"]), (SMC, "Processes"), (SMC, process)),
                      seq("ProcessReference")),
            reference("Resource", shell_reference(resource["id"]), seq("Resource")),
            prop("SkillId", step["skill"], seq("SkillId")),
            reference("Skill", model(("Submodel", skills), (SMC, "Skills"), (SMC, step["skill"])), seq("Skill")),
            prop("ExecutionMode", "station", seq("ExecutionMode")),
            collection("Bindings", bindings, seq("Bindings")),
        ], seq("Step")))
    plan = submodel(plan_id(aas_id), "ProductionSequence", PRODUCTION_SEQUENCE, [
        prop("PlanSchema", "production-sequence/2.0", seq("PlanSchema")),
        prop("Revision", 1, seq("Revision"), "xs:nonNegativeInteger"),
        prop("SequenceId", "product", seq("SequenceId")), prop("Name", spec["name"], seq("Name")),
        prop("Role", "Primary", seq("Role")), reference("Subject", shell_reference(aas_id), seq("Subject")),
        collection("Steps", steps, seq("Steps"))])

    submodels = [nameplate(nameplate_template, aas_id, spec), bom, parameters_sm, capabilities, plan]
    shell = {"modelType": "AssetAdministrationShell", "id": aas_id, "idShort": f"{name}AAS",
             "displayName": [{"language": "en", "text": spec["name"]}],
             "description": [{"language": "en", "text": spec.get("description", spec["name"])}],
             "assetInformation": {"assetKind": "Type", "globalAssetId": f"{BASE}/assets/{name}"},
             "submodels": [model(("Submodel", s["id"])) for s in submodels]}
    return {"assetAdministrationShells": [shell], "submodels": submodels}


# Checking ---------------------------------------------------------------------------------------

def number(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def unit_of(element: dict) -> str | None:
    """An element's unit: its ``Unit`` qualifier, else its IEC 61360 data specification."""
    for qualifier in element.get("qualifiers") or []:
        if qualifier.get("type") == "Unit":
            return qualifier.get("value")
    for spec in element.get("embeddedDataSpecifications") or []:
        if spec.get("dataSpecificationContent", {}).get("unit"):
            return spec["dataSpecificationContent"]["unit"]
    return None


def covers(offered: dict, wanted: dict) -> bool:
    """An offered value or range covers the value a product asks for."""
    if offered.get("modelType") == "Range":
        value = number(wanted.get("value"))
        return value is not None and number(offered.get("min")) <= value <= number(offered.get("max"))
    a, b = number(offered.get("value")), number(wanted.get("value"))
    return a == b if a is not None and b is not None else str(offered.get("value")) == str(wanted.get("value"))


def check(product: dict, resources: dict[str, dict]) -> list[str]:
    """What does not hold when the product's plan is followed into the resources: one line each,
    none if every step can be run as planned."""
    envs, found = [product, *resources.values()], []
    by_id = {shell_of(env)["id"]: env for env in resources.values()}
    plan = next(s for s in product["submodels"] if s["idShort"] == "ProductionSequence")
    for step in children(at(plan, "Steps")):
        name = at(step, "Name")["value"]
        process = resolve(envs, at(step, "ProcessReference")["value"])
        resource = by_id.get(at(step, "Resource")["value"]["keys"][0]["value"])
        skill = resolve(envs, at(step, "Skill")["value"])
        if process is None or resource is None or skill is None:
            missing = [what for what, it in (("process", process), ("resource", resource), ("skill", skill)) if it is None]
            found.append(f"{name}: no such {' or '.join(missing)}")
            continue
        if skill["idShort"] != at(step, "SkillId")["value"]:
            found.append(f"{name}: SkillId {at(step, 'SkillId')['value']} is not the skill {skill['idShort']} it refers to")

        # The capability the process requires is one the resource offers, realized by this skill.
        wanted = resolve(envs, at(process, "RequiredCapability")["value"])
        needs = resolve(envs, {**at(process, "RequiredCapability")["value"],
                               "keys": at(process, "RequiredCapability")["value"]["keys"][:-1]})
        meaning = set(semantic_ids(wanted or {})[1:])
        offers = [container for capability_set in children(next(s for s in resource["submodels"] if s["idShort"] == "CapabilityDescription"))
                  for container in children(capability_set) if meaning & set(semantic_ids(at(container, "Capability") or {})[1:])]
        if wanted is None or not offers:
            found.append(f"{name}: {shell_of(resource)['idShort']} offers no capability with the meaning the process requires")
            continue
        offer = offers[0]
        realized = [resolve(envs, relation.get("second")) for relation in children(at(offer, "CapabilityRelations"))]
        if skill not in realized:
            found.append(f"{name}: the capability {offer['idShort']} is not realized by {skill['idShort']}")
        for asked in children(at(needs, "PropertySet")):
            value = at(asked, "Value")
            given = next((at(c, "Value") for c in children(at(offer, "PropertySet"))
                          if set(semantic_ids(at(c, "Value"))[1:]) & set(semantic_ids(value)[1:])), None)
            if given is None:
                found.append(f"{name}: {offer['idShort']} says nothing about {asked['idShort']}")
            elif unit_of(given) != unit_of(value):
                found.append(f"{name}: {asked['idShort']} is asked in {unit_of(value)} and offered in {unit_of(given)}")
            elif not covers(given, value):
                found.append(f"{name}: {asked['idShort']} = {value['value']} is not covered by {offer['idShort']}")

        # What is bound reaches a parameter of the skill, within its limits.
        for binding in children(at(step, "Bindings")):
            parameter = at(skill, "Parameters", at(binding, "Name")["value"])
            source = resolve(envs, at(binding, "SourceElement")["value"])
            label = f"{name}: {skill['idShort']}.{at(binding, 'Name')['value']}"
            if parameter is None:
                found.append(f"{label} is not a parameter of the skill")
            elif source is None:
                found.append(f"{label} is bound to a product parameter that does not exist")
            else:
                limits = {q["type"]: number(q["value"]) for q in parameter.get("qualifiers") or []}
                value = number(source["value"])
                if unit_of(parameter) != unit_of(source):
                    found.append(f"{label} is in {unit_of(parameter)}, {source['idShort']} in {unit_of(source)}")
                elif value is None or not (limits.get("Minimum", value) <= value <= limits.get("Maximum", value)):
                    found.append(f"{label}: {source['idShort']} = {source['value']} is outside "
                                 f"{limits.get('Minimum')} to {limits.get('Maximum')}")
    return found
