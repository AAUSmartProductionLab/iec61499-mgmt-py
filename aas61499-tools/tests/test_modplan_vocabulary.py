"""The vocabulary's planning terms (0.2): every primitive of the line's modules realizes a capability
of its component, and every constraint is of the language and about the capability's properties."""
from pathlib import Path

import pytest

from modgen import load

from modplan.vocabulary import LAB, PPRL, Vocabulary, local

SPECS = Path(__file__).resolve().parents[2] / "cell" / "modules"
# Primitives that serve no capability: RetractPiston draws the piston in after an abort; AwaitJob
# waits for a robot's job to end.
SERVING_NONE = {"RetractPiston", "AwaitJob"}


@pytest.fixture(scope="module")
def vocabulary() -> Vocabulary:
    return Vocabulary()


@pytest.mark.parametrize("spec", ["filling.yaml", "stoppering.yaml", "capping.yaml", "planned/inspection.yaml",
                                  "python/loading.yaml", "python/unloading.yaml"])
def test_every_primitive_realizes_a_capability_of_its_component(vocabulary, spec):
    for name in load(SPECS / spec).skills:
        realized = vocabulary.realized(name)
        if name in SERVING_NONE:
            assert realized is None
            continue
        assert realized is not None, f"{name} realizes no capability (lab:realizes in skills.ttl)"
        assert not vocabulary.process(realized), f"{name} realizes {realized}, a process capability"
        assert any(s.kind == "Post" for s in vocabulary.constraints(realized)), f"{realized} does nothing"


def test_every_constraint_is_about_the_capabilitys_own_properties(vocabulary):
    capabilities = {local(c) for kind in (PPRL.pre, PPRL.post, PPRL.invariant) for c in vocabulary.graph.subjects(kind)}
    assert len(capabilities) >= 12
    for name in capabilities:
        lineage = set(vocabulary.lineage(name))                  # what describes Filling describes BottomUpFilling
        for stated in vocabulary.constraints(name):              # parsed: of the language, and of its kind
            assert lineage & vocabulary.characterizes(stated.prop), f"{name}: {stated.prop} does not characterize it"
            for named in stated.expression.names:
                assert lineage & vocabulary.characterizes(named), f"{name}: {named}"


def test_the_products_state_and_what_a_result_needs(vocabulary):
    assert all(vocabulary.product(p) for p in ("ContentVolume", "Weighed", "Stoppered", "Capped", "Inspected"))
    assert not any(vocabulary.product(p) for p in ("Position", "Referenced", "Tared", "Weight", "FillVolume"))
    (weighed,) = vocabulary.needs("FillWeight")
    assert (weighed.prop, str(weighed.expression)) == ("Weighed", "= true")
    # A process capability is defined by what it does to the product.
    assert [(s.kind, s.prop, str(s.expression)) for s in vocabulary.constraints("Filling")] == [
        ("Pre", "ContentVolume", "= 0.0"), ("Post", "ContentVolume", "= FillVolume")]


STANDARDS = {"http://www.w3id.org/hsu-aut/VDI2860": "VDI2860", "http://www.w3id.org/hsu-aut/DIN8580": "DIN8580"}


def test_the_capabilities_are_kinds_of_the_standards_classes(vocabulary):
    """0.9: a capability below DIN 8580 (what changes the product) or VDI 2860 (what moves or checks
    it), each class it names declared in the copy kept here, and the copies are what it imports."""
    from rdflib import OWL, RDF, RDFS, Graph, URIRef
    ontology = Path(__file__).resolve().parents[2] / "ontology"
    graph = Graph()
    for folder in STANDARDS.values():
        graph.parse(ontology / folder / f"{folder}.ttl", format="turtle")
    assert set(STANDARDS) <= {str(o) for o in vocabulary.graph.objects(None, OWL.imports)}
    assert set(STANDARDS) == {str(o) for o in graph.subjects(RDF.type, OWL.Ontology)}
    named = [o for o in vocabulary.graph.objects(None, RDFS.subClassOf) if str(o).startswith(tuple(STANDARDS))]
    assert len(named) >= 8 and all((o, RDF.type, OWL.Class) in graph for o in named), named
    both = vocabulary.graph + graph

    def kinds(capability: str) -> set[str]:
        return {str(o).rsplit("#", 1)[-1] for o in both.transitive_objects(URIRef(f"{LAB}{capability}"), RDFS.subClassOf)}
    assert {"Einfuellen", "Fuellen"} <= kinds("BottomUpFilling")           # through Filling
    assert "Fuegen_durch_Presspassung" in kinds("Stoppering") and "Fuegen" in kinds("Capping")
    assert {"Positionieren", "Bewegen"} <= kinds("Positioning") and "Messen" in kinds("Weighing")
    # The kinds the lab's planning rests on are untouched: still disjoint, still the lab's own lineage.
    assert vocabulary.process("Filling") and not vocabulary.process("Dosing")
    assert vocabulary.lineage("BottomUpFilling") == ["BottomUpFilling", "Filling"]
