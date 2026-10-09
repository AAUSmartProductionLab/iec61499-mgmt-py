"""From the ontology to pydantic classes, by way of submodel templates.

The lab's shared AAS model (aas-model) makes its pydantic classes from submodel templates: AAS
JSON in which every element carries its cardinality (``SMT/Cardinality``). It has the IDTA
templates; the submodels that are the resource ontology's own (Skills, Operational Data,
Parameters, Control Configuration) have no template. This module writes one for each from what
the ontology states, and has aas-model's generator make the classes from them:

    ontology (ARSO)  --template-->  templates/<Submodel>.json  --aas-model-->  generated/<submodel>.py

An element of a template is a class of the ontology: its AAS model type, its idShort (a class
without one stands for any number of elements the user names), its semanticId and, from the
restrictions of its parent, its cardinality. Children are the classes that name the parent as
``arso:parentClass`` and the classes its restrictions ask for.

Two more templates are kept as files, because they are not the ontology's: Process Parameters
(IDTA 02031-1 as published, with the lab's extension: the parameters as Properties, MaterialUse and
RequiredCapability) and Production Sequence 2.0 (the process planner's, written from the plans it
saves). Their classes are made the same way; a product's AAS is built from them (``product``).

The generator is the one in the aas-model checkout (``aas-model/scripts/idta_generate.py``), run
with field names equal to the idShorts, which is the style of the classes aas-model ships.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

from rdflib import RDFS, URIRef

from .ontology import AAS, ARSO, CONTAINS, Blueprint, Restriction, name

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"
GENERATED = HERE / "generated"
AAS_MODEL = HERE.parents[1] / "aas-model"
# The submodels of the ontology that aas-model has no template of.
SUBMODELS = ("SkillsSubmodel", "OperationalDataSubmodel", "ParametersSubmodel", "ControlConfigurationSubmodel")
# Templates kept as files in ``templates``: not written from the ontology.
GIVEN = ("ProcessParameters", "ProductionSequence")
CARDINALITY = "https://admin-shell.io/SubmodelTemplates/Cardinality/1/0"
SUFFIX = re.compile(r"(Submodel|SMC|SML|Property|Ref|Element|Rel|Entity)$")
MANY = ("ZeroToMany", "OneToMany")


def reference(value: str) -> dict:
    return {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": value}]}


def stem(cls: URIRef) -> str:
    """The name of what a class stands for: SkillSMC is a Skill."""
    return SUFFIX.sub("", name(cls))


class Templates:
    """Submodel templates from the classes of an ontology."""

    def __init__(self, blueprint: Blueprint):
        self.b = blueprint
        # Classes in the order the ontology declares them, so a template lists children that way.
        self.position: dict[URIRef, int] = {}
        text = "\n".join(p.read_text(encoding="utf-8") for p in sorted(blueprint.folder.rglob("*.ttl")))
        local = {name(c): c for c in blueprint.classes}
        # The idShorts of a class in the order it names them (the commands of a skill: Start, Stop, ...).
        self.named: dict[URIRef, list[str]] = {}
        for match in re.finditer(r"^\w*:(\w+)\s+(?:rdf:type|a)\s+owl:Class", text, re.MULTILINE):
            if match.group(1) in local and local[match.group(1)] not in self.position:
                self.position[local[match.group(1)]] = match.start()
                stated = re.search(r"\w*:idShort\s+([^;\n]+)", text[match.start():text.find("\n\n", match.start())])
                self.named[local[match.group(1)]] = re.findall(r'"([^"]+)"', stated.group(1)) if stated else []

    def semantic_id(self, cls: URIRef) -> str:
        """The class's semanticId; of several, the lab's own (the others are ids it also accepts)."""
        ids = sorted(s for s, classes in self.b.by_semantic.items() if cls in classes)
        return next((s for s in ids if "smartproductionlab" in s), ids[0] if ids else "")

    def children(self, parent: URIRef) -> list[URIRef]:
        b = self.b
        asked = {r.target for r in b.all_restrictions(parent) if isinstance(r, Restriction) and str(r.prop) in CONTAINS
                 and isinstance(r.target, URIRef) and not str(r.target).startswith(AAS)}
        found = {c for c in b.classes if parent in b.parents[c]} | asked
        return sorted(found - {parent}, key=lambda c: self.position.get(c, 0))

    def cardinality(self, parent: URIRef, child: URIRef, named: bool) -> str:
        """How many of the child the parent holds, from the parent's restrictions on it."""
        low, high = 0, None if not named else 1
        for r in self.b.all_restrictions(parent):
            if not (isinstance(r, Restriction) and str(r.prop) in CONTAINS and r.target == child):
                continue
            if r.kind == "exactly":
                low, high = r.number, r.number
            elif r.kind in ("min", "some"):
                low = max(low, r.number)
            elif r.kind == "max":
                high = r.number
        if high == 1:
            return "One" if low else "ZeroToOne"
        return "OneToMany" if low else "ZeroToMany"

    def value_type(self, cls: URIRef) -> str:
        for r in self.b.all_restrictions(cls):
            if isinstance(r, Restriction) and r.kind == "value" and str(r.prop) == f"{AAS}Property/valueType":
                return "xs:" + name(r.target)[:1].lower() + name(r.target)[1:]
        return "xs:string"

    def description(self, cls: URIRef) -> str:
        """The first sentence of the class's comment, without the lead-in that repeats its name."""
        comment = " ".join(str(self.b.graph.value(cls, RDFS.comment) or "").split())
        comment = re.sub(r"^(SMC|SML|Property|ReferenceElement|RelationshipElement|Operation)\s[^—]*?\s(—|--)\s+", "", comment)
        sentence = re.split(r"(?<=[a-z0-9)])\.\s|;\ssee\s|, as currently|\s\(v\d", comment, maxsplit=1)[0].rstrip(".")
        return sentence[:1].upper() + sentence[1:] + "." if sentence else ""

    def elements(self, parent: URIRef, cls: URIRef, seen: tuple) -> list[dict]:
        """The class as template elements below ``parent``: one per idShort, or one that stands
        for the elements a user names."""
        b = self.b
        model_type = b.model_type[cls]
        order = self.named.get(cls, [])
        id_shorts = sorted(b.id_short[cls], key=lambda i: (order.index(i) if i in order else len(order), i))
        made = []
        for id_short in id_shorts or [f"{stem(cls)}__00__"]:
            element = {"modelType": model_type, "idShort": id_short}
            if self.semantic_id(cls):
                element["semanticId"] = reference(self.semantic_id(cls))
            if self.description(cls):
                element["description"] = [{"language": "en", "text": self.description(cls)}]
            element["qualifiers"] = [{"type": "SMT/Cardinality", "valueType": "xs:string", "kind": "TemplateQualifier",
                                      "value": self.cardinality(parent, cls, bool(id_shorts)),
                                      "semanticId": reference(CARDINALITY)}]
            # A class that holds its own kind (the steps of a branch of a step) is named once
            # more, without its content: the generator then refers to the class it already made.
            inside = [e for c in self.children(cls)
                      for e in (self.elements(cls, c, (*seen, cls)) if c not in seen else self.again(cls, c))]
            if model_type == "Property":
                element["valueType"] = self.value_type(cls)
            elif model_type == "SubmodelElementCollection":
                element["value"] = inside
            elif model_type == "SubmodelElementList":
                element["orderRelevant"] = True
                element["typeValueListElement"] = inside[0]["modelType"] if inside else "SubmodelElement"
                element["value"] = inside[:1]
            made.append(element)
        return made

    def again(self, parent: URIRef, cls: URIRef) -> list[dict]:
        """A class met again inside itself: its element without content."""
        if self.b.model_type[cls] != "SubmodelElementCollection":
            return []
        return [{"modelType": "SubmodelElementCollection", "idShort": id_short, "semanticId": reference(self.semantic_id(cls)),
                 "qualifiers": [{"type": "SMT/Cardinality", "valueType": "xs:string", "kind": "TemplateQualifier",
                                 "value": self.cardinality(parent, cls, True), "semanticId": reference(CARDINALITY)}],
                 "value": []} for id_short in sorted(self.b.id_short[cls])]

    def submodel(self, cls: URIRef) -> dict:
        """The template of a submodel class: an AAS environment with that one submodel."""
        semantic = self.semantic_id(cls)
        version = re.search(r"/(\d+)/(\d+)(?:/|$)", semantic)
        submodel = {
            "modelType": "Submodel", "kind": "Template", "idShort": stem(cls), "id": semantic,
            "semanticId": reference(semantic),
            "administration": {"version": version.group(1), "revision": version.group(2)} if version else {},
            "description": [{"language": "en", "text": self.description(cls)}],
            "submodelElements": [e for c in self.children(cls) for e in self.elements(cls, c, (cls,))]}
        return {"assetAdministrationShells": [], "submodels": [submodel], "conceptDescriptions": []}


def write_templates(ontology: Path | str, out: Path = TEMPLATES) -> list[Path]:
    """Write the template of every submodel in SUBMODELS."""
    templates = Templates(Blueprint(ontology))
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for local in SUBMODELS:
        template = templates.submodel(ARSO[local])
        path = out / f"{template['submodels'][0]['idShort']}.json"
        path.write_text(json.dumps(template, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        written.append(path)
    return written


def given(folder: Path = TEMPLATES) -> list[Path]:
    """The templates that are kept as files."""
    return [folder / f"{name}.json" for name in GIVEN]


# aas-model's generator names a field after its element in snake_case; the classes aas-model ships
# (and so the AAS: a field's name is the element's idShort) keep the idShort as it is.
RUN = """
import keyword, sys
sys.path.insert(0, sys.argv[1])
import idta_generate as generator
def exact(id_short):
    name = generator.safe_name(id_short)
    return name + "_" if keyword.iskeyword(name) else name
generator.field_name = exact
for template in sys.argv[3:]:
    generator.gen_template(template, sys.argv[2])
"""


ALIAS = re.compile(r"(?:^# alias [^\n]*\n)?^(\w+)_t: TypeAlias = \1\n", re.MULTILINE)
REBUILD = "# ── Resolve forward references"


def aliases_after_classes(source: str) -> str:
    """A container that holds its own kind (the steps inside a step of a plan) is named by the
    generator before its class is written. Such a name moves behind the classes, where the
    annotations are resolved."""
    early = [m for m in ALIAS.finditer(source)
             if (cls := re.search(rf"^class {m.group(1)}\(", source, re.MULTILINE)) and cls.start() > m.start()]
    if not early or REBUILD not in source:
        return source
    for m in reversed(early):
        source = source[:m.start()] + source[m.end():]
    return source.replace(REBUILD, "".join(m.group(0) for m in early) + "\n" + REBUILD, 1)


def generate(templates: list[Path], out: Path = GENERATED, aas_model: Path = AAS_MODEL) -> list[Path]:
    """Have aas-model's generator make the pydantic classes of the templates."""
    scripts = aas_model / "scripts"
    if not (scripts / "idta_generate.py").exists():
        raise FileNotFoundError(f"no aas-model checkout at {aas_model} (git submodule update --init aas-model)")
    out.mkdir(parents=True, exist_ok=True)
    run = subprocess.run([sys.executable, "-c", RUN, str(scripts), str(out), *map(str, templates)],
                         capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
    if run.returncode:
        raise RuntimeError(f"aas-model's generator failed:\n{run.stderr[-2000:]}")
    made = sorted(p for p in out.glob("*.py") if p.name != "__init__.py")
    for path in made:                                   # one line ending, whatever the platform wrote
        path.write_text(aliases_after_classes(path.read_text(encoding="utf-8")).rstrip() + "\n", encoding="utf-8", newline="\n")
    (out / "__init__.py").write_text(
        '"""Pydantic classes of the submodels aas-model has no classes of (the resource ontology\'s own, Process\n'
        'Parameters and Production Sequence), made by aas-model\'s generator from the templates in\n'
        '``modreg/templates`` (``modreg generate``). Do not edit."""\n', encoding="utf-8", newline="\n")
    return made
