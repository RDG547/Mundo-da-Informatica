"""Verifica configuração dos providers e links cuja entrega foi autorizada."""

from __future__ import annotations

from datetime import datetime, timedelta
import os

from app import (
    DatasheetDocument, DatasheetProviderConfig, DatasheetProviderEvent, app, build_configured_datasheet_providers,
    db, ensure_default_datasheet_providers,
)
from technical_content.storage import HttpStorageProvider


def run(document_limit: int = 100) -> dict[str, int]:
    result = {"providers": 0, "ready": 0, "not_configured": 0, "documents": 0, "online": 0, "broken": 0, "events_pruned": 0}
    with app.app_context():
        ensure_default_datasheet_providers()
        configs = DatasheetProviderConfig.query.order_by(DatasheetProviderConfig.priority.asc()).all()
        configured = {item.provider.name: item.provider for item in build_configured_datasheet_providers(configs)}
        for config in configs:
            result["providers"] += 1
            cutoff = datetime.utcnow() - timedelta(days=max(1, int(config.retention_days or 30)))
            result["events_pruned"] += DatasheetProviderEvent.query.filter(
                DatasheetProviderEvent.provider == config.provider_name,
                DatasheetProviderEvent.created_at < cutoff,
            ).delete(synchronize_session=False)
            provider = configured.get(config.provider_name)
            if not provider or not provider.is_enabled():
                config.provider_status = "not_configured"
                result["not_configured"] += 1
                continue
            health = provider.health_check()
            if health.get("online"):
                config.provider_status = "ready"
                config.last_success_at = datetime.utcnow()
                result["ready"] += 1
                if hasattr(provider, "credit_balance"):
                    try:
                        config.credits_remaining = provider.credit_balance()
                        config.last_credit_check_at = datetime.utcnow()
                    except Exception as exc:
                        app.logger.info("Saldo de créditos indisponível para %s: %s", config.provider_name, exc)
            else:
                config.provider_status = str(health.get("status") or "failed")[:40]
                config.last_error_at = datetime.utcnow()
                config.last_error_message = str(health.get("message") or "Provider indisponível")[:2000]
        db.session.commit()

        allowed_hosts = {host.strip().lower() for host in os.environ.get("DATASHEET_STORAGE_ALLOWED_HOSTS", "").split(",") if host.strip()}
        storage = HttpStorageProvider(allowed_hosts=allowed_hosts)
        documents = DatasheetDocument.query.filter(
            DatasheetDocument.is_active.is_(True),
            DatasheetDocument.distribution_policy.in_(["stream_allowed", "mirror_allowed"]),
            DatasheetDocument.source_reference.isnot(None),
        ).order_by(DatasheetDocument.updated_at.asc()).limit(max(1, min(1000, int(document_limit)))).all()
        for document in documents:
            result["documents"] += 1
            online, _message, _status = storage.health(document.source_reference)
            document.verification_status = "online" if online else "broken"
            result["online" if online else "broken"] += 1
        db.session.commit()
    return result


if __name__ == "__main__":
    print(run())
