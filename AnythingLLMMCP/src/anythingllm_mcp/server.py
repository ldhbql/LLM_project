"""MCP server exposing one AnythingLLM workspace as a question-answering tool.

Built against the MCP ``2026-07-28`` (modern) protocol revision: no
``initialize`` handshake, per-request metadata in ``_meta``, and a mandatory
``server/discover`` RPC. The official Python SDK (``mcp`` >= 2) implements all
of that for us, including ``server/discover`` on stdio.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Annotated, Callable, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from .anythingllm import AnythingLLMClient, AnythingLLMError
from .config import ConfigError, load_settings
from .models import Answer

SERVER_NAME = "anythingllm-mcp"
SERVER_VERSION = "0.1.0"

logger = logging.getLogger(SERVER_NAME)

INSTRUCTIONS = (
    "通过本地 AnythingLLM 中唯一配置的工作区文档来回答问题。"
    "当问题可能与该工作区中的资料有关时，使用 ask_workspace 工具。"
)

WorkspaceQuestion = Annotated[
    str,
    Field(
        min_length=1,
        max_length=4000,
        description="要向工作区知识库提出的问题，使用自然语言。",
    ),
]

AnswerMode = Annotated[
    Literal["query", "chat"],
    Field(
        description=(
            '回答模式："query" 仅依据工作区文档回答（推荐）；'
            '"chat" 允许结合对话历史。'
        )
    ),
]


@lru_cache(maxsize=1)
def get_settings():
    """Load configuration once; raises :class:`ConfigError` when incomplete."""
    return load_settings()


@lru_cache(maxsize=1)
def get_client() -> AnythingLLMClient:
    """Create the shared AnythingLLM client lazily."""
    return AnythingLLMClient(get_settings())


def build_server(
    client_factory: Callable[[], AnythingLLMClient] | None = None,
) -> MCPServer:
    """Create the MCP server, optionally injecting a client factory for tests."""
    get_client_fn = client_factory or get_client

    mcp = MCPServer(
        SERVER_NAME,
        version=SERVER_VERSION,
        instructions=INSTRUCTIONS,
        log_level="WARNING",
    )

    @mcp.tool(
        title="向 AnythingLLM 工作区提问",
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
    )
    async def ask_workspace(question: WorkspaceQuestion, mode: AnswerMode = "query") -> Answer:
        """基于本地 AnythingLLM 工作区的文档回答问题，并返回引用来源。"""
        try:
            client = get_client_fn()
        except ConfigError as exc:
            raise ToolError(f"服务未正确配置：{exc}") from exc
        try:
            return await client.ask(question, mode=mode)
        except AnythingLLMError as exc:
            raise ToolError(str(exc)) from exc

    return mcp


mcp = build_server()


def main() -> None:
    """Run the server over stdio (the default transport)."""
    mcp.run()


if __name__ == "__main__":
    main()
