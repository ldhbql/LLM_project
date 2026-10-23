"""The ``add_pet`` tool: create a new pet record.

Maps to the upstream ``POST /api/v1/pets`` endpoint.

Missing required fields are collected interactively, one at a time:

1. If the current connection can send server-initiated requests and the client
   declared the ``elicitation`` capability, ask the user for each missing field
   with ``elicitation/create`` (form mode), one field per prompt.
2. Otherwise (no capability, or a stateless 2026-07-28 connection with no
   back-channel) fall back to a tool-execution error naming the missing fields,
   so the model asks the user in the conversation and retries.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.shared.exceptions import NoBackChannelError
from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations
from pydantic import ValidationError

from ..models import Pet
from ..tools.list_pets import SPECIES, STATUSES
from ..upstream import PetHospitalClient, UpstreamError

ADD_PET_TOOL_NAME = "add_pet"
ADD_PET_TITLE = "新增宠物档案"
ADD_PET_DESCRIPTION = (
    "新增一条宠物医院档案（写操作）。必填：宠物姓名 name、种类 species、主人姓名 ownerName、"
    "主人电话 ownerPhone、医生 doctor、疾病 disease；若调用时未提供，服务端会逐项向用户询问"
    "（在对话中依次补齐）。可选：品种 breed、性别 gender、月龄 ageMonths、毛色 color、芯片号 chipNo、"
    "住址 ownerAddr、过敏史 allergy、备注 note、就诊状态 status（默认 待就诊）。"
    "成功后返回带自动编号（PET-xxxxxx）的完整档案。"
)

GENDERS: tuple[str, ...] = ("公", "母")
DEFAULT_STATUS = "待就诊"

REQUIRED_FIELDS: tuple[str, ...] = ("name", "species", "ownerName", "ownerPhone", "doctor", "disease")
OPTIONAL_STRING_FIELDS: tuple[str, ...] = (
    "breed",
    "color",
    "chipNo",
    "ownerAddr",
    "allergy",
    "note",
)
_OPTIONAL_FIELDS: tuple[str, ...] = ("gender", "ageMonths", "status", *OPTIONAL_STRING_FIELDS)
_ALLOWED_FIELDS: tuple[str, ...] = (*REQUIRED_FIELDS, *_OPTIONAL_FIELDS)

# Human-readable labels used in prompts/fallback messages.
_FIELD_LABELS: dict[str, str] = {
    "name": "宠物姓名",
    "species": "种类",
    "ownerName": "主人姓名",
    "ownerPhone": "主人电话",
    "doctor": "主治医生",
    "disease": "疾病 / 主要诊断",
}

# JSON Schema fragment used for each field's elicitation prompt.
_ELICIT_PROPERTY: dict[str, dict[str, Any]] = {
    "name": {"type": "string", "title": "宠物姓名", "description": "请输入宠物姓名"},
    "species": {"type": "string", "title": "种类", "enum": list(SPECIES), "description": "请选择宠物种类"},
    "ownerName": {"type": "string", "title": "主人姓名", "description": "请输入主人姓名"},
    "ownerPhone": {"type": "string", "title": "主人电话", "description": "请输入主人电话"},
    "doctor": {"type": "string", "title": "主治医生", "description": "请输入主治医生"},
    "disease": {"type": "string", "title": "疾病", "description": "请输入疾病 / 主要诊断"},
}

ADD_PET_INPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1, "description": "宠物姓名（必填，缺失时会询问用户）"},
        "species": {
            "type": "string",
            "enum": list(SPECIES),
            "description": "种类（必填，缺失时会询问用户）",
        },
        "ownerName": {"type": "string", "minLength": 1, "description": "主人姓名（必填，缺失时会询问用户）"},
        "ownerPhone": {"type": "string", "minLength": 1, "description": "主人电话（必填，缺失时会询问用户）"},
        "doctor": {"type": "string", "minLength": 1, "description": "主治医生（必填，缺失时会询问用户）"},
        "disease": {"type": "string", "minLength": 1, "description": "疾病 / 主要诊断（必填，缺失时会询问用户）"},
        "breed": {"type": "string", "description": "品种"},
        "gender": {"type": "string", "enum": list(GENDERS), "description": "性别"},
        "ageMonths": {"type": "integer", "minimum": 0, "description": "月龄"},
        "color": {"type": "string", "description": "毛色"},
        "chipNo": {"type": "string", "description": "芯片号"},
        "ownerAddr": {"type": "string", "description": "主人住址"},
        "allergy": {"type": "string", "description": "过敏史"},
        "note": {"type": "string", "description": "备注"},
        "status": {
            "type": "string",
            "enum": list(STATUSES),
            "default": DEFAULT_STATUS,
            "description": "就诊状态，默认 待就诊",
        },
    },
    # NOTE: required fields are intentionally not marked `required` so the model
    # may call with a partial argument set; the server then asks for the rest.
    "additionalProperties": False,
}

ADD_PET_OUTPUT_SCHEMA: dict[str, Any] = Pet.model_json_schema(by_alias=True)


def build_tool() -> Tool:
    """Build the MCP ``Tool`` definition for ``add_pet``."""
    return Tool(
        name=ADD_PET_TOOL_NAME,
        title=ADD_PET_TITLE,
        description=ADD_PET_DESCRIPTION,
        input_schema=ADD_PET_INPUT_SCHEMA,
        output_schema=ADD_PET_OUTPUT_SCHEMA,
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        ),
    )


def _error_result(message: str) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=message)], isError=True)


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def missing_required_fields(arguments: dict[str, Any]) -> list[str]:
    """Required fields absent from ``arguments``, in a stable asking order."""
    return [field for field in REQUIRED_FIELDS if not _is_present(arguments.get(field))]


def _field_label(field: str) -> str:
    return _FIELD_LABELS.get(field, field)


def _fallback_message(missing: list[str]) -> str:
    names = "、".join(f"{_field_label(field)}（{field}）" for field in missing)
    first = missing[0]
    return (
        f"新增宠物档案还缺少必填项：{names}。"
        f"请先提供「{_field_label(first)}」（{first}），"
        f"获取后再调用 add_pet；也可以一次性补齐所有缺失项后重试。"
    )


def _can_elicit(session: Any) -> bool:
    """Whether this connection can ask the user via ``elicitation/create``."""
    if session is None or not getattr(session, "can_send_request", False):
        return False
    capabilities = getattr(session, "client_capabilities", None)
    return capabilities is not None and getattr(capabilities, "elicitation", None) is not None


async def _elicit_field(session: Any, field: str, request_id: Any) -> str | None:
    """Ask the user for one field. Returns the value, or None if declined/cancelled."""
    requested_schema = {
        "type": "object",
        "properties": {field: _ELICIT_PROPERTY[field]},
        "required": [field],
    }
    result = await session.elicit_form(
        f"新增宠物档案：请填写「{_field_label(field)}」",
        requested_schema,
        related_request_id=request_id,
    )
    if result.action != "accept":
        return None
    content = result.content or {}
    return content.get(field)


async def _collect_missing(missing: list[str], ctx: Any) -> tuple[dict[str, Any], str | None]:
    """Fill the missing fields one at a time. Returns (answers, error_message)."""
    session = getattr(ctx, "session", None)
    if not _can_elicit(session):
        return {}, _fallback_message(missing)
    try:
        answers: dict[str, Any] = {}
        for field in missing:
            value = await _elicit_field(session, field, getattr(ctx, "request_id", None))
            if value is None:
                return {}, "已取消新增宠物档案。"
            answers[field] = value
        return answers, None
    except NoBackChannelError:
        # Connection cannot deliver server-initiated requests: degrade gracefully.
        return {}, _fallback_message(missing)


def build_create_payload(arguments: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize tool arguments into the upstream create payload.

    Raises :class:`ValueError` with a model-readable message on invalid input.
    """
    if not isinstance(arguments, dict):
        raise ValueError("arguments 必须是对象")

    unknown = set(arguments) - set(_ALLOWED_FIELDS)
    if unknown:
        raise ValueError(f"不支持的参数：{', '.join(sorted(unknown))}")

    payload: dict[str, Any] = {}

    for field in REQUIRED_FIELDS:
        value = arguments.get(field)
        if not isinstance(value, str) or value.strip() == "":
            raise ValueError(f"{field} 为必填项且不能为空")
        payload[field] = value.strip()

    if payload["species"] not in SPECIES:
        raise ValueError(f"species 必须是以下之一：{', '.join(SPECIES)}")

    for field in OPTIONAL_STRING_FIELDS:
        value = arguments.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValueError(f"{field} 必须是字符串")
        value = value.strip()
        if value:
            payload[field] = value

    gender = arguments.get("gender")
    if gender is not None and gender != "":
        if gender not in GENDERS:
            raise ValueError(f"gender 必须是以下之一：{', '.join(GENDERS)}")
        payload["gender"] = gender

    age_months = arguments.get("ageMonths")
    if age_months is not None:
        if isinstance(age_months, bool) or not isinstance(age_months, int) or age_months < 0:
            raise ValueError("ageMonths 必须是 >=0 的整数")
        payload["ageMonths"] = age_months

    status = arguments.get("status")
    if status is not None and status != "":
        if status not in STATUSES:
            raise ValueError(f"status 必须是以下之一：{', '.join(STATUSES)}")
        payload["status"] = status
    else:
        payload["status"] = DEFAULT_STATUS

    return payload


async def handle_add_pet(client: PetHospitalClient, arguments: dict[str, Any], ctx: Any = None) -> CallToolResult:
    """Execute the ``add_pet`` tool, interactively filling missing required fields."""
    collected = dict(arguments)

    missing = missing_required_fields(collected)
    if missing:
        answers, error = await _collect_missing(missing, ctx)
        if error is not None:
            return _error_result(error)
        collected.update(answers)

    try:
        payload = build_create_payload(collected)
    except ValueError as exc:
        return _error_result(f"参数错误：{exc}")

    try:
        data = await client.create_pet(payload)
    except UpstreamError as exc:
        return _error_result(str(exc))

    try:
        created = Pet.model_validate(data)
    except ValidationError as exc:
        return _error_result(f"上游响应结构不符合预期：{exc}")

    structured = created.model_dump(mode="json", by_alias=True, exclude_none=True)
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(structured, ensure_ascii=False, indent=2))],
        structuredContent=structured,
    )
