"""Unit tests for the ``add_pet`` tool: schema, payload building and error paths."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import anyio
import pytest
from mcp.types import ClientCapabilities, ElicitationCapability, ElicitResult

from petmcp.tools.add_pet import (
    ADD_PET_TOOL_NAME,
    build_create_payload,
    build_tool,
    handle_add_pet,
    missing_required_fields,
)
from petmcp.upstream import UpstreamError

VALID_ARGS: dict[str, Any] = {
    "name": "测试动物",
    "species": "犬",
    "ownerName": "测试主人",
    "ownerPhone": "13900000000",
    "doctor": "李医生",
    "disease": "测试疾病",
}


class FakeClient:
    def __init__(self, *, data: dict | None = None, error: Exception | None = None) -> None:
        self._data = data if data is not None else {"id": "PET-001009", **VALID_ARGS, "records": None, "charges": None}
        self._error = error
        self.calls: list[dict] = []

    async def create_pet(self, payload: dict) -> dict:
        self.calls.append(payload)
        if self._error is not None:
            raise self._error
        return self._data


class FakeSession:
    """Minimal stand-in for ``ServerSession`` covering the elicitation surface."""

    def __init__(self, answers: dict[str, Any], *, elicitation: bool = True, can_send: bool = True) -> None:
        self._answers = answers
        self.can_send_request = can_send
        capabilities = ClientCapabilities()
        if elicitation:
            capabilities = ClientCapabilities(elicitation=ElicitationCapability())
        self.client_capabilities = capabilities
        self.asked: list[str] = []

    async def elicit_form(self, message: str, requested_schema: dict, related_request_id: Any = None) -> ElicitResult:
        field = next(iter(requested_schema["properties"]))
        self.asked.append(field)
        value = self._answers.get(field)
        if value is None:
            return ElicitResult(action="decline")
        return ElicitResult(action="accept", content={field: value})


def _ctx(session: Any) -> SimpleNamespace:
    return SimpleNamespace(session=session, request_id=7)


def test_tool_definition() -> None:
    tool = build_tool()
    assert tool.name == ADD_PET_TOOL_NAME
    assert tool.input_schema["additionalProperties"] is False
    # Required fields are requested interactively, so they are not enforced by the schema.
    assert "required" not in tool.input_schema
    assert tool.input_schema["properties"]["species"]["enum"] == ["犬", "猫", "兔", "鸟", "仓鼠", "爬宠", "其他"]
    assert tool.output_schema is not None
    assert "id" in tool.output_schema["properties"]


def test_missing_required_fields_order() -> None:
    assert missing_required_fields({}) == ["name", "species", "ownerName", "ownerPhone", "doctor", "disease"]
    assert missing_required_fields({"name": "x", "species": " ", "ownerName": "y"}) == [
        "species",
        "ownerPhone",
        "doctor",
        "disease",
    ]


def test_missing_fields_without_elicitation_returns_fallback() -> None:
    client = FakeClient()
    result = anyio.run(handle_add_pet, client, {"name": "只有名字"})
    assert result.is_error is True
    text = result.content[0].text
    assert "species" in text and "ownerPhone" in text
    assert client.calls == []


def test_missing_fields_are_elicited_one_by_one() -> None:
    client = FakeClient()
    session = FakeSession(
        {
            "species": "猫",
            "ownerName": "主人甲",
            "ownerPhone": "13900000000",
            "doctor": "李医生",
            "disease": "测试病",
        }
    )
    result = anyio.run(handle_add_pet, client, {"name": "橘座"}, _ctx(session))
    assert result.is_error is False
    assert session.asked == ["species", "ownerName", "ownerPhone", "doctor", "disease"]
    assert client.calls[0]["name"] == "橘座"
    assert client.calls[0]["species"] == "猫"
    assert client.calls[0]["ownerPhone"] == "13900000000"


def test_declined_elicitation_cancels_creation() -> None:
    client = FakeClient()
    session = FakeSession({})  # first prompt is declined
    result = anyio.run(handle_add_pet, client, {}, _ctx(session))
    assert result.is_error is True
    assert "取消" in result.content[0].text
    assert session.asked == ["name"]
    assert client.calls == []


def test_client_without_elicitation_capability_falls_back() -> None:
    client = FakeClient()
    session = FakeSession({"name": "x"}, elicitation=False)
    result = anyio.run(handle_add_pet, client, {}, _ctx(session))
    assert result.is_error is True
    assert session.asked == []
    assert client.calls == []


def test_build_payload_minimum_required() -> None:
    payload = build_create_payload(VALID_ARGS)
    assert payload == {**VALID_ARGS, "status": "待就诊"}


def test_build_payload_full() -> None:
    payload = build_create_payload(
        {
            **VALID_ARGS,
            "name": "  旺财  ",
            "breed": "金毛",
            "gender": "公",
            "ageMonths": 36,
            "color": "金黄",
            "chipNo": "CHIP-1",
            "ownerAddr": "北京市",
            "allergy": "无",
            "note": "备注",
            "status": "就诊中",
        }
    )
    assert payload["name"] == "旺财"  # trimmed
    assert payload["breed"] == "金毛"
    assert payload["gender"] == "公"
    assert payload["ageMonths"] == 36
    assert payload["status"] == "就诊中"


@pytest.mark.parametrize(
    "arguments",
    [
        {k: v for k, v in VALID_ARGS.items() if k != "name"},
        {**VALID_ARGS, "name": "   "},
        {**VALID_ARGS, "species": "龙"},
        {**VALID_ARGS, "gender": "未知"},
        {**VALID_ARGS, "status": "已死亡"},
        {**VALID_ARGS, "ageMonths": -1},
        {**VALID_ARGS, "ageMonths": True},
        {**VALID_ARGS, "ageMonths": "3"},
        {**VALID_ARGS, "breed": 123},
        {**VALID_ARGS, "unknownField": 1},
    ],
)
def test_build_payload_rejects_bad_arguments(arguments: dict) -> None:
    with pytest.raises(ValueError):
        build_create_payload(arguments)


def test_handle_success() -> None:
    client = FakeClient()
    result = anyio.run(handle_add_pet, client, VALID_ARGS)
    assert result.is_error is False
    assert client.calls[0]["status"] == "待就诊"
    structured = result.structured_content
    assert structured is not None
    assert structured["id"] == "PET-001009"
    assert structured["name"] == "测试动物"
    # null lists from the create response are normalized to lists
    assert structured["records"] == []
    assert "PET-001009" in result.content[0].text


def test_handle_upstream_error() -> None:
    client = FakeClient(error=UpstreamError("上游 POST /api/v1/pets 返回 HTTP 400：ownerPhone 不能为空"))
    result = anyio.run(handle_add_pet, client, VALID_ARGS)
    assert result.is_error is True
    assert "ownerPhone" in result.content[0].text


def test_handle_bad_arguments_does_not_call_upstream() -> None:
    client = FakeClient()
    result = anyio.run(handle_add_pet, client, {**VALID_ARGS, "species": "龙"})
    assert result.is_error is True
    assert client.calls == []
