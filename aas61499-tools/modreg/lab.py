"""What every AAS of the lab starts from, where aas-model's own defaults say "Not specified"."""
from __future__ import annotations

from aas_model.constants import BASE_URL
from aas_pydantic.submodel_templates.nameplate import (
    AddressInformation, CityTown, CountryOfOrigin, ManufacturerName, ManufacturerProductDesignation, Nameplate,
    NationalCode, OrderCodeOfManufacturer, Street, URIOfTheProduct, YearOfConstruction, Zipcode,
)


def nameplate() -> Nameplate:
    """The nameplate of the lab, which a resource or a product then states its own values in."""
    return Nameplate(
        id_short="Nameplate",
        URIOfTheProduct=URIOfTheProduct(value=f"{BASE_URL}/product/1"),
        ManufacturerName=ManufacturerName(value={"en": "AAU Smart Production Lab"}),
        ManufacturerProductDesignation=ManufacturerProductDesignation(value={"en": "Pharmaceutical Processing Resource"}),
        AddressInformation=AddressInformation(
            Street=Street(value={"en": "Fibigerstræde 14"}), Zipcode=Zipcode(value={"en": "9220"}),
            CityTown=CityTown(value={"en": "Aalborg Øst"}), NationalCode=NationalCode(value={"en": "DK"})),
        OrderCodeOfManufacturer=OrderCodeOfManufacturer(value=""),
        YearOfConstruction=YearOfConstruction(value="2026"),
        CountryOfOrigin=CountryOfOrigin(value="DK"),
    )
