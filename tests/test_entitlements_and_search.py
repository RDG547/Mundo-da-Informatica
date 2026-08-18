import pytest

from app import Post, get_post_search_score, normalize_sha256
from services.entitlement_service import (
    can_request_priority_content,
    can_use_public_chat,
    get_plan_entitlements,
)


def test_canonical_entitlement_matrix():
    free = get_plan_entitlements("free")
    premium = get_plan_entitlements("premium")
    vip = get_plan_entitlements("vip")

    assert (free["download_limit"], free["download_period"]) == (1, "weekly")
    assert free["comments_limit"] == 3
    assert free["favorites_limit"] == 10
    assert free["device_limit"] == 1
    assert not free["download_history_access"]

    assert (premium["download_limit"], premium["download_period"]) == (15, "weekly")
    assert premium["comments_limit"] == 10
    assert premium["favorites_limit"] is None
    assert premium["device_limit"] == 2
    assert premium["download_history_limit"] == 5

    assert vip["download_limit"] is None
    assert vip["comments_limit"] is None
    assert vip["device_limit"] == 5
    assert can_use_public_chat("vip")
    assert not can_use_public_chat("premium")
    assert can_request_priority_content("vip")
    assert not can_request_priority_content("free")


def test_exact_board_code_has_search_priority():
    exact_board = Post(
        title="BIOS Lenovo",
        content="Arquivo técnico",
        download_link="https://example.test/a.bin",
        board_code="LA-K091P",
    )
    title_only = Post(
        title="Referência LA-K091P para diagnóstico",
        content="Material auxiliar",
        download_link="https://example.test/b.pdf",
    )

    assert get_post_search_score("la k091p", exact_board) < get_post_search_score("la k091p", title_only)


def test_sha256_validation():
    valid = "A" * 64
    assert normalize_sha256(valid) == valid.lower()
    assert normalize_sha256("") is None
    with pytest.raises(ValueError):
        normalize_sha256("1234")
