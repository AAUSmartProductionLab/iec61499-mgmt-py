"""modreg.derive: the capabilities a module offers, derived from its skills and the lab's vocabulary.

Needs the ``registration`` extra (aas-model, rdflib); skipped without it.
"""
import pytest

pytest.importorskip("aas_model")
pytest.importorskip("rdflib")

from modgen import SPECS, load                                              # noqa: E402
from modreg.derive import offers                                            # noqa: E402
from modreg.profile import lean                                             # noqa: E402
from modreg.projection import project                                       # noqa: E402
from test_modsync import composed                                           # noqa: E402

BASE = "https://smartproductionlab.aau.dk"
# What each module of the line offers, as its specs stated it by hand before 26 Oct: the capability,
# the skill realizing it, and the properties a parameter of that skill sets (name, limits, unit).
LINE = {"filling": ("Filling", "Dispensing", [("FillVolume", "0.5", "10.0", "mL", "Volume")]),
        "stoppering": ("Stoppering", "Stoppering", []),
        "planned/capping": ("Capping", "Capping", []),
        "planned/inspection": ("Inspection", "Inspection", [])}


@pytest.mark.parametrize("name", LINE)
def test_what_is_derived_is_what_the_modules_offered_before(name):
    """The capability, the skill realizing it and the ranges of the properties a parameter sets are
    derived from the skills; the facts of the machine (the container it takes) are not the skills'."""
    spec = load(SPECS / f"{name}.yaml")
    capability, skill, properties = LINE[name]
    [offer] = offers(project(lean(spec), structure=False))
    assert (offer.name, offer.skill_name, offer.built) == (capability, skill, True)
    assert offer.keys == [("Submodel", f"{BASE}/aas/{spec.module}ModuleAAS/submodels/Skills"),
                          ("SubmodelElementCollection", "Skills"), ("SubmodelElementCollection", skill)]
    assert [(p.meaning, p.minimum, p.maximum, p.unit) for p in offer.properties] == \
           [(f"{BASE}/semantics/{p}", low, high, unit) for p, low, high, unit, _ in properties]
    for prop, (*_, parameter) in zip(offer.properties, properties):
        assert prop.parameter.endswith(f"/Skills/Skills/{skill}/Start/Start/{parameter}")


def test_a_skill_described_but_not_built_is_offered_after_a_reconfiguration():
    """DoubleDose is described in the Skills submodel, but the record of what was built is the
    delivered module's: no block of the program carries it out, so it offers Filling only once it
    is built. Its parameter Dose states no meaning; it hands its value to Dispense's Volume, which
    means FillVolume, so the offer has that range."""
    module, *components = lean(composed().spec)
    delivered = lean(load(SPECS / "filling.yaml"))[0]
    module["submodels"] = [next(s for s in delivered["submodels"] if s["idShort"] == "ControlConfiguration")
                           if s["idShort"] == "ControlConfiguration" else s for s in module["submodels"]]
    found = {(o.skill_name, o.name): o for o in offers(project([module, *components], structure=False))}
    assert set(found) == {("Dispensing", "Filling"), ("DoubleDose", "Filling")}
    assert found["Dispensing", "Filling"].built and not found["DoubleDose", "Filling"].built
    (volume,) = found["DoubleDose", "Filling"].properties
    assert (volume.meaning, volume.minimum, volume.maximum, volume.unit) == (f"{BASE}/semantics/FillVolume", "0.5", "10.0", "mL")
    assert volume.parameter.endswith("/Skills/Skills/DoubleDose/Start/Start/Dose")
