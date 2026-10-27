"""A module's planning domain from its AAS alone (ARSO 0.11; docs/skill-planning.md, sections 2 to 4).

- Its Capability Description: the set of each component holds the component's capabilities, the
  actions; the OfferedCapabilities hold the tasks. A capability is realized by the skill its
  CapabilityRealizedBy names.
- A capability's properties: one with a Range is a parameter (its default the realizing skill's);
  one with a value is a named value; one a constraint is about is a state variable: the data point
  its SameProperty names, else the product's if its meaning is a property of the product, else the
  component's whose set holds it.
- Its constraints: the BasicConstraint of each PropertyConstraintContainer, about the property its
  ConstraintHasProperty names.
- The results a task can give: the vocabulary's properties of its class that say when they are
  known (a fill weight: once the container is weighed).
- The rest state: what the module's Reset procedure leaves (``Domain.after`` its steps).
"""
from __future__ import annotations

from modsync.aasjson import at, children, submodel
from modsync.described import described

from .domain import PRODUCT, Capability, Constraint, Domain, Parameter, Var
from .expression import parse
from .vocabulary import Vocabulary, local

OFFERED_SET = "OfferedCapabilities"
RESET = "Resetting"


def _meaning(element: dict) -> str | None:
    ids = element.get("supplementalSemanticIds") or []
    return local(ids[0]["keys"][0]["value"]) if ids else None


def _value(element: dict):
    text, kind = element.get("value"), element.get("valueType")
    if text is None:
        return None
    if kind == "xs:boolean":
        return str(text).lower() == "true"
    return float(text) if kind in ("xs:double", "xs:float", "xs:decimal") else text


def read(module: dict, components: list[dict], vocabulary: Vocabulary | None = None) -> Domain:
    """The planning domain of the module ``module`` (its AAS, as JSON) with its ``components``."""
    voc = vocabulary or Vocabulary()
    spec = described(module, components)
    shell = module["assetAdministrationShells"][0]
    caps = {}
    for capability_set in children(submodel(module, "CapabilityDescription")):
        component = None if capability_set["idShort"] == OFFERED_SET else capability_set["idShort"]
        for container in children(capability_set):
            cap = _capability(container, component, spec, voc)
            if cap is not None:
                caps[cap.name if cap.name not in caps else f"{component}{cap.name}"] = cap
    domain = Domain(shell["idShort"], caps)
    reset = spec.procedures.get(RESET, [])
    domain.rest = domain.after([(step.skill, {k: v for k, v in step.bind.items() if not isinstance(v, str)}) for step in reset])
    return domain


def _capability(container: dict, component: str | None, spec, voc: Vocabulary) -> Capability | None:
    element = at(container, "Capability")
    if element is None:
        return None
    relations = at(container, "CapabilityRelations")
    realized = [r for r in children(relations) if r.get("modelType") == "RelationshipElement" and r.get("second")]
    skill = realized[0]["second"]["keys"][-1]["value"] if realized else None
    cap = Capability(name=container["idShort"], meaning=_meaning(element) or container["idShort"], skill=skill, component=component)
    decl = spec.skills.get(skill) or spec.composites.get(skill)
    variables: dict[str, Var] = {}
    for prop in children(at(container, "PropertySet")):
        value = at(prop, "Value")
        if value is None:
            continue
        name, meant = prop["idShort"], _meaning(value) or prop["idShort"]
        if value.get("modelType") == "Range":
            given = decl.parameters.get(name) if decl is not None else None
            cap.parameters[name] = Parameter(_number(value.get("min")), _number(value.get("max")),
                                             given.default if given is not None else None)
        elif value.get("value") is not None:
            cap.values[name] = _value(value)
        same = at(prop, "SameProperty")
        if same is not None and same.get("second"):
            variables[name] = Var(same["second"]["keys"][-1]["value"], meant)
        elif voc.product(meant):
            variables[name] = Var(PRODUCT, meant)
        else:
            variables[name] = Var(component or "module", meant)
    for record in children(at(relations, "ConstraintSet")):
        kind = at(record, "PropertyConditionalType")["value"]
        expression = parse(at(record, "BasicConstraint")["value"], kind)
        (has,) = [r for r in children(at(record, "ConstraintPropertyRelations")) if r.get("second")]
        prop = has["second"]["keys"][-2]["value"]
        constraint = Constraint(prop, variables[prop], expression)
        {"Pre": cap.pre, "Post": cap.post, "Invariant": cap.invariant}[kind].append(constraint)
    if component is None:
        for result in voc.results(cap.meaning):
            cap.results[result] = [Constraint(s.prop, Var(PRODUCT if voc.product(s.prop) else "module", s.prop), s.expression)
                                   for s in voc.needs(result)]
    return cap


def _number(text) -> float | None:
    return None if text is None else float(text)
