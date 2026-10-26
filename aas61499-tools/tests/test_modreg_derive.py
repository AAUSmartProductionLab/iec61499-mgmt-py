"""modreg.derive: the capabilities a module offers, derived from its skills and the lab's vocabulary.

Needs the ``registration`` extra (aas-model, rdflib); skipped without it.
"""
import pytest

pytest.importorskip("aas_model")
pytest.importorskip("rdflib")

from modgen import SPECS, load                                              # noqa: E402
from modreg.derive import offers                                            # noqa: E402
from modreg.projection import project                                       # noqa: E402
from test_modsync import composed                                           # noqa: E402
from test_modsync_desired import aas, wanting                               # noqa: E402

BASE = "https://smartproductionlab.aau.dk"
LINE = [SPECS / "filling.yaml", SPECS / "stoppering.yaml", SPECS / "planned" / "capping.yaml",
        SPECS / "planned" / "inspection.yaml"]


@pytest.mark.parametrize("path", LINE, ids=lambda p: p.stem)
def test_what_is_derived_is_what_the_module_spec_states(path):
    """Each capability the spec states is derived: of the same class, realized by the same skill,
    with the ranges of the properties a parameter sets. The facts of the machine the spec states
    besides (the container it takes) are not the skills' to derive."""
    spec = load(path)
    module, components = aas(spec, next(iter(spec.targets)))
    found = offers(project([module, *components], structure=False))
    assert [(o.name, o.skill_name, o.built) for o in found] == \
           [(name, c.realized_by, True) for name, c in spec.capabilities.items()]
    for offer, capability in zip(found, spec.capabilities.values()):
        set_by_parameter = {f"{BASE}/semantics/{name}": p for name, p in capability.properties.items() if p.parameter}
        assert [p.meaning for p in offer.properties] == sorted(set_by_parameter)
        for prop in offer.properties:
            stated = set_by_parameter[prop.meaning]
            assert (float(prop.minimum), float(prop.maximum), prop.unit) == (stated.minimum, stated.maximum, stated.unit)
            assert prop.parameter.endswith(f"/Skills/Skills/{offer.skill_name}/Start/Start/{stated.parameter}")


def test_a_skill_described_but_not_built_is_offered_after_a_reconfiguration(with_double_dose):
    """DoubleDose is described in the Skills submodel, but no block of the program carries it out:
    it offers Filling only once it is built. Its parameter Dose states no meaning; it hands its
    value to Dispense's Volume, which means FillVolume, so the offer has that range."""
    module, components = with_double_dose
    found = {(o.skill_name, o.name): o for o in offers(project([module, *components], structure=False))}
    assert set(found) == {("Dispensing", "Filling"), ("DoubleDose", "Filling")}
    assert found["Dispensing", "Filling"].built and not found["DoubleDose", "Filling"].built
    (volume,) = found["DoubleDose", "Filling"].properties
    assert (volume.meaning, volume.minimum, volume.maximum, volume.unit) == (f"{BASE}/semantics/FillVolume", "0.5", "10.0", "mL")
    assert volume.parameter.endswith("/Skills/Skills/DoubleDose/Start/Start/Dose")


@pytest.fixture(scope="module")
def with_double_dose():
    return wanting(composed().spec, aas(load(SPECS / "filling.yaml"))[0])
