"""modreg.templates: submodel templates from an ontology, and the classes aas-model's generator
makes of them. The first tests use a tiny ontology; the last ones need the working copy's
ontology (local) and the aas-model submodule, and are skipped without them."""
import json
from pathlib import Path
import re
import subprocess

import pytest

pytest.importorskip("rdflib")

from modreg import templates                                    # noqa: E402
from modreg.ontology import ARSO as NS, Blueprint               # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ARSO = ROOT / "ontology" / "ARSO"
GENERATOR = templates.AAS_MODEL / "scripts" / "idta_generate.py"

TINY = """
@prefix t:    <https://w3id.org/2025/arso#> .
@prefix aas:  <https://admin-shell.io/aas/3/1/> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

t:PlateSubmodel a owl:Class ; rdfs:subClassOf aas:Submodel ; t:semanticId "urn:other:plate" , "https://smartproductionlab.aau.dk/Plate/2/1/Submodel" ;
  rdfs:comment "What is on the plate. More about it." ;
  rdfs:subClassOf
  [ a owl:Restriction ; owl:onProperty <https://admin-shell.io/aas/3/1/Submodel/submodelElements> ;
    owl:qualifiedCardinality "1"^^xsd:nonNegativeInteger ; owl:onClass t:MakerProperty ] ,
  [ a owl:Restriction ; owl:onProperty <https://admin-shell.io/aas/3/1/Submodel/submodelElements> ; owl:someValuesFrom t:PartSMC ] .
t:MakerProperty a owl:Class ; rdfs:subClassOf aas:Property ; t:parentClass t:PlateSubmodel ; t:idShort "Maker" ;
  rdfs:comment "Property Maker (xs:string) — who made it." .
t:PartSMC a owl:Class ; rdfs:subClassOf aas:SubmodelElementCollection ; t:parentClass t:PlateSubmodel ;
  rdfs:subClassOf [ a owl:Restriction ; owl:onProperty <https://admin-shell.io/aas/3/1/SubmodelElementCollection/value> ;
                    owl:maxQualifiedCardinality "1"^^xsd:nonNegativeInteger ; owl:onClass t:WeightProperty ] .
t:WeightProperty a owl:Class ; rdfs:subClassOf aas:Property ; t:parentClass t:PartSMC ; t:idShort "Weight" ; t:semanticId "urn:weight" ;
  rdfs:subClassOf [ a owl:Restriction ; owl:onProperty <https://admin-shell.io/aas/3/1/Property/valueType> ;
                    owl:hasValue <https://admin-shell.io/aas/3/1/DataTypeDefXsd/Decimal> ] .
t:NotesSML a owl:Class ; rdfs:subClassOf aas:SubmodelElementList ; t:parentClass t:PlateSubmodel ; t:idShort "Notes" .
t:NoteProperty a owl:Class ; rdfs:subClassOf aas:Property ; t:parentClass t:NotesSML .
"""


def cardinality(element: dict) -> str:
    return next(q["value"] for q in element["qualifiers"] if q["type"] == "SMT/Cardinality")


@pytest.fixture(scope="module")
def plate(tmp_path_factory):
    folder = tmp_path_factory.mktemp("ontology")
    (folder / "tiny.ttl").write_text(TINY, encoding="utf-8")
    return templates.Templates(Blueprint(folder)).submodel(NS.PlateSubmodel)


def test_a_template_states_what_the_ontology_states(plate):
    submodel = plate["submodels"][0]
    assert submodel["kind"] == "Template" and submodel["idShort"] == "Plate"
    # Of several semanticIds the lab's own; its version is the template's.
    assert submodel["semanticId"]["keys"][0]["value"] == "https://smartproductionlab.aau.dk/Plate/2/1/Submodel"
    assert submodel["administration"] == {"version": "2", "revision": "1"}
    assert submodel["description"][0]["text"] == "What is on the plate."
    maker, part, notes = submodel["submodelElements"]               # in the order the ontology declares them
    assert (maker["idShort"], maker["modelType"], cardinality(maker)) == ("Maker", "Property", "One")
    assert maker["description"][0]["text"] == "Who made it." and maker["valueType"] == "xs:string"
    # A class without an idShort stands for the elements a user names; the parent asks for at least one.
    assert (part["idShort"], cardinality(part)) == ("Part__00__", "OneToMany")
    weight = part["value"][0]
    assert (weight["idShort"], cardinality(weight), weight["valueType"]) == ("Weight", "ZeroToOne", "xs:decimal")
    assert weight["semanticId"]["keys"][0]["value"] == "urn:weight"
    # Nothing asks for the list; it holds any number of items of its one kind.
    assert (notes["modelType"], cardinality(notes), notes["typeValueListElement"]) == ("SubmodelElementList", "ZeroToOne", "Property")
    assert cardinality(notes["value"][0]) == "ZeroToMany"


@pytest.mark.skipif(not GENERATOR.exists(), reason="no aas-model checkout (git submodule update --init aas-model)")
def test_aas_models_generator_makes_the_classes(plate, tmp_path):
    pytest.importorskip("aas_pydantic")
    template = tmp_path / "Plate.json"
    template.write_text(json.dumps(plate), encoding="utf-8")
    made, = templates.generate([template], tmp_path / "generated")
    source = made.read_text(encoding="utf-8")
    # Fields are named like the idShorts, as in the classes aas-model ships; cardinalities decide their kind.
    assert "    Maker: Property\n" in source and "    Part: Dict[str, Part_t] = {}" in source
    assert "    Weight: Optional[Weight_t] = None" in source and 'value_type: str = "xs:decimal"' in source
    namespace = {}
    exec(compile(source, str(made), "exec"), namespace)             # noqa: S102 (the generated module)
    Plate, Part, Property = namespace["Plate"], namespace["Part"], namespace["Property"]
    built = Plate(id_short="Plate", Maker=Property(value="AAU"), Part={"Lid": Part()})
    assert built.Part["Lid"].id_short == "Lid" and built.semantic_id.endswith("/Plate/2/1/Submodel")
    with pytest.raises(ValueError):
        Plate(id_short="Plate")                                     # the Maker is mandatory


@pytest.mark.skipif(not (ARSO.exists() and GENERATOR.exists()), reason="needs ontology/ARSO (local) and the aas-model submodule")
def test_the_committed_templates_and_classes_are_those_of_the_ontology(tmp_path):
    def same(a: Path, b: Path) -> bool:
        return a.read_text(encoding="utf-8").replace("\r\n", "\n") == b.read_text(encoding="utf-8").replace("\r\n", "\n")

    written = templates.write_templates(ARSO, tmp_path / "templates")
    made = templates.generate([*written, *templates.given()], tmp_path / "generated")
    assert [p.name for p in written] == ["Skills.json", "OperationalData.json", "Parameters.json", "ControlConfiguration.json"]
    assert {p.name for p in made} >= {"process_parameters.py", "production_sequence.py"}
    stale = [p.name for p in written if not same(p, templates.TEMPLATES / p.name)]
    stale += [p.name for p in made if not same(p, templates.GENERATED / p.name)]
    assert stale == [], "run: modreg generate --ontology ontology/ARSO"


def test_the_templates_kept_as_files_are_the_planners():
    """Process Parameters is IDTA 02031-1 with the lab's extension; Production Sequence the planner's 2.0."""
    def template(name: str) -> dict:
        return json.loads((templates.TEMPLATES / f"{name}.json").read_text(encoding="utf-8"))["submodels"][0]

    def at(element: dict, *path: str) -> dict:
        for step in path:
            element = next(c for c in element.get("submodelElements") or element["value"] if c["idShort"] == step)
        return element

    parameters, sequence = template("ProcessParameters"), template("ProductionSequence")
    assert [p.stem for p in templates.given()] == ["ProcessParameters", "ProductionSequence"]
    assert parameters["kind"] == sequence["kind"] == "Template"
    assert parameters["semanticId"]["keys"][0]["value"] == "https://admin-shell-io/idta/SubmodelTemplate/ProcessParameters/1/0"
    process = at(parameters, "Processes", "Process__00__")
    assert cardinality(at(process, "PlannedProcessTime")) == "One"                     # IDTA's
    assert cardinality(at(process, "RequiredCapability")) == "ZeroToOne"               # the lab's extension
    assert at(process, "ProcessBoM", "MaterialUse__00__")["semanticId"]["keys"][0]["value"].startswith("https://smartproductionlab.aau.dk/")
    assert sequence["semanticId"]["keys"][0]["value"] == "https://smartproductionlab.aau.dk/SubmodelTemplate/ProductionSequence/2/0"
    step = at(sequence, "Steps", "Step__00__")
    assert [cardinality(at(step, name)) for name in ("NodeId", "Kind", "Skill", "Bindings")] == ["One", "One", "ZeroToOne", "ZeroToOne"]
    assert cardinality(at(step, "Bindings", "Binding__00__")) == "ZeroToMany"
    # A node holds nodes: the template names the container, the classes make it the same Steps.
    assert at(step, "Steps")["value"] == [] and at(step, "Branches", "Branch__00__", "Steps")["value"] == []
    assert "    Steps: Optional[Steps_t] = None" in (templates.GENERATED / "production_sequence.py").read_text(encoding="utf-8")


@pytest.mark.skipif(not GENERATOR.exists(), reason="no aas-model checkout")
def test_the_submodule_is_the_aas_model_the_package_installs():
    """The classes are generated with the checkout and run with the installed package: one commit."""
    pinned = re.search(r"aas-model/archive/([0-9a-f]{40})\.zip", (ROOT / "pyproject.toml").read_text(encoding="utf-8")).group(1)
    checked_out = subprocess.run(["git", "-C", str(templates.AAS_MODEL), "rev-parse", "HEAD"],
                                 capture_output=True, text=True, check=True).stdout.strip()
    assert checked_out == pinned
