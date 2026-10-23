import json

from rich.text import Text
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Static

from core.events import ToolCallInfo


class TitleBar(Horizontal):
    """顶部标题栏：左侧项目信息，右侧实时时钟。"""

    def compose(self):
        yield Static(id="title-left")
        yield Static(id="title-right")


class ToolCard(Static):
    """暗茶绿工具调用区块，无入参默认折叠、有入参默认展开，可点击切换。"""

    def __init__(self, call: ToolCallInfo, **kwargs) -> None:
        super().__init__(**kwargs)
        self.call_info = call
        self.result: str | None = None
        self.duration_ms: float = 0.0
        self.expanded = bool(call.arguments)
        self._refresh()

    def set_result(self, result: str, duration_ms: float = 0.0) -> None:
        self.result = result
        self.duration_ms = duration_ms
        self._refresh()

    def _refresh(self) -> None:
        text = Text()
        arrow = "▾" if self.expanded else "▸"
        text.append(f"{arrow} {self.call_info.name}", style="bold #8faa93")
        if self.result is not None:
            text.append(f"   {self.duration_ms:.0f} ms", style="#77837c")
            if not self.expanded:
                text.append("   ✓", style="#7fa88a")

        if self.expanded:
            text.append("\n入参  ", style="#7d8b83")
            text.append(
                json.dumps(self.call_info.arguments, ensure_ascii=False, indent=2),
                style="#a6b4b8",
            )
            if self.result is not None:
                text.append("\n返回  ", style="#7d8b83")
                text.append(self.result.strip(), style="#a6b4b8")
        self.update(text)

    def on_click(self) -> None:
        self.expanded = not self.expanded
        self._refresh()


class ConversationView(VerticalScroll):
    """对话主视图：用户/助手消息与工具卡片，支持逐 token 流式更新。"""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current: Static | None = None
        self._buffer = ""
        self._pending: list[ToolCard] = []

    def add_user(self, text: str) -> None:
        self._finalize_assistant()
        self._mount(Text("你  " + text, style="bold #c08a63"))

    def add_info(self, text: str, style: str = "#6f767d") -> None:
        self._finalize_assistant()
        self._mount(Text(text, style=style))

    def add_assistant_token(self, text: str) -> None:
        if self._current is None:
            self._current = Static(classes="assistant")
            self.mount(self._current)
            self._buffer = ""
        self._buffer += text
        self._current.update(self._assistant_text())
        self.scroll_end(animate=False)

    def finalize_assistant(self) -> None:
        self._finalize_assistant()
        self.scroll_end(animate=False)

    def add_tool_calls(self, calls: list[ToolCallInfo]) -> None:
        self._finalize_assistant()
        for call in calls:
            card = ToolCard(call)
            self._pending.append(card)
            self.mount(card)
        self.scroll_end(animate=False)

    def add_tool_result(self, name: str, result: str, duration_ms: float = 0.0) -> None:
        for index, card in enumerate(self._pending):
            if card.call_info.name == name:
                card.set_result(result, duration_ms)
                self._pending.pop(index)
                break
        self.scroll_end(animate=False)

    def _assistant_text(self) -> Text:
        text = Text()
        text.append("xAgent  ", style="bold #96adc2")
        text.append(self._buffer, style="#8ba3ba")
        return text

    def _finalize_assistant(self) -> None:
        self._current = None
        self._buffer = ""

    def _mount(self, content: Text) -> None:
        self.mount(Static(content))
        self.scroll_end(animate=False)
