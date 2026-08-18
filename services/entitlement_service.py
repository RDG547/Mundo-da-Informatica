"""Fonte única das permissões e da comunicação dos planos.

Este módulo não depende do Flask nem dos models. Assim, backend, templates e
testes podem consumir a mesma matriz sem criar dependências circulares.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


PLAN_ENTITLEMENTS: dict[str, dict[str, Any]] = {
    "free": {
        "label": "Grátis",
        "audience": "Para conhecer a plataforma",
        "description": "Ideal para quem consulta ou baixa arquivos ocasionalmente.",
        "download_limit": 1,
        "download_period": "weekly",
        "support": "Suporte em até 48h",
        "favorites_limit": 10,
        "device_limit": 1,
        "download_history_access": False,
        "download_history_limit": 0,
        "comments_limit": 3,
        "public_chat": False,
        "priority_content_request": False,
        "vip_area": False,
    },
    "premium": {
        "label": "Premium",
        "audience": "Para técnicos ativos",
        "description": "Ideal para quem trabalha regularmente com manutenção e precisa de arquivos durante a semana.",
        "download_limit": 15,
        "download_period": "weekly",
        "support": "Suporte em até 24h",
        "favorites_limit": None,
        "device_limit": 2,
        "download_history_access": True,
        "download_history_limit": 5,
        "comments_limit": 10,
        "public_chat": False,
        "priority_content_request": False,
        "vip_area": False,
    },
    "vip": {
        "label": "VIP",
        "audience": "Para assistência técnica e uso profissional intensivo",
        "description": "Ideal para profissionais que precisam de uso intensivo, suporte prioritário e busca prioritária de conteúdo.",
        "download_limit": None,
        "download_period": "unlimited",
        "support": "Suporte prioritário",
        "favorites_limit": None,
        "device_limit": 5,
        "download_history_access": True,
        "download_history_limit": None,
        "comments_limit": None,
        "public_chat": True,
        "priority_content_request": True,
        "vip_area": True,
    },
}


def normalize_plan(plan: Any) -> str:
    raw_plan = getattr(plan, "plan", plan)
    key = str(raw_plan or "free").strip().lower()
    return key if key in PLAN_ENTITLEMENTS else "free"


def get_plan_entitlements(plan: Any) -> dict[str, Any]:
    """Retorna uma cópia para impedir mutações acidentais da matriz oficial."""
    return deepcopy(PLAN_ENTITLEMENTS[normalize_plan(plan)])


def can_use_public_chat(plan: Any) -> bool:
    return bool(get_plan_entitlements(plan)["public_chat"])


def can_request_priority_content(plan: Any) -> bool:
    return bool(get_plan_entitlements(plan)["priority_content_request"])


def get_download_limit(plan: Any) -> int | None:
    return get_plan_entitlements(plan)["download_limit"]


def get_device_limit(plan: Any) -> int:
    return int(get_plan_entitlements(plan)["device_limit"])


def get_support_level(plan: Any) -> str:
    return str(get_plan_entitlements(plan)["support"])
