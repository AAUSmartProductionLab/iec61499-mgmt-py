"""modreg: a product with its plan on the lab's shared AAS model, built like a module's AAS (a
profile is the pydantic dump, the AAS is built from it), and the plans the process planner saves
read into the same classes.

Needs the ``registration`` extra (aas-model); skipped without it.
"""
import base64
import io
import json

import pytest

pytest.importorskip("aas_model")

from aas_pydantic import Capability, Key, ModelReference, Property, Qualifier       # noqa: E402
from aas_pydantic.convert_aas_instance import convert_submodel_to_model_instance   # noqa: E402
from aas_pydantic.convert_pydantic_model import convert_model_to_submodel          # noqa: E402
from aas_pydantic.submodel_templates import capability_description as cd            # noqa: E402
from basyx.aas import model as basyx                                                # noqa: E402
from basyx.aas.adapter.json import AASToJsonEncoder, read_aas_json_file             # noqa: E402

from modreg import model                                                            # noqa: E402
from modreg.generated import process_parameters as pp, production_sequence as ps    # noqa: E402
from modreg.product import BillOfMaterial, Part, Product, ProductTypeAAS, plan_id   # noqa: E402

BASE = "https://smartproductionlab.aau.dk"
SMC = "SubmodelElementCollection"
REQUIRED = "https://admin-shell.io/idta/CapabilityDescription/CapabilityRoleQualifier/Required/1/0"


def ref(*keys: tuple[str, str]) -> ModelReference:
    return ModelReference(key=tuple(Key(type_=t, value=v) for t, v in keys))


def own(submodel: str, *keys: tuple[str, str]) -> ModelReference:
    return ref(("Submodel", "{aas_id}/submodels/" + submodel), *keys)


def children(element: dict) -> list[dict]:
    held = element.get("submodelElements") or element.get("statements") or element.get("value")
    return [c for c in held if isinstance(c, dict) and "modelType" in c] if isinstance(held, list) else []


def at(element: dict, *path: str) -> dict:
    for step in path:
        element = next(c for c in children(element) if c.get("idShort") == step)
    return element


def submodel(env: dict, id_short: str) -> dict:
    return next(s for s in env["submodels"] if s["idShort"] == id_short)


def paths(element: dict, path: str = "") -> set[str]:
    return {q for c in children(element) for q in {f"{path}/{c['idShort']}", *paths(c, f"{path}/{c['idShort']}")}}


def bottle() -> ProductTypeAAS:
    """A product with one part, one process and one step, as small as the type allows."""
    volume = Property(value="5.0", value_type="xs:double", semantic_id=f"{BASE}/semantics/FillVolume",
                      qualifiers=[Qualifier(type_="Unit", value="mL", kind="ConceptQualifier")])
    process = pp.Process(
        ProcessId=pp.ProcessId(value="Filling"), ProcessName=pp.ProcessName(value="Filling"),
        ProcessDescription=pp.ProcessDescription(value={"en": "Fill the bottle"}), PlannedProcessTime=pp.PlannedProcessTime(value="PT8S"),
        ProductParameters=pp.ProductParameters(Parameter={"FillVolume": volume}),
        ProcessParameters=pp.ProcessParameters_process_parameters(), ResourceParameters=pp.ResourceParameters(),
        ProcessBoM=pp.ProcessBoM(MaterialUse={"Bottle": pp.MaterialUse(
            MaterialReference=pp.MaterialReference(value=own("HierarchicalStructures", ("Entity", "EntryNode"), ("Entity", "Bottle"))),
            Role=pp.Role(value="workpiece"), Quantity=pp.Quantity(value="1.0"), Unit=pp.Unit(value="piece"))}),
        RequiredCapability=pp.RequiredCapability(value=own("CapabilityDescription", (SMC, "RequiredCapabilities"), (SMC, "Filling"),
                                                             ("Capability", "Capability"))))
    required = cd.CapabilityContainer(Capability=Capability(
        semantic_id="https://admin-shell.io/idta/CapabilityDescription/Capability/1/0", supplemental_semantic_ids=[f"{BASE}/semantics/Filling"],
        qualifiers=[Qualifier(type_="CapabilityRoleQualifier/Required", value="true", semantic_id=REQUIRED, kind="ConceptQualifier")]))
    resource = f"{BASE}/aas/FillingModuleAAS"
    step = ps.Step(
        NodeId=ps.NodeId(value="Filling"), Kind=ps.Kind(value="step"), Name=ps.Name(value="Filling"), Order=ps.Order(value="0"),
        ProcessOwner=ps.ProcessOwner(value=ref(("AssetAdministrationShell", "{aas_id}"))),
        ProcessReference=ps.ProcessReference(value=own("ProcessParameters", (SMC, "Processes"), (SMC, "Filling"))),
        Resource=ps.Resource(value=ref(("AssetAdministrationShell", resource))), SkillId=ps.SkillId(value="Dispensing"),
        Skill=ps.Skill(value=ref(("Submodel", f"{resource}/submodels/Skills"), (SMC, "Skills"), (SMC, "Dispensing"))),
        ExecutionMode=ps.ExecutionMode(value="station"),
        Bindings=ps.Bindings(Binding={"Binding_0000": ps.Binding(
            Name=ps.Name(value="Volume"), Value=ps.Value(value=""),
            SourceAas=ps.SourceAas(value=ref(("AssetAdministrationShell", "{aas_id}"))),
            SourceElement=ps.SourceElement(value=own("ProcessParameters", (SMC, "Processes"), (SMC, "Filling"),
                                                     (SMC, "ProductParameters"), ("Property", "FillVolume"))))}))
    return ProductTypeAAS(
        id_short="BottleAAS", id=f"{BASE}/aas/BottleAAS", display_name={"en": "Bottle"},
        hierarchical_structures=BillOfMaterial(
            id_short="HierarchicalStructures", ArcheType=ProductTypeAAS.model_fields["hierarchical_structures"].default.ArcheType,
            EntryNode=Product(global_asset_id=f"{BASE}/assets/Bottle", Node={"Bottle": Part(
                Quantity=Property(value="1.0", value_type="xs:double"), QuantityUnit=Property(value="piece"))})),
        process_parameters=pp.ProcessParameters(id_short="ProcessParameters", Processes=pp.Processes(Process={"Filling": process})),
        capability_description=cd.CapabilityDescription(id_short="CapabilityDescription", CapabilitySet={
            "RequiredCapabilities": cd.CapabilitySet(CapabilityContainer={"Filling": required})}),
        production_sequence=ps.ProductionSequence(
            id_short="ProductionSequence", PlanSchema=ps.PlanSchema(value="production-sequence/2.0"), Revision=ps.Revision(value="1"),
            SequenceId=ps.SequenceId(value="product"), Name=ps.Name(value="Bottle"), Role=ps.Role(value="Primary"),
            Subject=ps.Subject(value=ref(("AssetAdministrationShell", "{aas_id}"))), Steps=ps.Steps(Step={"Step_0000": step})))


@pytest.fixture(scope="module")
def profile() -> dict:
    return model.profile(bottle(), global_asset_id=f"{BASE}/assets/Bottle")


def test_a_products_profile_is_its_dump_without_what_the_type_says(profile):
    assert profile["aas_type"] == "ProductTypeAAS"
    # The nameplate is the type's; what the product says is its own.
    assert "nameplate" not in profile
    filling = profile["process_parameters"]["Processes"]["Process"]["Filling"]
    assert filling["ProductParameters"]["Parameter"]["FillVolume"]["value"] == "5.0"
    assert profile["production_sequence"]["Steps"]["Step"]["Step_0000"]["SkillId"] == {"value": "Dispensing"}
    assert json.loads(json.dumps(profile)) == profile                # plain JSON
    assert model.validated(profile).model_dump(mode="json") == bottle().model_dump(mode="json")


def test_the_aas_of_a_product_is_what_the_planner_reads(profile):
    env = model.build(profile)
    read_aas_json_file(io.StringIO(json.dumps(env)), failsafe=False)             # valid as BaSyx reads it
    shell, = env["assetAdministrationShells"]
    aas_id = f"{BASE}/aas/BottleAAS"
    # A product AAS describes a kind of product.
    assert shell["assetInformation"]["assetKind"] == "Type" and shell["assetInformation"]["globalAssetId"] == f"{BASE}/assets/Bottle"
    assert [s["idShort"] for s in env["submodels"]] == [
        "Nameplate", "HierarchicalStructures", "ProcessParameters", "CapabilityDescription", "ProductionSequence"]
    semantic = {s["idShort"]: s["semanticId"]["keys"][0]["value"] for s in env["submodels"]}
    assert semantic["ProcessParameters"] == "https://admin-shell-io/idta/SubmodelTemplate/ProcessParameters/1/0"     # IDTA's spelling
    assert semantic["ProductionSequence"] == f"{BASE}/SubmodelTemplate/ProductionSequence/2/0"

    # The planner finds the plan of a product by its identifier: the product's, encoded.
    plan = submodel(env, "ProductionSequence")
    assert plan["id"] == plan_id(aas_id)
    encoded = plan["id"].rsplit("/", 1)[1]
    assert base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode() == aas_id
    step = at(plan, "Steps", "Step_0000")
    assert step["semanticId"]["keys"][0]["value"] == f"{BASE}/ProductionSequence/Step/1/0"
    assert at(step, "Order")["valueType"] == "xs:nonNegativeInteger"
    # References to the product itself are written with its identifier.
    assert at(plan, "Subject")["value"]["keys"] == [{"type": "AssetAdministrationShell", "value": aas_id}]
    source = at(step, "Bindings", "Binding_0000", "SourceElement")["value"]["keys"]
    assert [k["value"] for k in source] == [f"{aas_id}/submodels/ProcessParameters", "Processes", "Filling", "ProductParameters", "FillVolume"]

    # A process with the product's value (and its unit the standard way), its material and what it requires.
    process = at(submodel(env, "ProcessParameters"), "Processes", "Filling")
    volume = at(process, "ProductParameters", "FillVolume")
    assert (volume["value"], volume["valueType"]) == ("5.0", "xs:double")
    assert volume["embeddedDataSpecifications"][0]["dataSpecificationContent"]["unit"] == "mL"
    assert at(process, "PlannedProcessTime")["value"] == "PT8S"
    assert at(process, "ProcessBoM", "Bottle", "Role")["value"] == "workpiece"
    capability = at(submodel(env, "CapabilityDescription"), "RequiredCapabilities", "Filling", "Capability")
    assert at(process, "RequiredCapability")["value"]["keys"][-1] == {"type": "Capability", "value": "Capability"}
    assert [(q["type"], q["value"], q["valueType"]) for q in capability["qualifiers"]] == [
        ("CapabilityRoleQualifier/Required", "true", "xs:boolean")]
    part = at(submodel(env, "HierarchicalStructures"), "EntryNode", "Bottle")
    assert part["entityType"] == "CoManagedEntity" and at(part, "QuantityUnit")["value"] == "piece"


@pytest.mark.parametrize("change, told", [
    (lambda p: p["production_sequence"]["Steps"]["Step"]["Step_0000"].pop("NodeId"), "NodeId"),
    (lambda p: p["process_parameters"]["Processes"]["Process"]["Filling"].pop("PlannedProcessTime"), "PlannedProcessTime"),
    (lambda p: p["production_sequence"]["Steps"]["Step"]["Step_0000"].update(Station={"value": "Filling"}), "Station"),
    (lambda p: p.update(skills={}), "skills"),
])
def test_what_is_not_a_product_is_refused(profile, change, told):
    changed = json.loads(json.dumps(profile))
    change(changed)
    with pytest.raises(model.ProfileError, match=told):
        model.build(changed)


# A plan as the process planner saves it ---------------------------------------------------------

def seq(name: str) -> dict:
    return {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": f"{BASE}/ProductionSequence/{name}/1/0"}]}


def p(id_short: str, value: str, value_type: str = "xs:string") -> dict:
    return {"modelType": "Property", "idShort": id_short, "semanticId": seq(id_short), "valueType": value_type, "value": value}


def r(id_short: str, *keys: tuple[str, str], concept: str | None = None) -> dict:
    return {"modelType": "ReferenceElement", "idShort": id_short, "semanticId": seq(concept or id_short),
            "value": {"type": "ModelReference", "keys": [{"type": t, "value": v} for t, v in keys]}}


def c(id_short: str, held: list[dict], concept: str | None = None) -> dict:
    return {"modelType": SMC, "idShort": id_short, "semanticId": seq(concept or id_short), "value": held}


def node(order: int, kind: str, name: str, *more: dict) -> dict:
    return c(f"Step_{order:04d}", [p("NodeId", name), p("Kind", kind), p("Name", name), p("Order", str(order), "xs:nonNegativeInteger"), *more], "Step")


def saved_plan() -> dict:
    """A Production Sequence 2.0 with a node of every kind, in the shape the planner saves."""
    product, station = ("AssetAdministrationShell", f"{BASE}/demo/aas/vial"), ("AssetAdministrationShell", f"{BASE}/demo/aas/filling-station")
    parameters, called = ("Submodel", f"{BASE}/demo/sm/vial/parameters"), ("Submodel", f"{BASE}/sm/process-plan/abc/subprocess/1")
    filling = node(
        0, "step", "Filling", r("ProcessOwner", product), r("ProcessReference", parameters, (SMC, "Processes"), (SMC, "Process_0")),
        c("RequiredCapabilities", [r("RequiredCapability_0000", ("Submodel", f"{BASE}/demo/sm/vial/capabilities"), (SMC, "Capabilities"),
                                     (SMC, "Filling_1"), ("Capability", "Capability"), concept="RequiredCapability")]),
        r("Resource", station), p("SkillId", "Filling_vial"), r("Skill", ("Submodel", f"{BASE}/demo/sm/filling-station/skills"), (SMC, "Filling_vial")),
        p("ExecutionMode", "station"),
        c("Bindings", [c("Binding_0000", [p("Name", "ContainerType"), p("Value", ""), r("SourceAas", product),
                                          r("SourceElement", parameters, (SMC, "Processes"), (SMC, "Process_0"), (SMC, "ProductParameters"),
                                            ("Property", "ContainerType"))], "Binding"),
                       c("Binding_0001", [p("Name", "FillVolume"), p("Value", "0.5")], "Binding")]))
    inspection = node(0, "step", "Inspection", r("ProcessOwner", product), p("SkillId", "Inspection_vial"), p("ExecutionMode", "manual"))
    sampled = node(1, "conditional", "Every fifth", c("Condition", [
        p("ConditionType", "everyNthProduct"), p("EveryNProducts", "5", "xs:positiveInteger"), p("CounterScope", "productionRun")]),
        c("Steps", [inspection]))
    part = node(0, "call", "Build the drive", r("SequenceReference", called), p("OccurrenceId", "drive-1"), c("Component", [
        p("GlobalAssetId", f"{BASE}/demo/asset/drive"), r("SourceAas", product), r("SourceElement", ("Submodel", f"{BASE}/demo/sm/vial/bom"), ("Entity", "Product"))]))
    both = node(2, "parallel", "Assemblies", c("Branches", [c("Branch_0000", [
        p("BranchId", "drive-branch"), p("Name", "Drive assembly"), p("Order", "0", "xs:nonNegativeInteger"), c("Steps", [part])], "Branch")]))
    return {"modelType": "Submodel", "kind": "Instance", "idShort": "ProductionSequence", "id": f"{BASE}/sm/process-plan/abc",
            "semanticId": {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": f"{BASE}/SubmodelTemplate/ProductionSequence/2/0"}]},
            "submodelElements": [
                p("PlanSchema", "production-sequence/2.0"), p("Revision", "3", "xs:nonNegativeInteger"), p("SequenceId", "product"),
                p("Name", "Vial, inspected every fifth"), p("Role", "Primary"), r("Subject", product),
                c("Subprocesses", [r("Subprocess_0", called, concept="SequenceReference")]),
                c("Steps", [filling, sampled, both, node(3, "call", "Pack", r("SequenceReference", called))])]}


def test_a_plan_the_planner_saved_reads_into_the_classes():
    saved = saved_plan()
    store = read_aas_json_file(io.StringIO(json.dumps({"assetAdministrationShells": [], "submodels": [saved], "conceptDescriptions": []})),
                               failsafe=False)
    plan = convert_submodel_to_model_instance(next(o for o in store if isinstance(o, basyx.Submodel)), ps.ProductionSequence)
    steps = plan.Steps.Step
    assert [(s.Kind.value, s.Name.value) for s in steps.values()] == [
        ("step", "Filling"), ("conditional", "Every fifth"), ("parallel", "Assemblies"), ("call", "Pack")]
    filling = steps["Step_0000"]
    assert filling.Skill.value.key[-1].value == "Filling_vial" and filling.Resource.value.key[0].value.endswith("/filling-station")
    assert {b.Name.value: b.Value.value for b in filling.Bindings.Binding.values()} == {"ContainerType": "", "FillVolume": "0.5"}
    assert filling.Bindings.Binding["Binding_0000"].SourceElement.value.key[-1].value == "ContainerType"
    assert list(filling.RequiredCapabilities.RequiredCapability) == ["RequiredCapability_0000"]
    # A node holds nodes: the steps a condition guards, and the steps of a branch.
    sampled = steps["Step_0001"]
    assert sampled.Condition.EveryNProducts.value == "5"
    assert sampled.Steps.Step["Step_0000"].ExecutionMode.value == "manual"
    branch = steps["Step_0002"].Branches.Branch["Branch_0000"]
    assert branch.Steps.Step["Step_0000"].Component.GlobalAssetId.value.endswith("/drive")
    assert steps["Step_0003"].SequenceReference.value.key[0].value == plan.Subprocesses.Subprocess["Subprocess_0"].value.key[0].value

    # Written back it holds the same elements.
    written = json.loads(json.dumps(convert_model_to_submodel(plan), cls=AASToJsonEncoder))
    assert paths(written) == paths(saved)
    assert written["id"] == saved["id"] and written["semanticId"] == saved["semanticId"]
