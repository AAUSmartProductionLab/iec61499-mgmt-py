"""Consistency aid for the design guide (not part of the software's tests, and not a validation
of the models): every ontology file parses, the set is consistent under OWL RL, and the worked
filling-line example (PPRL/examples/filling-line.ttl) behaves as the design intends.

    python -m pytest ontology/checks
"""
from pathlib import Path

import pytest

rdflib = pytest.importorskip("rdflib")
owlrl = pytest.importorskip("owlrl")
pyshacl = pytest.importorskip("pyshacl")
from rdflib import Namespace, RDF  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PPRL = Namespace("https://w3id.org/2025/pprl#")
CSS = Namespace("http://www.w3id.org/hsu-aut/css#")
EX = Namespace("https://smartproductionlab.aau.dk/example/filling-line#")
ERR = Namespace("http://www.daml.org/2002/03/agents/agent-ont#")
EXAMPLE = ROOT / "PPRL" / "examples" / "filling-line.ttl"
RULES = ROOT / "PPRL" / "PPRL-rules.shacl.ttl"
ONTOLOGIES = [p for p in sorted(ROOT.rglob("*.ttl")) if p not in (EXAMPLE, RULES)]


def graph(*paths):
    g = rdflib.Graph()
    for p in paths:
        g.parse(p, format="turtle")
    return g


def errors(g):
    return sorted(str(o) for o in g.objects(None, ERR.error))


@pytest.mark.parametrize("path", sorted(ROOT.rglob("*.ttl")), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_every_file_parses(path):
    assert len(graph(path)) > 0


def test_the_whole_set_is_consistent():
    """AAS, CSS, APSO, ARSO, AProSO and PPRL together, with the example: no OWL RL inconsistency."""
    g = graph(*ONTOLOGIES, EXAMPLE)
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)
    assert errors(g) == []


def test_every_import_resolves_to_a_file():
    defined = set()
    imported = set()
    for p in ONTOLOGIES:
        g = graph(p)
        defined |= {str(s) for s in g.subjects(RDF.type, rdflib.OWL.Ontology)}
        imported |= {str(o) for o in g.objects(None, rdflib.OWL.imports)}
    assert imported - defined == set()


@pytest.fixture(scope="module")
def closure():
    g = graph(ROOT / "CSS" / "CSS-Ontology.ttl", ROOT / "PPRL" / "PPRL.ttl", EXAMPLE)
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)
    assert errors(g) == []
    return g


def test_candidates_of_a_step_are_derived(closure):
    assert set(closure.objects(EX.Dispense, PPRL.candidateSkill)) == {EX.Dispensing}
    assert set(closure.objects(EX.Dispense, PPRL.candidateResource)) == {EX.FillingModule}
    assert set(closure.objects(EX.Close, PPRL.candidateResource)) == {EX.StopperingModule}


def test_order_decomposition_and_skill_kinds_are_derived(closure):
    assert (EX.Dispense, PPRL.precedes, EX.Close) in closure             # transitive order
    assert (EX.Line, PPRL.containsResource, EX.NeedleAxis) in closure    # parts at any depth
    assert (EX.Dispensing, RDF.type, PPRL.CompositeSkill) in closure     # uses other skills
    assert (EX.Dispensing, CSS.controls, EX.Dispense) in closure         # CSS view of the binding


def validate(g):
    ok, _, text = pyshacl.validate(g, shacl_graph=graph(RULES), inference="rdfs", advanced=True)
    return ok, text


def test_the_example_satisfies_the_rules():
    ok, text = validate(graph(EXAMPLE))
    assert ok, text


@pytest.mark.parametrize("change, message", [
    ((EX.Dispensing, PPRL.usesSkill, EX.LowerPiston), "not provided by its resource"),     # across modules
    ((EX.Dwell, PPRL.occupies, EX.Piston), "not its resource or one of its parts"),
    ((EX.Close, PPRL.boundTo, EX.Dispensing), "does not realise a capability matching"),
    ((EX.Close, PPRL.directlyPrecedes, EX.Dispense), "cycle"),
    ((EX.Dispense, PPRL.directlyPrecedes, EX.BoP_Close), "not a sibling"),
    ((EX.Transfer, CSS.requiresCapability, EX.ReqDispensing), "exactly one capability"),
    ((EX.Produce, CSS.requiresCapability, EX.ReqMove), "its leaves do"),
])
def test_rule_violations_are_found(change, message):
    g = graph(EXAMPLE)
    g.add(change)
    ok, text = validate(g)
    assert not ok and message in text, text
