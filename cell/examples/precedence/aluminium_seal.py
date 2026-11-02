"""The aluminium crimp seal of the flip-off seal (``flip_off_seal.py``): a part with an AAS of its own,
its nameplate only.
"""
from __future__ import annotations

from aas_model.constants import BASE_URL
from aas_model.product_template import Product
from aas_pydantic.submodel_templates.nameplate import (
    AddressInformation, CityTown, CountryOfOrigin, ManufacturerName, ManufacturerProductDesignation, Nameplate,
    NationalCode, OrderCodeOfManufacturer, Street, URIOfTheProduct, YearOfConstruction, Zipcode,
)

AAS_ID = f"{BASE_URL}/aas/AluminiumSealAAS"
ASSET_ID = f"{BASE_URL}/assets/AluminiumSeal13mm"


def aluminium_seal() -> Product:
    return Product(
        id_short="AluminiumSealAAS", id=AAS_ID,
        description="A 13 mm aluminium crimp seal",
        display_name={"en": "Aluminium seal 13 mm"},
        nameplate=Nameplate(
            id_short="Nameplate",
            URIOfTheProduct=URIOfTheProduct(value=ASSET_ID),
            ManufacturerName=ManufacturerName(value={"en": "Demo seal supplier"}),
            ManufacturerProductDesignation=ManufacturerProductDesignation(value={"en": "Aluminium crimp seal 13 mm"}),
            AddressInformation=AddressInformation(
                Street=Street(value={"en": "Demo street 3"}), Zipcode=Zipcode(value={"en": "9220"}),
                CityTown=CityTown(value={"en": "Aalborg Øst"}), NationalCode=NationalCode(value={"en": "DK"})),
            OrderCodeOfManufacturer=OrderCodeOfManufacturer(value="ALS-13"),
            YearOfConstruction=YearOfConstruction(value="2026"),
            CountryOfOrigin=CountryOfOrigin(value="DE"),
        ),
    )
