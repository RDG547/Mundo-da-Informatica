"""Enfileira part numbers monitorados e demandas públicas sem consulta ampla.

Uso: ``python -m jobs.sync_datasheets``. O processamento na mesma execução
é opt-in por ``DATASHEET_SYNC_PROCESS=true``.
"""

from __future__ import annotations

import os
import re

from app import DatasheetDemand, TechnicalResource, app, enqueue_datasheet, looks_like_part_number
from jobs.process_datasheet_queue import run as process_queue


def run() -> dict[str, int | bool | dict]:
    raw = os.environ.get("DATASHEET_SYNC_PART_NUMBERS", "")
    monitored = [value.strip() for value in re.split(r"[,;\n]+", raw) if looks_like_part_number(value)]
    demand_limit = max(0, min(100, int(os.environ.get("DATASHEET_SYNC_DEMAND_LIMIT", "20"))))
    result: dict[str, int | bool | dict] = {"created": 0, "existing": 0, "demands": 0, "processed": False}
    with app.app_context():
        entries = [(value, None, 1000, None, None) for value in monitored]
        resource_limit = max(0, min(1000, int(os.environ.get("DATASHEET_SYNC_RESOURCE_LIMIT", "100"))))
        if resource_limit:
            resources = TechnicalResource.query.filter(
                TechnicalResource.part_number.isnot(None),
                TechnicalResource.part_number != "",
            ).order_by(TechnicalResource.updated_at.desc()).limit(resource_limit).all()
            entries.extend(
                (resource.part_number, resource.manufacturer, 100 + int(bool(resource.board_id)), resource.board_id, resource.id)
                for resource in resources
                if looks_like_part_number(resource.part_number)
            )
            result["resources"] = len(resources)
        if demand_limit:
            demands = DatasheetDemand.query.order_by(
                DatasheetDemand.request_count.desc(), DatasheetDemand.last_requested_at.desc(),
            ).limit(demand_limit).all()
            entries.extend((demand.display_query, None, min(999, demand.request_count), None, None) for demand in demands)
            result["demands"] = len(demands)
        for part_number, manufacturer, priority, board_id, resource_id in entries:
            _item, created = enqueue_datasheet(
                part_number, manufacturer, priority=priority, board_id=board_id, resource_id=resource_id,
            )
            result["created" if created else "existing"] = int(result["created" if created else "existing"]) + 1
    if os.environ.get("DATASHEET_SYNC_PROCESS", "false").lower() in {"1", "true", "yes", "on"}:
        result["processed"] = True
        result["processing_result"] = process_queue()
    return result


if __name__ == "__main__":
    print(run())
