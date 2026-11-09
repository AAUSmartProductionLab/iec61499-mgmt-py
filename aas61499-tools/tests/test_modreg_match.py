"""modreg.match: the one capability matcher (the skill service's /match, the agents, the plan check
and the CIRP paper's evaluation call it). The cases the web UI's matcher was tested on, and those
of the plan check's ``covers`` it replaced.

The AASs are written here as an AAS server holds them; no extra is needed but for ``lineage``.
"""
import pytest

from modreg.match import (AFTER, CONSTRAINED, NOW, Capability, Parameter, Property, candidates, capabilities, compare,
                          evaluate, local, match, offered, required, values)

LAB = "https://smartproductionlab.aau.dk/semantics"
IDTA = "https://admin-shell.io/idta"


def ref(value: str) -> dict:
    return {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": value}]}


def sem(name: str) -> dict:
    return ref(f"{IDTA}/CapabilityDescription/{name}/1/0")


def element(name: str, value=None, unit: str = "", kind: str = "xs:double", low=None, high=None, items=None) -> dict:
    """A property container with its Value: a Property, a Range (``low``, ``high``) or a list (``items``)."""
    value_ = {"idShort": "Value", "supplementalSemanticIds": [ref(f"{LAB}/{name}")],
              "qualifiers": [{"type": "Unit", "valueType": "xs:string", "value": unit}] if unit else []}
    if items is not None:
        value_.update(modelType="SubmodelElementList", valueTypeListElement=kind,
                      value=[{"modelType": "Property", "valueType": kind, "value": str(i)} for i in items])
    elif low is not None:
        value_.update(modelType="Range", valueType=kind, min=str(low), max=str(high))
    else:
        value_.update(modelType="Property", valueType=kind, **({"value": str(value)} if value is not None else {}))
    return {"modelType": "SubmodelElementCollection", "idShort": name, "semanticId": sem("PropertyContainer"), "value": [value_]}


def container(aas: str, name: str, meaning: str, props: list[dict], role: str = "Offered", skill: str | None = None,
              after: bool = False, constrained: bool = False, held_in: str = "OfferedCapabilities") -> dict:
    marks = [{"type": f"CapabilityRoleQualifier/{role}", "valueType": "xs:boolean", "value": "true",
              "semanticId": sem(f"CapabilityRoleQualifier/{role}")}]
    if after:
        marks.append({"type": "Availability", "valueType": "xs:string", "value": AFTER})
    relations = []
    if skill:
        relations.append({"modelType": "RelationshipElement", "idShort": "RealizedBy", "semanticId": sem("CapabilityRealizedBy"),
                          "first": {"type": "ModelReference", "keys": [
                              {"type": "Submodel", "value": f"{aas}/submodels/CapabilityDescription"},
                              {"type": "SubmodelElementCollection", "value": held_in},
                              {"type": "SubmodelElementCollection", "value": name}, {"type": "Capability", "value": "Capability"}]},
                          "second": {"type": "ModelReference", "keys": [{"type": "Submodel", "value": f"{aas}/submodels/Skills"},
                                                                        {"type": "SubmodelElementCollection", "value": skill}]}})
    if constrained:
        relations.append({"modelType": "SubmodelElementCollection", "idShort": "ConstraintSet", "semanticId": sem("ConstraintSet"), "value": []})
    return {"modelType": "SubmodelElementCollection", "idShort": name, "semanticId": sem("CapabilityContainer"), "value": [
        {"modelType": "Capability", "idShort": "Capability", "semanticId": sem("Capability"), "qualifiers": marks,
         "supplementalSemanticIds": [ref(f"{LAB}/{meaning}")]},
        {"modelType": "SubmodelElementCollection", "idShort": "PropertySet", "semanticId": sem("PropertySet"), "value": props},
        {"modelType": "SubmodelElementCollection", "idShort": "CapabilityRelations", "semanticId": sem("CapabilityRelations"),
         "value": relations}]}


def aas(name: str, *containers: dict, held_in: str = "OfferedCapabilities") -> dict:
    return {"assetAdministrationShells": [{"id": name, "idShort": name}], "submodels": [{
        "id": f"{name}/submodels/CapabilityDescription", "idShort": "CapabilityDescription",
        "semanticId": ref(f"{IDTA}/SubmodelTemplate/CapabilityDescription/1/0"),
        "submodelElements": [{"modelType": "SubmodelElementCollection", "idShort": held_in, "semanticId": sem("CapabilitySet"),
                              "value": list(containers)}]}]}


def filling(name="Filling", skill="Dispensing", high=10.0, after=False, constrained=False, meaning="Filling", aas_="filling"):
    return container(aas_, name, meaning, [element("FillVolume", unit="mL", low=0.5, high=high),
                                           element("ContainerType", kind="xs:string", items=["vial", "syringe"]),
                                           element("AbsoluteFillError", 0.05, "mL")], skill=skill, after=after, constrained=constrained)


VIAL = aas("vial", container("vial", "Filling", "Filling", [element("FillVolume", 2.0, "mL"), element("ContainerType", "vial", kind="xs:string"),
                                                            element("AbsoluteFillError", unit="mL", low=0.0, high=0.1)],
                             role="Required", held_in="RequiredCapabilities"), held_in="RequiredCapabilities")


def need(env: dict = VIAL) -> Capability:
    return next(c for c in capabilities(env) if c.role == "Required")


def prop(kind="value", value="", low="", high="", unit="mL", value_type="xs:double", items=()):
    return Property("FillVolume", f"{LAB}/FillVolume", unit, value_type, kind, value, low, high, list(items))


# A property ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("wanted, given, status", [
    (prop(value="2.0"), prop("range", low="0.5", high="10.0"), "match"),          # a value in an offered range
    (prop(value="12"), prop("range", low="0.5", high="10.0"), "mismatch"),
    (prop("range", low="0", high="0.1"), prop(value="0.05"), "match"),              # at most so much fill error
    (prop("range", low="0", high="0.01"), prop(value="0.05"), "mismatch"),
    (prop(value="2"), prop(value="2.0", value_type="xs:float"), "match"),           # numbers as numbers
    (prop(value="2"), prop("values", items=["1.0", "2.0"]), "match"),               # one of the values it takes
    (prop("range", low="1.5", high="3"), prop("values", items=["1.0", "2.0"]), "match"),
    (prop("range", low="0", high="1"), prop("range", low="0", high="2"), "unknown"),  # range to range: no rule
    (prop(value="2", unit="L"), prop("range", low="0.5", high="10.0"), "unknown"),  # units are not converted
    (prop(value="2"), prop("range", low="10", high="0.5"), "unknown"),               # an invalid range
    (prop(value="2"), prop(value=""), "unknown"),                                   # a state, not a value offered
    (prop(value="2"), prop(value="2.0", value_type="xs:string"), "unknown"),        # a number written as a string
    (prop(value="vial", value_type="xs:string", unit=""), prop("values", value_type="xs:string", unit="", items=["vial", "syringe"]), "match"),
    (prop(value="bag", value_type="xs:string", unit=""), prop("values", value_type="xs:string", unit="", items=["vial", "syringe"]), "mismatch"),
    (prop(value="true", value_type="xs:boolean", unit=""), prop(value="true", value_type="xs:boolean", unit=""), "match"),
    (prop(value="2", value_type=""), prop("range", low="0.5", high="10.0"), "unknown"),   # no type stated
])
def test_a_required_property_against_the_offered_one(wanted, given, status):
    assert compare(wanted, given).status == status


def test_a_property_the_offer_says_nothing_about_is_unknown_and_said_so():
    check = compare(prop(value="2"), None)
    assert (check.status, check.why, check.reason) == ("unknown", "undescribed", "FillVolume: property not described by the station")
    check = compare(prop(value="12"), prop("range", low="0.5", high="10.0"))
    assert check.reason == "FillVolume: required 12, offered 0.5–10.0 mL"


# A resource ---------------------------------------------------------------------------------------

def test_a_resource_matches_with_the_capability_and_its_skill():
    [found] = match([need()], [aas("filling", filling())])
    assert (found.aas_id, found.status, found.availability, found.reconfigure) == ("filling", "match", NOW, [])
    assert [c.name for c in found.capabilities] == ["Filling"]
    assert found.capabilities[0].realized_by[0]["keys"][-1]["value"] == "Dispensing"
    # The web UI's names.
    assert set(found.json()) == {"aasId", "status", "reasons", "capabilities", "availability", "reconfigure"}
    assert found.json()["capabilities"][0]["properties"][1]["values"] == ["vial", "syringe"]


def test_one_offered_now_comes_before_one_offered_after_a_reconfiguration():
    # 12 mL: Dispensing (up to 10 mL) does not take it; a described DoubleDose (up to 20 mL) would.
    twelve = Parameter("FillVolume", [f"{LAB}/FillVolume"], "12", "mL", "xs:double")
    module = aas("filling", filling(), filling("Filling_DoubleDose", "DoubleDose", 20.0, after=True))
    [found] = match([need()], [module], [twelve])
    assert (found.status, found.availability, found.reconfigure) == ("match", AFTER, ["DoubleDose"])
    assert "Filling: offered after a reconfiguration (the skill is described, not built yet)" in found.reasons
    # Both would do: the one offered now.
    both = aas("filling", filling(high=20.0), filling("Filling_DoubleDose", "DoubleDose", 20.0, after=True))
    [now] = match([need()], [both], [twelve])
    assert (now.status, now.availability, now.reconfigure) == ("match", NOW, [])


def test_the_recipe_gives_a_required_value_unless_its_association_is_unclear():
    module = [aas("filling", filling())]
    volume = Parameter("Dose target", [f"{LAB}/FillVolume"], "12", "mL", "xs:double")
    [found] = match([need()], module, [volume])
    assert found.status == "mismatch" and any(r.startswith("FillVolume: required 12") for r in found.reasons)
    two = Parameter("FillVolume", [f"{LAB}/FillVolume"], "2", "mL", "xs:double")
    assert match([need()], module, [two, two])[0].status == "unknown"                       # ambiguous
    assert match([need()], module, [Parameter("V", [f"{LAB}/FillVolume"], "2", "L", "xs:double")])[0].status == "unknown"
    # A range is a tolerance: a parameter of its meaning does not replace it.
    error = Parameter("Accuracy", [f"{LAB}/AbsoluteFillError"], "0.05", "mL", "xs:double")
    assert match([need()], module, [two, error])[0].status == "match"
    syringe = Parameter("ContainerType", [f"{LAB}/ContainerType"], "bag", "", "xs:string")
    assert match([need()], module, [syringe])[0].status == "mismatch"


def test_a_capability_stating_constraints_needs_them_evaluated():
    [found] = match([need()], [aas("filling", filling(constrained=True))])
    assert found.status == "unknown" and found.reasons[-1] == CONSTRAINED
    [candidate] = evaluate(need(), offered(aas("filling", filling(constrained=True))))
    assert candidate.fits and candidate.constrained


def test_a_resource_without_the_capability_is_a_mismatch_and_an_unresolved_requirement_unknown():
    stoppering = aas("stoppering", container("stoppering", "Stoppering", "Stoppering", [], skill="Stoppering"))
    [found] = match([need()], [stoppering, VIAL])                     # a product offers nothing: not answered
    assert (found.aas_id, found.status, found.reasons) == ("stoppering", "mismatch", ["Filling: capability not offered"])
    assert match([Capability("Filling", [])], [stoppering])[0].reasons == ["Filling: unresolved requirement"]
    assert match([], [stoppering]) == []


def test_a_narrower_class_is_offered_only_when_asked_and_after_the_class_itself(monkeypatch):
    monkeypatch.setattr("modreg.match.lineage", lambda name: ("BottomUpFilling", "Filling") if name == "BottomUpFilling" else (name,))
    bottom_up = filling("BottomUpFilling", "BottomUp", meaning="BottomUpFilling")
    assert evaluate(need(), offered(aas("filling", bottom_up))) == []
    [narrower] = evaluate(need(), offered(aas("filling", bottom_up)), narrower=True)
    assert not narrower.exact
    both = evaluate(need(), offered(aas("filling", bottom_up, filling())), narrower=True)
    assert min(both, key=lambda c: c.rank()).capability.name == "Filling"


# A requirement ------------------------------------------------------------------------------------

def test_a_requirement_is_found_by_its_model_reference_or_named_by_its_meaning():
    reference = need().reference
    assert reference["keys"][1:] == [{"type": "SubmodelElementCollection", "value": "RequiredCapabilities"},
                                     {"type": "SubmodelElementCollection", "value": "Filling"}, {"type": "Capability", "value": "Capability"}]
    found = required(reference, [aas("filling", filling()), VIAL], "Filling step")
    assert (found.name, found.meanings, len(found.properties), found.aas_id) == ("Filling step", [f"{LAB}/Filling"], 3, "vial")
    assert required({**reference, "keys": reference["keys"][:-1]}, [VIAL]).meanings == [f"{LAB}/Filling"]   # its container
    assert required(ref(f"{LAB}/Filling"), []).meanings == [f"{LAB}/Filling"]
    assert required({"type": "ModelReference", "keys": [{"type": "Submodel", "value": "nowhere"}]}, [VIAL], "X").meanings == []
    # The first demo's vocabulary is the lab's.
    assert required(ref("https://smartproductionlab.aau.dk/demo/pharma/semantics/Filling"), []).meanings == [f"{LAB}/Filling"]
    assert local("https://smartproductionlab.aau.dk/demo/pharma/semantics/Filling") == "Filling"


def test_what_a_requirement_is_planned_with():
    syringe = Parameter("ContainerType", [f"{LAB}/ContainerType"], "syringe", "", "xs:string")
    assert values(need(), [Parameter("Volume", [f"{LAB}/FillVolume"], "3.5", "mL", "xs:double"), syringe]) == \
        {"FillVolume": 3.5, "ContainerType": "syringe"}
    assert values(need()) == {"FillVolume": 2.0, "ContainerType": "vial"}


def test_a_skill_is_planned_where_none_realizes_the_capability_or_a_broader_class_is_offered():
    lineage = {"BottomUpFilling": ("BottomUpFilling", "Filling")}
    planned = aas("planned", filling("Filling", None, after=True, aas_="planned"))   # discovered: no skill yet
    broader = aas("broader", filling(aas_="broader"))
    stoppering = aas("stoppering", container("stoppering", "Stoppering", "Stoppering", []))
    resources = [planned, broader, stoppering]
    assert candidates(need(), match([need()], resources), resources, lambda n: lineage.get(n, (n,))) == ["planned", "broader"]
    bottom_up = Capability("BottomUpFilling", [f"{LAB}/BottomUpFilling"])
    assert candidates(bottom_up, match([bottom_up], resources), resources, lambda n: lineage.get(n, (n,))) == ["planned", "broader"]
