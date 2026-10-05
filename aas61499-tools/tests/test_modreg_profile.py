"""modreg: a module's profile on the lab's shared AAS model and the AAS built from it.

Needs the ``registration`` extra (aas-model, rdflib); skipped without it.
"""
import json
from pathlib import Path

import pytest

pytest.importorskip("aas_model")
pytest.importorskip("rdflib")

from modgen import SPECS, load                                              # noqa: E402
from modreg import model, profile as profiles                               # noqa: E402
from modreg.ontology import Blueprint, check                                # noqa: E402
from modsync.compare import compare, expected, expected_values              # noqa: E402
from modsync.device import Snapshot                                         # noqa: E402

ARSO = Path(__file__).resolve().parents[2] / "ontology" / "ARSO"
BASE = "https://smartproductionlab.aau.dk"


# What an AAS environment holds -----------------------------------------------------------------

def children(element: dict) -> list[dict]:
    held = element.get("submodelElements") or element.get("statements") or element.get("value")
    return [c for c in held if isinstance(c, dict) and "modelType" in c] if isinstance(held, list) else []


def submodel(env: dict, id_short: str) -> dict:
    return next(s for s in env["submodels"] if s["idShort"] == id_short)


def at(element: dict, *path: str) -> dict:
    for step in path:
        element = next(c for c in children(element) if c.get("idShort") == step)
    return element


def names(element: dict) -> list[str]:
    return [c.get("idShort") for c in children(element)]


def references(element: dict, path: str):
    for key, value in element.items():
        if isinstance(value, dict) and value.get("type") == "ModelReference":
            yield f"{path}/{key}", value
    for child in children(element):
        yield from references(child, f"{path}/{child.get('idShort', '-')}")


def resolve(env: dict, reference: dict) -> dict | None:
    keys = reference["keys"]
    node = next((s for s in env["submodels"] if s["id"] == keys[0]["value"]), None)
    for key in keys[1:]:
        if node is None:
            return None
        node = next((c for c in children(node) if c.get("idShort") == key["value"] and c["modelType"] == key["type"]), None)
    return node


# The modules ------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def stoppering():
    spec = load(SPECS / "stoppering.yaml")
    return spec, profiles.describe(spec, "pi", spec_path="cell/modules/stoppering.yaml")


@pytest.fixture(scope="module")
def stoppering_aas(stoppering):
    return model.build(stoppering[1])


def test_a_profile_is_small_and_gives_the_module_back(stoppering):
    spec, profile = stoppering
    assert profile["aas_type"] == "ModuleTypeAAS" and profile["id_short"] == "StopperingModuleAAS"
    assert profile["global_asset_id"] == f"{BASE}/assets/StopperingModule"
    text = json.dumps(profile)                                  # plain JSON
    full = model.asset(profile).model_dump(mode="json")
    assert len(text) < len(json.dumps(full)) / 4                # what the types say is not repeated
    # Reading it gives the model it was written from (model.profile checks that when it writes),
    # and writing that model again gives the same profile.
    assert model.profile(model.validated(profile), global_asset_id=profile["global_asset_id"]) == profile


def test_a_module_speaks_opc_ua_only(stoppering, stoppering_aas):
    spec, _ = stoppering
    interfaces = submodel(stoppering_aas, "AssetInterfacesDescription")
    assert names(interfaces) == ["interface_opcua"]
    assert at(interfaces, "interface_opcua", "EndpointMetadata", "base")["value"] == "opc.tcp://" + spec.targets["pi"].host + ":4840"
    actions = at(interfaces, "interface_opcua", "InteractionMetadata", "actions")
    offered = [n for n, s in [*spec.skills.items(), *spec.composites.items()] if s.offered]
    for skill in offered:
        assert {f"{skill}_{m}" for m in ("Start", "Stop", "Abort", "Reset")} <= set(names(actions))
    assert {"Occupation_Occupy", "Occupation_Release", "Module_Reset", "Module_Clear"} <= set(names(actions))
    start = at(actions, "RaisePiston_Start")
    path = "/0:Objects/1:Stoppering/1:Skills/1:RaisePiston/1:Start"
    assert at(start, "forms", "href")["value"] == at(start, "forms", "uav_browsePath")["value"] == path
    # The arguments in call order: the session, then the skill's parameters.
    assert names(at(start, "input", "properties")) == ["Session", *spec.skills["RaisePiston"].parameters]
    assert names(at(start, "output", "properties")) == ["Accepted", "ErrorID"]
    state = at(interfaces, "interface_opcua", "InteractionMetadata", "properties", "Module_State")
    assert at(state, "forms", "href")["value"] == "/0:Objects/1:Stoppering/1:Module/1:State"


def test_skills_are_arsos_skills_with_what_reconfiguration_needs(stoppering, stoppering_aas):
    spec, _ = stoppering
    described = submodel(stoppering_aas, "Skills")
    assert names(described) == ["Interfaces", "Skills", "Errors"]
    assert described["semanticId"]["keys"][0]["value"] == f"{BASE}/ARSO/Skills/1/0/Submodel"
    assert at(described, "Errors", "Timeout", "ErrorCode")["value"] == "3"
    skills = at(described, "Skills")
    offered = [n for n, s in [*spec.skills.items(), *spec.composites.items()] if s.offered]
    assert names(skills) == ["Occupy", "Release", *offered]
    primitive = at(skills, "RaisePiston")
    decl = spec.skills["RaisePiston"]
    assert at(primitive, "SemanticId")["value"] == f"{BASE}/skills/RaisePiston"
    assert at(primitive, "InterfaceReference")["value"]["keys"][-1]["value"] == "RaisePiston_Start"
    operation = at(primitive, "RaisePiston")                        # the Operation is named like the skill
    assert operation["modelType"] == "Operation"
    assert [v["value"]["idShort"] for v in operation["inputVariables"]] == ["Session", "Duration"]
    assert [v["value"]["idShort"] for v in operation["outputVariables"]] == ["Accepted", "ErrorID"]
    assert at(primitive, "Kind")["value"] == "Primitive"
    assert at(primitive, "Contract", "After")["value"] == decl.after
    duration = at(primitive, "Parameters", "Duration")
    declared = {q["type"]: q["value"] for q in duration["qualifiers"]}
    assert float(duration["value"]) == decl.parameters["Duration"].default
    assert float(declared["Maximum"]) == decl.parameters["Duration"].maximum and declared["Unit"] == "s"
    assert [r["value"]["keys"][-1]["value"] for r in children(at(primitive, "Occupies"))] == [decl.equipment]
    assert at(primitive, "StateReference")["value"]["keys"][-1]["value"] == "RaisePiston_State"
    name, composite = next(iter(spec.composites.items()))
    sequence = at(skills, name)
    assert at(sequence, "Kind")["value"] == "Composite"
    steps = children(at(sequence, "Execute"))
    assert at(sequence, "Execute")["modelType"] == "SubmodelElementList" and len(steps) == len(composite.execute)
    assert at(steps[0], "Skill")["value"]["keys"][-1]["value"] == composite.execute[0].skill
    assert at(steps[0], "InstancePath")["value"] == f"{name}.Execute.{composite.execute[0].name}"
    assert len(children(at(sequence, "Uses"))) == len({s.skill for s in [*composite.execute, *composite.stop]})


def test_a_skill_that_only_runs_as_a_step_is_named_not_listed():
    """ARSO asks every skill for an Operation and an action of the interface; Dwell has neither."""
    spec = load(SPECS / "filling.yaml")
    assert not spec.skills["Dwell"].offered
    env = model.build(profiles.describe(spec, "pi"))
    skills = at(submodel(env, "Skills"), "Skills")
    assert "Dwell" not in names(skills)
    step = next(s for s in children(at(skills, "Dispensing", "Execute")) if "Dwell" in at(s, "InstancePath")["value"])
    assert at(step, "Skill")["value"] == {"type": "ExternalReference",
                                          "keys": [{"type": "GlobalReference", "value": f"{BASE}/skills/Dwell"}]}
    assert float(at(step, "Bindings", "Duration")["value"]) == 1.0
    # A result carries the unit of the equipment input behind it, through the step for a composite.
    properties = at(submodel(env, "AssetInterfacesDescription"), "interface_opcua", "InteractionMetadata", "properties")
    for key in ("Weigh_Result_Weight", "Dispensing_Result_Weight"):
        assert at(properties, key, "unit")["value"] == spec.equipment["Scale"].inputs["Weight"].unit == "g"
        assert at(properties, key, "type")["value"] == "number"
    # No skill of the filling module has a parameter of its own, so it has no Parameters submodel.
    assert "Parameters" not in [s["idShort"] for s in env["submodels"]]


def test_equipment_data_points_and_mappings(stoppering, stoppering_aas):
    spec, _ = stoppering
    structure = submodel(stoppering_aas, "HierarchicalStructures")
    assert at(structure, "EntryNode")["globalAssetId"] == stoppering_aas["assetAdministrationShells"][0]["assetInformation"]["globalAssetId"]
    assert names(at(structure, "EntryNode")) == list(spec.equipment)
    data = submodel(stoppering_aas, "OperationalData")
    assert data["semanticId"]["keys"][0]["value"] == f"{BASE}/ARSO/OperationalData/1/0/Submodel"
    inputs = [f"{item}_{s}" for item, eq in spec.equipment.items() for s in eq.inputs]
    assert {"PackMLState", "OccupationState", *inputs} <= set(names(data))
    # A data point is a decimal with a value and the concept it stands for.
    assert all(d["valueType"] == "xs:decimal" and d["value"] == "0" and d["semanticId"] for d in children(data))
    mappings = at(submodel(stoppering_aas, "AssetInterfacesMappingConfiguration"), "MappingConfigurations")
    feed = children(mappings)[0]
    # Every data point has a source: the property of the interface that publishes it.
    assert len(children(at(feed, "Sinks"))) == len(children(at(feed, "Sources"))) == len(names(data))
    parameters = submodel(stoppering_aas, "Parameters")
    assert parameters["semanticId"]["keys"][0]["value"] == f"{BASE}/ARSO/Parameters/1/0/Submodel"
    entry = at(parameters, "RaisePiston_Duration")
    assert float(at(entry, "Value")["value"]) == spec.skills["RaisePiston"].parameters["Duration"].default
    assert at(entry, "InterfaceReference")["value"]["keys"][-1]["value"] == "RaisePiston_Parameter_Duration"


def test_every_reference_resolves(stoppering_aas):
    found = [(path, ref) for sm in stoppering_aas["submodels"] for path, ref in references(sm, sm["idShort"])]
    assert len(found) > 50 and [path for path, ref in found if resolve(stoppering_aas, ref) is None] == []


def test_a_module_that_was_read_shows_what_runs_there():
    spec = load(SPECS / "stoppering.yaml")
    app = expected(spec, "pi")
    values = expected_values(spec, app)
    snap = Snapshot("192.168.0.50", 61499, fbs=dict(app.fbs), hashes={t: f"v2:{t}" for t in set(app.fbs.values())},
                    connections=set(app.event_connections + app.data_connections),
                    values={**values, "RaisePiston.Duration": "5.5"}, read_at="2026-10-02T10:00:00+00:00")
    drift = compare(app, values, snap, set())
    profile = profiles.describe(spec, "pi", snap, drift, "cell/modules/stoppering.yaml", "opc.tcp://192.168.0.50:4840")
    env = model.build(profile)
    config = submodel(env, "ControlConfiguration")
    assert at(config, "SyncState")["value"] == "Drift" and len(names(at(config, "Differences"))) == 1
    assert at(config, "Runtime", "ManagementEndpoint")["value"] == "192.168.0.50:61499"
    assert len(names(at(config, "Types"))) == len(set(app.fbs.values()))
    assert float(at(submodel(env, "Parameters"), "RaisePiston_Duration", "Value")["value"]) == 5.5
    assert float(at(submodel(env, "Skills"), "Skills", "RaisePiston", "Parameters", "Duration")["value"]) == 5.5
    implementation = at(submodel(env, "Skills"), "Skills", "RaisePiston", "Implementation")
    assert at(implementation, "FBType")["value"] == app.fbs["RaisePiston"]
    assert at(implementation, "TypeHash")["value"] == f"v2:{app.fbs['RaisePiston']}"
    # The program digest is of the spec, not of what was read.
    assert at(config, "ProgramDigest")["value"] == profiles.program_digest(spec, "pi")


def test_the_labs_own_resources_go_the_same_way():
    env = model.build({"id_short": "SomeStationAAS", "asset_type": f"{BASE}/Resource/Station"})
    assert names(submodel(env, "AssetInterfacesDescription")) == ["interface_mqtt"]
    assert {"Halt", "Occupy", "Release"} == set(names(at(submodel(env, "ControlComponentInstance"), "Skills")))


def test_what_is_not_a_profile_is_refused():
    with pytest.raises(model.ProfileError, match="id_short"):
        model.asset({"aas_type": "ModuleTypeAAS"})
    with pytest.raises(model.ProfileError, match="unknown AAS type"):
        model.asset({"aas_type": "Nothing", "id_short": "X"})
    with pytest.raises(model.ProfileError, match="[Ee]xtra"):
        model.asset({"aas_type": "ModuleTypeAAS", "id_short": "X", "variables": {}})


@pytest.mark.skipif(not ARSO.exists(), reason="the ontologies are a local working document (ontology/ARSO)")
def test_a_module_breaks_no_restriction_of_arso(stoppering_aas):
    report = check(stoppering_aas, Blueprint(ARSO))
    assert report.errors == [], report.lines()[:20]
