"""modreg.derive: the capabilities a module offers, derived from its skills and the lab's vocabulary.

Needs the ``registration`` extra (aas-model, rdflib); skipped without it.
"""
import copy

import pytest

pytest.importorskip("aas_model")
pytest.importorskip("rdflib")

from modgen import SPECS, load                                              # noqa: E402
from modreg.derive import offers                                            # noqa: E402
from modreg.offer import capabilities                                       # noqa: E402
from modreg.profile import lean                                             # noqa: E402
from modreg.projection import project                                       # noqa: E402
from test_modsync import composed                                           # noqa: E402
from test_modsync_desired import aas, wanting                               # noqa: E402

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


# Derived anew from an AAS alone (modreg.offer.capabilities) ---------------------------------------

def capability_set(env: dict) -> dict:
    """The offered capabilities of an AAS by container, without the ids aas-model draws anew."""
    def bare(element):
        if isinstance(element, dict):
            return {k: bare(v) for k, v in element.items() if k != "embeddedDataSpecifications"}
        return [bare(v) for v in element] if isinstance(element, list) else element
    description = next(s for s in env["submodels"] if s["idShort"] == "CapabilityDescription")
    return {box["idShort"]: bare(box) for box in description["submodelElements"][0]["value"]}


def marks(box: dict, *path: str) -> dict:
    element = box
    for step in path:
        element = next(c for c in element["value"] if c["idShort"] == step)
    return {q["type"]: q["value"] for q in element.get("qualifiers", [])}


@pytest.fixture(scope="module")
def delivered():
    return aas(load(SPECS / "filling.yaml"))


def test_a_delivered_module_derives_what_it_was_delivered_with(delivered):
    module, components = delivered
    assert capability_set(capabilities(module, components)) == capability_set(module)


def test_a_skill_described_in_the_aas_gets_a_capability_of_its_own(delivered):
    """DoubleDose described (as the skill editor saves it), not built: Filling keeps its container
    and facts; DoubleDose offers Filling in a container of its own, after a reconfiguration."""
    module, components = wanting(composed().spec, delivered[0])
    module["submodels"] = [next(s for s in delivered[0]["submodels"] if s["idShort"] == "CapabilityDescription")
                           if s["idShort"] == "CapabilityDescription" else s for s in module["submodels"]]
    found = capability_set(capabilities(module, components))
    assert list(found) == ["Filling", "Filling_DoubleDose"]
    assert found["Filling"] == capability_set(delivered[0])["Filling"]
    double = found["Filling_DoubleDose"]
    assert marks(double, "Capability") == {"CapabilityRoleQualifier/Offered": "true", "Derived": "true",
                                           "Availability": "AfterReconfiguration"}
    facts = {c["idShort"] for c in next(c for c in double["value"] if c["idShort"] == "PropertySet")["value"]}
    assert facts == {"ContainerType", "GraspDiameter", "AbsoluteFillError", "FillVolume"}
    assert marks(double, "PropertySet", "FillVolume", "Value")["Derived"] == "true"
    realized = next(c for c in double["value"] if c["idShort"] == "CapabilityRelations")["value"][0]["second"]
    assert realized["keys"][-1]["value"] == "DoubleDose"


def test_a_capability_written_by_hand_stays_and_one_no_skill_offers_goes(delivered):
    module, components = delivered
    module = copy.deepcopy(module)
    boxes = next(s for s in module["submodels"] if s["idShort"] == "CapabilityDescription")["submodelElements"][0]["value"]
    by_hand = copy.deepcopy(boxes[0])
    by_hand["idShort"] = "Weighing"
    capability = next(c for c in by_hand["value"] if c["idShort"] == "Capability")
    capability["supplementalSemanticIds"][0]["keys"][0]["value"] = f"{BASE}/semantics/Weighing"
    capability["qualifiers"] = [q for q in capability["qualifiers"] if q["type"] != "Derived"]
    gone = copy.deepcopy(boxes[0])
    gone["idShort"] = "Stoppering"
    next(c for c in gone["value"] if c["idShort"] == "Capability")["supplementalSemanticIds"][0]["keys"][0]["value"] = \
        f"{BASE}/semantics/Stoppering"
    boxes += [by_hand, gone]
    assert list(capability_set(capabilities(module, components))) == ["Filling", "Weighing"]
