"""The flip-off seal of the 2 mL vial (``vial_2ml.py``): a subassembly bought in. Its AAS has a
bill of material (the aluminium crimp seal, with an AAS of its own, and the plastic button) and no
Production Sequence: the supplier makes it, and the joint between seal and button is theirs.
"""
from __future__ import annotations

from aas_model.constants import BASE_URL
from aas_model.product_template import (
    BillOfMaterial, ProductPart, PartQuantity, PartQuantityUnit, Product, ProductEntry,
)
from aas_pydantic.submodel_templates.hierarchical_structures import ArcheType
from aas_pydantic.submodel_templates.nameplate import (
    AddressInformation, CityTown, CountryOfOrigin, ManufacturerName, ManufacturerProductDesignation, Nameplate,
    NationalCode, OrderCodeOfManufacturer, Street, URIOfTheProduct, YearOfConstruction, Zipcode,
)

from aluminium_seal import ASSET_ID as ALUMINIUM_SEAL

AAS_ID = f"{BASE_URL}/aas/FlipOffSealAAS"
ASSET_ID = f"{BASE_URL}/assets/FlipOffSeal13mm"


def flip_off_seal() -> Product:
    return Product(
        id_short="FlipOffSealAAS", id=AAS_ID,
        description="A 13 mm flip-off seal: an aluminium crimp seal with a plastic button, bought in",
        display_name={"en": "Flip-off seal 13 mm"},
        nameplate=Nameplate(
            id_short="Nameplate",
            URIOfTheProduct=URIOfTheProduct(value=ASSET_ID),
            ManufacturerName=ManufacturerName(value={"en": "Demo seal supplier"}),
            ManufacturerProductDesignation=ManufacturerProductDesignation(value={"en": "Flip-off seal 13 mm"}),
            AddressInformation=AddressInformation(
                Street=Street(value={"en": "Demo street 3"}), Zipcode=Zipcode(value={"en": "9220"}),
                CityTown=CityTown(value={"en": "Aalborg Øst"}), NationalCode=NationalCode(value={"en": "DK"})),
            OrderCodeOfManufacturer=OrderCodeOfManufacturer(value="FOS-13"),
            YearOfConstruction=YearOfConstruction(value="2026"),
            CountryOfOrigin=CountryOfOrigin(value="DE"),
        ),
        hierarchical_structures=BillOfMaterial(
            id_short="HierarchicalStructures", ArcheType=ArcheType(value="OneDown"),
            EntryNode=ProductEntry(
                display_name={"en": "Flip-off seal 13 mm"}, global_asset_id=ASSET_ID,
                Node={
                    "AluminiumSeal": ProductPart(id_short="AluminiumSeal", entity_type="SelfManagedEntity",
                                                 global_asset_id=ALUMINIUM_SEAL, display_name={"en": "Aluminium crimp seal"},
                                                 Quantity=PartQuantity(value="1.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                    "PlasticButton": ProductPart(id_short="PlasticButton", display_name={"en": "Plastic flip-off button"},
                                                 Quantity=PartQuantity(value="1.0"), QuantityUnit=PartQuantityUnit(value="piece")),
                },
            ),
        ),
    )
