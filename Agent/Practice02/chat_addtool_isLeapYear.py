import configparser
import json
import os
import subprocess
import requests

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini"))
base_url = config["default"]["base_url"]
model = config["default"]["model"]
api_key = config["default"]["api_key"]


def getData():
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "date"],
        capture_output=True, text=True, encoding="mbcs", errors="replace"
    )
    return result.stdout.strip()


def isLeapYear(year):
    year = int(year)
    if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
        return f"{year} 是闰年"
    return f"{year} 不是闰年"


tools = [{
    "type": "function",
    "function": {
        "name": "getData",
        "description": "获取当前电脑的日期和时间",
        "parameters": {"type": "object", "properties": {}}
    }
}, {
    "type": "function",
    "function": {
        "name": "isLeapYear",
        "description": "判断输入的年份是否为闰年",
        "parameters": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "要判断的年份"}
            },
            "required": ["year"]
        }
    }
}]


def chat(messages):
    resp = requests.post(
        base_url.rstrip("/") + "/chat/completions",
        headers={"Authorization": "Bearer " + api_key},
        json={"model": model, "messages": messages, "tools": tools, "stream": True},
        stream=True,
    )
    reply = ""
    tool_calls = {}
    finish_reason = None
    for line in resp.iter_lines():
        if line and line.startswith(b"data: ") and line != b"data: [DONE]":
            choice = json.loads(line[6:])["choices"][0]
            delta = choice["delta"]
            content = delta.get("content") or ""
            reply += content
            print(content, end="", flush=True)
            for tc in delta.get("tool_calls") or []:
                index = tc["index"]
                entry = tool_calls.setdefault(index, {
                    "id": "", "type": "function",
                    "function": {"name": "", "arguments": ""}
                })
                if tc.get("id"):
                    entry["id"] = tc["id"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    entry["function"]["name"] += fn["name"]
                if fn.get("arguments"):
                    entry["function"]["arguments"] += fn["arguments"]
            finish_reason = choice.get("finish_reason") or finish_reason
    return reply, [tool_calls[i] for i in sorted(tool_calls)], finish_reason


messages = []

while True:
    print()
    print("请输入你的问题？")
    prompt = input()
    print("---")

    messages.append({"role": "user", "content": prompt})

    while True:
        reply, tool_calls, finish_reason = chat(messages)
        if tool_calls:
            names = ", ".join(tc["function"]["name"] for tc in tool_calls)
            print(f"\n[调用工具: {names}]")
            messages.append({
                "role": "assistant",
                "content": reply or None,
                "tool_calls": tool_calls
            })
            for tc in tool_calls:
                name = tc["function"]["name"]
                if name == "getData":
                    result = getData()
                elif name == "isLeapYear":
                    args = json.loads(tc["function"]["arguments"] or "{}")
                    result = isLeapYear(args.get("year"))
                else:
                    result = "未知工具: " + name
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result
                })
            print()
            continue
        messages.append({"role": "assistant", "content": reply})
        break
