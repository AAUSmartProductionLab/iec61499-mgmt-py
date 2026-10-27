"""What a module's planner reads in its Capability Description (IDTA 02020, ARSO 0.11;
docs/skill-planning.md): a CapabilitySet per component with the capabilities its primitives realize
(role NotAssigned: no product asks for them), and the constraints of every capability, the offered
ones included.

A capability's constraints are what the vocabulary says of its class wherever it is used and, for a
component's capability, what the module spec says holds on this module (a skill's ``capability``:
named values, conditions on another item's state). Each is a BasicConstraint about a property of the
capability. A property that is a state of the module names its data point in Operational Data with
SameProperty, so that the capabilities naming one data point talk about one state.
"""
from __future__ import annotations

import functools

from aas_pydantic import Capability, ModelReference, Qualifier
from aas_pydantic.submodel_templates import capability_description as cd

from modgen.spec import CapabilityProperty, ModuleSpec, Skill
from modplan.expression import parse
from modplan.vocabulary import Vocabulary

from . import model
from .profile import CAPABILITIES, CAPABILITY, DATA, SMC, capability_property, component_identity, meaning, path

NOT_ASSIGNED = "https://admin-shell.io/idta/CapabilityDescription/CapabilityRoleQualifier/NotAssigned/1/0"
# What an item with a position publishes of its state (the signals modgen gives it).
SIGNALS = {"Position": "ActualPosition", "Referenced": "Homed"}
XSD = {"number": "xs:double", "boolean": "xs:boolean", "string": "xs:string"}


@functools.cache
def vocabulary() -> Vocabulary:
    return Vocabulary()


def state_point(spec: ModuleSpec, item: str, meant: str) -> str | None:
    """The data point of the module's Operational Data that is ``item``'s state ``meant``, if the
    module publishes one: of an item with a position its ActualPosition and Homed; of any item its
    inputs."""
    eq = spec.equipment.get(item)
    if eq is None:
        return None
    if eq.position is not None and meant in SIGNALS:
        return f"{item}_{SIGNALS[meant]}"
    return f"{item}_{meant}" if meant in eq.inputs else None


class Container:
    """One capability container being written: its properties, then its constraints about them."""

    def __init__(self, set_name: str, name: str, properties: dict[str, model.StatedProperty] | None = None):
        self.set_name, self.name = set_name, name
        self.properties = dict(properties or {})
        self.constraints: dict[str, model.BasicConstraintContainer] = {}

    def at(self, *steps: tuple[str, str]) -> ModelReference:
        return path(CAPABILITIES, (SMC, self.set_name), (SMC, self.name), *steps)

    def value_of(self, name: str) -> tuple[str, str]:
        """The model type and idShort of the element a property container holds its value in."""
        container = self.properties[name]
        return ("Range", "Value") if container.PropertyRange else ("Property", "Value")

    def add(self, name: str, container: model.StatedProperty, point: str | None = None) -> None:
        if name in self.properties:
            return
        self.properties[name] = container
        if point:
            container.SameProperty = {"SameProperty": model.SameAs(
                first=self.at((SMC, "PropertySet"), (SMC, name), self.value_of(name)), second=path(DATA, ("Property", point)))}

    def state(self, name: str, meant: str, point: str | None = None) -> None:
        """A property that is a state: no value of its own; the data point ``point`` if it is one."""
        kind = XSD.get(vocabulary().value_type(meant) or "number", "xs:double")
        self.add(name, model.StatedProperty(PropertyProperty={"Value": cd.PropertyProperty(
            id_short="Value", value_type=kind, supplemental_semantic_ids=[meaning(meant)], display_name={"en": name})}), point)

    def constrain(self, kind: str, prop: str, expression: str) -> None:
        """A constraint of ``kind`` (Pre, Post, Invariant) about the property ``prop``."""
        named = parse(expression, kind).named                  # of the language, and of its kind
        for needed in (prop, named):
            if needed and needed not in self.properties:
                raise ValueError(f"{self.name}: {kind} {prop} {expression}: it has no property {needed}")
        id_short, n = f"{kind}{prop}", 2
        while id_short in self.constraints:
            id_short, n = f"{kind}{prop}{n}", n + 1
        relations = cd.ConstraintPropertyRelations(ConstraintHasProperty={"ConstraintHasProperty": cd.ConstraintHasProperty(
            first=self.at((SMC, "CapabilityRelations"), (SMC, "ConstraintSet"), (SMC, id_short), ("Property", "BasicConstraint")),
            second=self.at((SMC, "PropertySet"), (SMC, prop), self.value_of(prop)))})
        self.constraints[id_short] = model.BasicConstraintContainer(
            id_short=id_short, BasicConstraint=cd.BasicConstraint(value=expression),
            ConstraintType=cd.ConstraintType(value="BasicConstraint"), PropertyConditionalType=cd.PropertyConditionalType(value=kind),
            ConstraintPropertyRelations=relations)

    def constraint_set(self) -> dict[str, model.ModuleConstraintSet]:
        return {"ConstraintSet": model.ModuleConstraintSet(id_short="ConstraintSet", PropertyConstraintContainer=self.constraints)} \
            if self.constraints else {}

    def property_set(self) -> dict[str, model.StatedPropertySet]:
        return {"PropertySet": model.StatedPropertySet(id_short="PropertySet", PropertyContainer=self.properties)} \
            if self.properties else {}


def component_sets(spec: ModuleSpec) -> dict[str, model.ModuleCapabilitySet]:
    """One CapabilitySet per component, named like it, with the capabilities its primitives realize."""
    sets = {}
    for item in [i for i in spec.equipment if any(d.equipment == i for d in spec.skills.values())]:
        containers = {}
        for name, decl in spec.skills.items():
            if decl.equipment != item or (cls := vocabulary().realized(name)) is None:
                continue
            if cls in containers:
                raise ValueError(f"{spec.module}: {item} has two skills that realize {cls}")
            containers[cls] = component_capability(spec, item, name, decl, cls)
        if containers:
            sets[item] = model.ModuleCapabilitySet(id_short=item, CapabilityContainer=containers)
    return sets


def component_capability(spec: ModuleSpec, item: str, skill: str, decl: Skill, cls: str) -> model.ModuleCapabilityContainer:
    """The capability ``cls`` of ``item``, realized by its primitive ``skill``."""
    voc, box, use = vocabulary(), Container(item, cls), decl.capability
    # What it is given: the skill's parameters, as the property of the vocabulary of that name if
    # one describes the capability (a dose is a Volume), else as the parameter means.
    for name, p in decl.parameters.items():
        meant = name if cls in voc.characterizes(name) else (p.meaning or name).rsplit("/", 1)[-1]
        if p.minimum is None or p.maximum is None:
            box.state(name, meant, state_point(spec, item, meant))
            continue
        box.add(name, capability_property(name, meaning(meant), CapabilityProperty(minimum=p.minimum, maximum=p.maximum, unit=p.unit),
                                          derived=False), state_point(spec, item, meant))
    for name, value in (use.values.items() if use else ()):
        box.add(name, capability_property(name, meaning(name, value.semantic_id), value, derived=False))
    stated = voc.constraints(cls)
    for s in stated:
        for name in filter(None, (s.prop, s.expression.named)):
            box.state(name, name, None if voc.product(name) else state_point(spec, item, name))
    conditions = []
    for kind, about, expression in (use.conditions() if use else ()):
        other, _, meant = about.rpartition(".")
        if other:
            point = state_point(spec, other, meant)
            if point is None:
                raise ValueError(f"{spec.module}.{skill}: {other} publishes no {meant}, so {cls} cannot be about it")
            about = f"{other}{meant}"
            box.state(about, meant, point)
        conditions.append((kind, about, expression))
    for s in stated:
        box.constrain(s.kind, s.prop, str(s.expression))
    for kind, about, expression in conditions:
        box.constrain(kind, about, expression)
    capability = Capability(
        id_short="Capability", semantic_id=CAPABILITY, supplemental_semantic_ids=[meaning(cls)], display_name={"en": cls},
        description=f"{voc.label(cls) or cls} of {item}, realized by {skill}",
        qualifiers=[Qualifier(type_="CapabilityRoleQualifier/NotAssigned", value="true", semantic_id=NOT_ASSIGNED, kind="ConceptQualifier")])
    skills = f"{component_identity(spec, item)[1]}/submodels/Skills"
    realized = model.RealizedBySkill(id_short="RealizedBy", first=box.at(("Capability", "Capability")), second=path(skills, (SMC, skill)))
    return model.ModuleCapabilityContainer(
        id_short=cls, Capability=capability, PropertySet=box.property_set(),
        CapabilityRelations=model.ModuleCapabilityRelations(id_short="CapabilityRelations", CapabilityRealizedBy={"RealizedBy": realized},
                                                            ConstraintSet=box.constraint_set()))


def constrain_offer(container: model.ModuleCapabilityContainer, set_name: str, cls: str) -> None:
    """Add to an offered capability what the vocabulary says it needs and does to the product."""
    sets = container.PropertySet.get("PropertySet")
    box = Container(set_name, container.id_short, sets.PropertyContainer if sets else {})
    stated = vocabulary().constraints(cls)
    for s in stated:
        for name in filter(None, (s.prop, s.expression.named)):
            box.state(name, name)
    for s in stated:
        box.constrain(s.kind, s.prop, str(s.expression))
    container.PropertySet = box.property_set()
    if box.constraints:
        container.CapabilityRelations.ConstraintSet = box.constraint_set()
