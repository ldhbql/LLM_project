"""End-to-end elicitation: a legacy, elicitation-capable client is asked for each
missing ``add_pet`` required field, one prompt at a time.
"""

from __future__ import annotations

import os
import uuid

import httpx2
import pytest

REQUIRED_ORDER = ["species", "ownerName", "ownerPhone", "doctor", "disease"]


def _api_base() -> str:
    return os.environ.get("PET_API_URL", "http://127.0.0.1:8080").rstrip("/")


def test_add_pet_elicits_missing_fields_one_by_one(stdio_server) -> None:
    # Legacy handshake advertising the elicitation capability.
    init = stdio_server.call(
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {"elicitation": {}},
            "clientInfo": {"name": "eliciting-client", "version": "1.0.0"},
        },
        meta=None,
        request_id=1,
    )
    assert "tools" in init["result"]["capabilities"]
    stdio_server.send_raw({"jsonrpc": "2.0", "method": "notifications/initialized"})

    name = "MCP询问-" + uuid.uuid4().hex[:8]
    answers = {
        "species": "猫",
        "ownerName": "询问主人",
        "ownerPhone": "13700000000",
        "doctor": "李医生",
        "disease": "测试病",
    }

    # Fire tools/call with only `name`; required fields must be elicited.
    stdio_server.send_raw(
        {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/call",
            "params": {"name": "add_pet", "arguments": {"name": name}},
        }
    )

    asked: list[str] = []
    response: dict | None = None
    while response is None:
        message = stdio_server.recv()
        if message.get("method") == "elicitation/create":
            field = next(iter(message["params"]["requestedSchema"]["properties"]))
            asked.append(field)
            stdio_server.send_raw(
                {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "result": {"action": "accept", "content": {field: answers[field]}},
                }
            )
        elif message.get("id") == 99:
            response = message

    assert asked == REQUIRED_ORDER

    result = response["result"]
    if result.get("isError"):
        pytest.skip(f"upstream unavailable: {result['content'][0]['text']}")

    created = result["structuredContent"]
    assert created["name"] == name
    assert created["species"] == "猫"
    assert created["ownerPhone"] == "13700000000"

    try:
        with httpx2.Client(base_url=_api_base(), timeout=10) as http:
            assert http.get(f"/api/v1/pets/{created['id']}").status_code == 200
    finally:
        with httpx2.Client(base_url=_api_base(), timeout=10) as http:
            assert http.delete(f"/api/v1/pets/{created['id']}").status_code == 200


def test_add_pet_decline_cancels(stdio_server) -> None:
    stdio_server.call(
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {"elicitation": {}},
            "clientInfo": {"name": "declining-client", "version": "1.0.0"},
        },
        meta=None,
        request_id=1,
    )
    stdio_server.send_raw({"jsonrpc": "2.0", "method": "notifications/initialized"})
    stdio_server.send_raw(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "add_pet", "arguments": {}},
        }
    )

    while True:
        message = stdio_server.recv()
        if message.get("method") == "elicitation/create":
            stdio_server.send_raw({"jsonrpc": "2.0", "id": message["id"], "result": {"action": "decline"}})
        elif message.get("id") == 5:
            result = message["result"]
            assert result["isError"] is True
            assert "取消" in result["content"][0]["text"]
            return
