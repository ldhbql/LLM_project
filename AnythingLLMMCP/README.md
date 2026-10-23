# AnythingLLM MCP Server

一个用 Python 编写的 [MCP](https://modelcontextprotocol.io) 服务器，把本地安装的
[AnythingLLM](https://anythingllm.com) 中**唯一一个工作区**的知识库暴露给支持 MCP 的
AI 客户端，让模型可以基于该工作区的文档来回答问题。

- **协议版本**：MCP `2026-07-28`（modern 时代：无 `initialize` 握手、按请求携带
  `_meta`、服务器实现 `server/discover`、结果带 `resultType`）。
- **传输方式**：`stdio`（本地子进程；凭据通过环境变量传入）。
- **功能**：单个工具 `ask_workspace`，内部调用 AnythingLLM 的工作区问答
  （`POST /api/v1/workspace/{slug}/chat`），返回 AI 回答与引用来源。

## 环境要求

- Python 3.10+
- 一个正在运行的 AnythingLLM 实例（默认 `http://localhost:3001`）
- AnythingLLM API Key（AnythingLLM → Settings → API Keys）
- 目标工作区的 slug（可用 `GET /api/v1/workspaces` 查询）

## 安装

使用 [uv](https://docs.astral.sh/uv/)：

```powershell
uv sync
```

或使用 pip：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

## 配置

复制 `.env.example` 为 `.env` 并填写：

```dotenv
ANYTHINGLLM_BASE_URL=http://localhost:3001
ANYTHINGLLM_API_KEY=你的-anythingllm-api-key
ANYTHINGLLM_WORKSPACE_SLUG=你的-工作区-slug
ANYTHINGLLM_TIMEOUT=60
```

| 变量 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `ANYTHINGLLM_BASE_URL` | 否 | `http://localhost:3001` | 实例地址，不含 `/api` |
| `ANYTHINGLLM_API_KEY` | 是 | — | AnythingLLM API Key |
| `ANYTHINGLLM_WORKSPACE_SLUG` | 是 | — | 唯一工作区的 slug |
| `ANYTHINGLLM_TIMEOUT` | 否 | `60` | 请求超时（秒） |

> `.env` 只在本地运行时自动读取（从当前工作目录向上查找最近的 `.env`）；
> 通过 host 启动时请使用 host 自己的环境变量配置。

## 运行

标准输入输出（stdio）传输：

```powershell
uv run python -m anythingllm_mcp
# 或安装后
uv run anythingllm-mcp
```

使用内置 Inspect 调试：

```powershell
uv run mcp dev src/anythingllm_mcp/server.py
```

## 在客户端中配置

### opencode（项目级）

本目录已包含 `opencode.json`，把该服务器注册为项目级 MCP：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "anythingllm": {
      "type": "local",
      "command": [
        "E:/LLM/AnythingLLMMCP/.venv/Scripts/python.exe",
        "-m",
        "anythingllm_mcp"
      ],
      "cwd": "E:/LLM/AnythingLLMMCP",
      "enabled": true
    }
  }
}
```

配置值来自项目根目录的 `.env`（不会被提交）。修改配置后需退出并重启 opencode 生效。

### Claude Desktop

```json
{
  "mcpServers": {
    "anythingllm": {
      "command": "E:/LLM/AnythingLLMMCP/.venv/Scripts/python.exe",
      "args": ["-m", "anythingllm_mcp"],
      "env": {
        "ANYTHINGLLM_BASE_URL": "http://localhost:3001",
        "ANYTHINGLLM_API_KEY": "你的-anythingllm-api-key",
        "ANYTHINGLLM_WORKSPACE_SLUG": "你的-工作区-slug"
      }
    }
  }
}
```

### 通用配置

任何支持 MCP 的客户端都可以用以下启动命令：

```json
{
  "command": "E:/LLM/AnythingLLMMCP/.venv/Scripts/python.exe",
  "args": ["-m", "anythingllm_mcp"],
  "env": {
    "ANYTHINGLLM_BASE_URL": "http://localhost:3001",
    "ANYTHINGLLM_API_KEY": "你的-anythingllm-api-key",
    "ANYTHINGLLM_WORKSPACE_SLUG": "你的-工作区-slug"
  }
}
```

> 也可以使用 `uv --directory E:/LLM/AnythingLLMMCP run anythingllm-mcp`，但这要求 `uv`
> 已在 host 进程的 `PATH` 中。使用虚拟环境的 Python 可执行文件最稳妥。

## 工具

### `ask_workspace`

基于配置的工作区文档回答问题。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `question` | string | 是 | 自然语言问题 |
| `mode` | `"query"` \| `"chat"` | 否（默认 `query`） | `query` 仅依据文档；`chat` 结合历史 |

返回结构化结果：

```json
{
  "answer": "……",
  "sources": [{ "title": "文档名", "chunk": "命中的片段" }]
}
```

失败时以工具错误（`isError: true`）返回可读信息，模型可据此自我纠正。

## 开发

```powershell
uv sync
uv run pytest
```

## 设计说明

- **协议版本**：`2026-07-28` 是 MCP 的 modern 版本，服务器必须实现
  `server/discover`；官方 Python SDK（`mcp` v2）已自动实现。`MCPServer` 在每个传输上
  都会应答 `server/discover`。
- **无状态**：不依赖连接级会话；工作区与凭据通过环境变量固定。
- **已弃用特性**：不使用 Roots / Sampling / Logging；日志写入 `stderr`。
- **错误处理**：AnythingLLM 的 401/403、404、5xx、超时分别映射为可读的
  `ToolError`，API 细节保留在服务端日志中。
- **输出清洗**：自动移除模型泄漏的 `<think>...</think>` 推理块，并对重复的来源去重。
