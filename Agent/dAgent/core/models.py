from dataclasses import dataclass, field
from typing import Any

Message = dict[str, Any]


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str = "{}"


@dataclass
class ChatResult:
    reply: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None
