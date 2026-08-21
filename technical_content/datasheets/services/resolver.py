"""Orquestra providers em fallback de prioridade ou comparação paralela."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import time
from typing import Any

from .candidate_merger import merge_candidates
from ..policy import provider_query_policy
from ..providers.base import DatasheetProvider, ProviderError
from ..types import DatasheetCandidate, DatasheetResolution, ProviderTrace


@dataclass(slots=True)
class ConfiguredProvider:
    provider: DatasheetProvider
    config: Any


class DatasheetResolver:
    def __init__(self, providers: list[ConfiguredProvider], *, global_disabled: bool = False) -> None:
        self.providers = sorted(providers, key=lambda item: (int(getattr(item.config, "priority", 100)), item.provider.name))
        self.global_disabled = global_disabled

    def _consult(self, item: ConfiguredProvider, query: str) -> tuple[list[DatasheetCandidate], ProviderTrace]:
        decision = provider_query_policy(item.config, channel=item.provider.channel, global_disabled=self.global_disabled)
        if not decision.allowed:
            return [], ProviderTrace(item.provider.name, decision.status, message=decision.reason)
        started = time.monotonic()
        try:
            candidates = item.provider.search(query)
            duration = int((time.monotonic() - started) * 1000)
            return candidates, ProviderTrace(
                item.provider.name,
                "success" if candidates else "not_found",
                result_count=len(candidates),
                duration_ms=duration,
            )
        except ProviderError as exc:
            duration = int((time.monotonic() - started) * 1000)
            return [], ProviderTrace(
                item.provider.name,
                getattr(exc, "status", "failed"),
                duration_ms=duration,
                message=str(exc)[:500],
            )
        except Exception as exc:
            duration = int((time.monotonic() - started) * 1000)
            return [], ProviderTrace(item.provider.name, "failed", duration_ms=duration, message=str(exc)[:500])

    def resolve(self, query: str, *, strategy: str = "priority_fallback", max_providers: int | None = None) -> DatasheetResolution:
        strategy = strategy if strategy in {"priority_fallback", "parallel_compare", "maximum_precision"} else "priority_fallback"
        if strategy == "maximum_precision":
            strategy = "parallel_compare"
        available = self.providers
        if strategy == "priority_fallback":
            available = [item for item in available if getattr(item.config, "fallback_enabled", True)]
        active = available[:max_providers] if max_providers and max_providers > 0 else available
        candidates: list[DatasheetCandidate] = []
        traces: list[ProviderTrace] = []

        if strategy == "parallel_compare" and len(active) > 1:
            with ThreadPoolExecutor(max_workers=min(6, len(active)), thread_name_prefix="datasheet-provider") as executor:
                futures = {executor.submit(self._consult, item, query): item for item in active}
                ordered: dict[str, tuple[list[DatasheetCandidate], ProviderTrace]] = {}
                for future in as_completed(futures):
                    provider_candidates, trace = future.result()
                    ordered[futures[future].provider.name] = (provider_candidates, trace)
            for item in active:
                provider_candidates, trace = ordered[item.provider.name]
                candidates.extend(provider_candidates)
                traces.append(trace)
        else:
            for item in active:
                provider_candidates, trace = self._consult(item, query)
                candidates.extend(provider_candidates)
                traces.append(trace)
                if provider_candidates:
                    interim = merge_candidates(query, candidates)
                    threshold = max(0.0, min(1.0, float(getattr(item.config, "auto_publish_threshold", 0.95))))
                    if interim.selected and interim.confidence >= threshold and not interim.has_conflicts:
                        break

        resolution = merge_candidates(query, candidates)
        resolution.traces = traces
        return resolution
