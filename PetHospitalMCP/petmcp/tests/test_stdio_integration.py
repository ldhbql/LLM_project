"""End-to-end tests over real stdin/stdout against a live server process."""

from __future__ import annotations

import os
import uuid

import httpx2
import pytest

from petmcp.protocol import client_meta

SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"


def _api_base() -> str:
    return os.environ.get("PET_API_URL", "http://127.0.0.1:8080").rstrip("/")


def test_discover(stdio_server, modern_meta) -> None:
    result = stdio_server.call("server/discover", {}, meta=modern_meta)["result"]
    assert result["resultType"] == "complete"
    assert result["supportedVersions"] == ["2026-07-28"]
    assert set(result["capabilities"].keys()) == {"tools"}
    assert result["ttlMs"] == 3_600_000
    assert result["cacheScope"] == "public"
    assert result["_meta"][SERVER_INFO_KEY]["name"] == "pet-hospital-mcp"
    assert isinstance(result["instructions"], str) and result["instructions"]


def test_tools_list_is_deterministic_and_cached(stdio_server, modern_meta) -> None:
    first = stdio_server.call("tools/list", {}, meta=modern_meta, request_id=1)["result"]
    assert first["resultType"] == "complete"
    assert first["ttlMs"] == 3_600_000
    assert first["cacheScope"] == "public"
    assert [tool["name"] for tool in first["tools"]] == ["list_pets", "add_pet"]

    second = stdio_server.call("tools/list", {}, meta=client_meta(), request_id=2)["result"]
    assert [tool["name"] for tool in second["tools"]] == [tool["name"] for tool in first["tools"]]


def test_missing_client_capabilities_is_invalid_params(stdio_server) -> None:
    meta = client_meta()
    del meta["io.modelcontextprotocol/clientCapabilities"]
    response = stdio_server.call("tools/list", {}, meta=meta)
    assert response["error"]["code"] == -32602


def test_unsupported_protocol_version(stdio_server) -> None:
    response = stdio_server.call("tools/list", {}, meta=client_meta(protocol_version="2025-11-25"))
    assert response["error"]["code"] == -32022
    assert response["error"]["data"]["supported"] == ["2026-07-28"]
    assert response["error"]["data"]["requested"] == "2025-11-25"


def test_unknown_tool_is_protocol_error(stdio_server, modern_meta) -> None:
    response = stdio_server.call("tools/call", {"name": "nope", "arguments": {}}, meta=modern_meta)
    assert response["error"]["code"] == -32602


def test_unknown_method_and_resource_are_method_not_found(stdio_server, modern_meta) -> None:
    assert stdio_server.call("ping", {}, meta=modern_meta, request_id=1)["error"]["code"] == -32601
    assert stdio_server.call("resources/list", {}, meta=modern_meta, request_id=2)["error"]["code"] == -32601


def test_tools_call_list_pets_filters(stdio_server, modern_meta) -> None:
    response = stdio_server.call(
        "tools/call",
        {"name": "list_pets", "arguments": {"species": "犬", "pageSize": 2}},
        meta=modern_meta,
    )
    result = response["result"]
    assert result["resultType"] == "complete"

    if result.get("isError"):
        pytest.skip(f"upstream unavailable: {result['content'][0]['text']}")

    structured = result["structuredContent"]
    assert structured["pageSize"] == 2
    assert isinstance(structured["items"], list)
    assert all(pet["species"] == "犬" for pet in structured["items"])
    assert "items" in result["content"][0]["text"]
    assert "totalCost" in structured


def test_tools_call_bad_arguments_is_tool_execution_error(stdio_server, modern_meta) -> None:
    response = stdio_server.call(
        "tools/call",
        {"name": "list_pets", "arguments": {"page": 0}},
        meta=modern_meta,
    )
    result = response["result"]
    assert result["isError"] is True
    assert "page" in result["content"][0]["text"]


def test_tools_call_add_pet_creates_and_cleans_up(stdio_server, modern_meta) -> None:
    unique = "MCP测试-" + uuid.uuid4().hex[:8]
    response = stdio_server.call(
        "tools/call",
        {
            "name": "add_pet",
            "arguments": {
                "name": unique,
                "species": "犬",
                "ownerName": "MCP测试主人",
                "ownerPhone": "13900000000",
                "doctor": "李医生",
                "disease": "MCP测试疾病",
            },
        },
        meta=modern_meta,
    )
    result = response["result"]
    assert result["resultType"] == "complete"
    if result.get("isError"):
        pytest.skip(f"upstream unavailable: {result['content'][0]['text']}")

    created = result["structuredContent"]
    assert created["name"] == unique
    assert created["id"].startswith("PET-")
    assert created["status"] == "待就诊"
    assert created["records"] == []

    try:
        with httpx2.Client(base_url=_api_base(), timeout=10) as http:
            fetched = http.get(f"/api/v1/pets/{created['id']}")
            assert fetched.status_code == 200
            assert fetched.json()["data"]["name"] == unique
    finally:
        with httpx2.Client(base_url=_api_base(), timeout=10) as http:
            assert http.delete(f"/api/v1/pets/{created['id']}").status_code == 200


def test_tools_call_add_pet_missing_required_is_tool_execution_error(stdio_server, modern_meta) -> None:
    response = stdio_server.call(
        "tools/call",
        {
            "name": "add_pet",
            "arguments": {
                "name": "缺电话",
                "species": "犬",
                "ownerName": "某人",
                "doctor": "李医生",
                "disease": "测试",
            },
        },
        meta=modern_meta,
    )
    result = response["result"]
    assert result["isError"] is True
    assert "ownerPhone" in result["content"][0]["text"]
