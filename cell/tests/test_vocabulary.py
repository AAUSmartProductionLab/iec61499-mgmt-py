"""The capabilities the modules offer are named in the shared vocabulary (ontology/Vocabulary), with
its units, so that a product's required capability and a module's offered one can meet."""
from pathlib import Path

import pytest

rdflib = pytest.importorskip("rdflib")
from rdflib import Namespace, RDFS  # noqa: E402

from modgen import SPECS, load, specs  # noqa: E402

VOCABULARY = Path(__file__).resolve().parents[2] / "ontology" / "Vocabulary"
BASE = "https://smartproductionlab.aau.dk/semantics/"
LAB = Namespace(BASE)
SKILLS = Namespace("https://smartproductionlab.aau.dk/skills/")
CSS = Namespace("http://www.w3id.org/hsu-aut/css#")


@pytest.fixture(scope="module")
def vocabulary():
    graph = rdflib.Graph()
    for path in sorted(VOCABULARY.glob("*.ttl")):
        graph.parse(path, format="turtle")
    return graph


def line_specs():
    """The line's modules, the planned ones too: they are described before they are built."""
    return [load(path) for path in [*specs(), *sorted((SPECS / "planned").glob("*.yaml"))]]


def test_every_offered_capability_and_property_is_in_the_vocabulary(vocabulary):
    offered = 0
    for spec in line_specs():
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
    assert offered >= 4


def test_every_skill_primitive_has_a_type_that_says_what_it_contributes(vocabulary):
    """A module's offered capabilities are derived from the types of the skills its composites run."""
    contributed = set()
    for spec in line_specs():
        for name in spec.skills:
            kind = SKILLS[name]
            assert (kind, RDFS.subClassOf, CSS.Skill) in vocabulary, f"{spec.module}.{name}: no skill type {kind}"
            for capability in vocabulary.objects(kind, LAB.contributes):
                assert (capability, RDFS.subClassOf, CSS.Capability) in vocabulary, f"{name} contributes {capability}"
                contributed.add(capability)
        # A capability the spec states facts of is one a step of its module level skills contributes.
        steps = {step.skill for composite in spec.composites.values() for step in composite.execute}
        for cap_name in spec.capabilities:
            assert any((SKILLS[s], LAB.contributes, LAB[cap_name]) in vocabulary for s in steps), \
                f"{spec.module}: no step of its skills contributes {cap_name}"
    assert {LAB.Filling, LAB.Stoppering, LAB.Capping, LAB.Inspection, LAB.Positioning} <= contributed


def test_what_a_parameter_means_is_a_property_of_the_vocabulary_in_its_unit(vocabulary):
    meant = 0
    for spec in line_specs():
        for name, skill in [*spec.skills.items(), *spec.composites.items()]:
            for p, parameter in skill.parameters.items():
                if parameter.meaning:
                    meant += 1
                    term = rdflib.URIRef(parameter.meaning if "://" in parameter.meaning else BASE + parameter.meaning)
                    assert (term, RDFS.subClassOf, CSS.Property) in vocabulary, f"{spec.module}.{name}.{p}: {term}"
                    unit = vocabulary.value(term, LAB.unit)
                    assert (str(unit) if unit else None) == parameter.unit, f"{spec.module}.{name}.{p}: unit"
    assert meant >= 5


def test_a_product_can_require_only_process_capabilities(vocabulary):
    process, auxiliary = set(vocabulary.subjects(RDFS.subClassOf, LAB.ProcessCapability)), \
        set(vocabulary.subjects(RDFS.subClassOf, LAB.AuxiliaryCapability))
    assert not process & auxiliary
    assert {LAB.Filling, LAB.Stoppering} <= process and {LAB.Positioning, LAB.Weighing} <= auxiliary
    every = set(vocabulary.subjects(RDFS.subClassOf, CSS.Capability)) - {LAB.ProcessCapability, LAB.AuxiliaryCapability}
    assert every == process | auxiliary, f"capabilities of neither kind: {every - process - auxiliary}"


def test_the_fill_volume_is_set_by_a_skill_parameter(vocabulary):
    """A required fill volume has to reach the controller: Dispense contributes Filling, and its
    Volume means FillVolume, a property of Filling (so a skill handing Volume on offers its range)."""
    volume = load(SPECS / "filling.yaml").skills["Dispense"].parameters["Volume"]
    assert volume.meaning == "FillVolume" and volume.unit == "mL"
    assert (SKILLS.Dispense, LAB.contributes, LAB.Filling) in vocabulary
    assert (LAB.FillVolume, LAB.characterizes, LAB.Filling) in vocabulary
