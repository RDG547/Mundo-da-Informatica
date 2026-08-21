"""Normalização conservadora de part numbers e fabricantes."""

from __future__ import annotations

import re
import unicodedata


MANUFACTURER_ALIASES = {
    "TI": "Texas Instruments",
    "TEXAS INSTRUMENTS INC": "Texas Instruments",
    "TEXAS INSTRUMENTS INCORPORATED": "Texas Instruments",
    "RICHTEK TECHNOLOGY": "Richtek",
    "RICHTEK TECHNOLOGY CORP": "Richtek",
    "STMICROELECTRONICS": "STMicroelectronics",
    "ST MICROELECTRONICS": "STMicroelectronics",
    "NXP SEMICONDUCTORS": "NXP",
    "ON SEMICONDUCTOR": "onsemi",
    "ONSEMI": "onsemi",
}


def normalize_display_text(value: str | None) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).split()).strip()


def normalize_part_number(value: str | None) -> str:
    """Normaliza pontuação sem remover sufixos eletricamente relevantes."""
    text = normalize_display_text(value).upper()
    text = text.translate(str.maketrans({"\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-"}))
    # Espaços e hífens inconsistentes não alteram a identidade para busca.
    # Letras finais continuam presentes: TPS51225C != TPS51225.
    return re.sub(r"[\s\-_]+", "", text)


def normalize_manufacturer(value: str | None) -> str:
    original = normalize_display_text(value)
    if not original:
        return ""
    raw_key = re.sub(r"[.,\u00ae\u2122]", "", original).upper().strip()
    if raw_key in MANUFACTURER_ALIASES:
        return MANUFACTURER_ALIASES[raw_key]
    key = re.sub(r"\s+(CORPORATION|CORP|INCORPORATED|INC|LTD|LIMITED|CO)$", "", raw_key).strip()
    if key in MANUFACTURER_ALIASES:
        return MANUFACTURER_ALIASES[key]
    # Para nomes ainda não mapeados, remove somente o sufixo societário
    # e preserva a capitalização usada pelo fabricante.
    return re.sub(
        r"\s+(CORPORATION|CORP|INCORPORATED|INC|LTD|LIMITED|CO)[.,]?$",
        "", original, flags=re.IGNORECASE,
    ).strip()


def looks_like_part_number(value: str | None) -> bool:
    text = normalize_display_text(value)
    if not 3 <= len(text) <= 80 or " " in text:
        return False
    return bool(re.search(r"[A-Za-z]", text) and re.search(r"\d", text) and re.fullmatch(r"[\w.+/#-]+", text))


def safe_slug(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", normalize_display_text(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-") or "componente"
