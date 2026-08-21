"""Discovery HTML estritamente opt-in, sem bypass ou varredura ampla."""

from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import re
from typing import Any
from urllib.parse import quote, urljoin, urlparse
from urllib.robotparser import RobotFileParser

from .base import DatasheetProvider, ProviderBlockedError, ProviderCapabilities, ProviderConfigurationError
from ..normalization import normalize_part_number
from ..types import DatasheetCandidate


class _ResultLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None
            self._text = []


class AuthorizedHtmlDiscoveryProvider(DatasheetProvider):
    channel = "html"
    name = "html_discovery"

    def __init__(self, search_url_template: str, user_agent: str, *, robots_confirmed: bool, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.search_url_template = str(search_url_template or "").strip()
        self.user_agent = str(user_agent or "").strip()
        self.robots_confirmed = bool(robots_confirmed)

    def is_enabled(self) -> bool:
        return bool(self.search_url_template and self.user_agent and self.robots_confirmed)

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(api=False, html_discovery=True, pdf_reference=True)

    def _search_url(self, part_number: str) -> str:
        if "{part_number}" not in self.search_url_template:
            raise ProviderConfigurationError("A URL autorizada deve conter {part_number}; varreduras amplas são proibidas.")
        return self.search_url_template.replace("{part_number}", quote(part_number, safe=""))

    def _check_robots(self, url: str) -> None:
        if not self.robots_confirmed:
            raise ProviderBlockedError("robots.txt ainda não foi confirmado como permitido.")
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        parser = RobotFileParser(robots_url)
        try:
            response = self._request("GET", robots_url, headers={"User-Agent": self.user_agent})
            parser.parse(response.text.splitlines())
        except ProviderBlockedError:
            raise
        except Exception as exc:
            raise ProviderBlockedError("Não foi possível validar robots.txt; discovery bloqueado de forma segura.") from exc
        if not parser.can_fetch(self.user_agent, url):
            raise ProviderBlockedError("robots.txt não permite esta consulta.")

    def search(self, part_number: str) -> list[DatasheetCandidate]:
        if not self.is_enabled():
            raise ProviderConfigurationError("HTML discovery exige URL autorizada, User-Agent e validação de robots.txt.")
        url = self._search_url(part_number)
        self._check_robots(url)
        response = self._request("GET", url, headers={"User-Agent": self.user_agent, "Accept": "text/html"})
        content_type = response.headers.get("Content-Type", "").lower()
        body_prefix = response.text[:5000].lower()
        if "text/html" not in content_type or any(marker in body_prefix for marker in ("captcha", "cloudflare challenge", "cf-chl-")):
            raise ProviderBlockedError("O provider respondeu com bloqueio/challenge; nenhum bypass foi tentado.")
        parser = _ResultLinkParser()
        parser.feed(response.text[:1_000_000])
        normalized_query = normalize_part_number(part_number)
        results: list[DatasheetCandidate] = []
        seen: set[str] = set()
        for href, label in parser.links:
            text = " ".join((label or "").split())
            if normalized_query not in normalize_part_number(text):
                continue
            absolute = urljoin(url, href)
            if absolute in seen:
                continue
            seen.add(absolute)
            results.append(DatasheetCandidate(
                provider=self.name,
                external_id=hashlib.sha256(absolute.encode()).hexdigest()[:32],
                part_number=part_number,
                normalized_part_number=normalized_query,
                title=text[:300] or part_number,
                datasheet_reference=absolute,
                confidence=0.72,
                exact_match=bool(re.search(rf"(?<![A-Z0-9]){re.escape(part_number)}(?![A-Z0-9])", text, re.I)),
                raw_fingerprint=hashlib.sha256(f"{absolute}|{text}".encode()).hexdigest(),
            ))
            if len(results) >= 10:
                break
        return results

    def normalize(self, raw: dict[str, Any], query: str) -> DatasheetCandidate:
        raise NotImplementedError("HTML discovery normaliza durante a extração mínima.")
