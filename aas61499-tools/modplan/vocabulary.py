"""What holds of each kind of capability wherever it is used, as the lab's vocabulary states it
(``ontology/Vocabulary``, 0.2): a capability class's constraints (PPRL's pre, post and invariant),
the capability a skill type realizes, which properties are the product's, and what a result needs.
A module's Capability Description states the same for its components' capabilities, and adds what
holds on that module only.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph, Namespace, RDFS, URIRef

from .expression import Expression, parse

ONTOLOGY = Path(__file__).resolve().parents[2] / "ontology"
LAB = Namespace("https://smartproductionlab.aau.dk/semantics/")
SKILLS = Namespace("https://smartproductionlab.aau.dk/skills/")
PPRL = Namespace("https://w3id.org/2025/pprl#")
KINDS = {"Pre": PPRL.pre, "Post": PPRL.post, "Invariant": PPRL.invariant}


def local(iri) -> str:
    return str(iri).rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1]


@dataclass(frozen=True)
class Stated:
    kind: str                       # Pre, Post or Invariant
    prop: str                       # the property class it is about, by local name
    expression: Expression


class Vocabulary:
    def __init__(self, graph: Graph | None = None, ontology: Path = ONTOLOGY):
        if graph is None:
            graph = Graph()
            for path in sorted((ontology / "Vocabulary").glob("*.ttl")):
                graph.parse(path, format="turtle")
        self.graph = graph

    def _stated(self, subject: URIRef, kind: str, predicate) -> list[Stated]:
        found = []
        for node in self.graph.objects(subject, predicate):
            prop, text = self.graph.value(node, PPRL.onProperty), self.graph.value(node, PPRL.expression)
            found.append(Stated(kind, local(prop), parse(str(text), kind)))
        return sorted(found, key=lambda s: s.prop)

    def constraints(self, capability: str) -> list[Stated]:
        """What a capability of the class needs, does and keeps; Post constraints on the product last,
        so that a planner reaches them after the state of the resource."""
        cls = LAB[capability]
        found = [s for kind, predicate in KINDS.items() for s in self._stated(cls, kind, predicate)]
        return sorted(found, key=lambda s: (list(KINDS).index(s.kind), self.product(s.prop)))

    def needs(self, result: str) -> list[Stated]:
        """The state that holds once a result is known (pprl:knownWhen), as goals."""
        return self._stated(LAB[result], "Pre", PPRL.knownWhen)

    def realized(self, skill_type: str) -> str | None:
        """The capability of its component a primitive of the type realizes (lab:realizes)."""
        found = self.graph.value(SKILLS[skill_type], LAB.realizes)
        return local(found) if found is not None else None

    def contributed(self, skill_type: str) -> str | None:
        found = self.graph.value(SKILLS[skill_type], LAB.contributes)
        return local(found) if found is not None else None

    def _below(self, cls: URIRef, top: URIRef) -> bool:
        return top in set(self.graph.transitive_objects(cls, RDFS.subClassOf))

    def product(self, prop: str) -> bool:
        """A property of the product (pprl:ProductProperty), not of a resource."""
        return self._below(LAB[prop], PPRL.ProductProperty)

    def process(self, capability: str) -> bool:
        return self._below(LAB[capability], LAB.ProcessCapability)

    def characterizes(self, prop: str) -> set[str]:
        return {local(c) for c in self.graph.objects(LAB[prop], LAB.characterizes)}

    def unit(self, prop: str) -> str | None:
        found = self.graph.value(LAB[prop], LAB.unit)
        return str(found) if found is not None else None

    def value_type(self, prop: str) -> str | None:
        found = self.graph.value(LAB[prop], LAB.valueType)
        return str(found) if found is not None else None

    def label(self, iri_name: str) -> str | None:
        found = self.graph.value(LAB[iri_name], RDFS.label)
        return str(found) if found is not None else None

    def skill_types(self) -> list[str]:
        return sorted(local(s) for s in self.graph.subjects(RDFS.subClassOf, URIRef("http://www.w3id.org/hsu-aut/css#Skill"))
                      if str(s).startswith(str(SKILLS)))
