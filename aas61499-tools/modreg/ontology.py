"""Check that an AAS follows the structure its ontology describes.

The ontology (ARSO for a resource AAS) is the blueprint: one class per kind of submodel and
element, and OWL restrictions for what each must, may and may not contain. Its annotation
properties say how an element of an AAS is recognised as a member of a class:

- ``arso:semanticId``: by its semanticId;
- ``arso:parentClass`` with ``arso:idShort``: by its idShort below a parent of that class
  (``arso:transitiveParentClass``: below it at any depth);
- ``arso:parentClass`` alone: every child of that parent with the class's AAS model type that no
  idShort rule claims (an item of a list has neither idShort nor, often, a semanticId of its own, so
  there this also holds for a class that is otherwise recognised by its semanticId);
- ``arso:unconditionalAasType``: every element of that AAS model type.

``Blueprint`` reads a folder of Turtle files once; ``check`` gives every element of an AAS (the JSON
environment: shells and submodels) its classes and tests the restrictions of each. Nothing here is
specific to ARSO's content, so a change to the ontology changes the check.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, OWL, RDF, RDFS, URIRef
from rdflib.collection import Collection

AAS = "https://admin-shell.io/aas/3/1/"
ARSO = Namespace("https://w3id.org/2025/arso#")
RESOURCE_AAS = ARSO.ResourceAAS
# Containment properties of the AAS metamodel and the JSON member holding the children.
CONTAINS = {f"{AAS}Submodel/submodelElements": "submodelElements",
            f"{AAS}SubmodelElementCollection/value": "value",
            f"{AAS}SubmodelElementList/value": "value",
            f"{AAS}Entity/statements": "statements"}
CHILDREN = {"Submodel": "submodelElements", "SubmodelElementCollection": "value", "SubmodelElementList": "value",
            "Entity": "statements"}
# Links only the world outside the AAS can settle (which resource a shell stands for).
OUTSIDE = {ARSO.hasAAS, ARSO.representsResource}


@dataclass(frozen=True)
class Restriction:
    """One OWL restriction: ``kind`` on the values of ``prop``, counted against ``target``."""
    prop: URIRef
    kind: str                       # exactly | min | max | some | only | value
    number: int = 0
    target: object = None           # class, tuple of classes (union), frozenset of literals, value; None = any


@dataclass(frozen=True)
class Finding:
    severity: str                   # error: a restriction is broken; unknown: not in the ontology; note: not checked
    path: str
    message: str

    def __str__(self):
        return f"{self.severity}: {self.path}: {self.message}"


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    classes: dict[str, list[str]] = field(default_factory=dict)      # element path -> ontology classes

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def unknown(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "unknown"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def lines(self) -> list[str]:
        return [str(f) for f in self.findings]

    def summary(self) -> str:
        known = sum(1 for c in self.classes.values() if c)
        return (f"{known} of {len(self.classes)} elements are in the ontology, "
                f"{len(self.errors)} restrictions broken, {len(self.unknown)} not described")


def name(term) -> str:
    """Short name of a class for messages."""
    if isinstance(term, tuple):
        return " or ".join(name(t) for t in term)
    text = str(term)
    return text.rsplit("#", 1)[-1] if "#" in text else text.rstrip("/").rsplit("/", 1)[-1]


def semantic_ids(element: dict) -> list[str]:
    refs = [element.get("semanticId"), *element.get("supplementalSemanticIds", [])]
    return [r["keys"][0]["value"] for r in refs if r and r.get("keys")]


class Blueprint:
    """The classes of an ontology with how to recognise their members and what they must contain."""

    def __init__(self, folder: Path | str):
        self.folder = Path(folder)
        files = sorted(self.folder.rglob("*.ttl"))
        if not files:
            raise FileNotFoundError(f"no ontology files (*.ttl) in {self.folder}")
        g = self.graph = Graph()
        for f in files:
            g.parse(f, format="turtle")
        self.by_semantic: dict[str, set[URIRef]] = {}
        self.id_short: dict[URIRef, set[str]] = {}
        self.parents: dict[URIRef, set[URIRef]] = {}
        self.above: dict[URIRef, set[URIRef]] = {}
        self.everywhere: dict[str, set[URIRef]] = {}
        named = {s for s in g.subjects(RDF.type, OWL.Class) if isinstance(s, URIRef)}
        for c in named:
            for s in g.objects(c, ARSO.semanticId):
                self.by_semantic.setdefault(str(s), set()).add(c)
            self.id_short[c] = {str(o) for o in g.objects(c, ARSO.idShort)}
            self.parents[c] = set(g.objects(c, ARSO.parentClass))
            self.above[c] = set(g.objects(c, ARSO.transitiveParentClass))
            for t in g.objects(c, ARSO.unconditionalAasType):
                self.everywhere.setdefault(name(t), set()).add(c)
        self.supers = {c: self._supers(c) for c in named}
        self.model_type = {c: next((name(s) for s in self.supers[c] if str(s).startswith(AAS)), None) for c in named}
        self.restrictions = {c: self._restrictions(c) for c in named}
        self.classes = named
        # The kinds of resource, each recognised by how the asset type of its AAS begins.
        self.asset_types = {str(o): c for c in named for o in g.objects(c, ARSO.assetType)}
        # Classes with children the ontology describes: only there is an unrecognised child a finding.
        self.described = {p for c in named for p in self.parents[c] | self.above[c]}
        # Classes recognised by a fixed value (an Entity whose entityType is SelfManagedEntity).
        self.by_value = {c for c in named if not (self.id_short[c] or self.parents[c] or self.above[c])
                         and not any(c in v for v in self.by_semantic.values())
                         and any(r.kind == "value" for r in self.restrictions[c])
                         and self.model_type[c] and not str(c).startswith(AAS)}

    def _supers(self, c: URIRef) -> set[URIRef]:
        found, todo = set(), [c]
        while todo:
            for s in self.graph.objects(todo.pop(), RDFS.subClassOf):
                if isinstance(s, URIRef) and s not in found:
                    found.add(s)
                    todo.append(s)
        return found

    def _target(self, node):
        g = self.graph
        if isinstance(node, BNode):
            union = g.value(node, OWL.unionOf)
            if union is not None:
                return tuple(Collection(g, union))
            one_of = g.value(node, OWL.oneOf)
            if one_of is not None:
                return frozenset(str(v) for v in Collection(g, one_of))
        return node

    def _restriction(self, node) -> Restriction | None:
        g = self.graph
        prop = g.value(node, OWL.onProperty)
        if prop is None:
            return None
        on = g.value(node, OWL.onClass)
        for predicate, kind in ((OWL.qualifiedCardinality, "exactly"), (OWL.minQualifiedCardinality, "min"),
                                (OWL.maxQualifiedCardinality, "max"), (OWL.cardinality, "exactly"),
                                (OWL.minCardinality, "min"), (OWL.maxCardinality, "max")):
            n = g.value(node, predicate)
            if n is not None:
                return Restriction(prop, kind, int(n), self._target(on) if on is not None else None)
        for predicate, kind in ((OWL.someValuesFrom, "some"), (OWL.allValuesFrom, "only"), (OWL.hasValue, "value")):
            v = g.value(node, predicate)
            if v is not None:
                return Restriction(prop, kind, 1, self._target(v))
        return None

    def _restrictions(self, c: URIRef) -> list:
        """Restrictions of a class; a tuple of restrictions is a choice (one of them has to hold)."""
        g, found = self.graph, []
        for s in g.objects(c, RDFS.subClassOf):
            if not isinstance(s, BNode):
                continue
            union = g.value(s, OWL.unionOf)
            if union is not None:
                found.append(tuple(r for r in (self._restriction(n) for n in Collection(g, union)) if r))
            elif (r := self._restriction(s)) is not None:
                found.append(r)
        return found

    def all_restrictions(self, c: URIRef) -> list:
        return [r for k in (c, *sorted(self.supers[c])) if k in self.restrictions for r in self.restrictions[k]]

    # Recognising members ---------------------------------------------------------------------

    def shell_class(self, shell: dict) -> URIRef:
        """The kind of resource an AAS is, by its asset type (the longest beginning that fits); a
        resource as such if it states none that is known."""
        stated = (shell.get("assetInformation") or {}).get("assetType") or ""
        fitting = [start for start in self.asset_types if stated == start or stated.startswith(start + "/")]
        return self.asset_types[max(fitting, key=len)] if fitting else RESOURCE_AAS

    def fits(self, c: URIRef, model_type: str) -> bool:
        return self.model_type.get(c) in (None, model_type)

    def recognise(self, element: dict, parent: set[URIRef], ancestors: set[URIRef], item: bool = False) -> set[URIRef]:
        """The ontology classes an element belongs to, given those of its parent and of everything
        above; ``item``: it is an item of a list."""
        mt = element.get("modelType", "")
        below = lambda c: bool(self.parents[c] & parent or self.above[c] & ancestors)       # noqa: E731
        anchored = lambda c: bool(self.parents[c] or self.above[c])                         # noqa: E731
        by_id = {c for s in semantic_ids(element) for c in self.by_semantic.get(s, ()) if self.fits(c, mt)}
        found = {c for c in by_id if below(c) or not anchored(c)}
        id_short = element.get("idShort")
        if not found:
            found = {c for c in self.classes if id_short in self.id_short[c] and below(c) and self.fits(c, mt)}
        if not found:
            claimed_by_semantic = {c for v in self.by_semantic.values() for c in v}
            found = {c for c in self.classes if not self.id_short[c] and (item or c not in claimed_by_semantic)
                     and self.parents[c] & parent and self.model_type[c] == mt}
        found |= self.everywhere.get(mt, set())
        for c in self.by_value:
            if self.model_type[c] == mt and all(holds(self, r, element, {}) for r in self.restrictions[c]
                                               if isinstance(r, Restriction) and r.kind == "value"):
                found.add(c)
        return found


def member(blueprint: Blueprint, target, element: dict, classes: set[URIRef]) -> bool:
    if target is None:
        return True
    if isinstance(target, tuple):
        return any(member(blueprint, t, element, classes) for t in target)
    if str(target).startswith(AAS):
        return name(target) in (element.get("modelType"), "SubmodelElement", "Referable")
    return target in classes or any(target in blueprint.supers.get(c, ()) for c in classes)


def values(blueprint: Blueprint, r: Restriction, element: dict, kids: dict) -> list | None:
    """What the restricted property holds on this element; None if it cannot be read from an AAS."""
    prop = str(r.prop)
    if prop in CONTAINS:
        return [k for k in kids.get("children", []) if member(blueprint, r.target, k[0], k[1])] \
            if r.kind != "only" else kids.get("children", [])
    if prop == f"{AAS}Property/value":
        v = element.get("value")
        return [] if v in (None, "") else [v]
    if prop == f"{AAS}Property/valueType":
        return [element["valueType"].removeprefix("xs:").lower()] if element.get("valueType") else []
    if prop == f"{AAS}HasSemantics/semanticId":
        return semantic_ids(element)[:1]
    if prop == f"{AAS}Entity/entityType":
        return [element["entityType"]] if element.get("entityType") else []
    if prop == f"{AAS}Entity/globalAssetId":
        return [element["globalAssetId"]] if element.get("globalAssetId") else []
    if r.prop in blueprint.graph.subjects(RDFS.subPropertyOf, ARSO.hasSubmodel) or r.prop == ARSO.hasSubmodel:
        return [k for k in kids.get("submodels", []) if member(blueprint, r.target, k[0], k[1])]
    return None


def holds(blueprint: Blueprint, r: Restriction, element: dict, kids: dict) -> bool | None:
    found = values(blueprint, r, element, kids)
    if found is None:
        return None
    if r.kind == "exactly":
        return len(found) == r.number
    if r.kind == "min":
        return len(found) >= r.number
    if r.kind == "max":
        return len(found) <= r.number
    if r.kind == "some":
        return len(found) >= 1
    if r.kind == "value":
        return [name(v).lower() for v in found] == [name(r.target).lower()]
    if isinstance(r.target, frozenset):                                     # only: an enumeration of values
        return all(str(v) in r.target for v in found)
    return all(member(blueprint, r.target, k[0], k[1]) for k in found)       # only: a class of children


def wording(r: Restriction) -> str:
    what = "a value" if r.target is None else name(r.target)
    where = name(r.prop)
    if r.kind == "exactly":
        return f"needs exactly {r.number} {what} ({where})"
    if r.kind == "min":
        return f"needs at least {r.number} {what} ({where})"
    if r.kind == "max":
        return f"may have at most {r.number} {what} ({where})"
    if r.kind == "some":
        return f"needs a {what} ({where})"
    if r.kind == "value":
        return f"{where} has to be {what}"
    if isinstance(r.target, frozenset):
        return f"{where} has to be one of {', '.join(sorted(r.target))}"
    return f"may only contain {what} ({where})"


class Check:
    def __init__(self, blueprint: Blueprint):
        self.blueprint, self.report = blueprint, Report()

    def restrictions(self, path: str, element: dict, classes: set[URIRef], kids: dict):
        b = self.blueprint
        for c in sorted(classes):
            for r in b.all_restrictions(c):
                choice = r if isinstance(r, tuple) else (r,)
                if all(x.prop in OUTSIDE for x in choice):
                    continue
                results = [holds(b, x, element, kids) for x in choice]
                if any(x is None for x in results):
                    self.add("note", path, f"{name(c)} {wording(choice[0])}: not checked")
                elif not any(results):
                    self.add("error", path, f"{name(c)} " + ", or ".join(wording(x) for x in choice))

    def add(self, severity: str, path: str, message: str):
        finding = Finding(severity, path, message)
        if finding not in self.report.findings:
            self.report.findings.append(finding)

    def element(self, path: str, element: dict, parent: set[URIRef], ancestors: set[URIRef], item: bool = False) -> set[URIRef]:
        b = self.blueprint
        classes = b.recognise(element, parent, ancestors, item)
        self.report.classes[path] = sorted(name(c) for c in classes)
        if not classes and parent & b.described:
            what = semantic_ids(element)[:1] or ["no semanticId"]
            self.add("unknown", path, f"{element.get('modelType')} ({what[0]}) is not described below "
                     f"{name(tuple(sorted(parent & b.described)))}")
        member_name = CHILDREN.get(element.get("modelType", ""))
        children = []
        for i, child in enumerate(element.get(member_name) or [] if member_name else []):
            child_path = f"{path}/{child.get('idShort') or f'[{i}]'}"
            children.append((child, self.element(child_path, child, classes, ancestors | classes,
                                                 element["modelType"] == "SubmodelElementList")))
        self.restrictions(path, element, classes, {"children": children})
        return classes

    def environment(self, env: dict) -> Report:
        b = self.blueprint
        submodels = {}
        for sm in env.get("submodels", []):
            path = sm.get("idShort") or sm["id"]
            classes = self.element(path, sm, set(), set())
            submodels[sm["id"]] = (sm, classes)
            if not classes:
                what = semantic_ids(sm)[:1] or ["no semanticId"]
                self.add("unknown", path, f"submodel ({what[0]}) is not in the ontology")
        for shell in env.get("assetAdministrationShells", []):
            path = shell.get("idShort") or shell["id"]
            own = []
            for ref in shell.get("submodels", []):
                key = ref["keys"][0]["value"]
                if key in submodels:
                    own.append(submodels[key])
                else:
                    self.add("error", path, f"submodel {key} is referenced but not in the environment")
            kind = b.shell_class(shell)
            self.report.classes[path] = [name(kind)]
            self.restrictions(path, shell, {kind} & b.classes, {"submodels": own})
        return self.report


def check(env: dict, blueprint: Blueprint) -> Report:
    """Test an AAS environment (shells and submodels, as AAS JSON) against the blueprint."""
    return Check(blueprint).environment(env)
