"""Provedores oficiais opcionais. Nenhum scraping é realizado aqui."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any
from urllib.parse import quote

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


class MouserProvider(BaseProvider):
    name = "mouser"
    endpoint = "https://api.mouser.com/api/v1/search/partnumber"

    def __init__(self, api_key: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key

    def lookup(self, part_number: str) -> list[ProviderRecord]:
        if not self.api_key:
            raise ProviderError("Mouser API não configurada.")
        response = self._request(
            "POST",
            f"{self.endpoint}?apiKey={quote(self.api_key)}",
            json={"SearchByPartRequest": {"mouserPartNumber": part_number, "partSearchOptions": "None"}},
            timeout=self.timeout,
        )
        if response.status_code == 429:
            raise ProviderError("Limite da Mouser API atingido.")
        try:
            response.raise_for_status()
            parts = response.json().get("SearchResults", {}).get("Parts", [])
        except (requests.RequestException, ValueError, AttributeError) as exc:
            raise ProviderError("Resposta inválida da Mouser API.") from exc
        return [ProviderRecord(
            source=self.name,
            part_number=str(item.get("ManufacturerPartNumber") or part_number),
            manufacturer=item.get("Manufacturer"),
            title=str(item.get("Description") or item.get("ManufacturerPartNumber") or part_number),
            description=item.get("Description"),
            datasheet_url=item.get("DataSheetUrl"),
            product_url=item.get("ProductDetailUrl"),
            raw=item,
        ) for item in parts[:20]]


class DigiKeyProvider(BaseProvider):
    name = "digikey"
    token_endpoint = "https://api.digikey.com/v1/oauth2/token"
    product_endpoint = "https://api.digikey.com/products/v4/search/{part}/productdetails"

    def __init__(self, client_id: str, client_secret: str, account_id: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.client_id = client_id
        self.client_secret = client_secret
        self.account_id = account_id
        self._token: str | None = None
        self._expires_at = 0.0

    def _access_token(self) -> str:
        if self._token and self._expires_at > time.time() + 30:
            return self._token
        if not self.client_id or not self.client_secret:
            raise ProviderError("DigiKey API não configurada.")
        response = self._request(
            "POST",
            self.token_endpoint,
            data={"client_id": self.client_id, "client_secret": self.client_secret, "grant_type": "client_credentials"},
            timeout=self.timeout,
        )
        try:
            response.raise_for_status()
            payload = response.json()
            self._token = payload["access_token"]
            self._expires_at = time.time() + int(payload.get("expires_in", 600))
        except (requests.RequestException, ValueError, KeyError) as exc:
            raise ProviderError("Falha na autenticação da DigiKey API.") from exc
        return self._token

    def lookup(self, part_number: str) -> list[ProviderRecord]:
        headers = {
            "Authorization": f"Bearer {self._access_token()}",
            "X-DIGIKEY-Client-Id": self.client_id,
            "X-DIGIKEY-Locale-Site": "BR",
            "X-DIGIKEY-Locale-Language": "en",
        }
        if self.account_id:
            headers["X-DIGIKEY-Account-Id"] = self.account_id
        response = self._request(
            "GET",
            self.product_endpoint.format(part=quote(part_number, safe="")),
            headers=headers,
            timeout=self.timeout,
        )
        if response.status_code == 429:
            raise ProviderError("Limite da DigiKey API atingido.")
        try:
            response.raise_for_status()
            data = response.json().get("Product", response.json())
        except (requests.RequestException, ValueError, AttributeError) as exc:
            raise ProviderError("Resposta inválida da DigiKey API.") from exc
        manufacturer = data.get("Manufacturer", {})
        description = data.get("Description", {})
        record = ProviderRecord(
            source=self.name,
            part_number=str(data.get("ManufacturerProductNumber") or part_number),
            manufacturer=manufacturer.get("Name") if isinstance(manufacturer, dict) else str(manufacturer or "") or None,
            title=str(description.get("ProductDescription") if isinstance(description, dict) else description or part_number),
            description=description.get("DetailedDescription") if isinstance(description, dict) else None,
            datasheet_url=data.get("DatasheetUrl"),
            product_url=data.get("ProductUrl"),
            raw=data,
        )
        return [record]


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
