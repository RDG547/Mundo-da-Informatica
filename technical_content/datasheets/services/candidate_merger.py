"""Compara candidatos e aumenta confiança somente quando há consenso."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from .confidence import candidate_confidence
from ..normalization import normalize_manufacturer, normalize_part_number
from ..types import DatasheetCandidate, DatasheetResolution


def _unique_values(candidates: list[DatasheetCandidate], field: str) -> list[str]:
    values: list[str] = []
    for candidate in candidates:
        value = str(getattr(candidate, field, None) or "").strip()
        if value and value.casefold() not in {item.casefold() for item in values}:
            values.append(value)
    return values


def merge_candidates(query: str, candidates: list[DatasheetCandidate]) -> DatasheetResolution:
    normalized_query = normalize_part_number(query)
    resolution = DatasheetResolution(query=query, normalized_query=normalized_query, candidates=candidates)
    if not candidates:
        return resolution

    exact = [candidate for candidate in candidates if candidate.normalized_part_number == normalized_query]
    pool = exact or candidates
    pool.sort(key=lambda candidate: candidate_confidence(candidate, query), reverse=True)
    selected = replace(pool[0])

    manufacturer_groups: dict[str, list[DatasheetCandidate]] = defaultdict(list)
    for candidate in pool:
        key = normalize_manufacturer(candidate.manufacturer).casefold()
        if key:
            manufacturer_groups[key].append(candidate)
    if len(manufacturer_groups) > 1:
        resolution.conflicts["manufacturer"] = _unique_values(pool, "manufacturer")
    elif manufacturer_groups:
        best_group = max(manufacturer_groups.values(), key=lambda group: (len(group), max(item.confidence for item in group)))
        canonical = normalize_manufacturer(best_group[0].manufacturer)
        selected.manufacturer = canonical
        selected.normalized_manufacturer = canonical

    part_values = {candidate.normalized_part_number for candidate in pool if candidate.normalized_part_number}
    if len(part_values) > 1 and not exact:
        resolution.conflicts["part_number"] = _unique_values(pool, "part_number")

    for field in ("category", "package", "lifecycle_status"):
        values = _unique_values(pool, field)
        if len(values) > 1:
            resolution.conflicts[field] = values
        elif values and not getattr(selected, field):
            setattr(selected, field, values[0])

    merged_specs = dict(selected.specifications)
    for candidate in pool[1:]:
        for key, value in candidate.specifications.items():
            merged_specs.setdefault(key, value)
    selected.specifications = merged_specs

    scores = [candidate_confidence(candidate, query) for candidate in pool]
    agreement_bonus = min(0.12, max(0, len({candidate.provider for candidate in pool}) - 1) * 0.04)
    consensus = (max(scores) * 0.65) + (sum(scores) / len(scores) * 0.35) + agreement_bonus
    if resolution.conflicts:
        consensus -= min(0.25, len(resolution.conflicts) * 0.07)
    resolution.confidence = max(0.0, min(1.0, consensus))
    selected.confidence = resolution.confidence
    resolution.selected = selected
    return resolution
