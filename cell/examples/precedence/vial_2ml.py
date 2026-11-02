"""The 2 mL vial with the Production Sequence 4.0 (proposed, docs/precedence-graphs.md): the
reference vial of ``cell/examples/products/vial_2ml.py``, with two changes.

1. The cap is the flip-off seal, a subassembly bought in, with an AAS of its own
   (``flip_off_seal.py``): an aluminium crimp seal with a plastic button. In the bill of material it
   is ``FlipOffSeal`` (a SelfManagedEntity, by asset id) in place of ``Cap``.
2. The recipe is a Production Sequence 4.0 of the archetype Assembly: one partial block whose steps
   are ordered by After alone. GMP fixes the order, so the graph is a chain:

       Filling ──> Stoppering ──> Capping ──> Inspection

   Stoppering makes the press fit of stopper and vial, Capping the crimp of seal and vial; each
   joint (an AnnotatedRelationshipElement) sits in the step that makes it. Filling makes no joint:
   it incorporates the liquid.

Nameplate, Process Parameters and Capability Description are those of the reference vial, element
for element (Capping's material is the seal). The sequence is written with BaSyx's classes, as in
``battery_pack.py``.
"""
from __future__ import annotations

from aas_model.constants import BASE_URL
from aas_model.product_template import (
    BillOfMaterial, ProductPart, PartQuantity, PartQuantityUnit, Product, ProductEntry, plan_id,
)
from aas_model.submodel_templates.product import process_parameters as pp
from aas_pydantic import Capability, Key, ModelReference, Qualifier
from aas_pydantic.submodel_templates import capability_description as cd
from aas_pydantic.submodel_templates.hierarchical_structures import ArcheType
from basyx.aas import model as m
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
ASSEMBLY = f"{plan_id(AAS_ID)}/Assembly"
SEAL_ASSET = f"{BASE_URL}/assets/FlipOffSeal13mm"
# The Production Sequence 4.0: the submodel's semantic id, and its elements' (the planner's namespace).
SEQUENCE = f"{BASE_URL}/SubmodelTemplate/ProductionSequence/4/0"
SEQ = f"{BASE_URL}/ProductionSequence"


def reference(*keys: tuple[str, str]) -> ModelReference:
    """A model reference along ``keys``: (type, value) pairs."""
    return ModelReference(key=tuple(Key(type_=kind, value=value) for kind, value in keys))


def unit(symbol: str) -> list[Qualifier]:
    """The qualifier that states a value's unit."""
    return [Qualifier(type_="Unit", value=symbol, kind="ConceptQualifier")]


def vial_2ml() -> Product:
    return Product(
        id_short="Vial2mLAAS", id=AAS_ID,
        description="A 2 mL vial, filled, stoppered, sealed and inspected (Production Sequence 4.0)",
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
        # One vial, 2 mL of liquid, one stopper, one flip-off seal. A part states how much of it the product
        # holds and in which unit (IDTA counts parts only).
        hierarchical_structures=BillOfMaterial(
            id_short="HierarchicalStructures", ArcheType=ArcheType(value="OneDown"),
            EntryNode=ProductEntry(
                display_name={"en": "Vial 2 mL"}, global_asset_id=ASSET_ID,
                Node={
                    "Vial": ProductPart(id_short="Vial", display_name={"en": "Glass vial 2R"},
                                        Quantity=PartQuantity(value="1.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                    "Liquid": ProductPart(id_short="Liquid", display_name={"en": "Demo liquid"},
                                          Quantity=PartQuantity(value="2.0"), QuantityUnit=PartQuantityUnit(value="mL")),
                    "Stopper": ProductPart(id_short="Stopper", display_name={"en": "Rubber stopper 13 mm"},
                                           Quantity=PartQuantity(value="1.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                    # Bought in: the seal has an AAS of its own, found by its asset id.
                    "FlipOffSeal": ProductPart(id_short="FlipOffSeal", entity_type="SelfManagedEntity",
                                               global_asset_id=SEAL_ASSET, display_name={"en": "Flip-off seal 13 mm"},
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
                    ProcessDescription=pp.ProcessDescription(value={"en": "Put the flip-off seal on the stoppered vial and crimp it"}),
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
                        "FlipOffSeal": pp.MaterialUse(
                            id_short="FlipOffSeal",
                            MaterialReference=pp.MaterialReference(value=reference(
                                ("Submodel", BILL), ("Entity", "EntryNode"), ("Entity", "FlipOffSeal"))),
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
    )


# ---- the Production Sequence 4.0 ------------------------------------------------------------------
def sem(name: str) -> m.ExternalReference:
    """The semantic id of a Production Sequence element."""
    return m.ExternalReference((m.Key(m.KeyTypes.GLOBAL_REFERENCE, f"{SEQ}/{name}/1/0"),))


def means(name: str) -> m.ExternalReference:
    """A meaning of the lab's vocabulary, as supplemental semantic id."""
    return m.ExternalReference((m.Key(m.KeyTypes.GLOBAL_REFERENCE, f"{MEANS}/{name}"),))


def ref(*keys: tuple[m.KeyTypes, str]) -> m.ModelReference:
    return m.ModelReference(tuple(m.Key(kind, value) for kind, value in keys), m.Referable)


S, SMC, ENT = m.KeyTypes.SUBMODEL, m.KeyTypes.SUBMODEL_ELEMENT_COLLECTION, m.KeyTypes.ENTITY


def part(name: str) -> m.ModelReference:
    """An entity of the vial's bill of material."""
    return ref((S, BILL), (ENT, "EntryNode"), (ENT, name))


def process(name: str) -> m.ModelReference:
    return ref((S, PROCESSES), (SMC, "Processes"), (SMC, name))


def before(name: str) -> m.ReferenceElement:
    """An item of After: a step of the partial block FillAndClose."""
    return m.ReferenceElement(None, ref((S, ASSEMBLY), (SMC, "Steps"), (SMC, "Step_0000"), (SMC, "Steps"), (SMC, name)))


def text(id_short: str, value: str) -> m.Property:
    return m.Property(id_short, m.datatypes.String, value, semantic_id=sem(id_short))


def order(n: int) -> m.Property:
    return m.Property("Order", m.datatypes.NonNegativeInteger, n, semantic_id=sem("Order"))


def vial_2ml_sequence() -> m.Submodel:
    return m.Submodel(
        ASSEMBLY, id_short="ProductionSequenceAssembly", semantic_id=m.ExternalReference(
            (m.Key(m.KeyTypes.GLOBAL_REFERENCE, SEQUENCE),)),
        display_name=m.MultiLanguageNameType({"en": "Vial 2 mL: filling and closing"}),
        submodel_element=[
            text("ArcheType", "Assembly"),
            text("Name", "Vial 2 mL"),
            m.Property("Revision", m.datatypes.NonNegativeInteger, 1, semantic_id=sem("Revision")),
            m.ReferenceElement("Subject", ref((m.KeyTypes.ASSET_ADMINISTRATION_SHELL, AAS_ID)), semantic_id=sem("Subject")),
            m.SubmodelElementCollection("Steps", semantic_id=sem("Steps"), value=[
                m.SubmodelElementCollection("Step_0000", semantic_id=sem("Step"), value=[
                    text("NodeId", "FillAndClose"), text("Kind", "partial"), text("Name", "Fill and close the vial"), order(0),
                    m.SubmodelElementCollection("Steps", semantic_id=sem("Steps"), value=[

                        # Filling: nothing before it; no joint (the liquid is incorporated).
                        m.SubmodelElementCollection("Step_0000", semantic_id=sem("Step"), value=[
                            text("NodeId", "Filling"), text("Kind", "step"), text("Name", "Filling"), order(0),
                            m.ReferenceElement("ProcessReference", process("Filling"), semantic_id=sem("ProcessReference")),
                        ]),

                        # Stoppering: after Filling; makes the press fit of stopper and vial.
                        m.SubmodelElementCollection("Step_0001", semantic_id=sem("Step"), value=[
                            text("NodeId", "Stoppering"), text("Kind", "step"), text("Name", "Stoppering"), order(1),
                            m.ReferenceElement("ProcessReference", process("Stoppering"), semantic_id=sem("ProcessReference")),
                            m.SubmodelElementList("After", m.ReferenceElement, semantic_id=sem("After"),
                                                  value=[before("Step_0000")]),
                            m.SubmodelElementCollection("Joints", semantic_id=sem("Joints"), value=[
                                m.AnnotatedRelationshipElement(
                                    "J_Stopper", first=part("Stopper"), second=part("Vial"),
                                    display_name=m.MultiLanguageNameType({"en": "Stopper pressed into the vial"}),
                                    semantic_id=sem("JointConnection"), supplemental_semantic_id=[means("PressFitJoint")],
                                    annotation=[text("JointType", "PressFit"), text("JointStandard", "DIN 8593-3")]),
                            ]),
                        ]),

                        # Capping: after Stoppering; makes the crimp of seal and vial.
                        m.SubmodelElementCollection("Step_0002", semantic_id=sem("Step"), value=[
                            text("NodeId", "Capping"), text("Kind", "step"), text("Name", "Capping"), order(2),
                            m.ReferenceElement("ProcessReference", process("Capping"), semantic_id=sem("ProcessReference")),
                            m.SubmodelElementList("After", m.ReferenceElement, semantic_id=sem("After"),
                                                  value=[before("Step_0001")]),
                            m.SubmodelElementCollection("Joints", semantic_id=sem("Joints"), value=[
                                m.AnnotatedRelationshipElement(
                                    "J_Seal", first=part("FlipOffSeal"), second=part("Vial"),
                                    display_name=m.MultiLanguageNameType({"en": "Seal crimped onto the vial"}),
                                    semantic_id=sem("JointConnection"), supplemental_semantic_id=[means("CrimpedJoint")],
                                    annotation=[text("JointType", "Crimp"), text("JointStandard", "DIN 8593-5")]),
                            ]),
                        ]),

                        # Inspection: after Capping; declares the two cameras' results.
                        m.SubmodelElementCollection("Step_0003", semantic_id=sem("Step"), value=[
                            text("NodeId", "Inspection"), text("Kind", "step"), text("Name", "Inspection"), order(3),
                            m.ReferenceElement("ProcessReference", process("Inspection"), semantic_id=sem("ProcessReference")),
                            m.SubmodelElementList("After", m.ReferenceElement, semantic_id=sem("After"),
                                                  value=[before("Step_0002")]),
                            m.SubmodelElementCollection("Outputs", semantic_id=sem("Outputs"), value=[
                                m.SubmodelElementCollection("Output_0000", semantic_id=sem("Output"), value=[
                                    text("OutputId", "TopPassed"), text("Name", "Top camera passed"),
                                    text("DataType", "boolean"), text("Unit", ""),
                                ]),
                                m.SubmodelElementCollection("Output_0001", semantic_id=sem("Output"), value=[
                                    text("OutputId", "SidePassed"), text("Name", "Side camera passed"),
                                    text("DataType", "boolean"), text("Unit", ""),
                                ]),
                            ]),
                        ]),
                    ]),
                ]),
            ]),
        ])
