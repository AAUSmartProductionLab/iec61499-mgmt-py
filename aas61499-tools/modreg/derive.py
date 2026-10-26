"""Capabilities derived from skills (docs/ppr-model.md, section 5).

What a module offers follows from its skills and the lab's vocabulary: a module level skill offers
each process capability the types of its steps contribute, specified by the properties its
parameters and its steps' constants set. The rule is data (ontology/PPRL/derivation/*.rq) and runs
on the projection of the module's AASs (``modreg.projection``); this reads its result.

    found = offers(project([module_aas, *component_aases]))
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rdflib import Graph, Namespace, RDF

from .projection import CSS, ONTOLOGY, PA, PPRL, apply

DERIVATION = ONTOLOGY / "PPRL" / "derivation"
LAB = Namespace("https://smartproductionlab.aau.dk/semantics/")


@dataclass
class Property:
    """A property of a derived capability: a range (a parameter's limits) or a value (a constant)."""
    meaning: str                         # the property class of the vocabulary
    unit: str | None = None
    minimum: str | None = None
    maximum: str | None = None
    value: str | None = None
    parameter: str | None = None         # the element of the parameter that sets it


@dataclass
class Offer:
    """A capability a module level skill offers."""
    capability: str                      # the capability class of the vocabulary
    skill: str                           # the element of the skill realizing it
    built: bool                          # the program carries the skill out; else offered after a reconfiguration
    properties: list[Property] = field(default_factory=list)
    keys: list[tuple[str, str]] = field(default_factory=list)    # model reference to the skill: (type, value)

    @property
    def name(self) -> str:
        return local(self.capability)

    @property
    def skill_name(self) -> str:
        return local(self.skill)


def local(iri: str) -> str:
    return str(iri).rstrip("/").replace("#", "/").rsplit("/", 1)[-1]


def qualifier(graph: Graph, element, kind: str) -> str | None:
    for q in graph.objects(element, PA.qualifier):
        if str(graph.value(q, PA.type)) == kind:
            value = graph.value(q, PA.value)
            return None if value is None else str(value)
    return None


def keys(graph: Graph, element) -> list[tuple[str, str]]:
    """The keys of a model reference to an element: its submodel, then the idShorts down to it."""
    found = []
    while element is not None:
        model_type = str(graph.value(element, PA.modelType))
        if model_type == "Submodel":
            return [("Submodel", str(element)), *reversed(found)]
        found.append((model_type, str(graph.value(element, PA.idShort))))
        element = graph.value(None, PA.element, element)
    raise ValueError("an element outside a submodel")


def offers(graph: Graph, derivation: Path = DERIVATION) -> list[Offer]:
    """The capabilities the rule derives on the projection ``graph`` (which it extends), in the
    order of their skills and capabilities."""
    apply(graph, derivation)
    found = []
    for offer in set(graph.subjects(RDF.type, PPRL.DerivedCapability)):
        skill = graph.value(offer, CSS.isRealizedBySkill)
        capability = next(c for c in graph.objects(offer, RDF.type) if str(c).startswith(str(LAB)))
        element = graph.value(None, PPRL.describes, skill)
        properties = []
        for prop in graph.objects(offer, CSS.isSpecifiedBy):
            meaning = next(c for c in graph.objects(prop, RDF.type) if str(c).startswith(str(LAB)))
            unit = graph.value(meaning, LAB.unit)
            parameter = graph.value(prop, CSS.isRealizedBySkillParameter)
            if parameter is not None:
                variable = graph.value(None, PPRL.describes, parameter)
                properties.append(Property(str(meaning), str(unit) if unit else qualifier(graph, variable, "Unit"),
                                           qualifier(graph, variable, "Minimum"), qualifier(graph, variable, "Maximum"),
                                           parameter=str(variable)))
            else:
                properties.append(Property(str(meaning), str(unit) if unit else None, value=str(graph.value(prop, RDF.value))))
        found.append(Offer(str(capability), str(element), (skill, PPRL.implementedBy, None) in graph,
                           sorted(properties, key=lambda p: p.meaning), keys(graph, element)))
    return sorted(found, key=lambda o: (o.skill, o.capability))

