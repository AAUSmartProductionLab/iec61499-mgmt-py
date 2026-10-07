"""Whether a product's plan fits the resources it is planned on: every link of the plan is followed
from the product's AAS into the resources' AASs, the way an executor would.

    step -> process -> required capability -> offered capability -> skill -> bound parameter

Works on AAS environments (the JSON an AAS server holds), whoever built them.
"""
from __future__ import annotations


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
            given = at(binding, "SourceElement")
            # A binding without a source is a constant: its own Value.
            source = resolve(envs, given["value"]) if given else at(binding, "Value")
            label = f"{name}: {skill['idShort']}.{at(binding, 'Name')['value']}"
            if parameter is None:
                found.append(f"{label} is not a parameter of the skill")
            elif source is None:
                found.append(f"{label} is bound to a product parameter that does not exist")
            else:
                limits = {q["type"]: number(q["value"]) for q in parameter.get("qualifiers") or []}
                value, what = number(source.get("value")), source["idShort"] if given else "the constant"
                if given and unit_of(parameter) != unit_of(source):
                    found.append(f"{label} is in {unit_of(parameter)}, {source['idShort']} in {unit_of(source)}")
                elif value is None or not (limits.get("Minimum", value) <= value <= limits.get("Maximum", value)):
                    found.append(f"{label}: {what} = {source.get('value')} is outside "
                                 f"{limits.get('Minimum')} to {limits.get('Maximum')}")
    return found
