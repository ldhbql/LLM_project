import json
from typing import Any, Iterator, Protocol

import requests

from .config import Config
from .events import CompletionEvent, TokenEvent
from .models import Message


class LLMClient(Protocol):
    def stream_chat(
        self, messages: list[Message], tools: list[dict[str, Any]]
    ) -> Iterator[TokenEvent | CompletionEvent]: ...


class DeepSeekClient:
    def __init__(self, config: Config):
        self.base_url = config.base_url.rstrip("/")
        self.model = config.model
        self.api_key = config.api_key

    def stream_chat(
        self, messages: list[Message], tools: list[dict[str, Any]]
    ) -> Iterator[TokenEvent | CompletionEvent]:
        resp = requests.post(
            self.base_url + "/chat/completions",
            headers={"Authorization": "Bearer " + self.api_key},
            json={
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "stream": True,
            },
            stream=True,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"接口错误 {resp.status_code}: {resp.text}")

        tool_calls: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        for line in resp.iter_lines():
            if not line or not line.startswith(b"data: ") or line == b"data: [DONE]":
                continue
            chunk = json.loads(line[6:])
            choices = chunk.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta") or {}
            content = delta.get("content") or ""
            if content:
                yield TokenEvent(content)
            for tc in delta.get("tool_calls") or []:
                index = tc["index"]
                entry = tool_calls.setdefault(
                    index,
                    {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    },
                )
                if tc.get("id"):
                    entry["id"] = tc["id"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    entry["function"]["name"] += fn["name"]
                if fn.get("arguments"):
                    entry["function"]["arguments"] += fn["arguments"]
            finish_reason = choice.get("finish_reason") or finish_reason

        yield CompletionEvent([tool_calls[i] for i in sorted(tool_calls)], finish_reason)
