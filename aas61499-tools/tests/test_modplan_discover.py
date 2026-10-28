"""Discovery (G5): a module offers a process capability no skill of it carries out yet, after a
reconfiguration, if a skill for it can be planned from its components' capabilities."""
import copy
from pathlib import Path
import sys

from modgen import load
from modsync.aasjson import at, children, submodel

from modplan.discover import discover
from modreg.offer import capabilities

sys.path.insert(0, str(Path(__file__).parent))
from test_modplan import filling                                                     # noqa: E402
from test_modsync_desired import aas                                                 # noqa: E402

SPECS = Path(__file__).resolve().parents[2] / "cell" / "modules"
BASE = "https://smartproductionlab.aau.dk"


def test_the_filling_module_can_fill_for_what_its_pump_doses():
    (found,) = discover(filling())
    assert (found.capability, found.ranges) == ("Filling", {"FillVolume": (0.5, 10.0)})
    assert [s.capability for s in found.steps] == ["Positioning", "Dosing", "Referencing"]


def test_without_a_pump_nothing_is_filled():
    domain = filling()
    del domain.capabilities["Dosing"]
    assert discover(domain) == []


def test_a_skill_offers_what_it_reaches():
    """T9: DoubleDose doses its Dose (0.5 to 10 mL) twice, so it fills 1 to 20 mL; a rule over the
    meanings of its parameters can only say 0.5 to 10."""
    from test_modsync import composed
    from test_modsync_desired import wanting
    delivered = aas(load(SPECS / "filling.yaml"), "pi")[0]
    module, components = wanting(composed().spec, delivered)
    module["submodels"] = [submodel(delivered, "CapabilityDescription") if s["idShort"] == "CapabilityDescription" else s
                           for s in module["submodels"]]
    double = at(submodel(capabilities(module, components), "CapabilityDescription"), "OfferedCapabilities", "Filling_DoubleDose")
    volume = at(double, "PropertySet", "FillVolume", "Value")
    assert (volume["min"], volume["max"]) == ("1.0", "20.0")
    single = at(submodel(capabilities(module, components), "CapabilityDescription"), "OfferedCapabilities", "Filling")
    assert (at(single, "PropertySet", "FillVolume", "Value")["min"], at(single, "PropertySet", "FillVolume", "Value")["max"]) == ("0.5", "10.0")


def test_a_module_without_skills_offers_what_it_can_plan_after_a_reconfiguration():
    """T10: the filling module with its module level skills taken out still offers Filling, once a
    skill for it is planned and built; no skill realizes it yet."""
    module, components = aas(load(SPECS / "filling.yaml"), "pi")
    module = copy.deepcopy(module)
    skills = submodel(module, "Skills")
    composite = f"{BASE}/skill/Composite"
    skills["submodelElements"] = [e for e in children(skills)
                                  if composite not in [k["keys"][0]["value"] for k in e.get("supplementalSemanticIds", [])]]
    offered = at(submodel(capabilities(module, components), "CapabilityDescription"), "OfferedCapabilities", "Filling")
    marks = {q["type"]: q["value"] for q in at(offered, "Capability")["qualifiers"]}
    assert marks["Availability"] == "AfterReconfiguration" and marks["Derived"] == "true"
    assert not [r for r in children(at(offered, "CapabilityRelations")) if r.get("modelType") == "RelationshipElement"]
    volume = at(offered, "PropertySet", "FillVolume", "Value")
    assert (volume["min"], volume["max"]) == ("0.5", "10.0")
    assert at(offered, "PropertySet", "ContainerType", "Value")["value"] == "vial"      # the machine's facts stay
