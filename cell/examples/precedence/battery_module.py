"""A battery module of the pack (``battery_pack.py``): a subassembly with an AAS and a Production
Sequence of its own, which the pack's Disassembly sequence calls. Four modules, one AAS each
(``battery_module(1)`` to ``battery_module(4)``): they are instances, each with its own serial number
and, once tested, its own state of health.

Taken apart:

    RemoveLid ──> TestCells ──> StateOfHealth ≥ 80 %?  ── yes ──> SortForReuse
                                                       └─ no ──> SortForRecycling

RemoveLid breaks the lid's clip joint (between two parts of this module, so it is in this module's
sequence, not the pack's). TestCells declares its output StateOfHealth; the decision compares it,
as Production Sequence 3.0 does (Condition, Operand, Expected).

Written like ``battery_pack.py``: aas-model's classes for the AAS, BaSyx's for the sequence.
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
from aas_pydantic.submodel_templates.nameplate import (
    AddressInformation, CityTown, CountryOfOrigin, ManufacturerName, ManufacturerProductDesignation, Nameplate,
    NationalCode, OrderCodeOfManufacturer, SerialNumber, Street, URIOfTheProduct, YearOfConstruction, Zipcode,
)
from basyx.aas import model as m

from battery_cell import ASSET_ID as CELL_TYPE

MEANS = f"{BASE_URL}/semantics"
CAPABILITY = "https://admin-shell.io/idta/CapabilityDescription/Capability/1/0"
REQUIRED = "https://admin-shell.io/idta/CapabilityDescription/CapabilityRoleQualifier/Required/1/0"
SEQUENCE = f"{BASE_URL}/SubmodelTemplate/ProductionSequence/4/0"
SEQ = f"{BASE_URL}/ProductionSequence"


def ids(n: int) -> dict[str, str]:
    """The ids of module ``n``: its AAS, asset and submodels."""
    aas = f"{BASE_URL}/aas/BatteryModule{n}AAS"
    return {"aas": aas, "asset": f"{BASE_URL}/assets/BatteryModule/SN-0042-{n}",
            "processes": f"{aas}/submodels/ProcessParameters", "bill": f"{aas}/submodels/HierarchicalStructures",
            "capabilities": f"{aas}/submodels/CapabilityDescription", "disassembly": f"{plan_id(aas)}/Disassembly"}


def reference(*keys: tuple[str, str]) -> ModelReference:
    return ModelReference(key=tuple(Key(type_=kind, value=value) for kind, value in keys))


def unit(symbol: str) -> list[Qualifier]:
    return [Qualifier(type_="Unit", value=symbol, kind="ConceptQualifier")]


def required() -> list[Qualifier]:
    return [Qualifier(type_="CapabilityRoleQualifier/Required", value="true", semantic_id=REQUIRED, kind="ConceptQualifier")]


def sem(name: str) -> m.ExternalReference:
    return m.ExternalReference((m.Key(m.KeyTypes.GLOBAL_REFERENCE, f"{SEQ}/{name}/1/0"),))


def means(name: str) -> m.ExternalReference:
    return m.ExternalReference((m.Key(m.KeyTypes.GLOBAL_REFERENCE, f"{MEANS}/{name}"),))


def ref(*keys: tuple[m.KeyTypes, str]) -> m.ModelReference:
    return m.ModelReference(tuple(m.Key(kind, value) for kind, value in keys), m.Referable)


S, SMC, ENT = m.KeyTypes.SUBMODEL, m.KeyTypes.SUBMODEL_ELEMENT_COLLECTION, m.KeyTypes.ENTITY


def text(id_short: str, value: str) -> m.Property:
    return m.Property(id_short, m.datatypes.String, value, semantic_id=sem(id_short))


def order(k: int) -> m.Property:
    return m.Property("Order", m.datatypes.NonNegativeInteger, k, semantic_id=sem("Order"))


def battery_module(n: int) -> Product:
    i = ids(n)
    return Product(
        id_short=f"BatteryModule{n}AAS", id=i["aas"],
        description=f"Battery module {n} of pack SN-0042: twelve cells under a clipped lid",
        display_name={"en": f"Battery module {n}"},

        nameplate=Nameplate(
            id_short="Nameplate",
            URIOfTheProduct=URIOfTheProduct(value=i["asset"]),
            ManufacturerName=ManufacturerName(value={"en": "Demo EV maker"}),
            ManufacturerProductDesignation=ManufacturerProductDesignation(value={"en": "Battery module, 12 cells"}),
            AddressInformation=AddressInformation(
                Street=Street(value={"en": "Demo street 1"}), Zipcode=Zipcode(value={"en": "9220"}),
                CityTown=CityTown(value={"en": "Aalborg Øst"}), NationalCode=NationalCode(value={"en": "DK"})),
            OrderCodeOfManufacturer=OrderCodeOfManufacturer(value="MOD-12C"),
            SerialNumber=SerialNumber(value=f"SN-0042-{n}"),
            YearOfConstruction=YearOfConstruction(value="2019"),
            CountryOfOrigin=CountryOfOrigin(value="DE"),
        ),

        # ── Hierarchical Structures: lid, housing, 12 cells of one cell type (its AAS by asset id) ──
        hierarchical_structures=BillOfMaterial(
            id_short="HierarchicalStructures", ArcheType=ArcheType(value="OneDown"),
            EntryNode=ProductEntry(
                display_name={"en": f"Battery module {n}"}, global_asset_id=i["asset"],
                Node={
                    "Lid": ProductPart(id_short="Lid", display_name={"en": "Module lid"},
                                       Quantity=PartQuantity(value="1.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                    "ModuleHousing": ProductPart(id_short="ModuleHousing", display_name={"en": "Module housing"},
                                                 Quantity=PartQuantity(value="1.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                    "Cell": ProductPart(id_short="Cell", entity_type="SelfManagedEntity", global_asset_id=CELL_TYPE,
                                        display_name={"en": "Prismatic cell 60 Ah"},
                                        Quantity=PartQuantity(value="12.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                },
            ),
        ),

        process_parameters=pp.ProcessParameters(
            id_short="ProcessParameters",
            Processes=pp.Processes(Process={
                "Unclipping": pp.Process(
                    id_short="Unclipping",
                    ProcessId=pp.ProcessId(value="Unclipping"), ProcessName=pp.ProcessName(value="Unclipping"),
                    ProcessDescription=pp.ProcessDescription(value={"en": "Release the lid's clips and lift it off"}),
                    PlannedProcessTime=pp.PlannedProcessTime(value="PT20S"),
                    ProductParameters=pp.ProductParameters(Parameter={
                        "ReleaseForce": pp.Parameter(id_short="ReleaseForce", semantic_id=f"{MEANS}/Force",
                                                     value="25.0", value_type="xs:double", qualifiers=unit("N")),
                    }),
                    ProcessParameters=pp.ProcessParameterGroup(), ResourceParameters=pp.ResourceParameters(),
                    ProcessBoM=pp.ProcessBoM(MaterialUse={
                        "Lid": pp.MaterialUse(
                            id_short="Lid",
                            MaterialReference=pp.MaterialReference(value=reference(
                                ("Submodel", i["bill"]), ("Entity", "EntryNode"), ("Entity", "Lid"))),
                            Role=pp.Role(value="output"), Quantity=pp.Quantity(value="1.0"), Unit=pp.Unit(value="piece")),
                    }),
                    RequiredCapability=pp.RequiredCapability(value=reference(
                        ("Submodel", i["capabilities"]), ("SubmodelElementCollection", "RequiredCapabilities"),
                        ("SubmodelElementCollection", "Unclipping"), ("Capability", "Capability"))),
                ),
                "CellTesting": pp.Process(
                    id_short="CellTesting",
                    ProcessId=pp.ProcessId(value="CellTesting"), ProcessName=pp.ProcessName(value="CellTesting"),
                    ProcessDescription=pp.ProcessDescription(value={"en": "Test the twelve cells and give the module's state of health"}),
                    PlannedProcessTime=pp.PlannedProcessTime(value="PT300S"),
                    ProductParameters=pp.ProductParameters(Parameter={
                        "DischargeCurrent": pp.Parameter(id_short="DischargeCurrent", semantic_id=f"{MEANS}/Current",
                                                         value="10.0", value_type="xs:double", qualifiers=unit("A")),
                        "NominalCapacity": pp.Parameter(id_short="NominalCapacity", semantic_id=f"{MEANS}/Capacity",
                                                        value="60.0", value_type="xs:double", qualifiers=unit("A·h")),
                    }),
                    ProcessParameters=pp.ProcessParameterGroup(), ResourceParameters=pp.ResourceParameters(),
                    ProcessBoM=pp.ProcessBoM(MaterialUse={
                        "Cell": pp.MaterialUse(
                            id_short="Cell",
                            MaterialReference=pp.MaterialReference(value=reference(
                                ("Submodel", i["bill"]), ("Entity", "EntryNode"), ("Entity", "Cell"))),
                            Role=pp.Role(value="workpiece"), Quantity=pp.Quantity(value="12.0"), Unit=pp.Unit(value="piece")),
                    }),
                    RequiredCapability=pp.RequiredCapability(value=reference(
                        ("Submodel", i["capabilities"]), ("SubmodelElementCollection", "RequiredCapabilities"),
                        ("SubmodelElementCollection", "CellTesting"), ("Capability", "Capability"))),
                ),
                "SortingForReuse": pp.Process(
                    id_short="SortingForReuse",
                    ProcessId=pp.ProcessId(value="SortingForReuse"), ProcessName=pp.ProcessName(value="SortingForReuse"),
                    ProcessDescription=pp.ProcessDescription(value={"en": "Put the module on the reuse shelf"}),
                    PlannedProcessTime=pp.PlannedProcessTime(value="PT15S"),
                    ProductParameters=pp.ProductParameters(Parameter={
                        "Destination": pp.Parameter(id_short="Destination", semantic_id=f"{MEANS}/Destination", value="reuse"),
                    }),
                    ProcessParameters=pp.ProcessParameterGroup(), ResourceParameters=pp.ResourceParameters(),
                    ProcessBoM=pp.ProcessBoM(),
                    RequiredCapability=pp.RequiredCapability(value=reference(
                        ("Submodel", i["capabilities"]), ("SubmodelElementCollection", "RequiredCapabilities"),
                        ("SubmodelElementCollection", "SortingForReuse"), ("Capability", "Capability"))),
                ),
                "SortingForRecycling": pp.Process(
                    id_short="SortingForRecycling",
                    ProcessId=pp.ProcessId(value="SortingForRecycling"), ProcessName=pp.ProcessName(value="SortingForRecycling"),
                    ProcessDescription=pp.ProcessDescription(value={"en": "Put the module in the recycling bin"}),
                    PlannedProcessTime=pp.PlannedProcessTime(value="PT15S"),
                    ProductParameters=pp.ProductParameters(Parameter={
                        "Destination": pp.Parameter(id_short="Destination", semantic_id=f"{MEANS}/Destination", value="recycling"),
                    }),
                    ProcessParameters=pp.ProcessParameterGroup(), ResourceParameters=pp.ResourceParameters(),
                    ProcessBoM=pp.ProcessBoM(),
                    RequiredCapability=pp.RequiredCapability(value=reference(
                        ("Submodel", i["capabilities"]), ("SubmodelElementCollection", "RequiredCapabilities"),
                        ("SubmodelElementCollection", "SortingForRecycling"), ("Capability", "Capability"))),
                ),
            }),
        ),

        capability_description=cd.CapabilityDescription(
            id_short="CapabilityDescription",
            CapabilitySet={"RequiredCapabilities": cd.CapabilitySet(
                id_short="RequiredCapabilities",
                CapabilityContainer={
                    "Unclipping": cd.CapabilityContainer(
                        id_short="Unclipping",
                        Capability=Capability(id_short="Capability", semantic_id=CAPABILITY,
                                              supplemental_semantic_ids=[f"{MEANS}/Unclipping"],
                                              display_name={"en": "Unclipping"}, qualifiers=required()),
                    ),
                    "CellTesting": cd.CapabilityContainer(
                        id_short="CellTesting",
                        Capability=Capability(id_short="Capability", semantic_id=CAPABILITY,
                                              supplemental_semantic_ids=[f"{MEANS}/CellTesting"],
                                              display_name={"en": "Cell testing"}, qualifiers=required()),
                        PropertySet={"PropertySet": cd.PropertySet(PropertyContainer={
                            "Current": cd.PropertyContainer(id_short="Current", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "Current"},
                                                             supplemental_semantic_ids=[f"{MEANS}/Current"],
                                                             value="10.0", value_type="xs:double", qualifiers=unit("A"))}),
                        })},
                    ),
                    "SortingForReuse": cd.CapabilityContainer(
                        id_short="SortingForReuse",
                        Capability=Capability(id_short="Capability", semantic_id=CAPABILITY,
                                              supplemental_semantic_ids=[f"{MEANS}/Sorting"],
                                              display_name={"en": "Sorting"}, qualifiers=required()),
                        PropertySet={"PropertySet": cd.PropertySet(PropertyContainer={
                            "Destination": cd.PropertyContainer(id_short="Destination", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "Destination"},
                                                             supplemental_semantic_ids=[f"{MEANS}/Destination"],
                                                             value="reuse")}),
                        })},
                    ),
                    "SortingForRecycling": cd.CapabilityContainer(
                        id_short="SortingForRecycling",
                        Capability=Capability(id_short="Capability", semantic_id=CAPABILITY,
                                              supplemental_semantic_ids=[f"{MEANS}/Sorting"],
                                              display_name={"en": "Sorting"}, qualifiers=required()),
                        PropertySet={"PropertySet": cd.PropertySet(PropertyContainer={
                            "Destination": cd.PropertyContainer(id_short="Destination", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "Destination"},
                                                             supplemental_semantic_ids=[f"{MEANS}/Destination"],
                                                             value="recycling")}),
                        })},
                    ),
                },
            )},
        ),
    )


def battery_module_sequence(n: int) -> m.Submodel:
    i = ids(n)
    teardown = (S, i["disassembly"]), (SMC, "Steps"), (SMC, "Step_0000"), (SMC, "Steps")

    def process(name: str) -> m.ModelReference:
        return ref((S, i["processes"]), (SMC, "Processes"), (SMC, name))

    return m.Submodel(
        i["disassembly"], id_short="ProductionSequenceDisassembly", semantic_id=m.ExternalReference(
            (m.Key(m.KeyTypes.GLOBAL_REFERENCE, SEQUENCE),)),
        display_name=m.MultiLanguageNameType({"en": f"Battery module {n}: taking apart"}),
        submodel_element=[
            text("ArcheType", "Disassembly"),
            text("Name", f"Battery module {n}, taken apart and graded"),
            m.Property("Revision", m.datatypes.NonNegativeInteger, 1, semantic_id=sem("Revision")),
            m.ReferenceElement("Subject", ref((m.KeyTypes.ASSET_ADMINISTRATION_SHELL, i["aas"])), semantic_id=sem("Subject")),
            m.SubmodelElementCollection("Steps", semantic_id=sem("Steps"), value=[
                m.SubmodelElementCollection("Step_0000", semantic_id=sem("Step"), value=[
                    text("NodeId", "Teardown"), text("Kind", "partial"), text("Name", "Take the module apart"), order(0),
                    m.SubmodelElementCollection("Steps", semantic_id=sem("Steps"), value=[

                        # RemoveLid: breaks the clip joint between lid and housing.
                        m.SubmodelElementCollection("Step_0000", semantic_id=sem("Step"), value=[
                            text("NodeId", "RemoveLid"), text("Kind", "step"), text("Name", "Remove the lid"), order(0),
                            m.ReferenceElement("ProcessReference", process("Unclipping"), semantic_id=sem("ProcessReference")),
                            m.SubmodelElementCollection("Joints", semantic_id=sem("Joints"), value=[
                                m.AnnotatedRelationshipElement(
                                    "J_Lid",
                                    first=ref((S, i["bill"]), (ENT, "EntryNode"), (ENT, "Lid")),
                                    second=ref((S, i["bill"]), (ENT, "EntryNode"), (ENT, "ModuleHousing")),
                                    display_name=m.MultiLanguageNameType({"en": "Lid to housing, four clips"}),
                                    semantic_id=sem("JointConnection"), supplemental_semantic_id=[means("SnapFitJoint")],
                                    annotation=[text("JointType", "Clip")]),
                            ]),
                        ]),

                        # TestCells: after the lid; declares the module's state of health.
                        m.SubmodelElementCollection("Step_0001", semantic_id=sem("Step"), value=[
                            text("NodeId", "TestCells"), text("Kind", "step"), text("Name", "Test the cells"), order(1),
                            m.ReferenceElement("ProcessReference", process("CellTesting"), semantic_id=sem("ProcessReference")),
                            m.SubmodelElementList("After", m.ReferenceElement, semantic_id=sem("After"), value=[
                                m.ReferenceElement(None, ref(*teardown, (SMC, "Step_0000"))),
                            ]),
                            m.SubmodelElementCollection("Outputs", semantic_id=sem("Outputs"), value=[
                                m.SubmodelElementCollection("Output_0000", semantic_id=sem("Output"), value=[
                                    text("OutputId", "StateOfHealth"), text("Name", "State of health"),
                                    text("DataType", "number"), text("Unit", "%"),
                                ]),
                            ]),
                        ]),

                        # The decision: reuse at 80 % or more, else recycle.
                        m.SubmodelElementCollection("Step_0002", semantic_id=sem("Step"), value=[
                            text("NodeId", "Grade"), text("Kind", "decision"), text("Name", "State of health at least 80 %?"),
                            order(2),
                            m.SubmodelElementList("After", m.ReferenceElement, semantic_id=sem("After"), value=[
                                m.ReferenceElement(None, ref(*teardown, (SMC, "Step_0001"))),
                            ]),
                            m.SubmodelElementCollection("Condition", semantic_id=sem("Condition"), value=[
                                text("ConditionType", "comparison"), text("Operator", "gte"), text("Unit", "%"),
                                m.SubmodelElementCollection("Expected", semantic_id=sem("Expected"), value=[
                                    text("DataType", "number"),
                                    m.Property("Value", m.datatypes.Double, 80.0, semantic_id=sem("Value")),
                                ]),
                                m.SubmodelElementCollection("Operand", semantic_id=sem("Operand"), value=[
                                    text("OperandType", "output"), text("StepId", "TestCells"), text("OutputId", "StateOfHealth"),
                                ]),
                            ]),
                            m.SubmodelElementCollection("Branches", semantic_id=sem("Branches"), value=[
                                m.SubmodelElementCollection("Branch_0000", semantic_id=sem("Branch"), value=[
                                    text("BranchId", "Reuse"), text("Name", "Yes: reuse"), order(0),
                                    m.SubmodelElementCollection("Steps", semantic_id=sem("Steps"), value=[
                                        m.SubmodelElementCollection("Step_0000", semantic_id=sem("Step"), value=[
                                            text("NodeId", "SortForReuse"), text("Kind", "step"),
                                            text("Name", "Sort for reuse"), order(0),
                                            m.ReferenceElement("ProcessReference", process("SortingForReuse"),
                                                               semantic_id=sem("ProcessReference")),
                                        ]),
                                    ]),
                                ]),
                                m.SubmodelElementCollection("Branch_0001", semantic_id=sem("Branch"), value=[
                                    text("BranchId", "Recycle"), text("Name", "No: recycle"), order(1),
                                    m.SubmodelElementCollection("Steps", semantic_id=sem("Steps"), value=[
                                        m.SubmodelElementCollection("Step_0000", semantic_id=sem("Step"), value=[
                                            text("NodeId", "SortForRecycling"), text("Kind", "step"),
                                            text("Name", "Sort for recycling"), order(0),
                                            m.ReferenceElement("ProcessReference", process("SortingForRecycling"),
                                                               semantic_id=sem("ProcessReference")),
                                        ]),
                                    ]),
                                ]),
                            ]),
                        ]),
                    ]),
                ]),
            ]),
        ])
