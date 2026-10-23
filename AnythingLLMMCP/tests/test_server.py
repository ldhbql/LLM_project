from __future__ import annotations

import pytest
from mcp import Client

from anythingllm_mcp.anythingllm import AnythingLLMError
from anythingllm_mcp.config import ConfigError
from anythingllm_mcp.models import Answer, Source
from anythingllm_mcp.server import SERVER_VERSION, build_server


class FakeClient:
    def __init__(self, *, answer: Answer | None = None, error: Exception | None = None):
        self._answer = answer
        self._error = error
        self.calls: list[tuple[str, str]] = []

    async def ask(self, question: str, *, mode: str = "query") -> Answer:
        self.calls.append((question, mode))
        if self._error is not None:
            raise self._error
        assert self._answer is not None
        return self._answer


async def test_server_speaks_mcp_2026_07_28():
    mcp = build_server(lambda: FakeClient(answer=Answer(answer="x")))
    async with Client(mcp) as client:
        assert client.protocol_version == "2026-07-28"


async def test_discover_reports_server_identity():
    mcp = build_server(lambda: FakeClient(answer=Answer(answer="x")))
    async with Client(mcp) as client:
        discover = client.session.discover_result
        assert discover is not None
        assert "2026-07-28" in discover.supported_versions
        info = discover.meta["io.modelcontextprotocol/serverInfo"]
        assert info["name"] == "anythingllm-mcp"
        assert info["version"] == SERVER_VERSION


async def test_tools_list_exposes_only_ask_workspace():
    mcp = build_server(lambda: FakeClient(answer=Answer(answer="x")))
    async with Client(mcp) as client:
        result = await client.list_tools()

    names = [tool.name for tool in result.tools]
    assert names == ["ask_workspace"]

    schema = result.tools[0].model_dump(by_alias=True)["inputSchema"]
    assert schema["required"] == ["question"]
    assert schema["properties"]["question"]["type"] == "string"
    assert schema["properties"]["mode"]["enum"] == ["query", "chat"]


async def test_call_tool_returns_structured_answer():
    fake = FakeClient(
        answer=Answer(
            answer="这是回答",
            sources=[Source(title="doc.md", chunk="片段")],
        )
    )
    mcp = build_server(lambda: fake)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "ask_workspace", {"question": "问题？", "mode": "chat"}
        )

    assert result.is_error is False
    assert result.structured_content == {
        "answer": "这是回答",
        "sources": [{"title": "doc.md", "chunk": "片段"}],
    }
    assert fake.calls == [("问题？", "chat")]


async def test_tool_error_is_readable_by_the_model():
    fake = FakeClient(error=AnythingLLMError("工作区不可用"))
    mcp = build_server(lambda: fake)
    async with Client(mcp) as client:
        result = await client.call_tool("ask_workspace", {"question": "hi"})

    assert result.is_error is True
    assert "工作区不可用" in result.content[0].text


async def test_missing_config_becomes_tool_error():
    def broken_factory():
        raise ConfigError("缺少 ANYTHINGLLM_API_KEY")

    mcp = build_server(broken_factory)
    async with Client(mcp, raise_exceptions=True) as client:
        result = await client.call_tool("ask_workspace", {"question": "hi"})

    assert result.is_error is True
    assert "缺少 ANYTHINGLLM_API_KEY" in result.content[0].text


async def test_invalid_arguments_are_rejected_before_handler():
    fake = FakeClient(answer=Answer(answer="x"))
    mcp = build_server(lambda: fake)
    async with Client(mcp) as client:
        result = await client.call_tool("ask_workspace", {"question": ""})

    assert result.is_error is True
    assert fake.calls == []
