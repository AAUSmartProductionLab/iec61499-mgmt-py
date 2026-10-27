"""The vocabulary's planning terms (0.2): every primitive of the line's modules realizes a capability
of its component, and every constraint is of the language and about the capability's properties."""
from pathlib import Path

import pytest

from modgen import load

from modplan.vocabulary import PPRL, Vocabulary, local

SPECS = Path(__file__).resolve().parents[2] / "cell" / "modules"
# Primitives that serve no capability: RetractPiston draws the piston in after an abort.
SERVING_NONE = {"RetractPiston"}


@pytest.fixture(scope="module")
def vocabulary() -> Vocabulary:
    return Vocabulary()


@pytest.mark.parametrize("spec", ["filling.yaml", "stoppering.yaml", "planned/capping.yaml", "planned/inspection.yaml"])
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
        for stated in vocabulary.constraints(name):              # parsed: of the language, and of its kind
            assert name in vocabulary.characterizes(stated.prop), f"{name}: {stated.prop} does not characterize it"
            if stated.expression.named:
                assert name in vocabulary.characterizes(stated.expression.named), f"{name}: {stated.expression.named}"


def test_the_products_state_and_what_a_result_needs(vocabulary):
    assert all(vocabulary.product(p) for p in ("ContentVolume", "Weighed", "Stoppered", "Capped", "Inspected"))
    assert not any(vocabulary.product(p) for p in ("Position", "Referenced", "Tared", "Weight", "FillVolume"))
    (weighed,) = vocabulary.needs("FillWeight")
    assert (weighed.prop, str(weighed.expression)) == ("Weighed", "= true")
    # A process capability is defined by what it does to the product.
    assert [(s.kind, s.prop, str(s.expression)) for s in vocabulary.constraints("Filling")] == [
        ("Pre", "ContentVolume", "= 0.0"), ("Post", "ContentVolume", "= FillVolume")]
