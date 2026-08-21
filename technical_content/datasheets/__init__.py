"""Motor multi-fonte de componentes e datasheets.

O pacote não importa a aplicação Flask. Isso mantém providers e regras de
consenso testáveis sem banco e evita acoplamento circular com ``app.py``.
"""

from .types import DatasheetCandidate, DatasheetResolution
from .normalization import normalize_manufacturer, normalize_part_number

__all__ = [
    "DatasheetCandidate",
    "DatasheetResolution",
    "normalize_manufacturer",
    "normalize_part_number",
]
