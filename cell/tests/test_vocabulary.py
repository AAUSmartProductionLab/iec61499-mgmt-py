"""The capabilities the modules offer are named in the shared vocabulary (ontology/Vocabulary), with
its units, so that a product's required capability and a module's offered one can meet."""
from pathlib import Path

import pytest

rdflib = pytest.importorskip("rdflib")
from rdflib import Namespace, RDFS  # noqa: E402

from modgen import SPECS, load, specs  # noqa: E402

VOCABULARY = Path(__file__).resolve().parents[2] / "ontology" / "Vocabulary" / "capabilities.ttl"
BASE = "https://smartproductionlab.aau.dk/semantics/"
LAB = Namespace(BASE)
CSS = Namespace("http://www.w3id.org/hsu-aut/css#")


@pytest.fixture(scope="module")
def vocabulary():
    graph = rdflib.Graph()
    graph.parse(VOCABULARY, format="turtle")
    return graph


def test_every_offered_capability_and_property_is_in_the_vocabulary(vocabulary):
    offered = 0
    for path in specs():
        spec = load(path)
        for name, capability in spec.capabilities.items():
            offered += 1
            meaning = rdflib.URIRef(capability.semantic_id or BASE + name)
            assert (meaning, RDFS.subClassOf, CSS.Capability) in vocabulary, f"{spec.module}: {meaning}"
            for prop, value in capability.properties.items():
                term = rdflib.URIRef(value.semantic_id or BASE + prop)
                assert (term, RDFS.subClassOf, CSS.Property) in vocabulary, f"{spec.module}.{name}: {term}"
                assert (term, LAB.characterizes, meaning) in vocabulary, f"{prop} does not describe {name}"
                unit = vocabulary.value(term, LAB.unit)
                assert (str(unit) if unit else None) == value.unit, f"{spec.module}.{name}.{prop}: unit {value.unit}"
                kind = str(vocabulary.value(term, LAB.valueType))
                given = value.value if value.value is not None else value.minimum
                assert kind == ("string" if isinstance(given, str) else "number"), f"{spec.module}.{name}.{prop}"
    assert offered >= 2


def test_the_fill_volume_is_set_by_a_skill_parameter():
    """A required fill volume has to reach the controller: the capability names the parameter."""
    spec = load(SPECS / "filling.yaml")
    volume = spec.capabilities["Filling"].properties["FillVolume"]
    skill = spec.composites[spec.capabilities["Filling"].realized_by]
    assert volume.parameter == "Volume" and skill.parameters["Volume"].unit == volume.unit == "mL"
    assert (skill.parameters["Volume"].minimum, skill.parameters["Volume"].maximum) == (volume.minimum, volume.maximum)
