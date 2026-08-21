"""Processa previews elegíveis à automação completa.

Uso: ``python -m jobs.process_import_queue``
"""

from app import (
    ContentSource,
    ImportItem,
    app,
    db,
    publish_import_item,
    technical_auto_publish_decision,
)


def run(limit: int = 100) -> dict[str, int]:
    result = {"checked": 0, "published": 0, "review": 0, "errors": 0}
    with app.app_context():
        items = ImportItem.query.filter(
            ImportItem.status.in_(["pending_review", "needs_review"])
        ).order_by(ImportItem.created_at.asc()).limit(limit).all()
        for item in items:
            result["checked"] += 1
            source = ContentSource.query.filter(
                db.func.lower(ContentSource.name) == item.job.source.lower()
            ).first()
            allowed, reason = technical_auto_publish_decision(item, source)
            item.decision_reason = reason
            db.session.commit()
            if not allowed:
                result["review"] += 1
                continue
            try:
                publish_import_item(item, reviewer_id=None, automatic=True)
                result["published"] += 1
            except Exception as exc:  # registra sem parar toda a fila
                db.session.rollback()
                item = db.session.get(ImportItem, item.id)
                item.status = "error"
                item.error_message = str(exc)[:2000]
                db.session.commit()
                result["errors"] += 1
    return result


if __name__ == "__main__":
    print(run())
