import os
import time
from datetime import datetime

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.events import Resize
from textual.widgets import Input, Rule, Static

from core import create_agent, load_config
from core.agent import Agent
from core.config import BASE_DIR
from core.events import (
    DoneEvent,
    ErrorEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
)

from .widgets import ConversationView, TitleBar


class ChatApp(App):
    CSS = """
    Screen {
        layout: vertical;
        background: #14161a;
        color: #c7ccd1;
    }
    TitleBar {
        height: 1;
        background: #1a1d21;
    }
    #title-left {
        width: 1fr;
        padding: 0 1;
    }
    #title-right {
        width: auto;
        padding: 0 1;
        text-align: right;
    }
    #infobar {
        height: 1;
        padding: 0 1;
        background: #222a31;
    }
    #body {
        height: 1fr;
    }
    #conversation {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
        background: #14161a;
    }
    #sidebar {
        width: 38;
        padding: 0 1;
        background: #101215;
        border-left: solid #2a2e33;
    }
    #session-info {
        height: auto;
    }
    Rule {
        color: #2a2e33;
        margin: 0;
    }
    #tools-list {
        height: auto;
    }
    #prompt {
        height: 3;
        margin: 0 1;
        background: #22262b;
        border: round #2a2f35;
    }
    #prompt:focus {
        border: round #3a4750;
    }
    #statusbar {
        height: 1;
        background: #1a1d21;
    }
    #status-left {
        width: 1fr;
        padding: 0 1;
    }
    #status-right {
        width: auto;
        padding: 0 1;
        text-align: right;
    }
    ToolCard {
        height: auto;
        margin: 0 0 1 0;
        padding: 0 1;
        background: #1b2420;
        border: round #2d3a33;
    }
    """
    BINDINGS = [
        ("ctrl+b", "toggle_sidebar", "侧边栏"),
        ("ctrl+q", "quit", "退出"),
    ]

    def __init__(self, agent: Agent | None = None, config=None) -> None:
        super().__init__()
        if agent is None:
            self.config = config or load_config()
            self.agent = create_agent(self.config)
        else:
            self.agent = agent
            self.config = config
        self._state = "就绪"
        self._turn_start: float | None = None
        self._elapsed = 0.0
        self._busy = False
        self._auto_hidden = False
        self._layout_ready = False

    def compose(self) -> ComposeResult:
        yield TitleBar(id="titlebar")
        yield Static(id="infobar")
        with Horizontal(id="body"):
            yield ConversationView(id="conversation")
            with VerticalScroll(id="sidebar"):
                yield Static(id="session-info")
                yield Rule(line_style="solid")
                yield Static(id="tools-list")
        yield Input(placeholder="输入问题后按 Enter 发送，Ctrl+B 收起侧边栏", id="prompt")
        with Horizontal(id="statusbar"):
            yield Static(id="status-left")
            yield Static(id="status-right")

    def on_mount(self) -> None:
        self._base_url = getattr(self.config, "base_url", "-")
        self._model = getattr(self.config, "model", "-")
        self._tool_count = len(self.agent.tools)

        self._render_title()
        self._render_infobar()
        self._render_tools()
        self._refresh_session()
        self.query_one("#conversation", ConversationView).add_info(
            "欢迎使用 xAgent，请输入你的问题。", style="#6f767d"
        )
        self.query_one("#prompt", Input).focus()
        self._update_status()
        self._layout_ready = True
        self._apply_responsive(self.size.width)
        self.set_interval(1, self._tick)

    def _render_title(self) -> None:
        left = Text()
        left.append("xAgent", style="bold #9db0c2")
        left.append("   模型 ", style="#6f767d")
        left.append(self._model, style="#aab2ba")
        left.append("   目录 ", style="#6f767d")
        left.append(str(BASE_DIR), style="#8b949e")
        self.query_one("#title-left", Static).update(left)
        self._render_clock()

    def _render_clock(self) -> None:
        self.query_one("#title-right", Static).update(
            Text(datetime.now().strftime("%H:%M:%S"), style="#767f88")
        )

    def _render_infobar(self) -> None:
        text = Text()
        text.append("工具 ", style="#6f838f")
        text.append(str(self._tool_count), style="#a9b7c2")
        text.append("   模型 ", style="#6f838f")
        text.append(self._model, style="#a9b7c2")
        text.append("   目录 ", style="#6f838f")
        text.append(os.getcwd(), style="#a9b7c2")
        text.append(
            "   Enter 发送 · Ctrl+B 侧边栏 · Ctrl+Q 退出", style="#6f838f"
        )
        self.query_one("#infobar", Static).update(text)

    def _render_tools(self) -> None:
        text = Text()
        text.append("工具列表\n", style="bold #94a3b3")
        for schema in self.agent.tools:
            fn = schema["function"]
            text.append(f"{fn['name']}\n", style="#9fb0a5")
            text.append(f"  {fn.get('description', '')}\n", style="#76817a")
        self.query_one("#tools-list", Static).update(text)

    def _refresh_session(self) -> None:
        text = Text()
        text.append("会话信息\n", style="bold #94a3b3")
        text.append(f"模型地址  {self._base_url}\n", style="#8b98a5")
        text.append(
            f"会话 ID   {getattr(self.agent, 'session_id', '-')}\n", style="#8b98a5"
        )
        text.append(
            f"对话轮次  {getattr(self.agent, 'turn_count', 0)}\n", style="#8b98a5"
        )
        text.append(
            f"调用上限  {getattr(self.agent, 'max_tool_rounds', '-')} 次/轮",
            style="#8b98a5",
        )
        self.query_one("#session-info", Static).update(text)

    def action_toggle_sidebar(self) -> None:
        try:
            sidebar = self.query_one("#sidebar", VerticalScroll)
        except NoMatches:
            return
        sidebar.display = not sidebar.display
        self._auto_hidden = False

    def on_resize(self, event: Resize) -> None:
        if not self._layout_ready:
            return
        self._apply_responsive(event.size.width)

    def _apply_responsive(self, width: int) -> None:
        try:
            sidebar = self.query_one("#sidebar", VerticalScroll)
        except NoMatches:
            return
        if width < 90:
            if sidebar.display:
                sidebar.display = False
                self._auto_hidden = True
        elif self._auto_hidden and not sidebar.display:
            sidebar.display = True
            self._auto_hidden = False

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text or self._busy:
            return
        prompt = self.query_one("#prompt", Input)
        prompt.value = ""
        prompt.disabled = True
        self._busy = True
        self._turn_start = time.monotonic()
        self._elapsed = 0.0
        self.query_one("#conversation", ConversationView).add_user(text)
        self._refresh_session()
        self._update_status("思考中")
        self.run_agent(text)

    @work(thread=True, exclusive=True)
    def run_agent(self, text: str) -> None:
        try:
            for event in self.agent.send(text):
                self.call_from_thread(self.handle_event, event)
        except Exception as exc:  # noqa: BLE001 - 兜底展示
            self.call_from_thread(self.handle_event, ErrorEvent(str(exc)))
        finally:
            self.call_from_thread(self.finish_turn)

    def handle_event(self, event) -> None:
        convo = self.query_one("#conversation", ConversationView)
        if isinstance(event, TokenEvent):
            convo.add_assistant_token(event.text)
        elif isinstance(event, ToolCallEvent):
            convo.add_tool_calls(event.calls)
            self._update_status("调用工具")
        elif isinstance(event, ToolResultEvent):
            convo.add_tool_result(event.name, event.result, event.duration_ms)
            self._update_status("思考中")
        elif isinstance(event, ErrorEvent):
            convo.add_info("错误: " + event.message, style="#a86a6a")
            self._update_status("出错")
        elif isinstance(event, DoneEvent):
            convo.finalize_assistant()
            self._update_status("就绪")

    def finish_turn(self) -> None:
        self._busy = False
        if self._turn_start is not None:
            self._elapsed = time.monotonic() - self._turn_start
        prompt = self.query_one("#prompt", Input)
        prompt.disabled = False
        prompt.focus()
        self._refresh_session()
        self._update_status()

    def _tick(self) -> None:
        self._render_clock()
        if self._busy and self._turn_start is not None:
            self._elapsed = time.monotonic() - self._turn_start
            self._update_status()

    def _update_status(self, state: str | None = None) -> None:
        if state is not None:
            self._state = state
        if self._state == "就绪":
            color = "#6f9e7a"
        elif self._state == "出错":
            color = "#a86a6a"
        else:
            color = "#a89a6a"

        left = Text()
        left.append("● ", style=color)
        left.append("状态 ", style="#6f767d")
        left.append(self._state, style=color)
        left.append("    轮次 ", style="#6f767d")
        left.append(str(getattr(self.agent, "turn_count", 0)), style="#aab2ba")
        left.append("    工具调用 ", style="#6f767d")
        left.append(str(getattr(self.agent, "tool_call_count", 0)), style="#aab2ba")
        left.append("    耗时 ", style="#6f767d")
        left.append(f"{self._elapsed:.1f}s", style="#aab2ba")
        self.query_one("#status-left", Static).update(left)

        right = Text("Enter 发送 · Ctrl+B 侧边栏 · Ctrl+Q 退出", style="#6f767d")
        self.query_one("#status-right", Static).update(right)
