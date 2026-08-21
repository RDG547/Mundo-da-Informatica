"""Abstração de storage e entrega HTTP privada com suporte a Range."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import mimetypes
import os
import socket
from typing import Callable, Iterator
from urllib.parse import urljoin, urlparse

import requests
from werkzeug.http import parse_options_header


class StorageError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class UnsafeStorageUrl(StorageError):
    pass


@dataclass
class UpstreamDownload:
    status_code: int
    headers: dict[str, str]
    iterator: Iterator[bytes]
    close: Callable[[], None]


def _validate_public_http_url(url: str, allowed_hosts: set[str] | None = None) -> str:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeStorageUrl("Origem de storage inválida.")
    hostname = parsed.hostname.lower().rstrip(".")
    if allowed_hosts and not any(hostname == host or hostname.endswith(f".{host}") for host in allowed_hosts):
        raise UnsafeStorageUrl("Domínio não autorizado para este storage.")
    try:
        addresses = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise StorageError("Não foi possível resolver o storage.") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise UnsafeStorageUrl("Storage aponta para uma rede não pública.")
    return parsed.geturl()


def sanitize_download_name(value: str, fallback: str = "arquivo-tecnico") -> str:
    basename = os.path.basename(str(value or "").replace("\\", "/"))
    # Mantém o nome original do provider (incluindo espaços, colchetes e
    # identificadores U3/U6), removendo apenas controles e caracteres
    # incompatíveis com nomes de arquivo nos principais sistemas.
    forbidden = set('/\\:*?"<>|')
    safe = "".join(
        char for char in basename
        if char not in forbidden and ord(char) >= 32 and ord(char) != 127
    )
    return safe.strip(". ")[:180] or fallback


def filename_from_content_disposition(value: str | None) -> str | None:
    """Extrai com segurança o nome original informado pelo storage."""
    if not value:
        return None
    try:
        _disposition, options = parse_options_header(value)
    except (TypeError, ValueError):
        return None
    filename = options.get("filename")
    return sanitize_download_name(filename) if filename else None


class HttpStorageProvider:
    """Lê URLs HTTP(S) sem entregar a URL ao cliente.

    Redirecionamentos são seguidos manualmente para validar cada destino e
    evitar SSRF por redirect.
    """

    def __init__(
        self,
        *,
        allowed_hosts: set[str] | None = None,
        connect_timeout: float = 5.0,
        read_timeout: float = 45.0,
        max_redirects: int = 5,
        session: requests.Session | None = None,
    ) -> None:
        self.allowed_hosts = {host.strip().lower() for host in (allowed_hosts or set()) if host.strip()}
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.max_redirects = max_redirects
        self.session = session or requests.Session()

    def open(self, url: str, range_header: str | None = None) -> UpstreamDownload:
        current = _validate_public_http_url(url, self.allowed_hosts or None)
        response = None
        request_headers = {
            "User-Agent": "MundoDaInformatica-StorageProxy/1.0",
            "Accept-Encoding": "identity",
        }
        if range_header and range_header.startswith("bytes=") and "\n" not in range_header and "\r" not in range_header:
            request_headers["Range"] = range_header[:200]

        for redirect_index in range(self.max_redirects + 1):
            try:
                response = self.session.get(
                    current,
                    headers=request_headers,
                    stream=True,
                    allow_redirects=False,
                    timeout=(self.connect_timeout, self.read_timeout),
                )
            except requests.RequestException as exc:
                raise StorageError("Storage indisponível no momento.") from exc

            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location")
                response.close()
                if not location or redirect_index >= self.max_redirects:
                    raise StorageError("Redirecionamento inválido no storage.")
                current = _validate_public_http_url(urljoin(current, location), self.allowed_hosts or None)
                continue
            break

        if response is None or response.status_code not in {200, 206}:
            status = response.status_code if response is not None else 502
            if response is not None:
                response.close()
            raise StorageError(f"Storage respondeu com HTTP {status}.", status_code=status)

        content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
        if content_type in {"text/html", "application/xhtml+xml"}:
            response.close()
            raise StorageError(
                "O link configurado aponta para uma página, não para o arquivo direto.",
                status_code=response.status_code,
            )

        forwarded = {}
        for key in (
            "Content-Type", "Content-Length", "Content-Range", "Content-Disposition",
            "Accept-Ranges", "ETag", "Last-Modified",
        ):
            if response.headers.get(key):
                forwarded[key] = response.headers[key]
        forwarded.setdefault("Content-Type", "application/octet-stream")

        return UpstreamDownload(
            status_code=response.status_code,
            headers=forwarded,
            iterator=response.iter_content(chunk_size=128 * 1024),
            close=response.close,
        )

    def health(self, url: str) -> tuple[bool, str, int | None]:
        try:
            upstream = self.open(url, "bytes=0-0")
            upstream.close()
            return True, "online", upstream.status_code
        except StorageError as exc:
            return False, str(exc), exc.status_code


def guess_mimetype(filename: str, configured: str | None = None) -> str:
    return configured or mimetypes.guess_type(filename)[0] or "application/octet-stream"
