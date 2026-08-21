"""Tradução determinística de nomes técnicos; IA não é obrigatória."""

from __future__ import annotations

from typing import Callable


TECHNICAL_TERMS_PTBR = {
    "Input Voltage": "Tensão de entrada",
    "Output Voltage": "Tensão de saída",
    "Supply Voltage": "Tensão de alimentação",
    "Operating Temperature": "Temperatura de operação",
    "Package": "Encapsulamento",
    "Frequency": "Frequência",
    "Power": "Potência",
    "Current": "Corrente",
}


def translate_specifications(specifications: dict[str, str]) -> dict[str, str]:
    return {TECHNICAL_TERMS_PTBR.get(key, key): value for key, value in specifications.items()}


def generate_component_summary(
    part_number: str,
    manufacturer: str | None,
    category: str | None = None,
    *,
    ai_generator: Callable[..., str] | None = None,
) -> str:
    if ai_generator:
        try:
            generated = str(ai_generator(part_number=part_number, manufacturer=manufacturer, category=category) or "").strip()
            if generated:
                return generated[:2000]
        except Exception:
            pass
    maker = manufacturer or "fabricante ainda não confirmado"
    category_copy = f", classificado como {category}," if category else ""
    return (
        f"O {part_number} é um componente eletrônico da {maker}{category_copy} cadastrado na "
        "biblioteca técnica do Mundo da Informática. Consulte as informações confirmadas e os "
        "documentos relacionados disponíveis nesta página."
    )
