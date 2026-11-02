"""The cell type of the battery modules (``battery_module.py``): a part, one AAS for the type. The
modules count twelve of it in their bill of material; a cell's own instance AAS (its tested
capacity) is for later.
"""
from __future__ import annotations

from aas_model.constants import BASE_URL
from aas_model.product_template import Product
from aas_pydantic.submodel_templates.nameplate import (
    AddressInformation, CityTown, CountryOfOrigin, ManufacturerName, ManufacturerProductDesignation, Nameplate,
    NationalCode, OrderCodeOfManufacturer, Street, URIOfTheProduct, YearOfConstruction, Zipcode,
)

AAS_ID = f"{BASE_URL}/aas/CellAAS"
ASSET_ID = f"{BASE_URL}/assets/Cell/Prismatic60Ah"


def battery_cell() -> Product:
    return Product(
        id_short="CellAAS", id=AAS_ID,
        description="A prismatic lithium-ion cell, 60 Ah: the part the battery modules hold twelve of",
        display_name={"en": "Prismatic cell 60 Ah"},
        nameplate=Nameplate(
            id_short="Nameplate",
            URIOfTheProduct=URIOfTheProduct(value=ASSET_ID),
            ManufacturerName=ManufacturerName(value={"en": "Demo cell maker"}),
            ManufacturerProductDesignation=ManufacturerProductDesignation(value={"en": "Prismatic cell NMC 60 Ah"}),
            AddressInformation=AddressInformation(
                Street=Street(value={"en": "Demo street 2"}), Zipcode=Zipcode(value={"en": "9220"}),
                CityTown=CityTown(value={"en": "Aalborg Øst"}), NationalCode=NationalCode(value={"en": "DK"})),
            OrderCodeOfManufacturer=OrderCodeOfManufacturer(value="CELL-60AH"),
            YearOfConstruction=YearOfConstruction(value="2019"),
            CountryOfOrigin=CountryOfOrigin(value="KR"),
        ),
    )
