"""Provedores oficiais opcionais. Nenhum scraping é realizado aqui."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

import requests


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderRecord:
    source: str
    part_number: str
    manufacturer: str | None
    title: str
    description: str | None
    datasheet_url: str | None
    product_url: str | None
    raw: dict[str, Any]


class BaseProvider:
    name = "base"

    def __init__(self, *, timeout: float = 20.0, session: requests.Session | None = None) -> None:
        self.timeout = timeout
        self.session = session or requests.Session()

    def lookup(self, part_number: str) -> list[ProviderRecord]:
        raise NotImplementedError

    def _request(self, method: str, url: str, **kwargs):
        """Retry curto para quota/erros transitórios, sem esconder falhas."""
        response = None
        for attempt in range(3):
            try:
                response = self.session.request(method, url, **kwargs)
            except requests.RequestException as exc:
                if attempt >= 2:
                    raise ProviderError("O provedor oficial está indisponível no momento.") from exc
                time.sleep(0.25 * (2 ** attempt))
                continue
            if response.status_code not in {429, 500, 502, 503, 504}:
                return response
            if attempt < 2:
                retry_after = getattr(response, "headers", {}).get("Retry-After", "")
                try:
                    delay = min(2.0, max(0.1, float(retry_after)))
                except (TypeError, ValueError):
                    delay = 0.25 * (2 ** attempt)
                time.sleep(delay)
        if response is None:
            raise ProviderError("O provedor oficial não retornou uma resposta.")
        return response


class LicensedJsonFeedProvider(BaseProvider):
    """Adapter para catálogos oficiais/licenciados configurados pelo admin."""

    name = "licensed_feed"

    def __init__(self, source_name: str, endpoint: str, token: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.name = source_name
        self.endpoint = endpoint
        self.token = token

    def lookup(self, part_number: str) -> list[ProviderRecord]:
        if not self.endpoint:
            raise ProviderError(f"Feed oficial {self.name} não configurado.")
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        response = self._request(
            "GET", self.endpoint, params={"q": part_number}, headers=headers, timeout=self.timeout
        )
        try:
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ProviderError(f"Resposta inválida do feed {self.name}.") from exc
        if isinstance(payload, dict):
            items = payload.get("items", [])
        elif isinstance(payload, list):
            items = payload
        else:
            items = []
        return [ProviderRecord(
            source=self.name,
            part_number=str(item.get("part_number") or part_number),
            manufacturer=item.get("manufacturer"),
            title=str(item.get("title") or item.get("name") or part_number),
            description=item.get("description"),
            datasheet_url=item.get("datasheet_url"),
            product_url=item.get("product_url"),
            raw=item,
        ) for item in items[:100] if isinstance(item, dict)]
