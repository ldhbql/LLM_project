"""Unit tests for the ``list_pets`` tool: schemas, shaping and error paths."""

from __future__ import annotations

from typing import Any

import anyio

from petmcp.tools.list_pets import (
    LIST_PETS_TOOL_NAME,
    build_tool,
    handle_list_pets,
)
from petmcp.upstream import UpstreamError

SAMPLE_DATA: dict[str, Any] = {
    "items": [
        {
            "id": "PET-000001",
            "name": "旺财",
            "species": "犬",
            "ownerName": "张三",
            "totalCost": 1180.0,
            "visitCount": 2,
            "records": [],
            "charges": [],
        }
    ],
    "total": 1,
    "page": 1,
    "pageSize": 20,
    "totalPages": 1,
    "totalCost": 1180.0,
}


class FakeClient:
    def __init__(self, *, data: dict | None = None, error: Exception | None = None) -> None:
        self._data = data if data is not None else SAMPLE_DATA
        self._error = error
        self.calls: list[dict] = []

    async def list_pets(self, params: dict) -> dict:
        self.calls.append(params)
        if self._error is not None:
            raise self._error
        return self._data


def test_tool_definition() -> None:
    tool = build_tool()
    assert tool.name == LIST_PETS_TOOL_NAME
    assert tool.input_schema["type"] == "object"
    assert tool.input_schema["additionalProperties"] is False
    props = tool.input_schema["properties"]
    assert props["species"]["enum"] == ["犬", "猫", "兔", "鸟", "仓鼠", "爬宠", "其他"]
    assert props["pageSize"]["maximum"] == 100
    assert tool.output_schema is not None
    assert "items" in tool.output_schema["properties"]
    assert "pageSize" in tool.output_schema["properties"]


def test_handle_success_populates_content_and_structured_content() -> None:
    client = FakeClient()
    result = anyio.run(handle_list_pets, client, {"species": "犬", "pageSize": 20})
    assert result.is_error is False
    assert client.calls == [{"species": "犬", "pageSize": 20}]
    structured = result.structured_content
    assert structured is not None
    assert structured["items"][0]["id"] == "PET-000001"
    assert structured["pageSize"] == 20
    assert structured["totalCost"] == 1180.0
    # camelCase aliases must survive serialization
    assert structured["items"][0]["ownerName"] == "张三"
    assert "旺财" in result.content[0].text


def test_handle_upstream_error_is_tool_execution_error() -> None:
    client = FakeClient(error=UpstreamError("无法连接宠物医院服务"))
    result = anyio.run(handle_list_pets, client, {})
    assert result.is_error is True
    assert "无法连接宠物医院服务" in result.content[0].text


def test_handle_bad_arguments_does_not_call_upstream() -> None:
    client = FakeClient()
    result = anyio.run(handle_list_pets, client, {"pageSize": 9999})
    assert result.is_error is True
    assert client.calls == []
    assert "pageSize" in result.content[0].text
