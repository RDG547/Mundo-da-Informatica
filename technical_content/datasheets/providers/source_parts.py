"""Provider da API oficial Source Parts v1."""

from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import quote

from .base import DatasheetProvider, ProviderCapabilities, ProviderConfigurationError, json_items
from ..normalization import normalize_manufacturer, normalize_part_number
from ..types import DatasheetCandidate


class SourcePartsProvider(DatasheetProvider):
    name = "source_parts"

    def __init__(
        self,
        api_key: str,
        user_agent: str,
        *,
        base_url: str = "https://api.source.parts/v1",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.api_key = str(api_key or "").strip()
        self.user_agent = str(user_agent or "").strip()
        self.base_url = base_url.rstrip("/")

    def is_enabled(self) -> bool:
        return bool(self.api_key and self.user_agent)

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(api=True, pdf_reference=True, credits=True, batch=True)

    @property
    def headers(self) -> dict[str, str]:
        if not self.is_enabled():
            raise ProviderConfigurationError("Configure SOURCE_PARTS_API_KEY e SOURCE_PARTS_USER_AGENT.")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

    def search(self, part_number: str) -> list[DatasheetCandidate]:
        query = str(part_number or "").strip()
        response = self._request(
            "GET", f"{self.base_url}/parts/search",
            headers=self.headers, params={"q": query, "limit": 10},
        )
        payload = response.json()
        candidates = [self.normalize(item, query) for item in json_items(payload)]
        candidates.sort(key=lambda item: (not item.exact_match, -item.confidence))
        if candidates and candidates[0].exact_match:
            candidates[0] = self.fetch_details(candidates[0])
        return candidates[:10]

    def fetch_details(self, candidate: DatasheetCandidate) -> DatasheetCandidate:
        # Os endpoints de detalhe da API oficial recebem o SKU retornado pela
        # busca, que pode ser diferente do MPN exibido ao usuário.
        sku = quote(candidate.external_id or candidate.part_number, safe="")
        details: dict[str, Any] = {}
        for suffix in ("", "/specs", "/datasheet"):
            try:
                payload = self._request("GET", f"{self.base_url}/parts/{sku}{suffix}", headers=self.headers).json()
            except (ValueError, RuntimeError):
                continue
            if isinstance(payload, dict):
                details[suffix or "part"] = payload
        flattened = details.get("part", {}) if isinstance(details.get("part"), dict) else {}
        specs_payload = details.get("/specs", {})
        datasheet_payload = details.get("/datasheet", {})
        if isinstance(specs_payload, dict):
            raw_specs = specs_payload.get("specs") or specs_payload.get("specifications") or specs_payload
            if isinstance(raw_specs, dict):
                candidate.specifications = {str(key)[:120]: str(value)[:500] for key, value in list(raw_specs.items())[:100]}
        if isinstance(datasheet_payload, dict):
            candidate.datasheet_reference = str(
                datasheet_payload.get("url") or datasheet_payload.get("datasheet_url")
                or datasheet_payload.get("pdf_url") or candidate.datasheet_reference or ""
            ) or None
            candidate.pages = _safe_int(datasheet_payload.get("pages")) or candidate.pages
        candidate.package = str(flattened.get("package") or flattened.get("package_type") or candidate.package or "") or None
        candidate.lifecycle_status = str(flattened.get("lifecycle_status") or flattened.get("lifecycle") or candidate.lifecycle_status or "") or None
        candidate.confidence = min(1.0, candidate.confidence + 0.04)
        return candidate

    def normalize(self, raw: dict[str, Any], query: str) -> DatasheetCandidate:
        part = str(
            raw.get("part_number") or raw.get("mpn") or raw.get("sku")
            or raw.get("manufacturerPartNumber") or raw.get("manufacturer_part_number") or query
        ).strip()
        manufacturer_value = raw.get("manufacturer") or raw.get("manufacturer_name") or raw.get("brand")
        if isinstance(manufacturer_value, dict):
            manufacturer_value = manufacturer_value.get("name")
        manufacturer = str(manufacturer_value or "").strip() or None
        reference = raw.get("datasheet_url") or raw.get("datasheetUrl") or raw.get("pdf_url")
        exact = normalize_part_number(part) == normalize_part_number(query)
        confidence = float(raw.get("confidence") or raw.get("match_score") or (0.94 if exact else 0.72))
        fingerprint = hashlib.sha256(repr(sorted((str(key), repr(value)) for key, value in raw.items())).encode()).hexdigest()
        return DatasheetCandidate(
            provider=self.name,
            external_id=str(raw.get("sku") or raw.get("id") or raw.get("external_id") or part)[:255],
            part_number=part,
            normalized_part_number=normalize_part_number(part),
            manufacturer=manufacturer,
            normalized_manufacturer=normalize_manufacturer(manufacturer),
            title=str(raw.get("title") or raw.get("name") or part)[:300],
            description=str(raw.get("description") or "")[:2000] or None,
            category=str(raw.get("category") or raw.get("category_name") or "")[:120] or None,
            subcategory=str(raw.get("subcategory") or "")[:120] or None,
            package=str(raw.get("package") or raw.get("package_type") or "")[:120] or None,
            lifecycle_status=str(raw.get("lifecycle_status") or raw.get("lifecycle") or "")[:80] or None,
            datasheet_reference=str(reference or "")[:2000] or None,
            confidence=max(0.0, min(1.0, confidence)),
            exact_match=exact,
            raw_fingerprint=fingerprint,
        )

    def credit_balance(self) -> int | None:
        response = self._request("GET", f"{self.base_url}/credits/balance", headers=self.headers)
        payload = response.json()
        if not isinstance(payload, dict):
            return None
        for key in ("credits_remaining", "remaining", "balance", "credits"):
            if payload.get(key) is not None:
                return _safe_int(payload.get(key))
        return None


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
