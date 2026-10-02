"""modreg.ontology: recognise the elements of an AAS as members of the ontology's classes and test
the restrictions of each. The ontology here is a tiny one written for the test, so the check itself
is tested and not ARSO's content."""
import pytest

pytest.importorskip("rdflib")

from modreg.ontology import Blueprint, check        # noqa: E402

TINY = """
@prefix t:    <https://w3id.org/2025/arso#> .
@prefix aas:  <https://admin-shell.io/aas/3/1/> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

t:hasSubmodel a owl:ObjectProperty .
t:hasPlateSubmodel a owl:ObjectProperty ; rdfs:subPropertyOf t:hasSubmodel .
t:Plate a owl:Class ; rdfs:subClassOf aas:Submodel ; t:semanticId "urn:plate" ;
  rdfs:subClassOf
  [ a owl:Restriction ; owl:onProperty <https://admin-shell.io/aas/3/1/Submodel/submodelElements> ; owl:someValuesFrom t:Maker ] ,
  [ a owl:Restriction ; owl:onProperty <https://admin-shell.io/aas/3/1/Submodel/submodelElements> ;
    owl:maxQualifiedCardinality "1"^^xsd:nonNegativeInteger ; owl:onClass t:Parts ] .
t:Maker a owl:Class ; rdfs:subClassOf aas:Property ; t:parentClass t:Plate ; t:idShort "Maker" .
t:Parts a owl:Class ; rdfs:subClassOf aas:SubmodelElementCollection ; t:parentClass t:Plate ; t:idShort "Parts" ;
  rdfs:subClassOf [ a owl:Restriction ; owl:onProperty <https://admin-shell.io/aas/3/1/SubmodelElementCollection/value> ;
                    owl:allValuesFrom t:Part ] .
t:Part a owl:Class ; rdfs:subClassOf aas:SubmodelElementCollection ; t:parentClass t:Parts ;
  rdfs:subClassOf [ a owl:Restriction ; owl:onProperty <https://admin-shell.io/aas/3/1/SubmodelElementCollection/value> ;
                    owl:someValuesFrom t:Size ] .
t:Size a owl:Class ; rdfs:subClassOf aas:Property ; t:semanticId "urn:size" ;
  rdfs:subClassOf [ a owl:Restriction ; owl:onProperty <https://admin-shell.io/aas/3/1/Property/value> ;
                    owl:allValuesFrom [ a rdfs:Datatype ; owl:oneOf ( "S" "L" ) ] ] .
"""


# Every resource AAS has exactly one Plate.
SHELL = """
t:ResourceAAS a owl:Class ; rdfs:subClassOf aas:AssetAdministrationShell ,
  [ a owl:Restriction ; owl:onProperty t:hasPlateSubmodel ; owl:qualifiedCardinality "1"^^xsd:nonNegativeInteger ; owl:onClass t:Plate ] .
"""


def semantic(value: str) -> dict:
    return {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": value}]}


def small(*elements, plates: int = 1) -> dict:
    plate = {"modelType": "Submodel", "id": "urn:sm:plate", "idShort": "Plate", "semanticId": semantic("urn:plate"),
             "submodelElements": list(elements)}
    ref = {"type": "ModelReference", "keys": [{"type": "Submodel", "value": "urn:sm:plate"}]}
    return {"assetAdministrationShells": [{"modelType": "AssetAdministrationShell", "id": "urn:aas", "idShort": "Shell",
                                           "submodels": [ref] * plates}],
            "submodels": [plate] if plates else []}


def element(model_type: str, id_short: str, **more) -> dict:
    return {"modelType": model_type, "idShort": id_short, **more}


def part(name: str, size: str | None) -> dict:
    inside = [element("Property", "Size", value=size, semanticId=semantic("urn:size"))] if size else []
    return element("SubmodelElementCollection", name, value=inside)


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    folder = tmp_path_factory.mktemp("ontology")
    (folder / "tiny.ttl").write_text(TINY + SHELL, encoding="utf-8")
    return Blueprint(folder)


def test_elements_are_recognised_and_restrictions_checked(tiny):
    maker = element("Property", "Maker", value="AAU")
    good = check(small(maker, element("SubmodelElementCollection", "Parts", value=[part("A", "S"), part("B", "L")])), tiny)
    assert good.ok and good.findings == []
    assert good.classes["Plate"] == ["Plate"] and good.classes["Plate/Maker"] == ["Maker"]         # by semanticId, by idShort
    assert good.classes["Plate/Parts/A"] == ["Part"] and good.classes["Plate/Parts/A/Size"] == ["Size"]   # by parent


@pytest.mark.parametrize("env, message", [
    (small(), "Plate: Plate needs a Maker"),
    (small(element("Property", "Maker"), element("SubmodelElementCollection", "Parts", value=[part("A", None)])),
     "Plate/Parts/A: Part needs a Size"),
    (small(element("Property", "Maker"), element("SubmodelElementCollection", "Parts", value=[part("A", "XL")])),
     "Plate/Parts/A/Size: Size value has to be one of L, S"),
    (small(element("Property", "Maker"),
           element("SubmodelElementCollection", "Parts", value=[element("Property", "Loose", value="x")])),
     "Plate/Parts: Parts may only contain Part"),
    (small(plates=0), "Shell: ResourceAAS needs exactly 1 Plate"),
])
def test_a_broken_restriction_is_an_error(tiny, env, message):
    report = check(env, tiny)
    assert not report.ok and message in "\n".join(report.lines()), report.lines()


def test_what_the_ontology_does_not_describe_is_reported_not_refused(tiny):
    report = check(small(element("Property", "Maker"), element("Property", "Colour", value="red")), tiny)
    assert report.ok and [str(f) for f in report.unknown] == [
        "unknown: Plate/Colour: Property (no semanticId) is not described below Plate"]
    stranger = {"modelType": "Submodel", "id": "urn:sm:other", "idShort": "Other", "semanticId": semantic("urn:other")}
    env = small(element("Property", "Maker"))
    env["submodels"].append(stranger)
    assert "Other: submodel (urn:other) is not in the ontology" in "\n".join(check(env, tiny).lines())
