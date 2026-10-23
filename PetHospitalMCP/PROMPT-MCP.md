# 开发提示词：宠物医院 MCP Server MVP（Python / MCP 2026-07-28）

## 一、角色与目标

你是资深 Python 工程师，请用 **Python** 开发一个 **MCP Server**，把「宠物医院 REST API」（`pethospital.exe`，默认 `http://127.0.0.1:8080`）的数据通过 **REST API** 提取，暴露给 MCP Client / Agent 消费。

本次只做 **MVP（第一阶段）**：

- **只实现一个工具：`list_pets`**，用于列出宠物，并支持按各种参数筛选。
- **不实现**其余工具、Resources、Prompts（列入后续迭代，本次不写）。
- 其余 MCP 协议合规要求仍需满足（见第三节）。

- Python 版本：**3.11+**
- 传输：**stdio**（由 MCP Client 拉起子进程，newline-delimited JSON-RPC 2.0）
- 协议版本：**严格实现 `2026-07-28` 版 MCP 规范**
- 交付物：一个可通过 `python -m petmcp` 或 `uv run petmcp` 启动的 stdio MCP Server

## 二、技术选型

- **首选官方 `mcp` Python SDK**（`modelcontextprotocol` 官方包）承载协议层与 stdio 传输。
- **硬性前置校验**：开始编码前，先确认所选 SDK 版本明确支持协议版本 **`2026-07-28`**（检查其协议版本常量 / 能返回 `supportedVersions` 含该版本）。选定后**固定精确版本**写入 `pyproject.toml`。
- 若官方 SDK 尚不支持 `2026-07-28`：改用**纯标准库自行实现最小 JSON-RPC over stdio 层**（读 stdin 逐行解析、写 stdout 逐行响应、日志走 stderr），协议要求以第三节为准，不引入其它框架。
- HTTP 调用上游 REST 用 `httpx`（异步）即可；不要引入其它重型依赖。

## 三、MCP 2026-07-28 强制合规要求（必须逐条实现并测试）

> 旧版 MCP 写法一律作废。本 MVP 只需声明 `tools` 能力。

### 1. 无状态协议（禁止握手/会话）
- **禁止** `initialize` / `notifications/initialized` 握手；**禁止**任何 session/连接级状态。
- 每个请求的元数据都在 `params._meta` 内。
- 必须实现 `server/discover`（规范 **MUST**）：

```json
{
  "jsonrpc": "2.0", "id": 1,
  "result": {
    "resultType": "complete",
    "supportedVersions": ["2026-07-28"],
    "capabilities": { "tools": {} },
    "_meta": { "io.modelcontextprotocol/serverInfo": { "name": "pet-hospital-mcp", "version": "0.1.0" } },
    "instructions": "用于查询宠物医院档案。使用 list_pets 过滤/检索宠物，参数含义见工具 schema。",
    "ttlMs": 3600000,
    "cacheScope": "public"
  }
}
```

- 收到 legacy `initialize` → 作为未知方法返回 JSON-RPC 错误，message 中**列出支持版本 `2026-07-28`**。
- **禁止**实现 `ping`、`logging/setLevel`、`notifications/roots/list_changed`。

### 2. 每请求 `_meta` 校验
每个入站请求 `params._meta` 必须含：

- `io.modelcontextprotocol/protocolVersion`（**必填**）
- `io.modelcontextprotocol/clientCapabilities`（**必填**）
- `io.modelcontextprotocol/clientInfo`（可选）

缺失必填字段 → JSON-RPC `-32602`。需要客户端能力而客户端未声明 → `-32021`（本 MVP 应无需任何客户端能力）。

### 3. 版本协商
- 仅支持 `2026-07-28`；其它版本 → `-32022`（`UnsupportedProtocolVersion`），`data = { "supported": ["2026-07-28"], "requested": "<客户端版本>" }`。

### 4. 结果结构
- 所有成功结果 **MUST** 含 `"resultType": "complete"`。
- 每个结果 `_meta` **SHOULD** 含 `io.modelcontextprotocol/serverInfo`。
- **禁止**服务端主动发 JSON-RPC 请求；不使用 MRTR（本 MVP 不需要）。

### 5. `tools` 能力（本 MVP 只有一个工具）
- `capabilities.tools = {}`（不声明 `listChanged`，无状态服务器不推送）。
- `tools/list` 结果 **MUST** 含 `ttlMs` 与 `cacheScope`（用 `3600000` / `"public"`），且**每次顺序确定**。
- `tools/list` 只返回 `list_pets` 一个定义。
- `tools/call` 返回 `content`（至少一个 `text` 块，内含 JSON 字符串）+ `structuredContent`（符合 `outputSchema`）+ `isError`。
- 错误分两层：
  - **协议错误** → JSON-RPC `error`：未知工具 `-32602`；参数不符合 `CallToolRequest` `-32602`；未知方法 `-32601`。
  - **工具执行错误** → result 且 `"isError": true`：上游 API 失败/校验失败/网络不可达，文本给出可自纠提示（例如提示先启动 `pethospital.exe`）。

### 6. 生命周期与通知
- 收到 `notifications/cancelled`：尽力停止在途请求，**不得回复**。
- stdin 关闭 / EOF：**立即优雅退出**（退出码 0）。
- 日志一律写 **stderr**；**stdout 只能出现合法 JSON-RPC 消息**（每行一条，不得内嵌换行）。

### 7. 不采用的已弃用特性
Roots、Sampling、Logging 均已 Deprecated，**不实现**。不使用 Tasks / MCP Apps 等扩展。

## 四、本 MVP 唯一工具：`list_pets`

- 映射上游：`GET /api/v1/pets`
- 支持筛选/排序/分页参数（与上游列表接口一致，全部可选）：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `q` | string | 关键词（上游列表查询） |
| `name` | string | 宠物姓名 |
| `ownerName` | string | 主人姓名 |
| `ownerPhone` | string | 主人电话 |
| `species` | string | 种类（如 `犬`） |
| `doctor` | string | 主治医生 |
| `disease` | string | 疾病 |
| `status` | string | 就诊状态（如 `待就诊`/`就诊中`/`住院中`/`已康复`/`慢性病随访`） |
| `min` | number | 总花费下限 |
| `max` | number | 总花费上限 |
| `sortBy` | string | 排序字段（如 `totalCost`） |
| `order` | string | `asc` / `desc` |
| `page` | integer | 页码，≥1，默认 1 |
| `pageSize` | integer | 每页条数，≥1，默认 20，上限 100 |

要求：

- 使用 JSON Schema 2020-12 定义 `inputSchema`（含 `enum`、`minimum`、默认值说明）与 `outputSchema`。
- `annotations`: `readOnlyHint: true`、`destructiveHint: false`、`idempotentHint: true`、`openWorldHint: false`。
- 只传非空的筛选参数给上游；查询参数需正确 URL 编码（中文如 `species=犬`）。
- 上游统一信封 `{ code, message, data, time }`：**解包 `data`**；`code != 200` 或 HTTP 非 2xx → `isError: true`。
- **实现前先实际调用一次 `GET /api/v1/pets`**，按真实返回结构确定 `outputSchema`（预计含 `pets` 数组与分页/总数等字段；`Pet` 字段见 README 数据模型）。`structuredContent` 必须与 `outputSchema` 一致。
- **不得**暴露删除、批量、管理类（`admin/seed`、`admin/compact`、`batch-delete`）等上游接口。

## 五、配置

- 上游基址：环境变量 `PET_API_URL`，默认 `http://127.0.0.1:8080`；可选命令行参数 `--api`、`--timeout`（默认 10s）。
- 不引入鉴权（上游无鉴权）。

## 六、建议代码结构

```text
petmcp/
├── pyproject.toml
├── README.md                       # 启动方式 + MCP Client 配置示例
├── src/petmcp/
│   ├── __init__.py
│   ├── __main__.py                 # stdio 入口 / 参数解析
│   ├── server.py                   # server/discover、tools/list、tools/call 分发
│   ├── protocol.py                 # 2026-07-28 常量、_meta 校验、错误码
│   ├── upstream.py                 # httpx 客户端、信封解包
│   └── tools/list_pets.py          # list_pets 的 schema 与处理器
└── tests/
    ├── test_protocol.py
    └── test_list_pets.py
```

## 七、测试与验收清单（MVP 的 Definition of Done）

必须提供可运行测试并逐项通过：

1. **无握手**：直接发送带完整 `_meta` 的 `tools/list` 成功；未发送 `initialize` 不报错。
2. `server/discover` 返回 `supportedVersions: ["2026-07-28"]`、`capabilities: {"tools": {}}`、`serverInfo`、`instructions`、`ttlMs`、`cacheScope`。
3. 缺 `protocolVersion` 或 `clientCapabilities` → `-32602`。
4. 版本为 `2025-11-25` → `-32022`，`data.supported` 含 `2026-07-28`。
5. `initialize` → 错误且 message 列出支持版本。
6. 所有成功结果含 `resultType: "complete"`；`tools/list` 含 `ttlMs`、`cacheScope`，且只含 `list_pets`，两次调用顺序一致。
7. `tools/call` `list_pets`（带筛选参数）返回 `content`(text) 与符合 `outputSchema` 的 `structuredContent`。
8. 上游不可达/`code != 200` → `isError: true` 且提示可读。
9. 未知工具 → `-32602`；未知方法（如 `ping`）→ `-32601`。
10. 资源不涉及（MVP 不实现 resources，收到 `resources/*` → `-32601`）。
11. stdout 始终是合法逐行 JSON-RPC；日志走 stderr；关闭 stdin 后退出码 0。
12. 集成测试：启动 `pethospital.exe`（或对已运行实例）后，用真实 stdin/stdout 跑一遍 `server/discover` → `tools/list` → `tools/call list_pets`（含至少一种筛选）。

## 八、后续迭代（本次明确不做，勿提前实现）

- 其余工具（`get_pet`、`search_pets`、`list_pet_records`、`get_stats`、`top-spenders` 等）。
- Resources（`pethospital://pets/{id}` 等）与 `resources/templates/list`。
- 少量写操作（`add_pet_record`、`add_pet_charge`）。
- 以上均留待 MVP 验收通过后再开。

## 九、禁止事项（负面清单）

- 禁止 `initialize` 握手、`Mcp-Session-Id`、SSE/GET 流、`resources/subscribe`、`Last-Event-ID`、`ping`、`logging/setLevel`。
- 禁止服务端主动发 JSON-RPC 请求。
- 禁止把任何非 JSON-RPC 内容写入 stdout。
- 禁止在 MVP 阶段提前实现 Resources / Prompts / 其它工具 / 写操作。
- 禁止暴露删除、批量、管理类上游接口。
- 新增依赖需先说明理由；除 `mcp`（或 stdlib 自实现）与 `httpx` 外不要引入框架。

## 十、权威参考（以规范为准）

- 规范总览：`https://modelcontextprotocol.io/specification/2026-07-28/`
- 版本与兼容：`/specification/2026-07-28/basic/versioning`
- 基础协议与 `_meta`：`/specification/2026-07-28/basic/index`
- `server/discover`：`/specification/2026-07-28/server/discover`
- Tools：`/specification/2026-07-28/server/tools`
- stdio 传输：`/specification/2026-07-28/basic/transports/stdio`
- 变更日志：`/specification/2026-07-28/changelog`
