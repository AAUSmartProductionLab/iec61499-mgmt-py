"""The projection of AASs into RDF: their elements, and the individuals and relations they describe.

Three ids, three jobs (docs/ppr-model.md, section 3): an element's semanticId says what it is in its
template, its supplemental semantic id what it means in the domain, its own place which individual
it is. The projection follows them in three passes:

1. Every shell, submodel and element is written in the terms of ontology/PPRL/projection.ttl: its
   place, its ids, its value and qualifiers, and what its references point to, resolved to the
   element. It is named by the id of its submodel and the idShorts below it, as a model reference
   addresses it. The structure ontology (ARSO) types it by its semanticId, as ``modreg check`` does.
2. and 3. The rules in ontology/PPRL/projection/*.rq (SPARQL CONSTRUCT, in the order of their names)
   make the individuals an element describes (``pprl:describes``) and the relations of PPRL and CSS
   between them: skills of their kind and type, their parameters and what each means, the skills a
   skill's steps run and what they are handed, capabilities with their properties and the skill
   realizing them, the resource providing them, and which skills the program carries out.

The graph holds the vocabulary too, so the rules and whoever queries the result see its classes.

    graph = project([module_aas, *component_aases])         # AAS environments as JSON
"""
from __future__ import annotations

from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef

from .ontology import CHILDREN, Blueprint

ONTOLOGY = Path(__file__).resolve().parents[2] / "ontology"
RULES = ONTOLOGY / "PPRL" / "projection"
PA = Namespace("https://w3id.org/2025/pprl/aas#")
PPRL = Namespace("https://w3id.org/2025/pprl#")
CSS = Namespace("http://www.w3id.org/hsu-aut/css#")
VARIABLES = (("inputVariables", PA.input), ("inoutputVariables", PA.input), ("outputVariables", PA.output))


def node(text: str) -> URIRef:
    return URIRef(text.replace(" ", "%20"))


def target(reference: dict | None) -> URIRef | None:
    """What a reference points to: the element a model reference addresses (its keys joined, as the
    elements are named), or the id an external reference names."""
    keys = (reference or {}).get("keys") or []
    if not keys:
        return None
    if reference.get("type") == "ExternalReference":
        return node(keys[-1]["value"])
    return node("/".join(str(k["value"]) for k in keys))


class Projection:
    def __init__(self, blueprint: Blueprint | None = None):
        self.graph, self.blueprint = Graph(), blueprint
        for prefix, namespace in (("pa", PA), ("pprl", PPRL), ("css", CSS)):
            self.graph.bind(prefix, namespace)

    def add(self, s, p, o):
        if o is not None:
            self.graph.add((s, p, o))

    def element(self, iri: URIRef, element: dict, parent: set, ancestors: set, item: bool = False,
                optional: bool = False) -> set:
        """``optional``: the element is inside a decision or a conditional step of a flow (rule set 2),
        so it may not run (``pprl:mayNotRun``)."""
        g, add = self.graph, self.add
        if optional:
            add(iri, PPRL.mayNotRun, Literal(True))
        kind = next((c.get("value") for c in element.get("value") or [] if isinstance(c, dict) and c.get("idShort") == "Kind"), None)
        optional = optional or (element.get("modelType") == "SubmodelElementCollection" and kind in ("decision", "conditional"))
        model_type = element.get("modelType", "")
        add(iri, RDF.type, PA.Element)
        add(iri, PA.modelType, Literal(model_type))
        if element.get("idShort"):
            add(iri, PA.idShort, Literal(element["idShort"]))
        if element.get("semanticId", {}).get("keys"):
            add(iri, PA.semanticId, node(element["semanticId"]["keys"][0]["value"]))
        for reference in element.get("supplementalSemanticIds") or []:
            if reference.get("keys"):
                add(iri, PA.supplementalSemanticId, node(reference["keys"][0]["value"]))
        if model_type == "Property" and element.get("value") not in (None, ""):
            add(iri, PA.value, Literal(str(element["value"])))
        if element.get("valueType"):
            add(iri, PA.valueType, Literal(element["valueType"]))
        if model_type == "Range":
            for key, term in (("min", PA.min), ("max", PA.max)):
                if element.get(key) not in (None, ""):
                    add(iri, term, Literal(str(element[key])))
        if model_type == "ReferenceElement":
            add(iri, PA.refersTo, target(element.get("value")))
        if model_type in ("RelationshipElement", "AnnotatedRelationshipElement"):
            add(iri, PA.first, target(element.get("first")))
            add(iri, PA.second, target(element.get("second")))
        for qualifier in element.get("qualifiers") or []:
            q = BNode()
            g.add((iri, PA.qualifier, q))
            add(q, PA.type, Literal(qualifier.get("type", "")))
            if qualifier.get("value") is not None:
                add(q, PA.value, Literal(str(qualifier["value"])))
        classes = self.blueprint.recognise(element, parent, ancestors, item) if self.blueprint else set()
        for c in classes:
            g.add((iri, RDF.type, c))
        member = CHILDREN.get(model_type)
        for i, child in enumerate(element.get(member) or [] if member else []):
            here = URIRef(f"{iri}/{child.get('idShort') or i}")
            g.add((iri, PA.element, here))
            self.element(here, child, classes, ancestors | classes, model_type == "SubmodelElementList", optional)
        for kind, term in VARIABLES if model_type == "Operation" else ():
            for variable in element.get(kind) or []:
                child = variable["value"]
                here = URIRef(f"{iri}/{child['idShort']}")
                g.add((iri, PA.element, here))
                g.add((iri, term, here))
                self.element(here, child, classes, ancestors | classes)
        return classes

    def environment(self, env: dict):
        for sm in env.get("submodels", []):
            self.element(node(sm["id"]), sm, set(), set())
        for shell in env.get("assetAdministrationShells", []):
            iri = node(shell["id"])
            self.add(iri, RDF.type, PA.Element)
            self.add(iri, PA.modelType, Literal("AssetAdministrationShell"))
            self.add(iri, PA.idShort, Literal(shell.get("idShort", "")))
            for reference in shell.get("submodels", []):
                self.add(iri, PA.submodel, target(reference))
            if self.blueprint:
                self.graph.add((iri, RDF.type, self.blueprint.shell_class(shell)))


def vocabulary(ontology: Path = ONTOLOGY) -> Graph:
    """The lab's vocabulary: what the supplemental semantic ids name."""
    graph = Graph()
    for path in sorted((ontology / "Vocabulary").glob("*.ttl")):
        graph.parse(path, format="turtle")
    return graph


def apply(graph: Graph, rules: Path = RULES) -> Graph:
    """Add what the rules construct, in the order of their names (a later rule sees the earlier)."""
    for path in sorted(rules.glob("*.rq")):
        for triple in graph.query(path.read_text(encoding="utf-8")).graph:
            graph.add(triple)
    return graph


def project(envs: list[dict], ontology: Path = ONTOLOGY, blueprint: Blueprint | None = None,
            structure: bool = True) -> Graph:
    """The AAS environments (JSON) as RDF with the individuals and relations they describe.
    ``structure``: also type every element by the structure ontology (ARSO; slower)."""
    if structure and blueprint is None:
        blueprint = Blueprint(ontology / "ARSO")
    projection = Projection(blueprint if structure else None)
    for env in envs:
        projection.environment(env)
    graph = projection.graph
    graph += vocabulary(ontology)
    return apply(graph, ontology / "PPRL" / "projection")

