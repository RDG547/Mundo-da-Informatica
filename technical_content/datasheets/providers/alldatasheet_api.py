"""Adapter para o acesso oficial entregue individualmente pelo AllDatasheet.

O site confirma a existência de uma API por cadastro, mas não publica um
contrato REST universal. Por isso o endpoint e o nome do header de autenticação
precisam vir do pacote oficial recebido pelo administrador; nenhum formato é
inventado neste adapter.
"""

from __future__ import annotations

import hashlib
from typing import Any

from .base import DatasheetProvider, ProviderCapabilities, ProviderConfigurationError, json_items
from ..normalization import normalize_manufacturer, normalize_part_number
from ..types import DatasheetCandidate


class AllDatasheetApiProvider(DatasheetProvider):
    name = "alldatasheet_api"

    def __init__(self, api_key: str, endpoint: str, auth_header: str, *, query_parameter: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.api_key = str(api_key or "").strip()
        self.endpoint = str(endpoint or "").strip()
        self.auth_header = str(auth_header or "").strip()
        self.query_parameter = str(query_parameter or "").strip()

    def is_enabled(self) -> bool:
        return bool(self.api_key and self.endpoint and self.auth_header and self.query_parameter)

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(api=True, pdf_reference=True)

    def search(self, part_number: str) -> list[DatasheetCandidate]:
        if not self.is_enabled():
            raise ProviderConfigurationError(
                "O AllDatasheet fornece os detalhes da API apó aprovação. Configure URL, header e parâmetro conforme o acesso recebido."
            )
        response = self._request(
            "GET", self.endpoint,
            headers={self.auth_header: self.api_key, "Accept": "application/json"},
            params={self.query_parameter: part_number},
        )
        return [self.normalize(item, part_number) for item in json_items(response.json())][:10]

    def normalize(self, raw: dict[str, Any], query: str) -> DatasheetCandidate:
        part = str(raw.get("part_number") or raw.get("mpn") or raw.get("sku") or query).strip()
        manufacturer = str(raw.get("manufacturer") or raw.get("brand") or "").strip() or None
        exact = normalize_part_number(part) == normalize_part_number(query)
        fingerprint = hashlib.sha256(repr(sorted((str(key), repr(value)) for key, value in raw.items())).encode()).hexdigest()
        return DatasheetCandidate(
            provider=self.name,
            external_id=str(raw.get("id") or raw.get("external_id") or part)[:255],
            part_number=part,
            normalized_part_number=normalize_part_number(part),
            manufacturer=manufacturer,
            normalized_manufacturer=normalize_manufacturer(manufacturer),
            title=str(raw.get("title") or raw.get("document_title") or part)[:300],
            description=str(raw.get("description") or "")[:2000] or None,
            category=str(raw.get("category") or "")[:120] or None,
            package=str(raw.get("package") or "")[:120] or None,
            datasheet_reference=str(raw.get("datasheet_reference") or raw.get("datasheet_url") or raw.get("url") or "")[:2000] or None,
            pages=_safe_int(raw.get("pages")),
            confidence=float(raw.get("confidence") or (0.93 if exact else 0.68)),
            exact_match=exact,
            raw_fingerprint=fingerprint,
        )


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
