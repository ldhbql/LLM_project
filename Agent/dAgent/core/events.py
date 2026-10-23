from dataclasses import dataclass, field
from typing import Any


@dataclass
class TokenEvent:
    text: str


@dataclass
class CompletionEvent:
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None


@dataclass
class ToolCallInfo:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallEvent:
    calls: list[ToolCallInfo]

    @property
    def names(self) -> list[str]:
        return [call.name for call in self.calls]


@dataclass
class ToolResultEvent:
    name: str
    result: str
    duration_ms: float = 0.0


@dataclass
class DoneEvent:
    reply: str


@dataclass
class ErrorEvent:
    message: str


Event = TokenEvent | CompletionEvent | ToolCallEvent | ToolResultEvent | DoneEvent | ErrorEvent
