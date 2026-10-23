"""The single MVP tool: ``list_pets``.

Maps to the upstream ``GET /api/v1/pets`` endpoint and supports the full set of
filter / sort / pagination query parameters.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations
from pydantic import ValidationError

from ..models import ListPetsOutput
from ..upstream import PetHospitalClient, UpstreamError

LIST_PETS_TOOL_NAME = "list_pets"
LIST_PETS_TITLE = "列出宠物档案"
LIST_PETS_DESCRIPTION = (
    "列出宠物医院档案，可按关键词、姓名、主人、种类、医生、疾病、就诊状态、"
    "总花费区间筛选，并支持排序与分页。只读操作。"
    "参数与 GET /api/v1/pets 一致；返回 items 数组及 total/page/pageSize/totalPages/totalCost。"
)

SPECIES: tuple[str, ...] = ("犬", "猫", "兔", "鸟", "仓鼠", "爬宠", "其他")
STATUSES: tuple[str, ...] = ("待就诊", "就诊中", "住院中", "已康复", "慢性病随访")
SORT_FIELDS: tuple[str, ...] = (
    "id",
    "name",
    "ownerName",
    "species",
    "doctor",
    "disease",
    "status",
    "totalCost",
    "visitCount",
    "createdAt",
    "updatedAt",
)

# Order is significant: it is also the order parameters are forwarded upstream.
_FILTER_KEYS: tuple[str, ...] = (
    "q",
    "name",
    "ownerName",
    "ownerPhone",
    "species",
    "doctor",
    "disease",
    "status",
    "min",
    "max",
    "sortBy",
    "order",
    "page",
    "pageSize",
)

LIST_PETS_INPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "q": {"type": "string", "description": "关键词，跨字段匹配（含病历全文）"},
        "name": {"type": "string", "description": "宠物姓名"},
        "ownerName": {"type": "string", "description": "主人姓名"},
        "ownerPhone": {"type": "string", "description": "主人电话"},
        "species": {"type": "string", "enum": list(SPECIES), "description": "种类"},
        "doctor": {"type": "string", "description": "主治医生"},
        "disease": {"type": "string", "description": "疾病 / 主要诊断"},
        "status": {"type": "string", "enum": list(STATUSES), "description": "就诊状态"},
        "min": {"type": "number", "minimum": 0, "description": "总花费下限（含）"},
        "max": {"type": "number", "minimum": 0, "description": "总花费上限（含）"},
        "sortBy": {"type": "string", "enum": list(SORT_FIELDS), "description": "排序字段"},
        "order": {"type": "string", "enum": ["asc", "desc"], "default": "desc", "description": "排序方向"},
        "page": {"type": "integer", "minimum": 1, "default": 1, "description": "页码，从 1 开始"},
        "pageSize": {
            "type": "integer",
            "minimum": 1,
            "maximum": 100,
            "default": 20,
            "description": "每页条数，1..100",
        },
    },
    "additionalProperties": False,
}

LIST_PETS_OUTPUT_SCHEMA: dict[str, Any] = ListPetsOutput.model_json_schema(by_alias=True)


def build_tool() -> Tool:
    """Build the MCP ``Tool`` definition for ``list_pets``."""
    return Tool(
        name=LIST_PETS_TOOL_NAME,
        title=LIST_PETS_TITLE,
        description=LIST_PETS_DESCRIPTION,
        input_schema=LIST_PETS_INPUT_SCHEMA,
        output_schema=LIST_PETS_OUTPUT_SCHEMA,
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )


def _error_result(message: str) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=message)], isError=True)


def build_filter_params(arguments: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize tool arguments into upstream query parameters.

    Drops ``None`` / empty-string values, rejects unknown keys, validates enums
    and numeric ranges. Raises :class:`ValueError` with a model-readable message.
    """
    if not isinstance(arguments, dict):
        raise ValueError("arguments 必须是对象")

    unknown = set(arguments) - set(_FILTER_KEYS)
    if unknown:
        raise ValueError(f"不支持的参数：{', '.join(sorted(unknown))}")

    params: dict[str, Any] = {}
    for key in _FILTER_KEYS:
        if key not in arguments:
            continue
        value = arguments[key]
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                continue
        params[key] = value

    if "species" in params and params["species"] not in SPECIES:
        raise ValueError(f"species 必须是以下之一：{', '.join(SPECIES)}")
    if "status" in params and params["status"] not in STATUSES:
        raise ValueError(f"status 必须是以下之一：{', '.join(STATUSES)}")
    if "sortBy" in params and params["sortBy"] not in SORT_FIELDS:
        raise ValueError(f"sortBy 必须是以下之一：{', '.join(SORT_FIELDS)}")
    if "order" in params and params["order"] not in ("asc", "desc"):
        raise ValueError("order 必须是 asc 或 desc")

    page = params.get("page")
    if page is not None and (isinstance(page, bool) or not isinstance(page, int) or page < 1):
        raise ValueError("page 必须是 >=1 的整数")

    page_size = params.get("pageSize")
    if page_size is not None and (
        isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 100
    ):
        raise ValueError("pageSize 必须是 1..100 的整数")

    for key in ("min", "max"):
        value = params.get(key)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0
        ):
            raise ValueError(f"{key} 必须是 >=0 的数字")

    if "min" in params and "max" in params and params["min"] > params["max"]:
        raise ValueError("min 不能大于 max")

    return params


async def handle_list_pets(
    client: PetHospitalClient, arguments: dict[str, Any], ctx: Any = None
) -> CallToolResult:
    """Execute the ``list_pets`` tool and shape the MCP result.

    ``ctx`` is accepted to share the tool-handler signature; this read-only tool
    never needs it.
    """
    try:
        query = build_filter_params(arguments)
    except ValueError as exc:
        return _error_result(f"参数错误：{exc}")

    try:
        data = await client.list_pets(query)
    except UpstreamError as exc:
        return _error_result(str(exc))

    try:
        output = ListPetsOutput.model_validate(data)
    except ValidationError as exc:
        return _error_result(f"上游响应结构不符合预期：{exc}")

    structured = output.model_dump(mode="json", by_alias=True)
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(structured, ensure_ascii=False, indent=2))],
        structuredContent=structured,
    )
