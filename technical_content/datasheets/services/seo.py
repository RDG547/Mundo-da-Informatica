from __future__ import annotations


def component_seo(part_number: str, manufacturer: str | None) -> tuple[str, str]:
    maker = manufacturer or "componente eletrônico"
    return (
        f"{part_number} Datasheet — {maker} | Mundo da Informática",
        f"Consulte dados técnicos confirmados, encapsulamento, situação e documentos do {part_number} da {maker}.",
    )
