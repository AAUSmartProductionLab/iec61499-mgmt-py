"""modreg: a module's profile on the lab's shared AAS model and the AAS built from it.

Needs the ``registration`` extra (aas-model, rdflib); skipped without it.
"""
import json
from pathlib import Path

import pytest
import yaml

pytest.importorskip("aas_model")
pytest.importorskip("rdflib")

from modgen import SPECS, load                                              # noqa: E402
from modgen.spec import ModuleSpec                                          # noqa: E402
from modreg import model, profile as profiles                               # noqa: E402
from modreg.ontology import Blueprint, check                                # noqa: E402
from modsync.aas import browse_path                                         # noqa: E402
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
    # Which command the action carries out: the semantic id of the Operation that invokes it.
    assert [ref["keys"][0]["value"] for ref in start["supplementalSemanticIds"]] == [f"{BASE}/skills/RaisePiston"]
    stop = at(actions, "RaisePiston_Stop")
    assert [ref["keys"][0]["value"] for ref in stop["supplementalSemanticIds"]] == [f"{BASE}/skills/RaisePiston/Stop"]
    state = at(interfaces, "interface_opcua", "InteractionMetadata", "properties", "Module_State")
    assert at(state, "forms", "href")["value"] == "/0:Objects/1:Stoppering/1:Module/1:State"


def test_skills_are_arsos_skills_with_what_reconfiguration_needs(stoppering, stoppering_aas):
    spec, _ = stoppering
    described = submodel(stoppering_aas, "Skills")
    assert names(described) == ["Interfaces", "Skills", "Errors", "Module", "Procedures"]
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
    # The block type a step of the primitive would be an instance of, known without reading the module.
    assert at(primitive, "Implementation", "FBType")["value"] == f"{spec.package}::SK_RaisePiston"
    assert at(primitive, "Implementation", "InstancePath")["value"] == "RaisePiston"
    assert "TypeHash" not in names(at(primitive, "Implementation"))          # only a module that was read has it
    name, composite = next(iter(spec.composites.items()))
    sequence = at(skills, name)
    assert at(sequence, "Kind")["value"] == "Composite"
    # A module level skill has no type of its own: it is its Control block.
    assert at(sequence, "Implementation", "FBType")["value"] == "modlib::SKILL_Core"
    assert at(sequence, "Implementation", "InstancePath")["value"] == f"{name}.Control"
    steps = children(at(sequence, "Execute"))
    assert at(sequence, "Execute")["modelType"] == "SubmodelElementList" and len(steps) == len(composite.execute)
    assert at(steps[0], "Skill")["value"]["keys"][-1]["value"] == composite.execute[0].skill
    assert at(steps[0], "InstancePath")["value"] == f"{name}.Execute.{composite.execute[0].name}"
    # A constant bound to a step is the bound value, not the default of the step's skill.
    bound = next((i, s) for i, s in enumerate(composite.execute) if s.bind)
    for parameter, constant in bound[1].bind.items():
        assert float(at(steps[bound[0]], "Bindings", parameter)["value"]) == constant
    assert any(constant != spec.skills[bound[1].skill].parameters[p].default for p, constant in bound[1].bind.items())
    assert len(children(at(sequence, "Uses"))) == len({s.skill for s in [*composite.execute, *composite.stop]})


def test_a_skill_that_only_runs_as_a_step_is_a_building_block():
    """ARSO asks every skill for an Operation and an action of the interface; a primitive a module
    does not offer has neither (here: the filling module with Dispense not offered). It is a building
    block: what a step is an instance of, takes and needs."""
    data = yaml.safe_load((SPECS / "filling.yaml").read_text(encoding="utf-8"))
    data["skills"]["Dispense"]["offered"] = False
    spec = ModuleSpec.model_validate(data)
    assert load(SPECS / "filling.yaml").skills["Dispense"].offered          # the module itself offers it
    env = model.build(profiles.describe(spec, "pi"))
    skills = at(submodel(env, "Skills"), "Skills")
    blocks = at(submodel(env, "Skills"), "BuildingBlocks")
    assert names(blocks) == ["Dispense"] and not set(names(blocks)) & set(names(skills))
    block = at(blocks, "Dispense")
    assert at(block, "SemanticId")["value"] == f"{BASE}/skills/Dispense" and at(block, "Kind")["value"] == "Primitive"
    assert at(block, "Implementation", "FBType")["value"] == f"{spec.package}::SK_Dispense" == "filling::SK_Dispense"
    assert "InstancePath" not in names(at(block, "Implementation"))
    rate = at(block, "Parameters", "FlowRate")
    declared = {q["type"]: q["value"] for q in rate["qualifiers"]}
    assert float(rate["value"]) == 1.0 and declared["Unit"] == "mL/s" and float(declared["Maximum"]) == 5.0
    assert at(block, "Contract", "After")["value"] == "Volume / FlowRate"
    assert "Occupies" not in names(block)                           # it commands no equipment
    # A step and the skill's Uses refer to the building block.
    reference = {"type": "ModelReference", "keys": [
        {"type": "Submodel", "value": submodel(env, "Skills")["id"]},
        {"type": "SubmodelElementCollection", "value": "BuildingBlocks"},
        {"type": "SubmodelElementCollection", "value": "Dispense"}]}
    step = next(s for s in children(at(skills, "Dispensing", "Execute")) if "Dispense" in at(s, "InstancePath")["value"])
    assert at(step, "Skill")["value"] == reference
    assert reference in [u["value"] for u in children(at(skills, "Dispensing", "Uses"))]
    assert resolve(env, reference)["idShort"] == "Dispense"
    # The volume comes from the module level skill's parameter, the flow rate is the station's constant.
    handed_down = at(step, "Bindings", "Volume")
    assert handed_down["modelType"] == "ReferenceElement"
    assert resolve(env, handed_down["value"]) is at(skills, "Dispensing", "Parameters", "Volume")
    assert float(at(step, "Bindings", "FlowRate")["value"]) == 1.0
    # A result carries the unit of the equipment input behind it, through the step for a composite.
    properties = at(submodel(env, "AssetInterfacesDescription"), "interface_opcua", "InteractionMetadata", "properties")
    for key in ("Weigh_Result_Weight", "Dispensing_Result_Weight"):
        assert at(properties, key, "unit")["value"] == spec.equipment["Scale"].inputs["Weight"].unit == "g"
        assert at(properties, key, "type")["value"] == "number"
    # Dispensing's Volume is with the skill: an input of its Operation, and declared with its unit
    # and deployed value. There is no Parameters submodel for it.
    dispensing = at(skills, "Dispensing")
    assert [v["value"]["idShort"] for v in at(dispensing, "Dispensing")["inputVariables"]] == ["Session", "Volume"]
    volume = at(dispensing, "Parameters", "Volume")
    assert float(volume["value"]) == 1.0 and {q["type"]: q["value"] for q in volume["qualifiers"]}["Unit"] == "mL"
    assert "Parameters" not in [s["idShort"] for s in env["submodels"]]


def test_steps_publish_like_skills_where_the_program_puts_them():
    """A step's State, ErrorID, parameters and results are in the interface, at the path its
    instance publishes them in the generated program; the step refers to its State."""
    spec = load(SPECS / "filling.yaml")
    env = model.build(profiles.describe(spec, "pi"))
    values = expected_values(spec, expected(spec, "pi"))
    dispensing = at(submodel(env, "Skills"), "Skills", "Dispensing")
    steps = [*children(at(dispensing, "Execute")), *children(at(dispensing, "Stop"))]
    assert len(steps) == len(spec.composites["Dispensing"].execute) + len(spec.composites["Dispensing"].stop)
    for step in steps:
        state = resolve(env, at(step, "StateReference")["value"])
        ua_path = values[at(step, "InstancePath")["value"] + ".UaPath"].strip('"')
        assert at(state, "forms", "href")["value"] == browse_path(spec, f"{ua_path}/State")
    properties = at(submodel(env, "AssetInterfacesDescription"), "interface_opcua", "InteractionMetadata", "properties")
    assert at(properties, "Dispensing_Execute_Dispense_Parameter_FlowRate", "unit")["value"] == "mL/s"
    assert at(properties, "Dispensing_Execute_Weigh_Result_Weight", "unit")["value"] == "g"
    assert at(properties, "Dispensing_Stopping_MoveNeedleUp_ErrorID", "forms", "href")["value"].endswith(
        "/1:Dispensing/1:Stopping/1:MoveNeedleUp/1:ErrorID")
    # Their State and ErrorID are data points, fed like those of the skills.
    data = names(submodel(env, "OperationalData"))
    assert {"Dispensing_Execute_Weigh_State", "Dispensing_Stopping_MoveNeedleUp_ErrorID"} <= set(data)


def test_the_procedures_of_the_module_are_sequences_of_steps(stoppering, stoppering_aas):
    spec, _ = stoppering
    values = expected_values(spec, expected(spec, "pi"))
    procedures = at(submodel(stoppering_aas, "Skills"), "Procedures")
    assert names(procedures) == list(spec.procedures) == ["Resetting"]          # it stops without one
    for proc, steps in spec.procedures.items():
        described = children(at(procedures, proc))
        assert [at(s, "InstancePath")["value"] for s in described] == [f"{proc}.{s.name}" for s in steps]
        for step, item in zip(steps, described):
            assert at(item, "Skill")["value"]["keys"][-1]["value"] == step.skill
            state = resolve(stoppering_aas, at(item, "StateReference")["value"])
            ua_path = values[f"{proc}.{step.name}.UaPath"].strip('"')
            assert ua_path.startswith(f"/Procedures/{proc}/")
            assert at(state, "forms", "href")["value"] == browse_path(spec, f"{ua_path}/State")
    data = names(submodel(stoppering_aas, "OperationalData"))
    first = spec.procedures["Resetting"][0].name
    assert {f"Procedure_Resetting_{first}_State", f"Procedure_Resetting_{first}_ErrorID"} <= set(data)


IDTA_CAPABILITY = "https://admin-shell.io/idta/CapabilityDescription"


def semantic(element: dict) -> str:
    keys = (element.get("semanticId") or {}).get("keys") or []
    return keys[0]["value"] if keys else ""


def offered_capabilities(env: dict) -> list[dict]:
    """The offered capabilities of an AAS read the way the BaSyx web UI's process sequence module
    reads them (utils/capabilities.ts): standard containers by semanticId, the role by its boolean
    qualifier, the meaning by supplemental semanticId, units from the first IEC 61360 data
    specification, and the realizing skill by the CapabilityRealizedBy whose first is the capability."""
    found = []
    for sm in env["submodels"]:
        if semantic(sm) != "https://admin-shell.io/idta/SubmodelTemplate/CapabilityDescription/1/0":
            continue
        for cset in (c for c in children(sm) if semantic(c) == f"{IDTA_CAPABILITY}/CapabilitySet/1/0"):
            for box in (c for c in children(cset) if semantic(c) == f"{IDTA_CAPABILITY}/CapabilityContainer/1/0"):
                cap = next(c for c in children(box) if c["modelType"] == "Capability"
                           and semantic(c) == f"{IDTA_CAPABILITY}/Capability/1/0")
                role = [q for q in cap.get("qualifiers", []) if semantic(q).startswith(f"{IDTA_CAPABILITY}/CapabilityRoleQualifier/")
                        and q["valueType"] == "xs:boolean" and q["value"] in ("true", "1")]
                reference = {"type": "ModelReference", "keys": [
                    {"type": "Submodel", "value": sm["id"]}, {"type": "SubmodelElementCollection", "value": cset["idShort"]},
                    {"type": "SubmodelElementCollection", "value": box["idShort"]}, {"type": "Capability", "value": cap["idShort"]}]}
                properties = {}
                for pset in (c for c in children(box) if semantic(c) == f"{IDTA_CAPABILITY}/PropertySet/1/0"):
                    for item in (c for c in children(pset) if semantic(c) == f"{IDTA_CAPABILITY}/PropertyContainer/1/0"):
                        for prop in children(item):
                            meaning = prop["supplementalSemanticIds"][0]["keys"][0]["value"]
                            unit = ((prop.get("embeddedDataSpecifications") or [{}])[0].get("dataSpecificationContent") or {}).get("unit", "")
                            properties[meaning] = {"kind": prop["modelType"], "unit": unit, "value": prop.get("value"),
                                                   "min": prop.get("min"), "max": prop.get("max"), "type": prop.get("valueType")}
                realized = [r["second"] for rel in children(box) if semantic(rel) == f"{IDTA_CAPABILITY}/CapabilityRelations/1/0"
                            for r in children(rel) if r["modelType"] == "RelationshipElement"
                            and semantic(r) == f"{IDTA_CAPABILITY}/CapabilityRealizedBy/1/0" and r["first"] == reference]
                found.append({"role": [semantic(q).rsplit("/", 3)[-3] for q in role], "reference": reference,
                              "meanings": [r["keys"][0]["value"] for r in cap.get("supplementalSemanticIds", [])],
                              "properties": properties, "realized_by": realized})
    return found


def test_offered_capabilities_are_realized_by_skills_as_a_planner_reads_them():
    spec = load(SPECS / "filling.yaml")
    env = model.build(profiles.describe(spec, "pi"))
    [filling] = offered_capabilities(env)
    assert filling["role"] == ["Offered"]
    assert filling["meanings"] == [f"{BASE}/semantics/Filling"]
    # The capability is realized by the Dispensing skill of the Skills submodel: a reference.
    [skill] = filling["realized_by"]
    assert resolve(env, skill)["idShort"] == "Dispensing"
    assert skill["keys"][0]["value"] == submodel(env, "Skills")["id"]
    volume = filling["properties"][f"{BASE}/semantics/FillVolume"]
    assert (volume["kind"], volume["min"], volume["max"], volume["unit"]) == ("Range", "0.5", "10.0", "mL")
    assert filling["properties"][f"{BASE}/semantics/ContainerType"]["value"] == "vial"
    # A product's Vial 2 mL filling requirement (the planner's pharma example): the required value
    # lies in the offered range, the required error range holds the offered error, strings agree.
    required = {"FillVolume": 2.0, "ContainerType": "vial"}
    assert float(volume["min"]) <= required["FillVolume"] <= float(volume["max"])
    assert 0.0 <= float(filling["properties"][f"{BASE}/semantics/AbsoluteFillError"]["value"]) <= 0.1
    assert filling["properties"][f"{BASE}/semantics/ContainerType"]["value"] == required["ContainerType"]
    # The shell lists the submodel, and the profile gives the capabilities back.
    assert submodel(env, "CapabilityDescription")["id"] in [r["keys"][0]["value"] for r in
                                                           env["assetAdministrationShells"][0]["submodels"]]


def test_a_module_without_capabilities_has_no_capability_description():
    data = yaml.safe_load((SPECS / "filling.yaml").read_text(encoding="utf-8"))
    data.pop("capabilities")
    env = model.build(profiles.describe(ModuleSpec.model_validate(data), "pi"))
    assert "CapabilityDescription" not in [s["idShort"] for s in env["submodels"]]


def interaction(env: dict, kind: str) -> dict:
    return at(submodel(env, "AssetInterfacesDescription"), "interface_opcua", "InteractionMetadata", kind)


def href(env: dict, reference: dict) -> str:
    return at(resolve(env, reference), "forms", "href")["value"]


def test_a_skill_refers_to_every_action_and_property_of_its_interface(stoppering, stoppering_aas):
    spec, _ = stoppering
    root = "/0:Objects/1:Stoppering"
    skill = at(submodel(stoppering_aas, "Skills"), "Skills", "RaisePiston")
    methods = {m["idShort"]: href(stoppering_aas, m["value"]) for m in children(at(skill, "Methods"))}
    assert methods == {m: f"{root}/1:Skills/1:RaisePiston/1:{m}" for m in ("Start", "Stop", "Abort", "Reset")}
    assert href(stoppering_aas, at(skill, "StateReference")["value"]) == f"{root}/1:Skills/1:RaisePiston/1:State"
    assert href(stoppering_aas, at(skill, "ErrorReference")["value"]) == f"{root}/1:Skills/1:RaisePiston/1:ErrorID"
    # One Operation per command; the skill's own (Start) is named like the skill.
    operations = [c["idShort"] for c in children(skill) if c["modelType"] == "Operation"]
    assert operations == ["RaisePiston", "RaisePiston_Stop", "RaisePiston_Abort", "RaisePiston_Reset"]
    filling = model.build(profiles.describe(load(SPECS / "filling.yaml"), "pi"))
    results = at(submodel(filling, "Skills"), "Skills", "Dispensing", "Results")
    assert href(filling, at(results, "Weight")["value"]) == "/0:Objects/1:Filling/1:Skills/1:Dispensing/1:Results/1:Weight"
    # The module's own commands, state and occupation.
    machine = at(submodel(stoppering_aas, "Skills"), "Module")
    assert {m["idShort"]: href(stoppering_aas, m["value"]) for m in children(at(machine, "Methods"))} == \
        {m: f"{root}/1:Module/1:{m}" for m in ("Reset", "Start", "Stop", "Abort", "Clear")}
    assert href(stoppering_aas, at(machine, "StateReference")["value"]) == f"{root}/1:Module/1:State"
    assert href(stoppering_aas, at(machine, "OccupiedReference")["value"]) == f"{root}/1:Occupation/1:Occupied"


def test_the_aimc_maps_every_action_and_property_onto_a_submodel(stoppering_aas):
    env = stoppering_aas
    configs = children(at(submodel(env, "AssetInterfacesMappingConfiguration"), "MappingConfigurations"))
    fed: dict[str, list[dict]] = {}          # interface property -> the elements it feeds
    invoked: dict[str, list[dict]] = {}      # interface action -> the Operations invoking it
    for config in configs:
        sources = [resolve(env, at(s, "Source")["value"]) for s in children(at(config, "Sources"))]
        sinks = [resolve(env, at(s, "Sink")["value"]) for s in children(at(config, "Sinks"))]
        assert None not in sources and None not in sinks
        for found_source, found_sink in zip(sources, sinks):
            if found_source["modelType"] == "Operation":
                invoked.setdefault(found_sink["idShort"], []).append(found_source)
            else:
                fed.setdefault(found_source["idShort"], []).append(found_sink)
    assert sorted(fed) == sorted(names(interaction(env, "properties")))
    assert all(len(sinks) == 1 for sinks in fed.values())
    assert sorted(invoked) == sorted(names(interaction(env, "actions")))
    assert all(len(ops) == 1 for ops in invoked.values())
    # A parameter, result or state feeds its data point, an action is invoked by its Operation in
    # the Skills submodel.
    assert fed["RaisePiston_Parameter_Duration"][0]["idShort"] == "RaisePiston_Parameter_Duration"
    assert fed["Stoppering_Execute_ArmIn_Parameter_Angle"][0]["idShort"] == "Stoppering_Execute_ArmIn_Parameter_Angle"
    assert invoked["RaisePiston_Stop"][0]["idShort"] == "RaisePiston_Stop"
    assert invoked["Module_Reset"][0]["idShort"] == "Module_Reset"
    assert invoked["Occupation_Occupy"][0]["idShort"] == "Occupy"


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
    # A skill parameter of the current or last run is a data point as well, not a Parameters entry.
    assert at(data, "RaisePiston_Parameter_Duration")["semanticId"]["keys"][0]["value"] == \
        f"{BASE}/skills/RaisePiston/Parameters/Duration"
    assert "Parameters" not in [s["idShort"] for s in stoppering_aas["submodels"]]


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
    assert at(config, "Rules")["value"] == f"{BASE}/rules/module/1"          # docs/module-rules.md
    assert at(config, "Runtime", "ManagementEndpoint")["value"] == "192.168.0.50:61499"
    assert len(names(at(config, "Types"))) == len(set(app.fbs.values()))
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
