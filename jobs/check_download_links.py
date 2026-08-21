"""Valida links de storage em lotes pequenos.

Uso: ``python -m jobs.check_download_links``
"""

from datetime import datetime
import os

from app import TechnicalFile, app, db
from technical_content.storage import HttpStorageProvider


def run(limit: int = 200) -> dict[str, int]:
    result = {"checked": 0, "online": 0, "broken": 0}
    with app.app_context():
        files = TechnicalFile.query.filter_by(is_active=True).order_by(
            TechnicalFile.last_link_check_at.asc().nullsfirst(), TechnicalFile.id.asc()
        ).limit(limit).all()
        provider = HttpStorageProvider()
        storage_root = os.path.abspath(app.config["TECHNICAL_LOCAL_STORAGE_DIR"])
        for technical_file in files:
            result["checked"] += 1
            if technical_file.storage_provider == "local":
                path = os.path.abspath(os.path.join(storage_root, technical_file.provider_file_id or ""))
                online = os.path.commonpath([storage_root, path]) == storage_root and os.path.isfile(path)
                status_code = 200 if online else None
            else:
                online, _message, status_code = provider.health(
                    technical_file.provider_direct_url or technical_file.provider_url or ""
                )
            technical_file.link_status = "online" if online else "broken"
            technical_file.last_link_check_at = datetime.utcnow()
            technical_file.last_link_http_status = status_code
            result["online" if online else "broken"] += 1
        db.session.commit()
    return result


if __name__ == "__main__":
    print(run())
