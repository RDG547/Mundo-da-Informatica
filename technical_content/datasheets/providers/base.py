"""Interface, retries curtos, limiter e circuit breaker dos providers."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import random
import time
from typing import Any

import requests

from ..types import DatasheetCandidate


class ProviderError(RuntimeError):
    status = "failed"


class ProviderConfigurationError(ProviderError):
    status = "not_configured"


class ProviderRateLimitError(ProviderError):
    status = "rate_limited"


class ProviderBlockedError(ProviderError):
    status = "blocked_by_policy"


@dataclass(slots=True)
class ProviderCapabilities:
    api: bool = True
    html_discovery: bool = False
    pdf_reference: bool = False
    pdf_stream: bool = False
    pdf_mirror: bool = False
    credits: bool = False
    batch: bool = False


class SlidingWindowLimiter:
    """Limiter independente e conservador para um único provider/processo."""

    def __init__(self, per_minute: int, per_hour: int, per_day: int, per_month: int = 0) -> None:
        self.limits = ((60, per_minute), (3600, per_hour), (86400, per_day), (2592000, per_month))
        self.events: deque[float] = deque()
        self.retention_window = max((window for window, limit in self.limits if limit > 0), default=60)

    def check(self) -> None:
        now = time.monotonic()
        while self.events and now - self.events[0] >= self.retention_window:
            self.events.popleft()
        for window, limit in self.limits:
            if limit <= 0:
                continue
            used = sum(1 for event in self.events if now - event < window)
            if used >= limit:
                raise ProviderRateLimitError(f"Limite interno do provider atingido ({limit}/{window}s).")
        self.events.append(now)


class DatasheetProvider:
    name = "base"
    channel = "api"

    def __init__(
        self,
        *,
        timeout: float = 15.0,
        retry_limit: int = 2,
        requests_per_minute: int = 30,
        requests_per_hour: int = 500,
        requests_per_day: int = 5000,
        requests_per_month: int = 0,
        minimum_interval: float = 0.0,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = max(1.0, min(60.0, float(timeout)))
        self.retry_limit = max(0, min(5, int(retry_limit)))
        self.session = session or requests.Session()
        self.limiter = SlidingWindowLimiter(
            requests_per_minute, requests_per_hour, requests_per_day, requests_per_month,
        )
        self.minimum_interval = max(0.0, min(60.0, float(minimum_interval)))
        self._last_request_at = 0.0
        self.consecutive_failures = 0

    def is_enabled(self) -> bool:
        return True

    def search(self, part_number: str) -> list[DatasheetCandidate]:
        raise NotImplementedError

    def fetch_details(self, candidate: DatasheetCandidate) -> DatasheetCandidate:
        return candidate

    def normalize(self, raw: dict[str, Any], query: str) -> DatasheetCandidate:
        raise NotImplementedError

    def health_check(self) -> dict[str, Any]:
        return {"online": self.is_enabled(), "status": "ready" if self.is_enabled() else "not_configured"}

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities()

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        response: requests.Response | None = None
        last_error: Exception | None = None
        for attempt in range(self.retry_limit + 1):
            self.limiter.check()
            elapsed = time.monotonic() - self._last_request_at
            if self._last_request_at and elapsed < self.minimum_interval:
                time.sleep(self.minimum_interval - elapsed)
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                self._last_request_at = time.monotonic()
            except requests.RequestException as exc:
                last_error = exc
                self.consecutive_failures += 1
                if attempt >= self.retry_limit:
                    raise ProviderError("Provider indisponível apó retries limitados.") from exc
                time.sleep(min(2.0, (0.2 * (2 ** attempt)) + random.uniform(0, 0.15)))
                continue
            if response.status_code in {403}:
                self.consecutive_failures += 1
                raise ProviderBlockedError("Provider recusou a consulta (403); nenhum bypass foi tentado.")
            if response.status_code == 429:
                self.consecutive_failures += 1
                if attempt >= self.retry_limit:
                    raise ProviderRateLimitError("Provider retornou 429; consulta pausada sem loop infinito.")
                retry_after = response.headers.get("Retry-After", "")
                try:
                    delay = min(2.0, max(0.1, float(retry_after)))
                except (TypeError, ValueError):
                    delay = min(2.0, (0.2 * (2 ** attempt)) + random.uniform(0, 0.15))
                time.sleep(delay)
                continue
            if response.status_code in {500, 502, 503, 504} and attempt < self.retry_limit:
                self.consecutive_failures += 1
                time.sleep(min(2.0, (0.2 * (2 ** attempt)) + random.uniform(0, 0.15)))
                continue
            try:
                response.raise_for_status()
            except requests.RequestException as exc:
                self.consecutive_failures += 1
                raise ProviderError(f"Provider retornou HTTP {response.status_code}.") from exc
            self.consecutive_failures = 0
            return response
        raise ProviderError("Provider não retornou resposta.") from last_error


def json_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("results", "items", "parts", "data", "components"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = json_items(value)
            if nested:
                return nested
    return [payload] if any(key in payload for key in ("mpn", "part_number", "sku", "manufacturerPartNumber")) else []
