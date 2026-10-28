"""The 2 mL vial: a product type of the example line, its AAS (ISA-88's general recipe).

What it is: a 2R glass vial (16 mm across where a gripper holds it) holding 2 mL of a demo liquid,
closed with a 13 mm rubber stopper and a 13 mm crimp cap. What it needs: filling, stoppering,
capping and inspection, in that order.

The recipe names no equipment: which module carries out each step, with which skill and what each
input of the skill is handed, is the process AAS's (``processes/vial_2ml_on_filling_line.py``).
The values follow the process sequence planner's pharma example (basyx-aas-web-ui,
``demo/pharma.ts``, "Vial 2 mL").

Every element is written out here, as the classes of aas-model make it (``aas_model.product_template``
for the AAS and its bill of material, ``aas_model.submodel_templates.product`` for Process Parameters
and Production Sequence, IDTA 02020 for the required capabilities).
"""
from __future__ import annotations

from aas_model.constants import BASE_URL
from aas_model.product_template import (
    BillOfMaterial, Part, PartQuantity, PartQuantityUnit, Product, ProductEntry, plan_id,
)
from aas_model.submodel_templates.product import process_parameters as pp, production_sequence as ps
from aas_pydantic import Capability, Key, ModelReference, Property, Qualifier
from aas_pydantic.submodel_templates import capability_description as cd
from aas_pydantic.submodel_templates.hierarchical_structures import ArcheType
from aas_pydantic.submodel_templates.nameplate import (
    AddressInformation, CityTown, CountryOfOrigin, ManufacturerName, ManufacturerProductDesignation, Nameplate,
    NationalCode, OrderCodeOfManufacturer, Street, URIOfTheProduct, YearOfConstruction, Zipcode,
)

AAS_ID = f"{BASE_URL}/aas/Vial2mLAAS"
ASSET_ID = f"{BASE_URL}/assets/Vial2mL"
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


def vial_2ml() -> Product:
    return Product(
        id_short="Vial2mLAAS", id=AAS_ID,
        description="A 2 mL vial, filled, stoppered, capped and inspected",
        display_name={"en": "Vial 2 mL"},

        # ── Nameplate (IDTA 02006): what the product is ─────────────────────────────────────────
        nameplate=Nameplate(
            id_short="Nameplate",
            URIOfTheProduct=URIOfTheProduct(value=ASSET_ID),
            ManufacturerName=ManufacturerName(value={"en": "AAU Smart Production Lab"}),
            ManufacturerProductDesignation=ManufacturerProductDesignation(value={"en": "Filled vial 2 mL"}),
            AddressInformation=AddressInformation(
                Street=Street(value={"en": "Fibigerstræde 14"}), Zipcode=Zipcode(value={"en": "9220"}),
                CityTown=CityTown(value={"en": "Aalborg Øst"}), NationalCode=NationalCode(value={"en": "DK"})),
            OrderCodeOfManufacturer=OrderCodeOfManufacturer(value="VIAL-2ML"),
            YearOfConstruction=YearOfConstruction(value="2026"),
            CountryOfOrigin=CountryOfOrigin(value="DK"),
        ),

        # ── Hierarchical Structures (IDTA 02011): the bill of material ──────────────────────────
        # One vial, 2 mL of liquid, one stopper, one cap. A part states how much of it the product
        # holds and in which unit (IDTA counts parts only).
        hierarchical_structures=BillOfMaterial(
            id_short="HierarchicalStructures", ArcheType=ArcheType(value="OneDown"),
            EntryNode=ProductEntry(
                display_name={"en": "Vial 2 mL"}, global_asset_id=ASSET_ID,
                Node={
                    "Vial": Part(id_short="Vial", display_name={"en": "Glass vial 2R"},
                                 Quantity=PartQuantity(value="1.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                    "Liquid": Part(id_short="Liquid", display_name={"en": "Demo liquid"},
                                   Quantity=PartQuantity(value="2.0"), QuantityUnit=PartQuantityUnit(value="mL")),
                    "Stopper": Part(id_short="Stopper", display_name={"en": "Rubber stopper 13 mm"},
                                    Quantity=PartQuantity(value="1.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                    "Cap": Part(id_short="Cap", display_name={"en": "Crimp cap 13 mm"},
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
                    ProcessDescription=pp.ProcessDescription(value={"en": "Fill 2 mL of liquid into the open vial"}),
                    PlannedProcessTime=pp.PlannedProcessTime(value="PT10S"),
                    ProductParameters=pp.ProductParameters(Parameter={
                        "ContainerType": pp.Parameter(id_short="ContainerType", semantic_id=f"{MEANS}/ContainerType",
                                                      value="vial"),
                        "GraspDiameter": pp.Parameter(id_short="GraspDiameter", semantic_id=f"{MEANS}/GraspDiameter",
                                                      value="16.0", value_type="xs:double", qualifiers=unit("mm")),
                        "FillVolume": pp.Parameter(id_short="FillVolume", semantic_id=f"{MEANS}/FillVolume",
                                                   value="2.0", value_type="xs:double", qualifiers=unit("mL")),
                    }),
                    ProcessParameters=pp.ProcessParameterGroup(),
                    ResourceParameters=pp.ResourceParameters(),
                    ProcessBoM=pp.ProcessBoM(MaterialUse={
                        # The vial is what is worked on; the liquid goes into it, as much as FillVolume.
                        "Vial": pp.MaterialUse(
                            id_short="Vial",
                            MaterialReference=pp.MaterialReference(value=reference(
                                ("Submodel", BILL), ("Entity", "EntryNode"), ("Entity", "Vial"))),
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
                    ProcessDescription=pp.ProcessDescription(value={"en": "Place the stopper on the filled vial and press it in"}),
                    PlannedProcessTime=pp.PlannedProcessTime(value="PT5S"),
                    ProductParameters=pp.ProductParameters(Parameter={
                        "ContainerType": pp.Parameter(id_short="ContainerType", semantic_id=f"{MEANS}/ContainerType",
                                                      value="vial"),
                        "GraspDiameter": pp.Parameter(id_short="GraspDiameter", semantic_id=f"{MEANS}/GraspDiameter",
                                                      value="16.0", value_type="xs:double", qualifiers=unit("mm")),
                        "StopperDiameter": pp.Parameter(id_short="StopperDiameter", semantic_id=f"{MEANS}/StopperDiameter",
                                                        value="13.0", value_type="xs:double", qualifiers=unit("mm")),
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
                "Capping": pp.Process(
                    id_short="Capping",
                    ProcessId=pp.ProcessId(value="Capping"),
                    ProcessName=pp.ProcessName(value="Capping"),
                    ProcessDescription=pp.ProcessDescription(value={"en": "Put the cap on the stoppered vial and crimp it"}),
                    PlannedProcessTime=pp.PlannedProcessTime(value="PT5S"),
                    ProductParameters=pp.ProductParameters(Parameter={
                        "ContainerType": pp.Parameter(id_short="ContainerType", semantic_id=f"{MEANS}/ContainerType",
                                                      value="vial"),
                        "GraspDiameter": pp.Parameter(id_short="GraspDiameter", semantic_id=f"{MEANS}/GraspDiameter",
                                                      value="16.0", value_type="xs:double", qualifiers=unit("mm")),
                        "CapDiameter": pp.Parameter(id_short="CapDiameter", semantic_id=f"{MEANS}/CapDiameter",
                                                    value="13.0", value_type="xs:double", qualifiers=unit("mm")),
                    }),
                    ProcessParameters=pp.ProcessParameterGroup(),
                    ResourceParameters=pp.ResourceParameters(),
                    ProcessBoM=pp.ProcessBoM(MaterialUse={
                        "Cap": pp.MaterialUse(
                            id_short="Cap",
                            MaterialReference=pp.MaterialReference(value=reference(
                                ("Submodel", BILL), ("Entity", "EntryNode"), ("Entity", "Cap"))),
                            Role=pp.Role(value="incorporated"), Quantity=pp.Quantity(value="1.0"), Unit=pp.Unit(value="piece")),
                    }),
                    RequiredCapability=pp.RequiredCapability(value=reference(
                        ("Submodel", CAPABILITIES), ("SubmodelElementCollection", "RequiredCapabilities"),
                        ("SubmodelElementCollection", "Capping"), ("Capability", "Capability"))),
                ),
                "Inspection": pp.Process(
                    id_short="Inspection",
                    ProcessId=pp.ProcessId(value="Inspection"),
                    ProcessName=pp.ProcessName(value="Inspection"),
                    ProcessDescription=pp.ProcessDescription(value={"en": "Inspect the closed vial and decide whether it passes"}),
                    PlannedProcessTime=pp.PlannedProcessTime(value="PT3S"),
                    ProductParameters=pp.ProductParameters(Parameter={
                        "ContainerType": pp.Parameter(id_short="ContainerType", semantic_id=f"{MEANS}/ContainerType",
                                                      value="vial"),
                        "GraspDiameter": pp.Parameter(id_short="GraspDiameter", semantic_id=f"{MEANS}/GraspDiameter",
                                                      value="16.0", value_type="xs:double", qualifiers=unit("mm")),
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
        # error is a range: at most 0.1 mL either way.
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
                                                             value="vial")}),
                            "GraspDiameter": cd.PropertyContainer(id_short="GraspDiameter", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "GraspDiameter"},
                                                             supplemental_semantic_ids=[f"{MEANS}/GraspDiameter"],
                                                             value="16.0", value_type="xs:double", qualifiers=unit("mm"))}),
                            "FillVolume": cd.PropertyContainer(id_short="FillVolume", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "FillVolume"},
                                                             supplemental_semantic_ids=[f"{MEANS}/FillVolume"],
                                                             value="2.0", value_type="xs:double", qualifiers=unit("mL"))}),
                            "AbsoluteFillError": cd.PropertyContainer(id_short="AbsoluteFillError", PropertyRange={
                                "Value": cd.PropertyRange(id_short="Value", display_name={"en": "AbsoluteFillError"},
                                                          supplemental_semantic_ids=[f"{MEANS}/AbsoluteFillError"],
                                                          min="0.0", max="0.1", value_type="xs:double", qualifiers=unit("mL"))}),
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
                                                             value="vial")}),
                            "GraspDiameter": cd.PropertyContainer(id_short="GraspDiameter", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "GraspDiameter"},
                                                             supplemental_semantic_ids=[f"{MEANS}/GraspDiameter"],
                                                             value="16.0", value_type="xs:double", qualifiers=unit("mm"))}),
                            "StopperDiameter": cd.PropertyContainer(id_short="StopperDiameter", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "StopperDiameter"},
                                                             supplemental_semantic_ids=[f"{MEANS}/StopperDiameter"],
                                                             value="13.0", value_type="xs:double", qualifiers=unit("mm"))}),
                        })},
                    ),
                    "Capping": cd.CapabilityContainer(
                        id_short="Capping",
                        Capability=Capability(
                            id_short="Capability", semantic_id=CAPABILITY, supplemental_semantic_ids=[f"{MEANS}/Capping"],
                            display_name={"en": "Capping"},
                            qualifiers=[Qualifier(type_="CapabilityRoleQualifier/Required", value="true",
                                                  semantic_id=REQUIRED, kind="ConceptQualifier")]),
                        PropertySet={"PropertySet": cd.PropertySet(PropertyContainer={
                            "ContainerType": cd.PropertyContainer(id_short="ContainerType", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "ContainerType"},
                                                             supplemental_semantic_ids=[f"{MEANS}/ContainerType"],
                                                             value="vial")}),
                            "GraspDiameter": cd.PropertyContainer(id_short="GraspDiameter", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "GraspDiameter"},
                                                             supplemental_semantic_ids=[f"{MEANS}/GraspDiameter"],
                                                             value="16.0", value_type="xs:double", qualifiers=unit("mm"))}),
                            "CapDiameter": cd.PropertyContainer(id_short="CapDiameter", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "CapDiameter"},
                                                             supplemental_semantic_ids=[f"{MEANS}/CapDiameter"],
                                                             value="13.0", value_type="xs:double", qualifiers=unit("mm"))}),
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
                                                             value="vial")}),
                            "GraspDiameter": cd.PropertyContainer(id_short="GraspDiameter", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "GraspDiameter"},
                                                             supplemental_semantic_ids=[f"{MEANS}/GraspDiameter"],
                                                             value="16.0", value_type="xs:double", qualifiers=unit("mm"))}),
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
        # Four steps in order, each running a process of Process Parameters and requiring its
        # capability. No resource, skill or binding: those are the process AAS's.
        production_sequence=ps.ProductionSequence(
            id_short="ProductionSequence", id=plan_id(AAS_ID),
            PlanSchema=ps.PlanSchema(value="production-sequence/2.0"),
            Revision=ps.Revision(value="1"),
            SequenceId=ps.SequenceId(value="product"),
            Name=ps.Name(value="Vial 2 mL"),
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
                    id_short="Step_0002", NodeId=ps.NodeId(value="Capping"), Kind=ps.Kind(value="step"),
                    Name=ps.Name(value="Capping"), Order=ps.Order(value="2"),
                    ProcessOwner=ps.ProcessOwner(value=reference(("AssetAdministrationShell", AAS_ID))),
                    ProcessReference=ps.ProcessReference(value=reference(
                        ("Submodel", PROCESSES), ("SubmodelElementCollection", "Processes"),
                        ("SubmodelElementCollection", "Capping"))),
                    RequiredCapabilities=ps.RequiredCapabilities(RequiredCapability={
                        "Capping": ps.RequiredCapability(id_short="Capping", value=reference(
                            ("Submodel", CAPABILITIES), ("SubmodelElementCollection", "RequiredCapabilities"),
                            ("SubmodelElementCollection", "Capping"), ("Capability", "Capability")))}),
                ),
                "Step_0003": ps.Step(
                    id_short="Step_0003", NodeId=ps.NodeId(value="Inspection"), Kind=ps.Kind(value="step"),
                    Name=ps.Name(value="Inspection"), Order=ps.Order(value="3"),
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
