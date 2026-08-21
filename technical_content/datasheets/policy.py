"""Decisões explícitas de consulta, persistência e publicação."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


VALID_MODES = {"disabled", "semi_automatic", "automatic"}
PDF_POLICIES = {
    "metadata_only", "reference_only", "stream_allowed", "mirror_allowed",
    "internal_storage_allowed", "manual_review",
}


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    status: str
    reason: str


def provider_query_policy(config: Any, *, channel: str, global_disabled: bool = False) -> PolicyDecision:
    if global_disabled:
        return PolicyDecision(False, "blocked_by_policy", "O kill switch global está ativo.")
    if not getattr(config, "enabled", False) or getattr(config, "mode", "disabled") == "disabled":
        return PolicyDecision(False, "disabled", "Provider desativado pelo administrador.")
    if channel == "api" and not getattr(config, "api_enabled", False):
        return PolicyDecision(False, "disabled", "Consulta por API desativada.")
    if channel == "html":
        if not getattr(config, "html_discovery_enabled", False):
            return PolicyDecision(False, "disabled", "HTML discovery desativado.")
        permission = bool(
            getattr(config, "written_permission_confirmed", False)
            or getattr(config, "source_policy_allows_html_discovery", False)
        )
        if not permission:
            return PolicyDecision(False, "blocked_by_policy", "HTML discovery exige autorização registrada.")
        if not getattr(config, "robots_allowed", False):
            return PolicyDecision(False, "blocked_by_policy", "robots.txt ainda não foi validado como permitido.")
    circuit_until = getattr(config, "circuit_open_until", None)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if circuit_until and circuit_until > now:
        return PolicyDecision(False, "temporarily_unhealthy", "Circuit breaker temporariamente aberto.")
    return PolicyDecision(True, "ready", "Consulta permitida pela política registrada.")


def persistence_policy(config: Any) -> PolicyDecision:
    if not getattr(config, "metadata_persistence_allowed", False):
        return PolicyDecision(False, "metadata_ephemeral", "A fonte permite apenas uso temporário para descoberta/comparação.")
    return PolicyDecision(True, "metadata_allowed", "Persistência de metadados autorizada.")


def publication_policy(
    config: Any,
    *,
    confidence: float,
    has_conflicts: bool,
    duplicate: bool,
    required_fields_present: bool,
    global_auto_publish: bool,
) -> PolicyDecision:
    if getattr(config, "mode", "disabled") != "automatic":
        return PolicyDecision(False, "needs_review", "Modo semiautomático exige aprovação administrativa.")
    if not global_auto_publish:
        return PolicyDecision(False, "needs_review", "Autopublicação global está desativada.")
    if not getattr(config, "public_republish_allowed", False):
        return PolicyDecision(False, "blocked_by_policy", "A fonte não possui autorização para republicação pública.")
    if not getattr(config, "written_permission_confirmed", False):
        return PolicyDecision(False, "blocked_by_policy", "A republicação exige autorização escrita confirmada.")
    if not getattr(config, "metadata_persistence_allowed", False):
        return PolicyDecision(False, "blocked_by_policy", "Persistência dos metadados não está autorizada.")
    if getattr(config, "provider_status", "not_configured") != "online":
        return PolicyDecision(False, "needs_review", "Provider sem estado de saúde confirmado para autopublicação.")
    if has_conflicts:
        return PolicyDecision(False, "needs_review", "As fontes apresentam conflito em campos essenciais.")
    if duplicate:
        return PolicyDecision(False, "duplicate", "O componente já existe no acervo.")
    if not required_fields_present:
        return PolicyDecision(False, "needs_review", "Part number e fabricante são obrigatórios.")
    threshold = max(0.0, min(1.0, float(getattr(config, "auto_publish_threshold", 0.95))))
    if confidence < threshold:
        return PolicyDecision(False, "needs_review", f"Confiança {confidence:.0%} abaixo do limite {threshold:.0%}.")
    return PolicyDecision(True, "approved", "Resultado elegível para publicação automática.")


def pdf_delivery_policy(config: Any, requested_action: str) -> PolicyDecision:
    mapping = {
        "reference": "pdf_reference_allowed",
        "stream": "pdf_stream_allowed",
        "mirror": "pdf_mirror_allowed",
    }
    field = mapping.get(requested_action)
    if not field or not getattr(config, field, False):
        return PolicyDecision(False, "blocked_by_policy", "A licença registrada não permite esta forma de entrega do PDF.")
    return PolicyDecision(True, f"{requested_action}_allowed", "Entrega permitida pela política da fonte.")
