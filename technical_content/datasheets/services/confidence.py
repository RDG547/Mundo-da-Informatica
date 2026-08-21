"""Pontuação explicável de candidatos."""

from __future__ import annotations

from ..types import DatasheetCandidate


def candidate_confidence(candidate: DatasheetCandidate, query: str) -> float:
    score = max(0.0, min(1.0, candidate.confidence)) * 0.45
    if candidate.exact_match:
        score += 0.35
    if candidate.manufacturer:
        score += 0.08
    if candidate.category:
        score += 0.03
    if candidate.package:
        score += 0.03
    if candidate.datasheet_reference:
        score += 0.04
    if candidate.specifications:
        score += 0.02
    return max(0.0, min(1.0, score))
