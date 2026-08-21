"""Provider para feeds JSON normalizados e expressamente licenciados."""

from __future__ import annotations

import hashlib
from typing import Any

from .base import DatasheetProvider, ProviderCapabilities, ProviderConfigurationError, json_items
from ..normalization import normalize_manufacturer, normalize_part_number
from ..types import DatasheetCandidate


class LicensedDatasheetProvider(DatasheetProvider):
    name = "licensed_provider"

    def __init__(self, endpoint: str, token: str = "", *, provider_name: str = "licensed_provider", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.endpoint = str(endpoint or "").strip()
        self.token = str(token or "").strip()
        self.name = provider_name

    def is_enabled(self) -> bool:
        return bool(self.endpoint)

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(api=True, pdf_reference=True)

    def search(self, part_number: str) -> list[DatasheetCandidate]:
        if not self.endpoint:
            raise ProviderConfigurationError(f"Endpoint do provider {self.name} não configurado.")
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        response = self._request("GET", self.endpoint, headers=headers, params={"q": part_number})
        return [self.normalize(item, part_number) for item in json_items(response.json())][:100]

    def normalize(self, raw: dict[str, Any], query: str) -> DatasheetCandidate:
        part = str(raw.get("part_number") or raw.get("mpn") or raw.get("sku") or query).strip()
        manufacturer = str(raw.get("manufacturer") or raw.get("brand") or "").strip() or None
        exact = normalize_part_number(part) == normalize_part_number(query)
        fingerprint = hashlib.sha256(repr(sorted((str(key), repr(value)) for key, value in raw.items())).encode()).hexdigest()
        specs = raw.get("specifications") if isinstance(raw.get("specifications"), dict) else {}
        return DatasheetCandidate(
            provider=self.name,
            external_id=str(raw.get("external_id") or raw.get("id") or part)[:255],
            part_number=part,
            normalized_part_number=normalize_part_number(part),
            manufacturer=manufacturer,
            normalized_manufacturer=normalize_manufacturer(manufacturer),
            title=str(raw.get("title") or raw.get("name") or part)[:300],
            description=str(raw.get("description") or "")[:2000] or None,
            category=str(raw.get("category") or "")[:120] or None,
            subcategory=str(raw.get("subcategory") or "")[:120] or None,
            package=str(raw.get("package") or raw.get("package_type") or "")[:120] or None,
            lifecycle_status=str(raw.get("lifecycle_status") or "")[:80] or None,
            datasheet_reference=str(raw.get("datasheet_reference") or raw.get("datasheet_url") or "")[:2000] or None,
            document_title=str(raw.get("document_title") or "")[:300] or None,
            document_revision=str(raw.get("revision") or "")[:80] or None,
            document_date=str(raw.get("document_date") or "")[:40] or None,
            document_language=str(raw.get("language") or "")[:20] or None,
            pages=_safe_int(raw.get("pages")),
            confidence=max(0.0, min(1.0, float(raw.get("confidence") or (0.96 if exact else 0.75)))),
            exact_match=exact,
            raw_fingerprint=fingerprint,
            specifications={str(key)[:120]: str(value)[:500] for key, value in list(specs.items())[:100]},
        )


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
