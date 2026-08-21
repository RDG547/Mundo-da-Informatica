"""Normalização e textos SEO determinísticos para itens importados."""

from __future__ import annotations

import re
import unicodedata


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", value)).strip("-")[:220]


def category_for_file_type(file_type: str) -> str:
    normalized = (file_type or "").casefold()
    if any(token in normalized for token in ("bios", "firmware ec", "firmware me", "firmware")):
        return "BIOS"
    if any(token in normalized for token in ("boardview", "esquema")):
        return "Esquemas"
    if "driver" in normalized:
        return "Drivers"
    if "software" in normalized:
        return "Softwares"
    if "datasheet" in normalized:
        return "Datasheet"
    return "Softwares"


def build_post_copy(metadata: dict) -> dict:
    manufacturer = str(metadata.get("manufacturer") or "").strip()
    model = str(metadata.get("model") or "").strip()
    board = str(metadata.get("board_code") or "").strip()
    revision = str(metadata.get("board_revision") or "").strip()
    file_type = str(metadata.get("file_type") or "Arquivo técnico").strip()
    identity = " ".join(filter(None, [manufacturer, model, board])).strip()
    title = " - ".join(filter(None, [file_type, identity])) or file_type
    compatibility = ", ".join(filter(None, [manufacturer, model, board, f"revisão {revision}" if revision else ""]))
    content = (
        f"<p><strong>{file_type}</strong> organizado para consulta técnica"
        f"{f' do equipamento {identity}' if identity else ''}.</p>"
        f"<p>Compatibilidade informada: {compatibility or 'confirme os dados antes do uso'}.</p>"
        "<p>Antes de gravar firmware ou aplicar qualquer arquivo, confirme modelo, código e revisão da placa. "
        "Faça backup do conteúdo original sempre que possível.</p>"
    )
    seo_description = (
        f"{file_type} {identity}. Consulte compatibilidade, revisão e informações técnicas antes do uso."
    )[:200]
    return {
        "title": title[:200],
        "slug": slugify(title),
        "content": content,
        "seo_title": title[:100],
        "seo_description": seo_description,
        "category": category_for_file_type(file_type),
        "compatibility": compatibility,
        "tags": ", ".join(filter(None, [file_type, manufacturer, model, board]))[:200],
    }
