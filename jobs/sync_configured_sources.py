"""Sincroniza fontes oficiais/licenciadas configuradas, sem scraping.

Mouser e DigiKey usam suas APIs oficiais. Dell, HP, Lenovo e a fonte
licenciada exigem um feed JSON normalizado autorizado; catálogos CAB ou
páginas HTML não são tratados como API. Cada registro vira um preview e
somente a política central decide se pode ser autopublicado.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
import re
from typing import TypedDict
from urllib.parse import urlparse

from app import (
    ContentSource,
    ImportItem,
    ImportJob,
    TechnicalResource,
    _append_import_item,
    _merge_parsed_metadata,
    _provider_records,
    app,
    db,
    get_technical_automation_settings,
    publish_import_item,
    technical_auto_publish_decision,
)
from technical_content.providers import LicensedJsonFeedProvider, ProviderError


SOURCE_FEED_ENV = {
    "Dell": ("DELL_CATALOG_URL", "DELL_CATALOG_TOKEN"),
    "HP": ("HP_CATALOG_URL", "HP_CATALOG_TOKEN"),
    "Lenovo": ("LENOVO_CATALOG_URL", "LENOVO_CATALOG_TOKEN"),
    "Feed licenciado": ("LICENSED_FEED_URL", "LICENSED_FEED_TOKEN"),
}


class SyncResult(TypedDict):
    sources: int
    items: int
    published: int
    duplicates: int
    errors: int
    messages: list[str]


def _part_numbers(source: ContentSource) -> list[str]:
    configured = source.configuration().get("part_numbers", [])
    if isinstance(configured, str):
        configured = re.split(r"[,;\n]+", configured)
    else:
        configured = list(configured) if isinstance(configured, list) else []
    env_key = f"TECHNICAL_SYNC_{re.sub(r'[^A-Z0-9]+', '_', source.name.upper()).strip('_')}_PART_NUMBERS"
    configured.extend(re.split(r"[,;\n]+", os.environ.get(env_key, "")))
    result: list[str] = []
    for value in configured:
        normalized = str(value or "").strip()[:160]
        if normalized and normalized.lower() not in {item.lower() for item in result}:
            result.append(normalized)
    return result[:100]


def _records_for_source(source: ContentSource, part_number: str):
    if source.name.lower() in {"mouser", "digikey"}:
        return _provider_records(source.name.lower(), part_number)

    env_names = SOURCE_FEED_ENV.get(source.name)
    if not env_names:
        raise ProviderError("Esta fonte não possui conector oficial configurado.")
    endpoint = (os.environ.get(env_names[0]) or "").strip()
    token = (os.environ.get(env_names[1]) or "").strip() or None
    if not endpoint:
        raise ProviderError(f"Configure {env_names[0]} com um feed JSON oficial/licenciado.")
    path = urlparse(endpoint).path.lower()
    if path.endswith((".cab", ".exe", ".msi", ".html", ".htm")):
        raise ProviderError(
            f"{env_names[0]} não é um feed JSON. Use um worker/extrator oficial e exponha um feed normalizado autorizado."
        )
    return LicensedJsonFeedProvider(source.name, endpoint, token).lookup(part_number)


def _version_from_record(record) -> str | None:
    raw = record.raw if isinstance(record.raw, dict) else {}
    for key in ("external_version", "version", "Version", "revision", "Revision"):
        value = raw.get(key)
        if value not in (None, ""):
            return str(value)[:120]
    return None


def _external_id_from_record(record) -> str:
    raw = record.raw if isinstance(record.raw, dict) else {}
    for key in ("external_id", "id", "Id", "softpaq", "package_id"):
        value = raw.get(key)
        if value not in (None, ""):
            return str(value)[:255]
    return f"{record.source}:{record.part_number}:{_version_from_record(record) or record.product_url or record.datasheet_url or 'metadata'}"[:255]


def _existing_resource(source: ContentSource, record):
    external_id = _external_id_from_record(record)
    existing = TechnicalResource.query.filter_by(external_id=external_id).first()
    if existing:
        return existing
    query = TechnicalResource.query.filter(
        db.func.lower(TechnicalResource.source_provider) == source.name.lower(),
        db.func.lower(TechnicalResource.part_number) == record.part_number.lower(),
    )
    version = _version_from_record(record)
    if version:
        query = query.filter(TechnicalResource.external_version == version)
    elif record.product_url:
        query = query.filter(TechnicalResource.source_reference == record.product_url)
    return query.first()


def _append_record(job: ImportJob, source: ContentSource, record) -> ImportItem:
    version = _version_from_record(record)
    metadata = _merge_parsed_metadata(record.part_number, {
        "manufacturer": record.manufacturer,
        "model": record.part_number,
        "part_number": record.part_number,
        "file_type": "Datasheet" if source.provider_type in {"api", "licensed"} else "BIOS oficial",
        "source_provider": source.name,
        "source_url": record.product_url,
        "provider_url": record.datasheet_url,
        "distribution_policy": "remote_only" if record.datasheet_url else "metadata_only",
        "license_status": "official_metadata",
        "title": record.title,
        "description": record.description,
        "version": version,
        "external_version": version,
        "external_id": _external_id_from_record(record),
        "confidence": 92 if source.trust_level == "A" else 88,
    })
    item = _append_import_item(
        job,
        metadata,
        source_name=record.part_number,
        raw={"provider": record.source, "record": record.raw},
    )
    existing = _existing_resource(source, record)
    if existing:
        item.status = "duplicate"
        item.resource_id = existing.id
        item.decision_reason = "Versão externa já sincronizada."
        job.review_count = max(0, job.review_count - 1)
        job.duplicate_count += 1
    return item


def run(source_names: set[str] | None = None, reviewer_id: int | None = None) -> SyncResult:
    result: SyncResult = {
        "sources": 0, "items": 0, "published": 0,
        "duplicates": 0, "errors": 0, "messages": [],
    }
    with app.app_context():
        automation = get_technical_automation_settings()
        if not automation["feature_enabled"] or not automation["configured_enabled"] or automation["mode"] == "off":
            result["messages"].append("O motor de automação está desativado.")
            return result

        query = ContentSource.query.filter_by(enabled=True)
        if source_names:
            query = query.filter(ContentSource.name.in_(list(source_names)))
        sources = query.order_by(ContentSource.id.asc()).all()
        for source in sources:
            if source.provider_type in {"manual", "contribution"}:
                continue
            result["sources"] += 1
            parts = _part_numbers(source)
            if not parts:
                source.last_error = "Nenhum part number monitorado foi configurado."
                result["messages"].append(f"{source.name}: {source.last_error}")
                result["errors"] += 1
                db.session.commit()
                continue

            job = ImportJob(
                job_type="source_sync", source=source.name, status="processing",
                automation_mode=automation["mode"], created_by=reviewer_id,
                started_at=datetime.utcnow(), created_at=datetime.utcnow(),
            )
            db.session.add(job)
            db.session.flush()
            source_errors: list[str] = []
            new_items: list[ImportItem] = []
            for part_number in parts:
                try:
                    records = _records_for_source(source, part_number)
                    if not records:
                        source_errors.append(f"{part_number}: nenhum registro encontrado.")
                    for record in records:
                        item = _append_record(job, source, record)
                        new_items.append(item)
                        result["items"] += 1
                        if item.status == "duplicate":
                            result["duplicates"] += 1
                except (ProviderError, ValueError) as exc:
                    source_errors.append(f"{part_number}: {exc}")
                    job.error_count += 1
                    result["errors"] += 1

            job.status = "reviewing" if new_items else "error"
            job.log_summary = "\n".join(source_errors) if source_errors else "Sincronização concluída."
            source.last_sync_at = datetime.utcnow()
            source.last_error = "\n".join(source_errors)[:4000] or None
            db.session.commit()

            for item in new_items:
                if item.status == "duplicate":
                    continue
                allowed, reason = technical_auto_publish_decision(item, source)
                item.decision_reason = reason
                db.session.commit()
                if allowed:
                    try:
                        publish_import_item(item, reviewer_id=reviewer_id, automatic=True)
                        result["published"] += 1
                    except ValueError as exc:
                        item.decision_reason = str(exc)
                        db.session.commit()

            terminal = {"published", "duplicate", "rejected", "error"}
            if new_items and all(item.status in terminal for item in job.items):
                job.status = "completed"
                job.finished_at = datetime.utcnow()
                db.session.commit()
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
