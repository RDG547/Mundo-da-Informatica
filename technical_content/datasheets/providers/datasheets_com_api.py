"""Provider server-to-server da Product Search API oficial Datasheets.com."""

from __future__ import annotations

import hashlib
from typing import Any

from .base import DatasheetProvider, ProviderCapabilities, ProviderConfigurationError, json_items
from ..normalization import normalize_manufacturer, normalize_part_number
from ..types import DatasheetCandidate


class DatasheetsComApiProvider(DatasheetProvider):
    name = "datasheets_com_api"

    def __init__(self, api_key: str, *, endpoint: str = "https://www.datasheets.com/api/v1/search", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.api_key = str(api_key or "").strip()
        self.endpoint = endpoint

    def is_enabled(self) -> bool:
        return bool(self.api_key)

    def capabilities(self) -> ProviderCapabilities:
        # A API retorna referência, mas os termos padrão não autorizam
        # republicação nem espelhamento.
        return ProviderCapabilities(api=True, pdf_reference=True)

    def search(self, part_number: str) -> list[DatasheetCandidate]:
        if not self.api_key:
            raise ProviderConfigurationError("Configure DATASHEETS_COM_API_KEY.")
        response = self._request(
            "GET", self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
            params={"q": part_number, "limit": 10, "page": 1},
        )
        return [self.normalize(item, part_number) for item in json_items(response.json())][:10]

    def normalize(self, raw: dict[str, Any], query: str) -> DatasheetCandidate:
        part = str(raw.get("mpn") or raw.get("part_number") or query).strip()
        manufacturer = str(raw.get("manufacturer") or "").strip() or None
        exact = normalize_part_number(part) == normalize_part_number(query)
        specs: dict[str, str] = {}
        for item in raw.get("specs", []) if isinstance(raw.get("specs"), list) else []:
            if isinstance(item, dict) and item.get("name") and item.get("value") is not None:
                specs[str(item["name"])[:120]] = str(item["value"])[:500]
        category = next((str(raw.get(key)) for key in ("category4", "category3", "category2", "category1") if raw.get(key)), None)
        fingerprint = hashlib.sha256(repr(sorted((str(key), repr(value)) for key, value in raw.items())).encode()).hexdigest()
        return DatasheetCandidate(
            provider=self.name,
            external_id=str(raw.get("id") or raw.get("url") or part)[:255],
            part_number=part,
            normalized_part_number=normalize_part_number(part),
            manufacturer=manufacturer,
            normalized_manufacturer=normalize_manufacturer(manufacturer),
            title=str(raw.get("title") or part)[:300],
            description=str(raw.get("description") or "")[:2000] or None,
            category=category,
            subcategory=str(raw.get("category4") or "")[:120] or None,
            package=str(raw.get("packageType") or raw.get("package") or "")[:120] or None,
            lifecycle_status=str(raw.get("lifecycleStatus") or "")[:80] or None,
            datasheet_reference=str(raw.get("datasheetUrl") or "")[:2000] or None,
            confidence=0.94 if exact else 0.7,
            exact_match=exact,
            raw_fingerprint=fingerprint,
            specifications=specs,
        )
