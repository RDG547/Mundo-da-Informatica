"""Provider para feed normalizado oficial de fabricante."""

from .licensed_provider import LicensedDatasheetProvider


class ManufacturerProvider(LicensedDatasheetProvider):
    name = "manufacturer_official"
