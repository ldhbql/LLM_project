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


def run_ps(cmd):
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "$ErrorActionPreference='Stop'; " + cmd],
        capture_output=True, text=True, encoding="mbcs", errors="replace"
    )
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode != 0:
        return "错误: " + (err or out or "PowerShell 执行失败")
    return out or "完成"


def q(text):
    return "'" + str(text).replace("'", "''") + "'"


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


def getCurrentDirectory():
    return run_ps("(Get-Location).Path")


def listDirectory(path):
    cmd = ("Get-ChildItem -LiteralPath " + q(path) +
           " | ForEach-Object { if ($_.PSIsContainer) { '[DIR] ' + $_.Name } else { '[FILE] ' + $_.Name } }")
    out = run_ps(cmd)
    return out if out != "完成" else "(目录为空)"


def getFileType(path):
    out = run_ps("(Get-Item -LiteralPath " + q(path) + ").Extension")
    return out if out != "完成" else "(无扩展名)"


def readTextFile(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="gbk", errors="replace") as f:
            return f.read()


def createFile(directory, filename, content=""):
    cmd = ("New-Item -ItemType Directory -Force -Path " + q(directory) + " | Out-Null; "
           "$p = Join-Path -Path " + q(directory) + " -ChildPath " + q(filename) + "; "
           "Set-Content -LiteralPath $p -Value " + q(content) + " -Encoding UTF8 -NoNewline; "
           "'已创建: ' + $p")
    return run_ps(cmd)


def editTextFile(path, content, mode="overwrite"):
    m = "a" if mode == "append" else "w"
    with open(path, m, encoding="utf-8") as f:
        f.write(content)
    return "已编辑: " + path


def createDirectory(path):
    return run_ps("New-Item -ItemType Directory -Force -Path " + q(path) +
                  " | Out-Null; '已创建目录: ' + " + q(path))


def deleteDirectory(path):
    return run_ps("Remove-Item -LiteralPath " + q(path) +
                  " -Recurse -Force; '已删除目录: ' + " + q(path))


def deleteFile(path):
    return run_ps("Remove-Item -LiteralPath " + q(path) +
                  " -Force; '已删除文件: ' + " + q(path))


def renamePath(path, newName):
    return run_ps("Rename-Item -LiteralPath " + q(path) +
                  " -NewName " + q(newName) + "; '已重命名: ' + " + q(newName))


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
}, {
    "type": "function",
    "function": {
        "name": "getCurrentDirectory",
        "description": "获取当前工作目录",
        "parameters": {"type": "object", "properties": {}}
    }
}, {
    "type": "function",
    "function": {
        "name": "listDirectory",
        "description": "列出指定目录下所有文件和子目录",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目录路径"}
            },
            "required": ["path"]
        }
    }
}, {
    "type": "function",
    "function": {
        "name": "getFileType",
        "description": "获取指定文件的文件类型（扩展名）",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"}
            },
            "required": ["path"]
        }
    }
}, {
    "type": "function",
    "function": {
        "name": "readTextFile",
        "description": "获取指定纯文本文件的内容",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"}
            },
            "required": ["path"]
        }
    }
}, {
    "type": "function",
    "function": {
        "name": "createFile",
        "description": "在指定目录下创建新文件，目录不存在时自动创建，同名文件会被覆盖",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "目录路径"},
                "filename": {"type": "string", "description": "文件名"},
                "content": {"type": "string", "description": "文件内容，默认为空"}
            },
            "required": ["directory", "filename"]
        }
    }
}, {
    "type": "function",
    "function": {
        "name": "editTextFile",
        "description": "编辑指定纯文本文件的内容",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "新内容"},
                "mode": {"type": "string", "enum": ["overwrite", "append"], "description": "overwrite 覆盖（默认），append 追加"}
            },
            "required": ["path", "content"]
        }
    }
}, {
    "type": "function",
    "function": {
        "name": "createDirectory",
        "description": "创建新目录（支持多级）",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目录路径"}
            },
            "required": ["path"]
        }
    }
}, {
    "type": "function",
    "function": {
        "name": "deleteDirectory",
        "description": "删除目录（递归删除非空目录）",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目录路径"}
            },
            "required": ["path"]
        }
    }
}, {
    "type": "function",
    "function": {
        "name": "deleteFile",
        "description": "删除指定文件",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"}
            },
            "required": ["path"]
        }
    }
}, {
    "type": "function",
    "function": {
        "name": "renamePath",
        "description": "重命名文件或目录",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "原路径"},
                "newName": {"type": "string", "description": "新名称（不含目录）"}
            },
            "required": ["path", "newName"]
        }
    }
}]

TOOL_FUNCS = {
    "getData": getData,
    "isLeapYear": isLeapYear,
    "getCurrentDirectory": getCurrentDirectory,
    "listDirectory": listDirectory,
    "getFileType": getFileType,
    "readTextFile": readTextFile,
    "createFile": createFile,
    "editTextFile": editTextFile,
    "createDirectory": createDirectory,
    "deleteDirectory": deleteDirectory,
    "deleteFile": deleteFile,
    "renamePath": renamePath,
}


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


if __name__ == "__main__":
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
                    func = TOOL_FUNCS.get(name)
                    if func is None:
                        result = "未知工具: " + name
                    else:
                        try:
                            args = json.loads(tc["function"]["arguments"] or "{}")
                            result = func(**args)
                        except Exception as e:
                            result = "错误: " + str(e)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result
                    })
                print()
                continue
            messages.append({"role": "assistant", "content": reply})
            break
