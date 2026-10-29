"""Whether a product's recipe fits the resources it is bound to: every link is followed from the
product's AAS and its process AAS into the resources' AASs, the way an executor would.

    step -> process -> required capability -> offered capability -> skill -> bound parameter

A parameter of a skill is an input variable of the Operation of its Start command. The bindings are
the process AAS's (``check_process``), or, as the process sequence planner writes them today, the
recipe's own (``check``).

Works on AAS environments (the JSON an AAS server holds), whoever built them.
"""
from __future__ import annotations


# What an AAS environment holds ------------------------------------------------------------------

def children(element: dict | None) -> list[dict]:
    """The elements an element holds (of an Operation: its variables); none for an element that is
    not there."""
    element = element or {}
    if element.get("modelType") == "Operation":
        return [v["value"] for kind in ("inputVariables", "inoutputVariables", "outputVariables")
                for v in element.get(kind) or []]
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
    """An offered value, list of values or range covers what a product asks for: a value, or a range
    the offered value has to lie in (at most so much fill error)."""
    if offered.get("modelType") == "SubmodelElementList":
        return any(covers(item, wanted) for item in offered.get("value") or [])
    if wanted.get("modelType") == "Range" and offered.get("modelType") != "Range":
        value = number(offered.get("value"))
        return value is not None and number(wanted.get("min")) <= value <= number(wanted.get("max"))
    if offered.get("modelType") == "Range":
        value = number(wanted.get("value"))
        return value is not None and number(offered.get("min")) <= value <= number(offered.get("max"))
    a, b = number(offered.get("value")), number(wanted.get("value"))
    return a == b if a is not None and b is not None else str(offered.get("value")) == str(wanted.get("value"))


def step_fits(name: str, envs: list[dict], process: dict | None, resource: dict | None, skill: dict | None,
              bindings: list[dict]) -> list[str]:
    """What does not hold of one step bound to ``resource`` and its ``skill``, ``bindings`` handing
    each input (by ``Name``) a value: a ``SourceElement`` of the product, or a constant ``Value``."""
    if process is None or resource is None or skill is None:
        missing = [what for what, it in (("process", process), ("resource", resource), ("skill", skill)) if it is None]
        return [f"{name}: no such {' or '.join(missing)}"]
    found = []

    # The capability the process requires is one the resource offers, realized by this skill.
    wanted = resolve(envs, at(process, "RequiredCapability")["value"])
    needs = resolve(envs, {**at(process, "RequiredCapability")["value"],
                           "keys": at(process, "RequiredCapability")["value"]["keys"][:-1]})
    meaning = set(semantic_ids(wanted or {})[1:])
    offers = [container for capability_set in children(next((s for s in resource["submodels"] if s["idShort"] == "CapabilityDescription"), None))
              for container in children(capability_set) if meaning & set(semantic_ids(at(container, "Capability") or {})[1:])]
    if wanted is None or not offers:
        return [f"{name}: {shell_of(resource)['idShort']} offers no capability with the meaning the process requires"]
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
            asked_for = value.get("value", f"{value.get('min')} to {value.get('max')}")
            found.append(f"{name}: {asked['idShort']} = {asked_for} is not covered by {offer['idShort']}")

    # What is bound reaches a parameter of the skill, within its limits.
    for binding in bindings:
        parameter = at(skill, "Start", "Start", at(binding, "Name")["value"])
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
        # A process AAS also names the input itself.
        named = at(binding, "InputReference")
        if named is not None and parameter is not None and resolve(envs, named["value"]) is not parameter:
            found.append(f"{label}: its InputReference is not that input")
    return found


def check_process(product: dict, process: dict, resources: dict[str, dict]) -> list[str]:
    """What does not hold when the process AAS's bindings of the product's recipe are followed into
    the resources: one line each, none if every step can be run as bound. Every step of the recipe
    needs a binding."""
    envs, found = [product, process, *resources.values()], []
    by_id = {shell_of(env)["id"]: env for env in resources.values()}
    recipe = next(s for s in product["submodels"] if s["idShort"] == "ProductionSequence")
    bound = set()
    for binding in children(next(s for s in process["submodels"] if s["idShort"] == "Bindings")):
        step = resolve(envs, at(binding, "Step")["value"])
        if step is None:
            found.append(f"{binding['idShort']}: its step is not in the recipe")
            continue
        bound.add(step["idShort"])
        resource = by_id.get(at(binding, "Resource")["value"]["keys"][0]["value"]) if at(binding, "Resource") else None
        skill = resolve(envs, at(binding, "Skill")["value"]) if at(binding, "Skill") else None
        found += step_fits(at(step, "Name")["value"], envs, resolve(envs, at(step, "ProcessReference")["value"]),
                           resource, skill, children(at(binding, "Bindings")))
    found += [f"{at(step, 'Name')['value']}: not bound" for step in children(at(recipe, "Steps"))
              if step["idShort"] not in bound]
    return found


def check(product: dict, resources: dict[str, dict]) -> list[str]:
    """What does not hold when the product's recipe, with the bindings it carries itself (as the
    planner writes them today), is followed into the resources: one line each, none if every step
    can be run as planned."""
    envs, found = [product, *resources.values()], []
    by_id = {shell_of(env)["id"]: env for env in resources.values()}
    plan = next(s for s in product["submodels"] if s["idShort"] == "ProductionSequence")
    for step in children(at(plan, "Steps")):
        name = at(step, "Name")["value"]
        resource = by_id.get(at(step, "Resource")["value"]["keys"][0]["value"]) if at(step, "Resource") else None
        skill = resolve(envs, at(step, "Skill")["value"]) if at(step, "Skill") else None
        if skill is not None and at(step, "SkillId") and skill["idShort"] != at(step, "SkillId")["value"]:
            found.append(f"{name}: SkillId {at(step, 'SkillId')['value']} is not the skill {skill['idShort']} it refers to")
        found += step_fits(name, envs, resolve(envs, at(step, "ProcessReference")["value"]), resource, skill,
                           children(at(step, "Bindings")))
    return found
