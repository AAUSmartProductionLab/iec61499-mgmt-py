"""The cartridge of 3 mL: a product type of the example line, its AAS (ISA-88's general recipe).

What it is: a 3 mL glass cartridge (11.6 mm across where a gripper holds it), as a pen injector takes
it, filled with 3 mL of a demo liquid and closed with a 10.3 mm plunger stopper. What it needs:
filling, stoppering and inspection, in that order. A cartridge is not capped here.

The recipe names no equipment: which module carries out each step, with which skill and what each
input of the skill is handed, is the process AAS's (``processes/cartridge_3ml_on_filling_line.py``).
The values follow the process sequence planner's pharma example (basyx-aas-web-ui,
``demo/pharma.ts``, "Cartridge 3 mL").

Every element is written out here, as the classes of aas-model make it (``aas_model.product_template``
for the AAS and its bill of material, ``aas_model.submodel_templates.product`` for Process Parameters
and Production Sequence, IDTA 02020 for the required capabilities).
"""
from __future__ import annotations

from aas_model.constants import BASE_URL
from aas_model.product_template import (
    BillOfMaterial, ProductPart, PartQuantity, PartQuantityUnit, Product, ProductEntry, plan_id,
)
from aas_model.submodel_templates.product import process_parameters as pp, production_sequence as ps
from aas_pydantic import Capability, Key, ModelReference, Property, Qualifier
from aas_pydantic.submodel_templates import capability_description as cd
from aas_pydantic.submodel_templates.hierarchical_structures import ArcheType
from aas_pydantic.submodel_templates.nameplate import (
    AddressInformation, CityTown, CountryOfOrigin, ManufacturerName, ManufacturerProductDesignation, Nameplate,
    NationalCode, OrderCodeOfManufacturer, Street, URIOfTheProduct, YearOfConstruction, Zipcode,
)

AAS_ID = f"{BASE_URL}/aas/Cartridge3mLAAS"
ASSET_ID = f"{BASE_URL}/assets/Cartridge3mL"
PROCESSES = f"{AAS_ID}/submodels/ProcessParameters"
BILL = f"{AAS_ID}/submodels/HierarchicalStructures"
CAPABILITIES = f"{AAS_ID}/submodels/CapabilityDescription"
# What a value means: the lab's vocabulary (ontology/Vocabulary).
MEANS = f"{BASE_URL}/semantics"
CAPABILITY = "https://admin-shell.io/idta/CapabilityDescription/Capability/1/0"
REQUIRED = "https://admin-shell.io/idta/CapabilityDescription/CapabilityRoleQualifier/Required/1/0"


def reference(*keys: tuple[str, str]) -> ModelReference:
    """A model reference along ``keys``: (type, value) pairs."""
    return ModelReference(key=tuple(Key(type_=kind, value=value) for kind, value in keys))


def unit(symbol: str) -> list[Qualifier]:
    """The qualifier that states a value's unit."""
    return [Qualifier(type_="Unit", value=symbol, kind="ConceptQualifier")]


def cartridge_3ml() -> Product:
    return Product(
        id_short="Cartridge3mLAAS", id=AAS_ID,
        description="A cartridge of 3 mL, filled, stoppered and inspected",
        display_name={"en": "Cartridge 3 mL"},

        # ── Nameplate (IDTA 02006): what the product is ─────────────────────────────────────────
        nameplate=Nameplate(
            id_short="Nameplate",
            URIOfTheProduct=URIOfTheProduct(value=ASSET_ID),
            ManufacturerName=ManufacturerName(value={"en": "AAU Smart Production Lab"}),
            ManufacturerProductDesignation=ManufacturerProductDesignation(value={"en": "Filled cartridge 3 mL"}),
            AddressInformation=AddressInformation(
                Street=Street(value={"en": "Fibigerstræde 14"}), Zipcode=Zipcode(value={"en": "9220"}),
                CityTown=CityTown(value={"en": "Aalborg Øst"}), NationalCode=NationalCode(value={"en": "DK"})),
            OrderCodeOfManufacturer=OrderCodeOfManufacturer(value="CARTRIDGE-3ML"),
            YearOfConstruction=YearOfConstruction(value="2026"),
            CountryOfOrigin=CountryOfOrigin(value="DK"),
        ),

        # ── Hierarchical Structures (IDTA 02011): the bill of material ──────────────────────────
        # One cartridge, 3 mL of liquid, one plunger stopper. A part states how much of it the
        # product holds and in which unit (IDTA counts parts only).
        hierarchical_structures=BillOfMaterial(
            id_short="HierarchicalStructures", ArcheType=ArcheType(value="OneDown"),
            EntryNode=ProductEntry(
                display_name={"en": "Cartridge 3 mL"}, global_asset_id=ASSET_ID,
                Node={
                    "Cartridge": ProductPart(id_short="Cartridge", display_name={"en": "Glass cartridge 3 mL"},
                                             Quantity=PartQuantity(value="1.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                    "Liquid": ProductPart(id_short="Liquid", display_name={"en": "Demo liquid"},
                                          Quantity=PartQuantity(value="3.0"), QuantityUnit=PartQuantityUnit(value="mL")),
                    "Stopper": ProductPart(id_short="Stopper", display_name={"en": "Plunger stopper 10.3 mm"},
                                           Quantity=PartQuantity(value="1.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                },
            ),
        ),

        # ── Process Parameters (IDTA 02031-1 and the lab's extension) ───────────────────────────
        # Each process: the product's values for it, the materials it uses, the capability it
        # requires. A binding in the process AAS hands a value from here to a skill's input.
        process_parameters=pp.ProcessParameters(
            id_short="ProcessParameters",
            Processes=pp.Processes(Process={
                "Filling": pp.Process(
                    id_short="Filling",
                    ProcessId=pp.ProcessId(value="Filling"),
                    ProcessName=pp.ProcessName(value="Filling"),
                    ProcessDescription=pp.ProcessDescription(value={"en": "Fill 3 mL of liquid into the open cartridge"}),
                    PlannedProcessTime=pp.PlannedProcessTime(value="PT10S"),
                    ProductParameters=pp.ProductParameters(Parameter={
                        "ContainerType": pp.Parameter(id_short="ContainerType", semantic_id=f"{MEANS}/ContainerType",
                                                      value="cartridge"),
                        "GraspDiameter": pp.Parameter(id_short="GraspDiameter", semantic_id=f"{MEANS}/GraspDiameter",
                                                      value="11.6", value_type="xs:double", qualifiers=unit("mm")),
                        "FillVolume": pp.Parameter(id_short="FillVolume", semantic_id=f"{MEANS}/FillVolume",
                                                   value="3.0", value_type="xs:double", qualifiers=unit("mL")),
                    }),
                    ProcessParameters=pp.ProcessParameterGroup(),
                    ResourceParameters=pp.ResourceParameters(),
                    ProcessBoM=pp.ProcessBoM(MaterialUse={
                        # The cartridge is what is worked on; the liquid goes into it, as much as FillVolume.
                        "Cartridge": pp.MaterialUse(
                            id_short="Cartridge",
                            MaterialReference=pp.MaterialReference(value=reference(
                                ("Submodel", BILL), ("Entity", "EntryNode"), ("Entity", "Cartridge"))),
                            Role=pp.Role(value="workpiece"), Quantity=pp.Quantity(value="1.0"), Unit=pp.Unit(value="piece")),
                        "Liquid": pp.MaterialUse(
                            id_short="Liquid",
                            MaterialReference=pp.MaterialReference(value=reference(
                                ("Submodel", BILL), ("Entity", "EntryNode"), ("Entity", "Liquid"))),
                            Role=pp.Role(value="incorporated"),
                            QuantityParameterReference=pp.QuantityParameterReference(value=reference(
                                ("Submodel", PROCESSES), ("SubmodelElementCollection", "Processes"),
                                ("SubmodelElementCollection", "Filling"),
                                ("SubmodelElementCollection", "ProductParameters"), ("Property", "FillVolume")))),
                    }),
                    RequiredCapability=pp.RequiredCapability(value=reference(
                        ("Submodel", CAPABILITIES), ("SubmodelElementCollection", "RequiredCapabilities"),
                        ("SubmodelElementCollection", "Filling"), ("Capability", "Capability"))),
                ),
                "Stoppering": pp.Process(
                    id_short="Stoppering",
                    ProcessId=pp.ProcessId(value="Stoppering"),
                    ProcessName=pp.ProcessName(value="Stoppering"),
                    ProcessDescription=pp.ProcessDescription(value={"en": "Place the plunger stopper in the filled cartridge and press it in"}),
                    PlannedProcessTime=pp.PlannedProcessTime(value="PT5S"),
                    ProductParameters=pp.ProductParameters(Parameter={
                        "ContainerType": pp.Parameter(id_short="ContainerType", semantic_id=f"{MEANS}/ContainerType",
                                                      value="cartridge"),
                        "GraspDiameter": pp.Parameter(id_short="GraspDiameter", semantic_id=f"{MEANS}/GraspDiameter",
                                                      value="11.6", value_type="xs:double", qualifiers=unit("mm")),
                        "StopperDiameter": pp.Parameter(id_short="StopperDiameter", semantic_id=f"{MEANS}/StopperDiameter",
                                                        value="10.3", value_type="xs:double", qualifiers=unit("mm")),
                    }),
                    ProcessParameters=pp.ProcessParameterGroup(),
                    ResourceParameters=pp.ResourceParameters(),
                    ProcessBoM=pp.ProcessBoM(MaterialUse={
                        "Stopper": pp.MaterialUse(
                            id_short="Stopper",
                            MaterialReference=pp.MaterialReference(value=reference(
                                ("Submodel", BILL), ("Entity", "EntryNode"), ("Entity", "Stopper"))),
                            Role=pp.Role(value="incorporated"), Quantity=pp.Quantity(value="1.0"), Unit=pp.Unit(value="piece")),
                    }),
                    RequiredCapability=pp.RequiredCapability(value=reference(
                        ("Submodel", CAPABILITIES), ("SubmodelElementCollection", "RequiredCapabilities"),
                        ("SubmodelElementCollection", "Stoppering"), ("Capability", "Capability"))),
                ),
                "Inspection": pp.Process(
                    id_short="Inspection",
                    ProcessId=pp.ProcessId(value="Inspection"),
                    ProcessName=pp.ProcessName(value="Inspection"),
                    ProcessDescription=pp.ProcessDescription(value={"en": "Inspect the closed cartridge and decide whether it passes"}),
                    PlannedProcessTime=pp.PlannedProcessTime(value="PT3S"),
                    ProductParameters=pp.ProductParameters(Parameter={
                        "ContainerType": pp.Parameter(id_short="ContainerType", semantic_id=f"{MEANS}/ContainerType",
                                                      value="cartridge"),
                        "GraspDiameter": pp.Parameter(id_short="GraspDiameter", semantic_id=f"{MEANS}/GraspDiameter",
                                                      value="11.6", value_type="xs:double", qualifiers=unit("mm")),
                        "InspectionMethod": pp.Parameter(id_short="InspectionMethod", semantic_id=f"{MEANS}/InspectionMethod",
                                                         value="vision"),
                    }),
                    ProcessParameters=pp.ProcessParameterGroup(),
                    ResourceParameters=pp.ResourceParameters(),
                    ProcessBoM=pp.ProcessBoM(),
                    RequiredCapability=pp.RequiredCapability(value=reference(
                        ("Submodel", CAPABILITIES), ("SubmodelElementCollection", "RequiredCapabilities"),
                        ("SubmodelElementCollection", "Inspection"), ("Capability", "Capability"))),
                ),
            }),
        ),

        # ── Capability Description (IDTA 02020, role Required) ───────────────────────────────────
        # What each process requires of a resource, with the product's values: a resource offers a
        # capability of the same meaning (supplemental id) whose properties cover these. The fill
        # error is a range: at most 0.05 mL either way.
        capability_description=cd.CapabilityDescription(
            id_short="CapabilityDescription",
            CapabilitySet={"RequiredCapabilities": cd.CapabilitySet(
                id_short="RequiredCapabilities",
                CapabilityContainer={
                    "Filling": cd.CapabilityContainer(
                        id_short="Filling",
                        Capability=Capability(
                            id_short="Capability", semantic_id=CAPABILITY, supplemental_semantic_ids=[f"{MEANS}/Filling"],
                            display_name={"en": "Filling"},
                            qualifiers=[Qualifier(type_="CapabilityRoleQualifier/Required", value="true",
                                                  semantic_id=REQUIRED, kind="ConceptQualifier")]),
                        PropertySet={"PropertySet": cd.PropertySet(PropertyContainer={
                            "ContainerType": cd.PropertyContainer(id_short="ContainerType", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "ContainerType"},
                                                             supplemental_semantic_ids=[f"{MEANS}/ContainerType"],
                                                             value="cartridge")}),
                            "GraspDiameter": cd.PropertyContainer(id_short="GraspDiameter", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "GraspDiameter"},
                                                             supplemental_semantic_ids=[f"{MEANS}/GraspDiameter"],
                                                             value="11.6", value_type="xs:double", qualifiers=unit("mm"))}),
                            "FillVolume": cd.PropertyContainer(id_short="FillVolume", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "FillVolume"},
                                                             supplemental_semantic_ids=[f"{MEANS}/FillVolume"],
                                                             value="3.0", value_type="xs:double", qualifiers=unit("mL"))}),
                            "AbsoluteFillError": cd.PropertyContainer(id_short="AbsoluteFillError", PropertyRange={
                                "Value": cd.PropertyRange(id_short="Value", display_name={"en": "AbsoluteFillError"},
                                                          supplemental_semantic_ids=[f"{MEANS}/AbsoluteFillError"],
                                                          min="0.0", max="0.05", value_type="xs:double", qualifiers=unit("mL"))}),
                        })},
                    ),
                    "Stoppering": cd.CapabilityContainer(
                        id_short="Stoppering",
                        Capability=Capability(
                            id_short="Capability", semantic_id=CAPABILITY, supplemental_semantic_ids=[f"{MEANS}/Stoppering"],
                            display_name={"en": "Stoppering"},
                            qualifiers=[Qualifier(type_="CapabilityRoleQualifier/Required", value="true",
                                                  semantic_id=REQUIRED, kind="ConceptQualifier")]),
                        PropertySet={"PropertySet": cd.PropertySet(PropertyContainer={
                            "ContainerType": cd.PropertyContainer(id_short="ContainerType", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "ContainerType"},
                                                             supplemental_semantic_ids=[f"{MEANS}/ContainerType"],
                                                             value="cartridge")}),
                            "GraspDiameter": cd.PropertyContainer(id_short="GraspDiameter", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "GraspDiameter"},
                                                             supplemental_semantic_ids=[f"{MEANS}/GraspDiameter"],
                                                             value="11.6", value_type="xs:double", qualifiers=unit("mm"))}),
                            "StopperDiameter": cd.PropertyContainer(id_short="StopperDiameter", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "StopperDiameter"},
                                                             supplemental_semantic_ids=[f"{MEANS}/StopperDiameter"],
                                                             value="10.3", value_type="xs:double", qualifiers=unit("mm"))}),
                        })},
                    ),
                    "Inspection": cd.CapabilityContainer(
                        id_short="Inspection",
                        Capability=Capability(
                            id_short="Capability", semantic_id=CAPABILITY, supplemental_semantic_ids=[f"{MEANS}/Inspection"],
                            display_name={"en": "Inspection"},
                            qualifiers=[Qualifier(type_="CapabilityRoleQualifier/Required", value="true",
                                                  semantic_id=REQUIRED, kind="ConceptQualifier")]),
                        PropertySet={"PropertySet": cd.PropertySet(PropertyContainer={
                            "ContainerType": cd.PropertyContainer(id_short="ContainerType", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "ContainerType"},
                                                             supplemental_semantic_ids=[f"{MEANS}/ContainerType"],
                                                             value="cartridge")}),
                            "GraspDiameter": cd.PropertyContainer(id_short="GraspDiameter", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "GraspDiameter"},
                                                             supplemental_semantic_ids=[f"{MEANS}/GraspDiameter"],
                                                             value="11.6", value_type="xs:double", qualifiers=unit("mm"))}),
                            "InspectionMethod": cd.PropertyContainer(id_short="InspectionMethod", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "InspectionMethod"},
                                                             supplemental_semantic_ids=[f"{MEANS}/InspectionMethod"],
                                                             value="vision")}),
                        })},
                    ),
                },
            )},
        ),

        # ── Production Sequence (the planner's recipe) ───────────────────────────────────────────
        # Three steps in order, each running a process of Process Parameters and requiring its
        # capability. No resource, skill or binding: those are the process AAS's.
        production_sequence=ps.ProductionSequence(
            id_short="ProductionSequence", id=plan_id(AAS_ID),
            PlanSchema=ps.PlanSchema(value="production-sequence/2.0"),
            Revision=ps.Revision(value="1"),
            SequenceId=ps.SequenceId(value="product"),
            Name=ps.Name(value="Cartridge 3 mL"),
            Role=ps.Role(value="Primary"),
            Subject=ps.Subject(value=reference(("AssetAdministrationShell", AAS_ID))),
            Steps=ps.Steps(Step={
                "Step_0000": ps.Step(
                    id_short="Step_0000", NodeId=ps.NodeId(value="Filling"), Kind=ps.Kind(value="step"),
                    Name=ps.Name(value="Filling"), Order=ps.Order(value="0"),
                    ProcessOwner=ps.ProcessOwner(value=reference(("AssetAdministrationShell", AAS_ID))),
                    ProcessReference=ps.ProcessReference(value=reference(
                        ("Submodel", PROCESSES), ("SubmodelElementCollection", "Processes"),
                        ("SubmodelElementCollection", "Filling"))),
                    RequiredCapabilities=ps.RequiredCapabilities(RequiredCapability={
                        "Filling": ps.RequiredCapability(id_short="Filling", value=reference(
                            ("Submodel", CAPABILITIES), ("SubmodelElementCollection", "RequiredCapabilities"),
                            ("SubmodelElementCollection", "Filling"), ("Capability", "Capability")))}),
                ),
                "Step_0001": ps.Step(
                    id_short="Step_0001", NodeId=ps.NodeId(value="Stoppering"), Kind=ps.Kind(value="step"),
                    Name=ps.Name(value="Stoppering"), Order=ps.Order(value="1"),
                    ProcessOwner=ps.ProcessOwner(value=reference(("AssetAdministrationShell", AAS_ID))),
                    ProcessReference=ps.ProcessReference(value=reference(
                        ("Submodel", PROCESSES), ("SubmodelElementCollection", "Processes"),
                        ("SubmodelElementCollection", "Stoppering"))),
                    RequiredCapabilities=ps.RequiredCapabilities(RequiredCapability={
                        "Stoppering": ps.RequiredCapability(id_short="Stoppering", value=reference(
                            ("Submodel", CAPABILITIES), ("SubmodelElementCollection", "RequiredCapabilities"),
                            ("SubmodelElementCollection", "Stoppering"), ("Capability", "Capability")))}),
                ),
                "Step_0002": ps.Step(
                    id_short="Step_0002", NodeId=ps.NodeId(value="Inspection"), Kind=ps.Kind(value="step"),
                    Name=ps.Name(value="Inspection"), Order=ps.Order(value="2"),
                    ProcessOwner=ps.ProcessOwner(value=reference(("AssetAdministrationShell", AAS_ID))),
                    ProcessReference=ps.ProcessReference(value=reference(
                        ("Submodel", PROCESSES), ("SubmodelElementCollection", "Processes"),
                        ("SubmodelElementCollection", "Inspection"))),
                    RequiredCapabilities=ps.RequiredCapabilities(RequiredCapability={
                        "Inspection": ps.RequiredCapability(id_short="Inspection", value=reference(
                            ("Submodel", CAPABILITIES), ("SubmodelElementCollection", "RequiredCapabilities"),
                            ("SubmodelElementCollection", "Inspection"), ("Capability", "Capability")))}),
                ),
            }),
        ),
    )
