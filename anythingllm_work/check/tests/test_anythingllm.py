from __future__ import annotations

import json

import httpx
import pytest
import respx

from anythingllm_mcp.anythingllm import (
    AnythingLLMAuthError,
    AnythingLLMClient,
    AnythingLLMUnavailableError,
    WorkspaceNotFoundError,
    clean_answer,
    dedupe_sources,
)
from anythingllm_mcp.config import Settings
from anythingllm_mcp.models import Source

BASE = "http://localhost:3001/api"
SETTINGS = Settings(
    base_url="http://localhost:3001",
    api_key="secret-key",
    workspace_slug="my-ws",
)
CHAT_URL = f"{BASE}/v1/workspace/my-ws/chat"
AUTH_URL = f"{BASE}/v1/auth"


def make_client() -> AnythingLLMClient:
    return AnythingLLMClient(SETTINGS)


@respx.mock
async def test_ask_returns_answer_and_sources():
    route = respx.post(CHAT_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chat-1",
                "type": "textResponse",
                "textResponse": "<think>内部推理</think> 这是回答 ",
                "sources": [
                    {"title": "doc.md", "chunk": "片段"},
                    {"title": "doc.md", "chunk": "片段"},
                ],
                "close": True,
                "error": None,
            },
        )
    )
    client = make_client()
    try:
        answer = await client.ask("问题？")
    finally:
        await client.aclose()

    assert answer.answer == "这是回答"
    assert len(answer.sources) == 1
    assert answer.sources[0].title == "doc.md"
    assert answer.sources[0].chunk == "片段"

    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer secret-key"
    assert json.loads(request.content) == {"message": "问题？", "mode": "query"}


def test_clean_answer_strips_reasoning_blocks():
    assert clean_answer("<think>hmm</think>答案") == "答案"
    assert clean_answer("前言<THINK>a</THINK>后语") == "前言后语"
    assert clean_answer("<think>没有闭合") == ""


def test_dedupe_sources_preserves_order():
    sources = [
        Source(title="a"),
        Source(title="a"),
        Source(title="b", chunk="x"),
        Source(title="a"),
    ]
    assert [s.title for s in dedupe_sources(sources)] == ["a", "b"]


@respx.mock
async def test_ask_raises_on_payload_error():
    respx.post(CHAT_URL).mock(
        return_value=httpx.Response(200, json={"textResponse": "", "error": "boom"})
    )
    client = make_client()
    try:
        with pytest.raises(Exception, match="boom"):
            await client.ask("hi")
    finally:
        await client.aclose()


@respx.mock
async def test_auth_error_mapping():
    respx.get(AUTH_URL).mock(return_value=httpx.Response(403, json={}))
    client = make_client()
    try:
        with pytest.raises(AnythingLLMAuthError):
            await client.verify()
    finally:
        await client.aclose()


@respx.mock
async def test_workspace_not_found_mapping():
    respx.post(CHAT_URL).mock(return_value=httpx.Response(404, json={}))
    client = make_client()
    try:
        with pytest.raises(WorkspaceNotFoundError):
            await client.ask("hi")
    finally:
        await client.aclose()


@respx.mock
async def test_server_error_mapping():
    respx.post(CHAT_URL).mock(return_value=httpx.Response(500, text="kaboom"))
    client = make_client()
    try:
        with pytest.raises(AnythingLLMUnavailableError):
            await client.ask("hi")
    finally:
        await client.aclose()


@respx.mock
async def test_connection_error_mapping():
    respx.post(CHAT_URL).mock(side_effect=httpx.ConnectError("refused"))
    client = make_client()
    try:
        with pytest.raises(AnythingLLMUnavailableError):
            await client.ask("hi")
    finally:
        await client.aclose()
