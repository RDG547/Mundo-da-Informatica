"""Motor incremental de conteúdo técnico.

Os módulos deste pacote não importam ``app.py``. Isso mantém parsing, storage e
provedores testáveis e evita ciclos com a aplicação Flask monolítica legada.
"""

from .parsers import (
    ArchiveSafetyError,
    ParsedTechnicalName,
    inspect_zip_archive,
    parse_technical_filename,
    sha256_file,
)

__all__ = [
    "ArchiveSafetyError",
    "ParsedTechnicalName",
    "inspect_zip_archive",
    "parse_technical_filename",
    "sha256_file",
]
