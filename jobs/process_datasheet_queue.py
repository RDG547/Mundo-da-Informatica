"""Processa a fila multi-fonte respeitando modos, permissões e kill switches.

Uso: ``python -m jobs.process_datasheet_queue``
"""

from __future__ import annotations

import os

from app import (
    DatasheetImportQueue, DatasheetProviderConfig, app, build_configured_datasheet_providers,
    db, get_datasheet_settings, process_datasheet_queue_item,
)


def run(limit: int | None = None) -> dict[str, int | bool | str]:
    result: dict[str, int | bool | str] = {
        "enabled": False, "paused": False, "processed": 0, "published": 0,
        "review": 0, "not_found": 0, "blocked": 0, "failed": 0,
    }
    with app.app_context():
        settings = get_datasheet_settings()
        result["enabled"] = bool(settings["feature_enabled"] and settings["configured_enabled"])
        result["paused"] = bool(settings["paused"])
        if not result["enabled"] or result["paused"]:
            result["reason"] = "Motor desativado ou pausado; nenhum item foi consultado."
            return result
        configured_limit = int(os.environ.get("DATASHEET_QUEUE_JOB_LIMIT", "25"))
        job_limit = max(1, min(500, int(limit if limit is not None else configured_limit)))
        provider_configs = DatasheetProviderConfig.query.filter(
            DatasheetProviderConfig.enabled.is_(True),
            DatasheetProviderConfig.mode != "disabled",
        ).order_by(DatasheetProviderConfig.priority.asc()).all()
        configured = build_configured_datasheet_providers(provider_configs)
        if configured:
            job_limit = min(job_limit, min(max(1, item.config.max_items_per_job) for item in configured))
        items = DatasheetImportQueue.query.filter_by(status="queued").order_by(
            DatasheetImportQueue.priority.desc(), DatasheetImportQueue.created_at.asc(),
        ).limit(job_limit).all()
        for queue_item in items:
            item_id = queue_item.id
            try:
                process_datasheet_queue_item(
                    queue_item, configured_providers=configured, provider_configs=provider_configs,
                )
            except Exception as exc:  # um provider não interrompe o lote inteiro
                db.session.rollback()
                queue_item = db.session.get(DatasheetImportQueue, item_id)
                queue_item.status = "failed"
                queue_item.error_message = str(exc)[:4000]
                db.session.commit()
            result["processed"] = int(result["processed"]) + 1
            status = queue_item.status
            if status == "published":
                result["published"] = int(result["published"]) + 1
            elif status in {"needs_review", "approved", "duplicate"}:
                result["review"] = int(result["review"]) + 1
            elif status == "not_found":
                result["not_found"] = int(result["not_found"]) + 1
            elif status == "blocked_by_policy":
                result["blocked"] = int(result["blocked"]) + 1
            elif status == "failed":
                result["failed"] = int(result["failed"]) + 1
    return result


if __name__ == "__main__":
    print(run())
