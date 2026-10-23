import unittest

from core.agent import Agent
from core.events import (
    CompletionEvent,
    DoneEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
)


class FakeClient:
    """第一次返回 isLeapYear 工具调用，第二次返回最终答案。"""

    def __init__(self):
        self.calls = 0

    def stream_chat(self, messages, tools):
        self.calls += 1
        if self.calls == 1:
            yield CompletionEvent(
                [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "isLeapYear",
                            "arguments": '{"year": 2024}',
                        },
                    }
                ],
                "tool_calls",
            )
        else:
            yield TokenEvent("2024 是闰年")
            yield CompletionEvent([], "stop")


class AgentTest(unittest.TestCase):
    def test_tool_call_flow(self):
        agent = Agent(FakeClient())
        events = list(agent.send("2024 是闰年吗"))

        self.assertTrue(any(isinstance(e, ToolCallEvent) for e in events))
        self.assertTrue(any(isinstance(e, ToolResultEvent) for e in events))
        done = [e for e in events if isinstance(e, DoneEvent)]
        self.assertEqual(len(done), 1)
        self.assertEqual(done[0].reply, "2024 是闰年")

        tool_messages = [m for m in agent.messages if m["role"] == "tool"]
        self.assertEqual(len(tool_messages), 1)
        self.assertIn("是闰年", tool_messages[0]["content"])

    def test_plain_reply(self):
        class PlainClient:
            def stream_chat(self, messages, tools):
                yield TokenEvent("你好")
                yield CompletionEvent([], "stop")

        agent = Agent(PlainClient())
        events = list(agent.send("hi"))
        self.assertTrue(any(isinstance(e, DoneEvent) for e in events))
        self.assertFalse(any(isinstance(e, ToolCallEvent) for e in events))


if __name__ == "__main__":
    unittest.main()
