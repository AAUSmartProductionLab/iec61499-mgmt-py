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
from modsync.compare import compare, expected, expected_values              # noqa: E402
from modsync.device import Snapshot                                         # noqa: E402

ARSO = Path(__file__).resolve().parents[2] / "ontology" / "ARSO"
BASE = "https://smartproductionlab.aau.dk"


# What an AAS environment holds -----------------------------------------------------------------

def children(element: dict) -> list[dict]:
    """The elements an element holds; of an Operation, its variables."""
    if element.get("modelType") == "Operation":
        return [v["value"] for kind in ("inputVariables", "inoutputVariables", "outputVariables") for v in element.get(kind) or []]
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


def resolve(env: dict | list, reference: dict) -> dict | None:
    """The element a model reference names, in an AAS or in several (a module and its components)."""
    keys = reference["keys"]
    node = next((s for e in (env if isinstance(env, list) else [env]) for s in e["submodels"] if s["id"] == keys[0]["value"]), None)
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


def described(spec, target="pi", *more, **options) -> dict[str, dict]:
    """The AASs of a module and of its components, by idShort; the module's first."""
    envs = [model.build(profile) for profile in profiles.describe_all(spec, target, *more, **options)]
    return {env["assetAdministrationShells"][0]["idShort"]: env for env in envs}


@pytest.fixture(scope="module")
def stoppering_all(stoppering):
    return described(stoppering[0], spec_path="cell/modules/stoppering.yaml")


def variables(operation: dict, kind: str) -> list[str]:
    return [v["value"]["idShort"] for v in operation.get(kind) or []]


def ids(element: dict) -> list[str]:
    refs = [element.get("semanticId"), *element.get("supplementalSemanticIds", [])]
    return [r["keys"][0]["value"] for r in refs if r]


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
    start = at(actions, "MoveAxis_Start")
    path = "/0:Objects/1:Stoppering/1:Skills/1:MoveAxis/1:Start"
    assert at(start, "forms", "href")["value"] == at(start, "forms", "uav_browsePath")["value"] == path
    # The arguments in call order: the session, then the skill's parameters.
    assert names(at(start, "input", "properties")) == ["Session", *spec.skills["MoveAxis"].parameters]
    assert names(at(start, "output", "properties")) == ["Accepted", "ErrorID"]
    # Which command the action carries out, and of which skill.
    assert [ref["keys"][0]["value"] for ref in start["supplementalSemanticIds"]] == [f"{BASE}/skill/Start", f"{BASE}/skills/MoveAxis"]
    stop = at(actions, "MoveAxis_Stop")
    assert [ref["keys"][0]["value"] for ref in stop["supplementalSemanticIds"]] == [f"{BASE}/skill/Stop", f"{BASE}/skills/MoveAxis"]
    state = at(interfaces, "interface_opcua", "InteractionMetadata", "properties", "Module_State")
    assert at(state, "forms", "href")["value"] == "/0:Objects/1:Stoppering/1:Module/1:State"


def test_a_skill_is_its_commands(stoppering, stoppering_all):
    """Start, Stop, Abort and Reset, each with the action that calls it, an Operation named like it
    and, for a module level skill, the steps it runs. Nothing else describes a skill."""
    spec, _ = stoppering
    envs = list(stoppering_all.values())
    described_ = submodel(stoppering_all["StopperingModuleAAS"], "Skills")
    assert names(described_) == ["Interfaces", "Skills", "Errors"]
    assert described_["semanticId"]["keys"][0]["value"] == f"{BASE}/ARSO/Skills/1/0/Submodel"
    assert at(described_, "Errors", "Timeout", "ErrorCode")["value"] == "3"
    # The module's own skills are those it composes: the primitives are with their components.
    assert names(at(described_, "Skills")) == list(spec.composites) == ["Stoppering"]
    stoppering_ = at(described_, "Skills", "Stoppering")
    assert ids(stoppering_) == [f"{BASE}/skill/Composite"]                       # what kind of element it is
    assert at(stoppering_, "SemanticId")["value"] == f"{BASE}/skills/Stoppering"   # what it does
    assert names(stoppering_) == ["SemanticId", "Start", "Stop", "Abort", "Reset"]
    for command in ("Start", "Stop", "Abort", "Reset"):
        held = at(stoppering_, command)
        assert ids(held) == [f"{BASE}/skill/{command}"]                          # the same on every skill
        action = resolve(envs, at(held, "InterfaceReference")["value"])
        assert at(action, "forms", "href")["value"] == f"/0:Objects/1:Stoppering/1:Skills/1:Stoppering/1:{command}"
        operation = at(held, command)
        assert operation["modelType"] == "Operation" and variables(operation, "inputVariables") == ["Session"]
        assert variables(operation, "outputVariables") == ["Accepted", "ErrorID"]
    # Start and Stop run steps; Abort and Reset run nothing.
    assert names(at(stoppering_, "Start")) == ["InterfaceReference", "Start", "Steps"]
    assert names(at(stoppering_, "Abort")) == ["InterfaceReference", "Abort"]
    steps = children(at(stoppering_, "Start", "Steps"))
    assert [s["idShort"] for s in steps] == ["P1", "P2", "P3"]
    assert [resolve(envs, at(s, "Skill")["value"])["idShort"] for s in steps] == ["MoveAxis", "PressStopper", "Home"]
    # A step holds what is connected to its skill's variables: here a constant, as it was bound.
    assert names(steps[0]) == ["Skill", "Position"] and float(at(steps[0], "Position")["value"]) == 40.0
    assert names(steps[1]) == ["Skill"]
    # What a step is called in the program is its meaning: its state is the data point named from there.
    assert ids(steps[0]) == [f"{BASE}/skills/Stoppering/Execute/HeadDown"]
    data = submodel(stoppering_all["StopperingModuleAAS"], "OperationalData")
    assert ids(at(data, "Stoppering_Execute_HeadDown_State")) == [f"{BASE}/skills/Stoppering/Execute/HeadDown/State"]
    assert [resolve(envs, at(s, "Skill")["value"])["idShort"] for s in children(at(stoppering_, "Stop", "Steps"))] == ["Home"]


def test_a_primitive_is_in_the_aas_of_its_component(stoppering, stoppering_all):
    spec, _ = stoppering
    assert list(stoppering_all) == ["StopperingModuleAAS", "StopperingLinearAxisAAS", "StopperingPistonAAS"]
    axis = stoppering_all["StopperingLinearAxisAAS"]
    shell = axis["assetAdministrationShells"][0]
    # What kind of component it is, every axis shares; which one it is, is its own.
    assert shell["assetInformation"]["assetType"] == f"{BASE}/Resource/Component/LinearAxis"
    assert shell["assetInformation"]["globalAssetId"] == f"{BASE}/assets/StopperingLinearAxis"
    assert [s["idShort"] for s in axis["submodels"]] == ["Skills"]
    assert names(at(submodel(axis, "Skills"), "Skills")) == ["Home", "MoveAxis"]
    move, decl = at(submodel(axis, "Skills"), "Skills", "MoveAxis"), spec.skills["MoveAxis"]
    assert ids(move) == [f"{BASE}/skill/Primitive"] and "Steps" not in names(at(move, "Start"))
    # The module carries the skill out: the command's action is in the module's interface.
    action = at(move, "Start", "InterfaceReference")["value"]
    assert action["keys"][0]["value"] == submodel(stoppering_all["StopperingModuleAAS"], "AssetInterfacesDescription")["id"]
    assert resolve(list(stoppering_all.values()), action)["idShort"] == "MoveAxis_Start"
    # The parameter is a variable of the Operation: its value, unit and limits are on it, and it means
    # what the data point showing it means.
    start = at(move, "Start", "Start")
    assert variables(start, "inputVariables") == ["Session", "Position"]
    position = at(start, "Position")
    declared = {q["type"]: q["value"] for q in position["qualifiers"]}
    assert float(position["value"]) == decl.parameters["Position"].default
    assert float(declared["Maximum"]) == decl.parameters["Position"].maximum and declared["Unit"] == "mm"
    assert position["embeddedDataSpecifications"][0]["dataSpecificationContent"]["unit"] == "mm"
    data = submodel(stoppering_all["StopperingModuleAAS"], "OperationalData")
    assert ids(position) == ids(at(data, "MoveAxis_Parameter_Position")) == [f"{BASE}/skills/MoveAxis/Parameters/Position"]
    # What starts, ends and bounds it.
    assert at(move, "Contract", "Requires")["value"] == "Homed"            # an axis that knows where it is
    assert at(move, "Contract", "Ensures")["value"] == decl.ensures
    assert at(move, "Contract", "Timeout")["value"] == "8s" and "Invariant" not in names(at(move, "Contract"))
    press = at(submodel(stoppering_all["StopperingPistonAAS"], "Skills"), "Skills", "PressStopper")
    assert at(press, "Contract", "After")["value"] == "3.0"
    # The module lists its components as its parts, each found by its asset id.
    nodes = children(at(submodel(stoppering_all["StopperingModuleAAS"], "HierarchicalStructures"), "EntryNode"))
    assert [(n["idShort"], n["entityType"], n["globalAssetId"]) for n in nodes] == [
        ("LinearAxis", "SelfManagedEntity", f"{BASE}/assets/StopperingLinearAxis"),
        ("Piston", "SelfManagedEntity", f"{BASE}/assets/StopperingPiston")]


def test_a_step_is_connected_to_the_variables_of_its_command():
    """Dispensing: the volume is handed down from the command to the step that dispenses, the flow
    rate is a constant of that step, and the weight the last step reads becomes the command's result."""
    spec = load(SPECS / "filling.yaml")
    found = described(spec)
    envs, module_aas = list(found.values()), found["FillingModuleAAS"]
    assert list(found) == ["FillingModuleAAS", "FillingLinearAxisAAS", "FillingPumpAAS", "FillingScaleAAS"]
    dispensing = at(submodel(module_aas, "Skills"), "Skills", "Dispensing")
    start = at(dispensing, "Start", "Start")
    assert variables(start, "inputVariables") == ["Session", "Volume"]
    assert variables(start, "outputVariables") == ["Accepted", "ErrorID", "Weight"]
    volume, weight = at(start, "Volume"), at(start, "Weight")
    assert float(volume["value"]) == 1.0 and {q["type"]: q["value"] for q in volume["qualifiers"]}["Unit"] == "mL"
    assert weight["embeddedDataSpecifications"][0]["dataSpecificationContent"]["unit"] == "g"
    steps = children(at(dispensing, "Start", "Steps"))
    assert [resolve(envs, at(s, "Skill")["value"])["idShort"] for s in steps] == ["MoveAxis", "Dispense", "Home", "Weigh"]
    dispense = steps[1]
    assert names(dispense) == ["Skill", "FlowRate", "Volume"]
    assert at(dispense, "FlowRate")["modelType"] == "Property" and float(at(dispense, "FlowRate")["value"]) == 1.0
    assert at(dispense, "Volume")["modelType"] == "ReferenceElement"
    assert resolve(envs, at(dispense, "Volume")["value"]) is volume           # a variable of the Operation
    assert [k["type"] for k in at(dispense, "Volume")["value"]["keys"]][-2:] == ["Operation", "Property"]
    assert resolve(envs, at(steps[3], "Weight")["value"]) is weight
    # The step's skill takes what it is handed under the same name.
    pump = at(submodel(found["FillingPumpAAS"], "Skills"), "Skills", "Dispense")
    assert variables(at(pump, "Start", "Start"), "inputVariables") == ["Session", "Volume", "FlowRate"]
    assert at(pump, "Contract", "After")["value"] == "Volume / FlowRate"
    # Nothing points from the skill to the capability: the parameter means what the capability's
    # property means, which is how a product's value finds it.
    assert ids(volume) == [f"{BASE}/skills/Dispensing/Parameters/Volume", f"{BASE}/semantics/FillVolume"]
    capability = at(submodel(module_aas, "CapabilityDescription"), "OfferedCapabilities", "Filling")
    assert f"{BASE}/semantics/FillVolume" in ids(at(capability, "PropertySet", "FillVolume", "Value"))
    assert not [r for path, r in references(submodel(module_aas, "Skills"), "Skills") if "CapabilityDescription" in r["keys"][0]["value"]]
    # A result carries the unit of the equipment input behind it, through the step for a composite.
    properties = at(submodel(module_aas, "AssetInterfacesDescription"), "interface_opcua", "InteractionMetadata", "properties")
    for key in ("Weigh_Result_Weight", "Dispensing_Result_Weight"):
        assert at(properties, key, "unit")["value"] == spec.equipment["Scale"].inputs["Weight"].unit == "g"
        assert at(properties, key, "type")["value"] == "number"
    assert "Parameters" not in [s["idShort"] for s in module_aas["submodels"]]


def test_a_skill_the_module_does_not_offer_has_a_start_nothing_calls():
    data = yaml.safe_load((SPECS / "filling.yaml").read_text(encoding="utf-8"))
    data["skills"]["Dispense"]["offered"] = False
    found = described(ModuleSpec.model_validate(data))
    pump = at(submodel(found["FillingPumpAAS"], "Skills"), "Skills", "Dispense")
    assert names(pump) == ["SemanticId", "Start", "Contract"] and names(at(pump, "Start")) == ["Start"]
    assert variables(at(pump, "Start", "Start"), "inputVariables") == ["Session", "Volume", "FlowRate"]
    actions = at(submodel(found["FillingModuleAAS"], "AssetInterfacesDescription"), "interface_opcua", "InteractionMetadata", "actions")
    assert not [a for a in names(actions) if a.startswith("Dispense_")]
    # It still runs as a step, and the block that is that step is known.
    step = children(at(submodel(found["FillingModuleAAS"], "Skills"), "Skills", "Dispensing", "Start", "Steps"))[1]
    assert resolve(list(found.values()), at(step, "Skill")["value"]) is pump
    instances = at(submodel(found["FillingModuleAAS"], "ControlConfiguration"), "Instances")
    assert "Dispense" not in names(instances) and "Dispensing_Execute_Dispense" in names(instances)


def test_steps_publish_like_skills_where_the_program_puts_them():
    """A step's State, ErrorID, parameters and results are in the interface, at the path its
    instance publishes them in the generated program; which instance a step is, is in the Control
    Configuration."""
    spec = load(SPECS / "filling.yaml")
    env = model.build(profiles.describe(spec, "pi"))
    values = expected_values(spec, expected(spec, "pi"))
    dispensing = at(submodel(env, "Skills"), "Skills", "Dispensing")
    steps = [*children(at(dispensing, "Start", "Steps")), *children(at(dispensing, "Stop", "Steps"))]
    assert len(steps) == len(spec.composites["Dispensing"].execute) + len(spec.composites["Dispensing"].stop)
    instances = {i["idShort"]: i for i in children(at(submodel(env, "ControlConfiguration"), "Instances"))}
    by_step = {id(resolve(env, at(i, "Skill")["value"])): i for i in instances.values()}
    properties = at(submodel(env, "AssetInterfacesDescription"), "interface_opcua", "InteractionMetadata", "properties")
    for step in steps:
        instance = at(by_step[id(step)], "InstancePath")["value"]
        ua_path = values[instance + ".UaPath"].strip('"')
        state = at(properties, instance.replace(".Stop.", ".Stopping.").replace(".", "_") + "_State")
        assert at(state, "forms", "href")["value"] == profiles.browse_path(spec, f"{ua_path}/State")
    assert at(instances["Dispensing_Execute_NeedleDown"], "FBType")["value"] == "filling::SK_MoveAxis"
    # A module level skill has no type of its own: it is its Control block. A primitive is its instance.
    control = instances["Dispensing_Control"]
    assert at(control, "FBType")["value"] == "modlib::SKILL_Core" and resolve(env, at(control, "Skill")["value"]) is dispensing
    assert at(instances["MoveAxis"], "Skill")["value"]["keys"][0]["value"] == f"{BASE}/aas/FillingLinearAxisAAS/submodels/Skills"
    assert "TypeHash" not in names(control)                       # only a module that was read has it
    assert at(properties, "Dispensing_Execute_Dispense_Parameter_FlowRate", "unit")["value"] == "mL/s"
    assert at(properties, "Dispensing_Execute_Weigh_Result_Weight", "unit")["value"] == "g"
    assert at(properties, "Dispensing_Stopping_Home_ErrorID", "forms", "href")["value"].endswith(
        "/1:Dispensing/1:Stopping/1:Home/1:ErrorID")
    # Their State and ErrorID are data points, fed like those of the skills.
    data = names(submodel(env, "OperationalData"))
    assert {"Dispensing_Execute_Weigh_State", "Dispensing_Stopping_Home_ErrorID"} <= set(data)


def test_the_modules_own_commands_are_a_submodel_in_the_same_shape(stoppering, stoppering_all):
    spec, _ = stoppering
    envs, env = list(stoppering_all.values()), stoppering_all["StopperingModuleAAS"]
    machine = submodel(env, "Module")
    assert machine["semanticId"]["keys"][0]["value"] == f"{BASE}/ARSO/Module/1/0/Submodel"
    assert names(machine) == ["Occupy", "Release", "Reset", "Start", "Stop", "Abort", "Clear"]
    root = "/0:Objects/1:Stoppering"
    for command in names(machine):
        held = at(machine, command)
        node = f"Occupation/1:{command}" if command in ("Occupy", "Release") else f"Module/1:{command}"
        assert at(resolve(envs, at(held, "InterfaceReference")["value"]), "forms", "href")["value"] == f"{root}/1:{node}"
        assert variables(at(held, command), "outputVariables") == ["Accepted", "ErrorID"]
    # What the module runs itself while resetting and stopping are the steps of Reset and Stop.
    ran = {c: [resolve(envs, at(s, "Skill")["value"])["idShort"] for s in children(at(machine, c, "Steps"))] for c in ("Reset", "Stop")}
    assert ran == {"Reset": [s.skill for s in spec.procedures["Resetting"]], "Stop": [s.skill for s in spec.procedures["Stopping"]]}
    assert ran == {"Reset": ["RetractPiston", "Home"], "Stop": ["Home"]}
    assert "Steps" not in names(at(machine, "Start"))
    # Its state and its occupation are data points, as are the states of those steps.
    data = submodel(env, "OperationalData")
    assert {"PackMLState", "OccupationState", "Procedure_Resetting_RetractPiston_State", "Procedure_Stopping_Home_ErrorID"} <= set(names(data))
    values = expected_values(spec, expected(spec, "pi"))
    assert values["Resetting.RetractPiston.UaPath"].strip('"') == "/Procedures/Resetting/RetractPiston"
    instance = at(submodel(env, "ControlConfiguration"), "Instances", "Resetting_RetractPiston")
    assert resolve(env, at(instance, "Skill")["value"]) is children(at(machine, "Reset", "Steps"))[0]


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


def test_the_aimc_maps_every_action_and_property_onto_an_element(stoppering_all):
    envs, env = list(stoppering_all.values()), stoppering_all["StopperingModuleAAS"]
    configs = children(at(submodel(env, "AssetInterfacesMappingConfiguration"), "MappingConfigurations"))
    fed: dict[str, list[dict]] = {}          # interface property -> the elements it feeds
    invoked: dict[str, list[dict]] = {}      # interface action -> the Operations invoking it
    for config in configs:
        sources = [resolve(envs, at(s, "Source")["value"]) for s in children(at(config, "Sources"))]
        sinks = [resolve(envs, at(s, "Sink")["value"]) for s in children(at(config, "Sinks"))]
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
    # A parameter, result or state feeds its data point; an action is invoked by the Operation of its
    # command, in the module's AAS or in a component's.
    assert fed["MoveAxis_Parameter_Position"][0]["idShort"] == "MoveAxis_Parameter_Position"
    assert fed["Stoppering_Execute_HeadDown_Parameter_Position"][0]["idShort"] == "Stoppering_Execute_HeadDown_Parameter_Position"
    axis = at(submodel(stoppering_all["StopperingLinearAxisAAS"], "Skills"), "Skills", "MoveAxis")
    assert invoked["MoveAxis_Stop"][0] is at(axis, "Stop", "Stop")
    assert invoked["Module_Reset"][0] is at(submodel(env, "Module"), "Reset", "Reset")
    assert invoked["Occupation_Occupy"][0] is at(submodel(env, "Module"), "Occupy", "Occupy")
    assert invoked["Stoppering_Start"][0] is at(submodel(env, "Skills"), "Skills", "Stoppering", "Start", "Start")


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
    assert at(data, "MoveAxis_Parameter_Position")["semanticId"]["keys"][0]["value"] == \
        f"{BASE}/skills/MoveAxis/Parameters/Position"
    assert "Parameters" not in [s["idShort"] for s in stoppering_aas["submodels"]]


def test_every_reference_resolves(stoppering_all):
    envs = list(stoppering_all.values())
    found = [(path, ref) for env in envs for sm in env["submodels"] for path, ref in references(sm, sm["idShort"])]
    assert len(found) > 50 and [path for path, ref in found if resolve(envs, ref) is None] == []


def test_a_module_that_was_read_shows_what_runs_there():
    spec = load(SPECS / "stoppering.yaml")
    app = expected(spec, "pi")
    values = expected_values(spec, app)
    snap = Snapshot("192.168.0.50", 61499, fbs=dict(app.fbs), hashes={t: f"v2:{t}" for t in set(app.fbs.values())},
                    connections=set(app.event_connections + app.data_connections),
                    values={**values, "MoveAxis.Position": "5.5"}, read_at="2026-10-02T10:00:00+00:00")
    drift = compare(app, values, snap, set())
    found = described(spec, "pi", snap, drift, "cell/modules/stoppering.yaml", "opc.tcp://192.168.0.50:4840")
    env = found["StopperingModuleAAS"]
    config = submodel(env, "ControlConfiguration")
    assert at(config, "SyncState")["value"] == "Drift" and len(names(at(config, "Differences"))) == 1
    assert at(config, "Rules")["value"] == f"{BASE}/rules/module/1"          # docs/module-rules.md
    assert at(config, "Runtime", "ManagementEndpoint")["value"] == "192.168.0.50:61499"
    assert len(names(at(config, "Types"))) == len(set(app.fbs.values()))
    # A parameter shows the value the module runs with; a block the type and hash it has there.
    axis = submodel(found["StopperingLinearAxisAAS"], "Skills")
    assert float(at(axis, "Skills", "MoveAxis", "Start", "Start", "Position")["value"]) == 5.5
    instance = at(config, "Instances", "MoveAxis")
    assert at(instance, "FBType")["value"] == app.fbs["MoveAxis"]
    assert at(instance, "TypeHash")["value"] == f"v2:{app.fbs['MoveAxis']}"
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
def test_a_module_and_its_components_break_no_restriction_of_arso(stoppering_all):
    blueprint = Blueprint(ARSO)
    for name, env in stoppering_all.items():
        report = check(env, blueprint)
        assert report.errors == [], (name, report.lines()[:20])
    # A component is asked for less than a module: its skills.
    assert check(stoppering_all["StopperingPistonAAS"], blueprint).classes["StopperingPistonAAS"] == ["ComponentAAS"]
    assert check(stoppering_all["StopperingModuleAAS"], blueprint).classes["StopperingModuleAAS"] == ["ResourceAAS"]
