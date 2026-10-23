import json
import time
import uuid
from typing import Iterator

from .events import (
    CompletionEvent,
    DoneEvent,
    ErrorEvent,
    Event,
    TokenEvent,
    ToolCallEvent,
    ToolCallInfo,
    ToolResultEvent,
)
from .llm import LLMClient
from .models import Message
from .tools import dispatch, get_schemas


class Agent:
    """界面无关的对话编排：维护历史、驱动 LLM、分发工具调用。"""

    def __init__(self, client: LLMClient, max_tool_rounds: int = 16):
        self.client = client
        self.tools = get_schemas()
        self.messages: list[Message] = []
        self.session_id = uuid.uuid4().hex[:8]
        self.turn_count = 0
        self.tool_call_count = 0
        self.max_tool_rounds = max_tool_rounds

    def reset(self) -> None:
        self.messages.clear()
        self.turn_count = 0
        self.tool_call_count = 0

    def send(self, user_input: str) -> Iterator[Event]:
        self.messages.append({"role": "user", "content": user_input})
        self.turn_count += 1
        rounds = 0
        while True:
            reply = ""
            tool_calls: list[dict] = []
            try:
                for event in self.client.stream_chat(self.messages, self.tools):
                    if isinstance(event, TokenEvent):
                        reply += event.text
                        yield event
                    elif isinstance(event, CompletionEvent):
                        tool_calls = event.tool_calls
            except Exception as exc:  # noqa: BLE001 - 以事件形式交给界面展示
                yield ErrorEvent(str(exc))
                return

            if tool_calls:
                parsed: list[tuple[dict, str, dict]] = []
                for tc in tool_calls:
                    name = tc["function"]["name"]
                    try:
                        arguments = json.loads(tc["function"].get("arguments") or "{}")
                    except json.JSONDecodeError:
                        arguments = {}
                    if not isinstance(arguments, dict):
                        arguments = {}
                    parsed.append((tc, name, arguments))

                yield ToolCallEvent([ToolCallInfo(name, args) for _, name, args in parsed])
                self.messages.append(
                    {
                        "role": "assistant",
                        "content": reply or None,
                        "tool_calls": tool_calls,
                    }
                )
                for tc, name, arguments in parsed:
                    started = time.perf_counter()
                    result = dispatch(name, arguments)
                    duration_ms = (time.perf_counter() - started) * 1000
                    self.tool_call_count += 1
                    yield ToolResultEvent(name, result, duration_ms)
                    self.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.get("id", ""),
                            "content": result,
                        }
                    )

                rounds += 1
                if rounds >= self.max_tool_rounds:
                    yield ErrorEvent(f"工具调用次数超过上限 {self.max_tool_rounds}")
                    return
                continue

            self.messages.append({"role": "assistant", "content": reply})
            yield DoneEvent(reply)
            return
