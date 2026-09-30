"""Unit tests for the protocol constants and argument validation."""

from __future__ import annotations

import pytest

from petmcp.protocol import PROTOCOL_VERSION, client_meta, has_modern_envelope
from petmcp.tools.list_pets import build_filter_params


def test_protocol_version_is_2026_07_28() -> None:
    assert PROTOCOL_VERSION == "2026-07-28"


def test_client_meta_has_required_keys() -> None:
    meta = client_meta()
    assert meta["io.modelcontextprotocol/protocolVersion"] == "2026-07-28"
    assert "io.modelcontextprotocol/clientCapabilities" in meta
    assert has_modern_envelope({"name": "list_pets", "_meta": meta})


def test_has_modern_envelope_rejects_missing_fields() -> None:
    assert not has_modern_envelope({})
    assert not has_modern_envelope({"_meta": {}})
    assert not has_modern_envelope({"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}})


def test_build_filter_params_empty() -> None:
    assert build_filter_params({}) == {}


def test_build_filter_params_drops_none_and_blank() -> None:
    assert build_filter_params({"q": None, "doctor": "  ", "species": "犬"}) == {"species": "犬"}


def test_build_filter_params_strips_strings() -> None:
    assert build_filter_params({"name": "  旺财  "}) == {"name": "旺财"}


def test_build_filter_params_full_set() -> None:
    result = build_filter_params(
        {
            "q": "肠胃炎",
            "species": "猫",
            "status": "住院中",
            "min": 100,
            "max": 999.5,
            "sortBy": "totalCost",
            "order": "desc",
            "page": 2,
            "pageSize": 50,
        }
    )
    assert result == {
        "q": "肠胃炎",
        "species": "猫",
        "status": "住院中",
        "min": 100,
        "max": 999.5,
        "sortBy": "totalCost",
        "order": "desc",
        "page": 2,
        "pageSize": 50,
    }


@pytest.mark.parametrize(
    "arguments",
    [
        {"species": "龙"},
        {"status": "已死亡"},
        {"sortBy": "price"},
        {"order": "up"},
        {"page": 0},
        {"page": True},
        {"pageSize": 0},
        {"pageSize": 101},
        {"pageSize": "20"},
        {"min": -1},
        {"max": "100"},
        {"min": 500, "max": 100},
        {"unknownParam": 1},
    ],
)
def test_build_filter_params_rejects_bad_values(arguments: dict) -> None:
    with pytest.raises(ValueError):
        build_filter_params(arguments)
