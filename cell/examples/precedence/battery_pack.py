"""An EV battery pack, remanufactured: its AAS with the Production Sequence 4.0 (proposed,
docs/precedence-graphs.md).

What it is: one pack, an instance (it comes back used), of a housing, a cover held by 12 screws, an
HV connector on the BMS, busbars over four battery modules. Each module is a subassembly with an
AAS of its own (``battery_module.py``).

What it needs, taken apart (Disassembly):

    UnscrewCover ──┐
                   ├──> RemoveBusbars ──> BatteryModule1..4 (each its own sequence, at once)
    UnplugHV ──────┤
                   └──> RemoveBMS

and closed again (Assembly), the joints referred to, not defined a second time:

    PlaceBMS ──> PlugHV ──┐
                          ├──> ScrewCover
    BoltBusbars ──────────┘

The Hierarchical Structures hold the parts only. Each joint (an AnnotatedRelationshipElement, the
colleagues' JointConnection) sits in the step that breaks it; its first and second are entities of
the bill of material. The recipe names no equipment: that is the process AAS's
(``battery_pack_on_disassembly_cell.py``).

Nameplate, bill of material, Process Parameters and Capability Description are aas-model's classes,
as in ``cell/examples/products/vial_2ml.py``. The two Production Sequences are written with BaSyx's
classes (``basyx.aas.model``): aas-model's template is still 2.0 and has no partial block, After or
joints.
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

AAS_ID = f"{BASE_URL}/aas/BatteryPackAAS"
ASSET_ID = f"{BASE_URL}/assets/BatteryPack/SN-0042"
PROCESSES = f"{AAS_ID}/submodels/ProcessParameters"
BILL = f"{AAS_ID}/submodels/HierarchicalStructures"
CAPABILITIES = f"{AAS_ID}/submodels/CapabilityDescription"
DISASSEMBLY = f"{plan_id(AAS_ID)}/Disassembly"
ASSEMBLY = f"{plan_id(AAS_ID)}/Assembly"
MODULES = [f"{BASE_URL}/aas/BatteryModule{n}AAS" for n in (1, 2, 3, 4)]
MODULE_ASSETS = [f"{BASE_URL}/assets/BatteryModule/SN-0042-{n}" for n in (1, 2, 3, 4)]
MEANS = f"{BASE_URL}/semantics"
CAPABILITY = "https://admin-shell.io/idta/CapabilityDescription/Capability/1/0"
REQUIRED = "https://admin-shell.io/idta/CapabilityDescription/CapabilityRoleQualifier/Required/1/0"
# The Production Sequence 4.0: the submodel's semantic id, and its elements' (the planner's namespace).
SEQUENCE = f"{BASE_URL}/SubmodelTemplate/ProductionSequence/4/0"
SEQ = f"{BASE_URL}/ProductionSequence"


# ---- aas-model's references and units ---------------------------------------------------------------
def reference(*keys: tuple[str, str]) -> ModelReference:
    """A model reference along ``keys``: (type, value) pairs."""
    return ModelReference(key=tuple(Key(type_=kind, value=value) for kind, value in keys))


def unit(symbol: str) -> list[Qualifier]:
    """The qualifier that states a value's unit."""
    return [Qualifier(type_="Unit", value=symbol, kind="ConceptQualifier")]


def required() -> list[Qualifier]:
    """The qualifier that makes a capability a required one."""
    return [Qualifier(type_="CapabilityRoleQualifier/Required", value="true", semantic_id=REQUIRED, kind="ConceptQualifier")]


# ---- BaSyx's, for the sequences --------------------------------------------------------------------
def sem(name: str) -> m.ExternalReference:
    """The semantic id of a Production Sequence element."""
    return m.ExternalReference((m.Key(m.KeyTypes.GLOBAL_REFERENCE, f"{SEQ}/{name}/1/0"),))


def means(name: str) -> m.ExternalReference:
    """A meaning of the lab's vocabulary, as supplemental semantic id."""
    return m.ExternalReference((m.Key(m.KeyTypes.GLOBAL_REFERENCE, f"{MEANS}/{name}"),))


def ref(*keys: tuple[m.KeyTypes, str]) -> m.ModelReference:
    return m.ModelReference(tuple(m.Key(kind, value) for kind, value in keys), m.Referable)


S, SMC, ENT, ARE = m.KeyTypes.SUBMODEL, m.KeyTypes.SUBMODEL_ELEMENT_COLLECTION, m.KeyTypes.ENTITY, \
    m.KeyTypes.ANNOTATED_RELATIONSHIP_ELEMENT


def part(name: str) -> m.ModelReference:
    """An entity of the pack's bill of material."""
    return ref((S, BILL), (ENT, "EntryNode"), (ENT, name))


def process(name: str) -> m.ModelReference:
    return ref((S, PROCESSES), (SMC, "Processes"), (SMC, name))


def step(sequence: str, *path: str) -> m.ModelReference:
    """A step of one of the pack's sequences, along its path of Steps."""
    keys = [(S, sequence)]
    for name in path:
        keys += [(SMC, "Steps"), (SMC, name)]
    return ref(*keys)


def text(id_short: str, value: str) -> m.Property:
    return m.Property(id_short, m.datatypes.String, value, semantic_id=sem(id_short))


def order(n: int) -> m.Property:
    return m.Property("Order", m.datatypes.NonNegativeInteger, n, semantic_id=sem("Order"))


# ---- the pack ----------------------------------------------------------------------------------------
def battery_pack() -> Product:
    return Product(
        id_short="BatteryPackAAS", id=AAS_ID,
        description="An EV battery pack, returned for remanufacturing: taken apart, its modules tested, closed again",
        display_name={"en": "Battery pack SN-0042"},

        # ── Nameplate (IDTA 02006): an instance, with its serial number ─────────────────────────
        nameplate=Nameplate(
            id_short="Nameplate",
            URIOfTheProduct=URIOfTheProduct(value=ASSET_ID),
            ManufacturerName=ManufacturerName(value={"en": "Demo EV maker"}),
            ManufacturerProductDesignation=ManufacturerProductDesignation(value={"en": "Battery pack, 4 modules"}),
            AddressInformation=AddressInformation(
                Street=Street(value={"en": "Demo street 1"}), Zipcode=Zipcode(value={"en": "9220"}),
                CityTown=CityTown(value={"en": "Aalborg Øst"}), NationalCode=NationalCode(value={"en": "DK"})),
            OrderCodeOfManufacturer=OrderCodeOfManufacturer(value="PACK-4M"),
            SerialNumber=SerialNumber(value="SN-0042"),
            YearOfConstruction=YearOfConstruction(value="2019"),
            CountryOfOrigin=CountryOfOrigin(value="DE"),
        ),

        # ── Hierarchical Structures (IDTA 02011): the parts only ────────────────────────────────
        # The four modules have AASs of their own (SelfManagedEntity, by asset id). No joint here:
        # each joint is held by the step that breaks it (the Production Sequences below).
        hierarchical_structures=BillOfMaterial(
            id_short="HierarchicalStructures", ArcheType=ArcheType(value="OneDown"),
            EntryNode=ProductEntry(
                display_name={"en": "Battery pack"}, global_asset_id=ASSET_ID,
                Node={
                    "Housing": ProductPart(id_short="Housing", display_name={"en": "Pack housing"},
                                           Quantity=PartQuantity(value="1.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                    "Cover": ProductPart(id_short="Cover", display_name={"en": "Pack cover"},
                                         Quantity=PartQuantity(value="1.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                    "CoverScrew": ProductPart(id_short="CoverScrew", display_name={"en": "Cover screw M5"},
                                              Quantity=PartQuantity(value="12.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                    "HVConnector": ProductPart(id_short="HVConnector", display_name={"en": "HV connector"},
                                               Quantity=PartQuantity(value="1.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                    "BMS": ProductPart(id_short="BMS", display_name={"en": "Battery management system"},
                                       Quantity=PartQuantity(value="1.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                    "Busbars": ProductPart(id_short="Busbars", display_name={"en": "Busbars"},
                                           Quantity=PartQuantity(value="1.0"), QuantityUnit=PartQuantityUnit(value="set")),
                    "BatteryModule1": ProductPart(id_short="BatteryModule1", entity_type="SelfManagedEntity",
                                                  global_asset_id=MODULE_ASSETS[0], display_name={"en": "Battery module 1"},
                                                  Quantity=PartQuantity(value="1.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                    "BatteryModule2": ProductPart(id_short="BatteryModule2", entity_type="SelfManagedEntity",
                                                  global_asset_id=MODULE_ASSETS[1], display_name={"en": "Battery module 2"},
                                                  Quantity=PartQuantity(value="1.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                    "BatteryModule3": ProductPart(id_short="BatteryModule3", entity_type="SelfManagedEntity",
                                                  global_asset_id=MODULE_ASSETS[2], display_name={"en": "Battery module 3"},
                                                  Quantity=PartQuantity(value="1.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                    "BatteryModule4": ProductPart(id_short="BatteryModule4", entity_type="SelfManagedEntity",
                                                  global_asset_id=MODULE_ASSETS[3], display_name={"en": "Battery module 4"},
                                                  Quantity=PartQuantity(value="1.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                },
            ),
        ),

        # ── Process Parameters (IDTA 02031-1 and the lab's extension) ───────────────────────────
        # The joints' parameters live here (the colleagues' JointParams): the step that breaks a
        # joint names its process. Taking apart: Unscrewing, Unplugging, Unbolting, Removing;
        # closing again: Placing, Plugging, Bolting, Screwing.
        process_parameters=pp.ProcessParameters(
            id_short="ProcessParameters",
            Processes=pp.Processes(Process={
                "Unscrewing": pp.Process(
                    id_short="Unscrewing",
                    ProcessId=pp.ProcessId(value="Unscrewing"), ProcessName=pp.ProcessName(value="Unscrewing"),
                    ProcessDescription=pp.ProcessDescription(value={"en": "Loosen the 12 cover screws and lift the cover off"}),
                    PlannedProcessTime=pp.PlannedProcessTime(value="PT60S"),
                    ProductParameters=pp.ProductParameters(Parameter={
                        # The joint's TypeParam: what it takes to loosen a screw that has sat for years.
                        "BreakawayTorque": pp.Parameter(id_short="BreakawayTorque", semantic_id=f"{MEANS}/Torque",
                                                        value="8.0", value_type="xs:double", qualifiers=unit("N·m")),
                        "ScrewSize": pp.Parameter(id_short="ScrewSize", semantic_id=f"{MEANS}/ScrewSize", value="M5"),
                    }),
                    ProcessParameters=pp.ProcessParameterGroup(), ResourceParameters=pp.ResourceParameters(),
                    ProcessBoM=pp.ProcessBoM(MaterialUse={
                        # Taken out: the screws and the cover (role output).
                        "CoverScrew": pp.MaterialUse(
                            id_short="CoverScrew",
                            MaterialReference=pp.MaterialReference(value=reference(
                                ("Submodel", BILL), ("Entity", "EntryNode"), ("Entity", "CoverScrew"))),
                            Role=pp.Role(value="output"), Quantity=pp.Quantity(value="12.0"), Unit=pp.Unit(value="piece")),
                        "Cover": pp.MaterialUse(
                            id_short="Cover",
                            MaterialReference=pp.MaterialReference(value=reference(
                                ("Submodel", BILL), ("Entity", "EntryNode"), ("Entity", "Cover"))),
                            Role=pp.Role(value="output"), Quantity=pp.Quantity(value="1.0"), Unit=pp.Unit(value="piece")),
                    }),
                    RequiredCapability=pp.RequiredCapability(value=reference(
                        ("Submodel", CAPABILITIES), ("SubmodelElementCollection", "RequiredCapabilities"),
                        ("SubmodelElementCollection", "Unscrewing"), ("Capability", "Capability"))),
                ),
                "Unplugging": pp.Process(
                    id_short="Unplugging",
                    ProcessId=pp.ProcessId(value="Unplugging"), ProcessName=pp.ProcessName(value="Unplugging"),
                    ProcessDescription=pp.ProcessDescription(value={"en": "Unplug the HV connector from the BMS"}),
                    PlannedProcessTime=pp.PlannedProcessTime(value="PT10S"),
                    ProductParameters=pp.ProductParameters(Parameter={
                        "PullForce": pp.Parameter(id_short="PullForce", semantic_id=f"{MEANS}/Force",
                                                  value="40.0", value_type="xs:double", qualifiers=unit("N")),
                    }),
                    ProcessParameters=pp.ProcessParameterGroup(), ResourceParameters=pp.ResourceParameters(),
                    ProcessBoM=pp.ProcessBoM(MaterialUse={
                        # The connector stays in the pack, unplugged: it is what is worked on.
                        "HVConnector": pp.MaterialUse(
                            id_short="HVConnector",
                            MaterialReference=pp.MaterialReference(value=reference(
                                ("Submodel", BILL), ("Entity", "EntryNode"), ("Entity", "HVConnector"))),
                            Role=pp.Role(value="workpiece"), Quantity=pp.Quantity(value="1.0"), Unit=pp.Unit(value="piece")),
                    }),
                    RequiredCapability=pp.RequiredCapability(value=reference(
                        ("Submodel", CAPABILITIES), ("SubmodelElementCollection", "RequiredCapabilities"),
                        ("SubmodelElementCollection", "Unplugging"), ("Capability", "Capability"))),
                ),
                "Unbolting": pp.Process(
                    id_short="Unbolting",
                    ProcessId=pp.ProcessId(value="Unbolting"), ProcessName=pp.ProcessName(value="Unbolting"),
                    ProcessDescription=pp.ProcessDescription(value={"en": "Unbolt the busbars from the four modules"}),
                    PlannedProcessTime=pp.PlannedProcessTime(value="PT80S"),
                    ProductParameters=pp.ProductParameters(Parameter={
                        "BreakawayTorque": pp.Parameter(id_short="BreakawayTorque", semantic_id=f"{MEANS}/Torque",
                                                        value="12.0", value_type="xs:double", qualifiers=unit("N·m")),
                        "ScrewSize": pp.Parameter(id_short="ScrewSize", semantic_id=f"{MEANS}/ScrewSize", value="M6"),
                    }),
                    ProcessParameters=pp.ProcessParameterGroup(), ResourceParameters=pp.ResourceParameters(),
                    ProcessBoM=pp.ProcessBoM(MaterialUse={
                        "Busbars": pp.MaterialUse(
                            id_short="Busbars",
                            MaterialReference=pp.MaterialReference(value=reference(
                                ("Submodel", BILL), ("Entity", "EntryNode"), ("Entity", "Busbars"))),
                            Role=pp.Role(value="output"), Quantity=pp.Quantity(value="1.0"), Unit=pp.Unit(value="set")),
                    }),
                    RequiredCapability=pp.RequiredCapability(value=reference(
                        ("Submodel", CAPABILITIES), ("SubmodelElementCollection", "RequiredCapabilities"),
                        ("SubmodelElementCollection", "Unbolting"), ("Capability", "Capability"))),
                ),
                "Removing": pp.Process(
                    id_short="Removing",
                    ProcessId=pp.ProcessId(value="Removing"), ProcessName=pp.ProcessName(value="Removing"),
                    ProcessDescription=pp.ProcessDescription(value={"en": "Lift the BMS out of the housing"}),
                    PlannedProcessTime=pp.PlannedProcessTime(value="PT15S"),
                    ProductParameters=pp.ProductParameters(Parameter={
                        "Mass": pp.Parameter(id_short="Mass", semantic_id=f"{MEANS}/Mass",
                                             value="1.2", value_type="xs:double", qualifiers=unit("kg")),
                    }),
                    ProcessParameters=pp.ProcessParameterGroup(), ResourceParameters=pp.ResourceParameters(),
                    ProcessBoM=pp.ProcessBoM(MaterialUse={
                        "BMS": pp.MaterialUse(
                            id_short="BMS",
                            MaterialReference=pp.MaterialReference(value=reference(
                                ("Submodel", BILL), ("Entity", "EntryNode"), ("Entity", "BMS"))),
                            Role=pp.Role(value="output"), Quantity=pp.Quantity(value="1.0"), Unit=pp.Unit(value="piece")),
                    }),
                    RequiredCapability=pp.RequiredCapability(value=reference(
                        ("Submodel", CAPABILITIES), ("SubmodelElementCollection", "RequiredCapabilities"),
                        ("SubmodelElementCollection", "Removing"), ("Capability", "Capability"))),
                ),
                "Placing": pp.Process(
                    id_short="Placing",
                    ProcessId=pp.ProcessId(value="Placing"), ProcessName=pp.ProcessName(value="Placing"),
                    ProcessDescription=pp.ProcessDescription(value={"en": "Place the BMS back in the housing"}),
                    PlannedProcessTime=pp.PlannedProcessTime(value="PT15S"),
                    ProductParameters=pp.ProductParameters(Parameter={
                        "Mass": pp.Parameter(id_short="Mass", semantic_id=f"{MEANS}/Mass",
                                             value="1.2", value_type="xs:double", qualifiers=unit("kg")),
                    }),
                    ProcessParameters=pp.ProcessParameterGroup(), ResourceParameters=pp.ResourceParameters(),
                    ProcessBoM=pp.ProcessBoM(MaterialUse={
                        "BMS": pp.MaterialUse(
                            id_short="BMS",
                            MaterialReference=pp.MaterialReference(value=reference(
                                ("Submodel", BILL), ("Entity", "EntryNode"), ("Entity", "BMS"))),
                            Role=pp.Role(value="incorporated"), Quantity=pp.Quantity(value="1.0"), Unit=pp.Unit(value="piece")),
                    }),
                    RequiredCapability=pp.RequiredCapability(value=reference(
                        ("Submodel", CAPABILITIES), ("SubmodelElementCollection", "RequiredCapabilities"),
                        ("SubmodelElementCollection", "Placing"), ("Capability", "Capability"))),
                ),
                "Plugging": pp.Process(
                    id_short="Plugging",
                    ProcessId=pp.ProcessId(value="Plugging"), ProcessName=pp.ProcessName(value="Plugging"),
                    ProcessDescription=pp.ProcessDescription(value={"en": "Plug the HV connector into the BMS"}),
                    PlannedProcessTime=pp.PlannedProcessTime(value="PT10S"),
                    ProductParameters=pp.ProductParameters(Parameter={
                        "InsertionForce": pp.Parameter(id_short="InsertionForce", semantic_id=f"{MEANS}/Force",
                                                       value="60.0", value_type="xs:double", qualifiers=unit("N")),
                    }),
                    ProcessParameters=pp.ProcessParameterGroup(), ResourceParameters=pp.ResourceParameters(),
                    ProcessBoM=pp.ProcessBoM(MaterialUse={
                        "HVConnector": pp.MaterialUse(
                            id_short="HVConnector",
                            MaterialReference=pp.MaterialReference(value=reference(
                                ("Submodel", BILL), ("Entity", "EntryNode"), ("Entity", "HVConnector"))),
                            Role=pp.Role(value="workpiece"), Quantity=pp.Quantity(value="1.0"), Unit=pp.Unit(value="piece")),
                    }),
                    RequiredCapability=pp.RequiredCapability(value=reference(
                        ("Submodel", CAPABILITIES), ("SubmodelElementCollection", "RequiredCapabilities"),
                        ("SubmodelElementCollection", "Plugging"), ("Capability", "Capability"))),
                ),
                "Bolting": pp.Process(
                    id_short="Bolting",
                    ProcessId=pp.ProcessId(value="Bolting"), ProcessName=pp.ProcessName(value="Bolting"),
                    ProcessDescription=pp.ProcessDescription(value={"en": "Bolt the busbars onto the four modules"}),
                    PlannedProcessTime=pp.PlannedProcessTime(value="PT80S"),
                    ProductParameters=pp.ProductParameters(Parameter={
                        "TighteningTorque": pp.Parameter(id_short="TighteningTorque", semantic_id=f"{MEANS}/Torque",
                                                         value="10.0", value_type="xs:double", qualifiers=unit("N·m")),
                        "ScrewSize": pp.Parameter(id_short="ScrewSize", semantic_id=f"{MEANS}/ScrewSize", value="M6"),
                    }),
                    ProcessParameters=pp.ProcessParameterGroup(), ResourceParameters=pp.ResourceParameters(),
                    ProcessBoM=pp.ProcessBoM(MaterialUse={
                        "Busbars": pp.MaterialUse(
                            id_short="Busbars",
                            MaterialReference=pp.MaterialReference(value=reference(
                                ("Submodel", BILL), ("Entity", "EntryNode"), ("Entity", "Busbars"))),
                            Role=pp.Role(value="incorporated"), Quantity=pp.Quantity(value="1.0"), Unit=pp.Unit(value="set")),
                    }),
                    RequiredCapability=pp.RequiredCapability(value=reference(
                        ("Submodel", CAPABILITIES), ("SubmodelElementCollection", "RequiredCapabilities"),
                        ("SubmodelElementCollection", "Bolting"), ("Capability", "Capability"))),
                ),
                "Screwing": pp.Process(
                    id_short="Screwing",
                    ProcessId=pp.ProcessId(value="Screwing"), ProcessName=pp.ProcessName(value="Screwing"),
                    ProcessDescription=pp.ProcessDescription(value={"en": "Put the cover on and drive the 12 screws"}),
                    PlannedProcessTime=pp.PlannedProcessTime(value="PT60S"),
                    ProductParameters=pp.ProductParameters(Parameter={
                        "TighteningTorque": pp.Parameter(id_short="TighteningTorque", semantic_id=f"{MEANS}/Torque",
                                                         value="6.0", value_type="xs:double", qualifiers=unit("N·m")),
                        "ScrewSize": pp.Parameter(id_short="ScrewSize", semantic_id=f"{MEANS}/ScrewSize", value="M5"),
                    }),
                    ProcessParameters=pp.ProcessParameterGroup(), ResourceParameters=pp.ResourceParameters(),
                    ProcessBoM=pp.ProcessBoM(MaterialUse={
                        "CoverScrew": pp.MaterialUse(
                            id_short="CoverScrew",
                            MaterialReference=pp.MaterialReference(value=reference(
                                ("Submodel", BILL), ("Entity", "EntryNode"), ("Entity", "CoverScrew"))),
                            Role=pp.Role(value="incorporated"), Quantity=pp.Quantity(value="12.0"), Unit=pp.Unit(value="piece")),
                        "Cover": pp.MaterialUse(
                            id_short="Cover",
                            MaterialReference=pp.MaterialReference(value=reference(
                                ("Submodel", BILL), ("Entity", "EntryNode"), ("Entity", "Cover"))),
                            Role=pp.Role(value="incorporated"), Quantity=pp.Quantity(value="1.0"), Unit=pp.Unit(value="piece")),
                    }),
                    RequiredCapability=pp.RequiredCapability(value=reference(
                        ("Submodel", CAPABILITIES), ("SubmodelElementCollection", "RequiredCapabilities"),
                        ("SubmodelElementCollection", "Screwing"), ("Capability", "Capability"))),
                ),
            }),
        ),

        # ── Capability Description (IDTA 02020, role Required) ───────────────────────────────────
        # A torque the resource must reach (the joint's TypeRange is the offered range it is
        # matched against); the others ask for the capability only.
        capability_description=cd.CapabilityDescription(
            id_short="CapabilityDescription",
            CapabilitySet={"RequiredCapabilities": cd.CapabilitySet(
                id_short="RequiredCapabilities",
                CapabilityContainer={
                    "Unscrewing": cd.CapabilityContainer(
                        id_short="Unscrewing",
                        Capability=Capability(id_short="Capability", semantic_id=CAPABILITY,
                                              supplemental_semantic_ids=[f"{MEANS}/Unscrewing"],
                                              display_name={"en": "Unscrewing"}, qualifiers=required()),
                        PropertySet={"PropertySet": cd.PropertySet(PropertyContainer={
                            "Torque": cd.PropertyContainer(id_short="Torque", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "Torque"},
                                                             supplemental_semantic_ids=[f"{MEANS}/Torque"],
                                                             value="8.0", value_type="xs:double", qualifiers=unit("N·m"))}),
                        })},
                    ),
                    "Unplugging": cd.CapabilityContainer(
                        id_short="Unplugging",
                        Capability=Capability(id_short="Capability", semantic_id=CAPABILITY,
                                              supplemental_semantic_ids=[f"{MEANS}/Unplugging"],
                                              display_name={"en": "Unplugging"}, qualifiers=required()),
                    ),
                    "Unbolting": cd.CapabilityContainer(
                        id_short="Unbolting",
                        Capability=Capability(id_short="Capability", semantic_id=CAPABILITY,
                                              supplemental_semantic_ids=[f"{MEANS}/Unscrewing"],
                                              display_name={"en": "Unbolting"}, qualifiers=required()),
                        PropertySet={"PropertySet": cd.PropertySet(PropertyContainer={
                            "Torque": cd.PropertyContainer(id_short="Torque", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "Torque"},
                                                             supplemental_semantic_ids=[f"{MEANS}/Torque"],
                                                             value="12.0", value_type="xs:double", qualifiers=unit("N·m"))}),
                        })},
                    ),
                    "Removing": cd.CapabilityContainer(
                        id_short="Removing",
                        Capability=Capability(id_short="Capability", semantic_id=CAPABILITY,
                                              supplemental_semantic_ids=[f"{MEANS}/PickAndPlace"],
                                              display_name={"en": "Removing"}, qualifiers=required()),
                    ),
                    "Placing": cd.CapabilityContainer(
                        id_short="Placing",
                        Capability=Capability(id_short="Capability", semantic_id=CAPABILITY,
                                              supplemental_semantic_ids=[f"{MEANS}/PickAndPlace"],
                                              display_name={"en": "Placing"}, qualifiers=required()),
                    ),
                    "Plugging": cd.CapabilityContainer(
                        id_short="Plugging",
                        Capability=Capability(id_short="Capability", semantic_id=CAPABILITY,
                                              supplemental_semantic_ids=[f"{MEANS}/Plugging"],
                                              display_name={"en": "Plugging"}, qualifiers=required()),
                    ),
                    "Bolting": cd.CapabilityContainer(
                        id_short="Bolting",
                        Capability=Capability(id_short="Capability", semantic_id=CAPABILITY,
                                              supplemental_semantic_ids=[f"{MEANS}/Screwing"],
                                              display_name={"en": "Bolting"}, qualifiers=required()),
                        PropertySet={"PropertySet": cd.PropertySet(PropertyContainer={
                            "Torque": cd.PropertyContainer(id_short="Torque", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "Torque"},
                                                             supplemental_semantic_ids=[f"{MEANS}/Torque"],
                                                             value="10.0", value_type="xs:double", qualifiers=unit("N·m"))}),
                        })},
                    ),
                    "Screwing": cd.CapabilityContainer(
                        id_short="Screwing",
                        Capability=Capability(id_short="Capability", semantic_id=CAPABILITY,
                                              supplemental_semantic_ids=[f"{MEANS}/Screwing"],
                                              display_name={"en": "Screwing"}, qualifiers=required()),
                        PropertySet={"PropertySet": cd.PropertySet(PropertyContainer={
                            "Torque": cd.PropertyContainer(id_short="Torque", PropertyProperty={
                                "Value": cd.PropertyProperty(id_short="Value", display_name={"en": "Torque"},
                                                             supplemental_semantic_ids=[f"{MEANS}/Torque"],
                                                             value="6.0", value_type="xs:double", qualifiers=unit("N·m"))}),
                        })},
                    ),
                },
            )},
        ),
    )


# ---- the Production Sequences 4.0 ------------------------------------------------------------------
def battery_pack_sequences() -> list[m.Submodel]:
    """Disassembly holds the joints; Assembly refers to them."""
    return [disassembly(), assembly()]


def disassembly() -> m.Submodel:
    return m.Submodel(
        DISASSEMBLY, id_short="ProductionSequenceDisassembly", semantic_id=m.ExternalReference(
            (m.Key(m.KeyTypes.GLOBAL_REFERENCE, SEQUENCE),)),
        display_name=m.MultiLanguageNameType({"en": "Battery pack: taking apart"}),
        submodel_element=[
            text("ArcheType", "Disassembly"),
            text("Name", "Battery pack, taken apart"),
            m.Property("Revision", m.datatypes.NonNegativeInteger, 1, semantic_id=sem("Revision")),
            m.ReferenceElement("Subject", ref((m.KeyTypes.ASSET_ADMINISTRATION_SHELL, AAS_ID)), semantic_id=sem("Subject")),
            m.SubmodelElementCollection("Steps", semantic_id=sem("Steps"), value=[
                # One partial block: its steps in any order their After allows.
                m.SubmodelElementCollection("Step_0000", semantic_id=sem("Step"), value=[
                    text("NodeId", "OpenPack"), text("Kind", "partial"), text("Name", "Open the pack"), order(0),
                    m.SubmodelElementCollection("Steps", semantic_id=sem("Steps"), value=[

                        # UnscrewCover: nothing before it; breaks the cover's screwed joint.
                        m.SubmodelElementCollection("Step_0000", semantic_id=sem("Step"), value=[
                            text("NodeId", "UnscrewCover"), text("Kind", "step"), text("Name", "Unscrew the cover"), order(0),
                            m.ReferenceElement("ProcessReference", process("Unscrewing"), semantic_id=sem("ProcessReference")),
                            m.SubmodelElementCollection("Joints", semantic_id=sem("Joints"), value=[
                                m.AnnotatedRelationshipElement(
                                    "J_Cover", first=part("Cover"), second=part("Housing"),
                                    display_name=m.MultiLanguageNameType({"en": "Cover to housing, 12 screws M5"}),
                                    semantic_id=sem("JointConnection"), supplemental_semantic_id=[means("ScrewedJoint")],
                                    annotation=[text("JointType", "Screw"), text("JointStandard", "DIN 8593-3")]),
                            ]),
                        ]),

                        # UnplugHV: nothing before it; breaks the plug between connector and BMS.
                        m.SubmodelElementCollection("Step_0001", semantic_id=sem("Step"), value=[
                            text("NodeId", "UnplugHV"), text("Kind", "step"), text("Name", "Unplug the HV connector"), order(1),
                            m.ReferenceElement("ProcessReference", process("Unplugging"), semantic_id=sem("ProcessReference")),
                            m.SubmodelElementCollection("Joints", semantic_id=sem("Joints"), value=[
                                m.AnnotatedRelationshipElement(
                                    "J_HV", first=part("HVConnector"), second=part("BMS"),
                                    display_name=m.MultiLanguageNameType({"en": "HV connector to BMS"}),
                                    semantic_id=sem("JointConnection"), supplemental_semantic_id=[means("PluggedJoint")],
                                    annotation=[text("JointType", "Plug")]),
                            ]),
                        ]),

                        # RemoveBusbars: after the cover and the HV connector; breaks the four busbar joints.
                        m.SubmodelElementCollection("Step_0002", semantic_id=sem("Step"), value=[
                            text("NodeId", "RemoveBusbars"), text("Kind", "step"), text("Name", "Remove the busbars"), order(2),
                            m.ReferenceElement("ProcessReference", process("Unbolting"), semantic_id=sem("ProcessReference")),
                            m.SubmodelElementList("After", m.ReferenceElement, semantic_id=sem("After"), value=[
                                m.ReferenceElement(None, step(DISASSEMBLY, "Step_0000", "Step_0000")),
                                m.ReferenceElement(None, step(DISASSEMBLY, "Step_0000", "Step_0001")),
                            ]),
                            m.SubmodelElementCollection("Joints", semantic_id=sem("Joints"), value=[
                                m.AnnotatedRelationshipElement(
                                    f"J_Busbar{n}", first=part("Busbars"), second=part(f"BatteryModule{n}"),
                                    display_name=m.MultiLanguageNameType({"en": f"Busbars to module {n}, bolted M6"}),
                                    semantic_id=sem("JointConnection"), supplemental_semantic_id=[means("ScrewedJoint")],
                                    annotation=[text("JointType", "Bolt"), text("JointStandard", "DIN 8593-3")])
                                for n in (1, 2, 3, 4)
                            ]),
                        ]),

                        # RemoveBMS: after the HV connector only.
                        m.SubmodelElementCollection("Step_0003", semantic_id=sem("Step"), value=[
                            text("NodeId", "RemoveBMS"), text("Kind", "step"), text("Name", "Remove the BMS"), order(3),
                            m.ReferenceElement("ProcessReference", process("Removing"), semantic_id=sem("ProcessReference")),
                            m.SubmodelElementList("After", m.ReferenceElement, semantic_id=sem("After"), value=[
                                m.ReferenceElement(None, step(DISASSEMBLY, "Step_0000", "Step_0001")),
                            ]),
                        ]),

                        # The four modules: each a call into the module's own Disassembly sequence, after
                        # the busbars; four agents take them apart at once.
                        *[m.SubmodelElementCollection(f"Step_{3 + n:04d}", semantic_id=sem("Step"), value=[
                            text("NodeId", f"BatteryModule{n}"), text("Kind", "call"),
                            text("Name", f"Take battery module {n} apart"), order(3 + n),
                            m.ReferenceElement("SequenceReference", ref(
                                (S, f"{plan_id(MODULES[n - 1])}/Disassembly")), semantic_id=sem("SequenceReference")),
                            m.SubmodelElementList("After", m.ReferenceElement, semantic_id=sem("After"), value=[
                                m.ReferenceElement(None, step(DISASSEMBLY, "Step_0000", "Step_0002")),
                            ]),
                        ]) for n in (1, 2, 3, 4)],
                    ]),
                ]),
            ]),
        ])


def assembly() -> m.Submodel:
    def joint(name: str) -> m.ReferenceElement:
        """A joint the Disassembly sequence defines, referred to by the step that makes it again."""
        where = {"J_Cover": "Step_0000", "J_HV": "Step_0001"}.get(name, "Step_0002")
        return m.ReferenceElement(name, ref(
            (S, DISASSEMBLY), (SMC, "Steps"), (SMC, "Step_0000"), (SMC, "Steps"), (SMC, where), (SMC, "Joints"),
            (ARE, name)), semantic_id=sem("JointReference"))

    return m.Submodel(
        ASSEMBLY, id_short="ProductionSequenceAssembly", semantic_id=m.ExternalReference(
            (m.Key(m.KeyTypes.GLOBAL_REFERENCE, SEQUENCE),)),
        display_name=m.MultiLanguageNameType({"en": "Battery pack: closing again"}),
        submodel_element=[
            text("ArcheType", "Assembly"),
            text("Name", "Battery pack, closed again"),
            m.Property("Revision", m.datatypes.NonNegativeInteger, 1, semantic_id=sem("Revision")),
            m.ReferenceElement("Subject", ref((m.KeyTypes.ASSET_ADMINISTRATION_SHELL, AAS_ID)), semantic_id=sem("Subject")),
            m.SubmodelElementCollection("Steps", semantic_id=sem("Steps"), value=[
                m.SubmodelElementCollection("Step_0000", semantic_id=sem("Step"), value=[
                    text("NodeId", "ClosePack"), text("Kind", "partial"), text("Name", "Close the pack"), order(0),
                    m.SubmodelElementCollection("Steps", semantic_id=sem("Steps"), value=[
                        m.SubmodelElementCollection("Step_0000", semantic_id=sem("Step"), value=[
                            text("NodeId", "PlaceBMS"), text("Kind", "step"), text("Name", "Place the BMS"), order(0),
                            m.ReferenceElement("ProcessReference", process("Placing"), semantic_id=sem("ProcessReference")),
                        ]),
                        m.SubmodelElementCollection("Step_0001", semantic_id=sem("Step"), value=[
                            text("NodeId", "BoltBusbars"), text("Kind", "step"), text("Name", "Bolt the busbars"), order(1),
                            m.ReferenceElement("ProcessReference", process("Bolting"), semantic_id=sem("ProcessReference")),
                            m.SubmodelElementCollection("Joints", semantic_id=sem("Joints"), value=[
                                joint("J_Busbar1"), joint("J_Busbar2"), joint("J_Busbar3"), joint("J_Busbar4"),
                            ]),
                        ]),
                        m.SubmodelElementCollection("Step_0002", semantic_id=sem("Step"), value=[
                            text("NodeId", "PlugHV"), text("Kind", "step"), text("Name", "Plug the HV connector in"), order(2),
                            m.ReferenceElement("ProcessReference", process("Plugging"), semantic_id=sem("ProcessReference")),
                            m.SubmodelElementList("After", m.ReferenceElement, semantic_id=sem("After"), value=[
                                m.ReferenceElement(None, step(ASSEMBLY, "Step_0000", "Step_0000")),
                            ]),
                            m.SubmodelElementCollection("Joints", semantic_id=sem("Joints"), value=[joint("J_HV")]),
                        ]),
                        m.SubmodelElementCollection("Step_0003", semantic_id=sem("Step"), value=[
                            text("NodeId", "ScrewCover"), text("Kind", "step"), text("Name", "Screw the cover on"), order(3),
                            m.ReferenceElement("ProcessReference", process("Screwing"), semantic_id=sem("ProcessReference")),
                            m.SubmodelElementList("After", m.ReferenceElement, semantic_id=sem("After"), value=[
                                m.ReferenceElement(None, step(ASSEMBLY, "Step_0000", "Step_0001")),
                                m.ReferenceElement(None, step(ASSEMBLY, "Step_0000", "Step_0002")),
                            ]),
                            m.SubmodelElementCollection("Joints", semantic_id=sem("Joints"), value=[joint("J_Cover")]),
                        ]),
                    ]),
                ]),
            ]),
        ])
