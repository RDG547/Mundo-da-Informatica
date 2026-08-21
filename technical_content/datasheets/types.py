"""Objetos temporários usados durante a resolução de datasheets."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class DatasheetCandidate:
    provider: str
    external_id: str
    part_number: str
    normalized_part_number: str
    manufacturer: str | None = None
    normalized_manufacturer: str | None = None
    title: str | None = None
    description: str | None = None
    category: str | None = None
    subcategory: str | None = None
    package: str | None = None
    lifecycle_status: str | None = None
    datasheet_reference: str | None = None
    document_title: str | None = None
    document_revision: str | None = None
    document_date: str | None = None
    document_language: str | None = None
    pages: int | None = None
    confidence: float = 0.0
    exact_match: bool = False
    raw_fingerprint: str | None = None
    specifications: dict[str, str] = field(default_factory=dict)

    def public_summary(self, *, include_values: bool) -> dict[str, Any]:
        """Retorna somente o preview normalizado, nunca o payload bruto."""
        result: dict[str, Any] = {
            "provider": self.provider,
            "confidence": round(max(0.0, min(1.0, self.confidence)), 4),
            "exact_match": self.exact_match,
            "raw_fingerprint": self.raw_fingerprint,
        }
        if include_values:
            allowed = asdict(self)
            allowed.pop("raw_fingerprint", None)
            result.update(allowed)
        return result


@dataclass(slots=True)
class ProviderTrace:
    provider: str
    status: str
    result_count: int = 0
    duration_ms: int = 0
    message: str | None = None
    credits_remaining: int | None = None


@dataclass(slots=True)
class DatasheetResolution:
    query: str
    normalized_query: str
    candidates: list[DatasheetCandidate] = field(default_factory=list)
    selected: DatasheetCandidate | None = None
    confidence: float = 0.0
    conflicts: dict[str, list[str]] = field(default_factory=dict)
    traces: list[ProviderTrace] = field(default_factory=list)
    duplicate_component_id: int | None = None

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts)

    @property
    def found(self) -> bool:
        return self.selected is not None
