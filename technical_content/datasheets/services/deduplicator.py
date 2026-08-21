from __future__ import annotations

from collections.abc import Callable

from ..normalization import normalize_manufacturer, normalize_part_number


def component_identity(manufacturer: str | None, part_number: str | None) -> tuple[str, str]:
    return normalize_manufacturer(manufacturer).casefold(), normalize_part_number(part_number)


def find_duplicate(
    manufacturer: str | None,
    part_number: str | None,
    lookup: Callable[[str, str], int | None],
) -> int | None:
    normalized_manufacturer, normalized_part = component_identity(manufacturer, part_number)
    if not normalized_part:
        return None
    return lookup(normalized_manufacturer, normalized_part)
