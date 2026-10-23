"""Wire the low-level MCP ``Server`` for revision 2026-07-28.

Only the ``tools`` capability is served. The SDK supplies the modern
per-request envelope, version negotiation, ``server/discover``, ``resultType`` /
``serverInfo`` stamping and ``ttlMs`` / ``cacheScope`` cache hints.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server import CacheHint
from mcp.server.lowlevel import Server
from mcp.shared.exceptions import MCPError
from mcp.types import CallToolResult, ListToolsResult, Tool

from . import SERVER_NAME, SERVER_TITLE, __version__
from .config import ServerConfig
from .protocol import CACHE_SCOPE_PUBLIC, DISCOVER_TTL_MS, INVALID_PARAMS, TOOLS_LIST_TTL_MS
from .tools import add_pet as add_pet_tool
from .tools import list_pets as list_pets_tool
from .upstream import PetHospitalClient

ToolHandler = Callable[[PetHospitalClient, dict[str, Any], Any], Awaitable[CallToolResult]]

# Registration order is the deterministic ``tools/list`` order.
_TOOL_BUILDERS: tuple[Callable[[], Tool], ...] = (
    list_pets_tool.build_tool,
    add_pet_tool.build_tool,
)

_TOOL_HANDLERS: dict[str, ToolHandler] = {
    list_pets_tool.LIST_PETS_TOOL_NAME: list_pets_tool.handle_list_pets,
    add_pet_tool.ADD_PET_TOOL_NAME: add_pet_tool.handle_add_pet,
}


def _instructions(api_base: str) -> str:
    return (
        "宠物医院档案服务。\n"
        "- list_pets：查询宠物档案，支持关键词 q、姓名 name、主人 ownerName/ownerPhone、"
        "种类 species、医生 doctor、疾病 disease、就诊状态 status、总花费区间 min/max，"
        "以及排序 sortBy/order 与分页 page/pageSize。\n"
        "- add_pet：新增一条宠物档案（写操作），需提供 name/species/ownerName/ownerPhone/doctor/disease。\n"
        f"数据来自本机宠物医院服务：{api_base}（需先启动 pethospital.exe）。"
    )


def build_server(client: PetHospitalClient, config: ServerConfig) -> Server[dict[str, Any]]:
    """Construct the MCP server around a live upstream client."""

    async def on_list_tools(ctx: Any, params: Any) -> ListToolsResult:
        # Deterministic order: rebuilt identically on every call.
        return ListToolsResult(tools=[builder() for builder in _TOOL_BUILDERS])

    async def on_call_tool(ctx: Any, params: Any) -> CallToolResult:
        handler = _TOOL_HANDLERS.get(params.name)
        if handler is None:
            # Unknown tool is a protocol error per the spec's tools page.
            raise MCPError(INVALID_PARAMS, f"Unknown tool: {params.name}")
        return await handler(client, params.arguments or {}, ctx)

    return Server(
        name=SERVER_NAME,
        title=SERVER_TITLE,
        version=__version__,
        instructions=_instructions(client.api_base),
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
        cache_hints={
            "tools/list": CacheHint(ttl_ms=TOOLS_LIST_TTL_MS, scope=CACHE_SCOPE_PUBLIC),
            "server/discover": CacheHint(ttl_ms=DISCOVER_TTL_MS, scope=CACHE_SCOPE_PUBLIC),
        },
    )
