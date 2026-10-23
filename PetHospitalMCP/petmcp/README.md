# 宠物医院 MCP Server（MVP）

把「宠物医院 REST API」的数据通过 REST 提取，并以 **MCP 协议 `2026-07-28`** 暴露给 Agent / MCP Client。

- 传输：**stdio**（由 MCP Client 拉起子进程，newline-delimited JSON-RPC 2.0）
- 能力：**仅 `tools`**，已实现 **`list_pets`**（查询）与 **`add_pet`**（新增）两个工具
- 现代协议：每个请求在 `_meta` 中自带协议版本与客户端能力，无状态、无 session
- **默认双代兼容**：也接受旧版 `initialize` 握手，以兼容尚未支持 2026-07-28 的 MCP 客户端（如 opencode 1.18.x）；用 `--modern-only` 可强制只接受 2026-07-28
- 数据来源：本机 `pethospital.exe`（默认 `http://127.0.0.1:8080`），需先启动它

> 完整需求见上级目录的 `PROMPT-MCP.md`。

## 运行前提

1. 先启动宠物医院服务：双击 `..\windows\pethospital.exe`（或运行该 exe），保持窗口开启。
2. Python **3.11+**。

## 安装

```bat
cd E:\LLM\PetHospitalMCP\petmcp
py -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## 运行

```bat
.venv\Scripts\python.exe -m petmcp
:: 或使用安装出的命令
.venv\Scripts\petmcp.exe
```

常用参数：

```bat
python -m petmcp --api http://127.0.0.1:8080   :: 上游基址（默认；也可用环境变量 PET_API_URL）
python -m petmcp --timeout 10                  :: 上游 HTTP 超时秒数（默认 10）
python -m petmcp --verbose                     :: 调试日志输出到 stderr
python -m petmcp --modern-only                 :: 只接受 2026-07-28，拒绝 legacy initialize 握手
```

stdout 只输出 JSON-RPC 帧，日志一律走 stderr。MCP Client 关闭 stdin 后进程会优雅退出（退出码 0）。

## MCP Client 配置

通用形式（把 `command` 指向虚拟环境里的 Python）：

```json
{
  "mcpServers": {
    "pet-hospital": {
      "command": "E:\\LLM\\PetHospitalMCP\\petmcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "petmcp"],
      "env": { "PET_API_URL": "http://127.0.0.1:8080" }
    }
  }
}
```

opencode（`opencode.json`）：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "pet-hospital": {
      "type": "local",
      "command": ["E:\\LLM\\PetHospitalMCP\\petmcp\\.venv\\Scripts\\python.exe", "-m", "petmcp"],
      "enabled": true
    }
  }
}
```

## 工具

### `list_pets`（查询）

映射上游 `GET /api/v1/pets`，只读（`readOnlyHint: true`）。参数全部可选：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `q` | string | 关键词，跨字段匹配（含病历全文） |
| `name` | string | 宠物姓名 |
| `ownerName` | string | 主人姓名 |
| `ownerPhone` | string | 主人电话 |
| `species` | string | 种类：`犬`/`猫`/`兔`/`鸟`/`仓鼠`/`爬宠`/`其他` |
| `doctor` | string | 主治医生 |
| `disease` | string | 疾病 / 主要诊断 |
| `status` | string | `待就诊`/`就诊中`/`住院中`/`已康复`/`慢性病随访` |
| `min` / `max` | number | 总花费区间（≥0） |
| `sortBy` | string | `id`/`name`/`ownerName`/`species`/`doctor`/`disease`/`status`/`totalCost`/`visitCount`/`createdAt`/`updatedAt` |
| `order` | string | `asc` / `desc`（默认 `desc`） |
| `page` | integer | 页码，≥1（默认 1） |
| `pageSize` | integer | 每页条数，1..100（默认 20） |

调用结果同时返回：

- `content`：人类可读的 JSON 文本
- `structuredContent`：符合工具 `outputSchema` 的结构化对象，含 `items`、`total`、`page`、`pageSize`、`totalPages`、`totalCost`

示例（MCP `tools/call` 参数）：

```json
{ "name": "list_pets", "arguments": { "species": "犬", "min": 1000, "sortBy": "totalCost", "order": "desc", "page": 1, "pageSize": 10 } }
```

### `add_pet`（新增）

映射上游 `POST /api/v1/pets`，写操作（`readOnlyHint: false`、`idempotentHint: false`）。

必填：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `name` | string | 宠物姓名 |
| `species` | string | 种类：`犬`/`猫`/`兔`/`鸟`/`仓鼠`/`爬宠`/`其他` |
| `ownerName` | string | 主人姓名 |
| `ownerPhone` | string | 主人电话 |
| `doctor` | string | 主治医生 |
| `disease` | string | 疾病 / 主要诊断 |

可选：`breed`、`gender`（`公`/`母`）、`ageMonths`（≥0）、`color`、`chipNo`、`ownerAddr`、`allergy`、`note`、`status`（默认 `待就诊`）。

成功返回新建档案（含自动编号 `PET-xxxxxx`，`totalCost=0`、`visitCount=0`、`records/charges` 为 `[]`）。

**缺失必填项会逐项询问**：

- 必填项在 schema 中故意**不设为 `required`**，模型可以先只提供部分参数调用。
- 若客户端当前连接可以发起服务端请求且声明了 `elicitation` 能力，服务端会用 `elicitation/create`（form 模式）**每次只问一个字段**，按 `name → species → ownerName → ownerPhone → doctor → disease` 的顺序补齐；用户拒绝/取消则中止。
- 否则自动回退：工具返回 `isError: true`，文本列出缺失字段并请模型在对话中逐项向用户询问，补齐后再调用。

示例（一次性提供全部必填项）：

```json
{ "name": "add_pet", "arguments": { "name": "旺财", "species": "犬", "ownerName": "张三", "ownerPhone": "13800001111", "doctor": "李医生", "disease": "急性肠胃炎" } }
```

示例（只给姓名，其余逐项询问）：

```json
{ "name": "add_pet", "arguments": { "name": "旺财" } }
```

## 协议合规（2026-07-28）

| 要求 | 实现 |
| --- | --- |
| 无状态、无 session | ✅ modern 请求走 per-request `_meta` 无状态路径 |
| `initialize` 握手 | ⚠️ 默认**双代兼容**接受（兼容旧客户端）；`--modern-only` 下返回 `-32022` |
| 每请求 `_meta` 携带版本/能力 | ✅ SDK 校验；缺失必填字段返回 `-32602` |
| `server/discover`（MUST） | ✅ 返回 `supportedVersions`、`capabilities`、`instructions`、`serverInfo`、`ttlMs`、`cacheScope` |
| 结果含 `resultType: "complete"` | ✅ SDK 自动加盖 |
| 每个结果含 `serverInfo` `_meta` | ✅ SDK 自动加盖 |
| `tools/list` 含 `ttlMs`/`cacheScope` 且顺序确定 | ✅ |
| 未知工具 → `-32602` | ✅ |
| 未知方法（如 `ping`）→ `-32601` | ✅ |
| 资源不存在/未实现 `resources/*` → `-32601` | ✅（本阶段不实现 Resources） |
| 不实现 `ping`/`logging/setLevel`/Roots/Sampling | ✅ |
| 日志只写 stderr | ✅ |
| `add_pet` 缺失必填项逐项询问 | ⚠️ legacy 连接用 `elicitation/create`；modern 连接回退为模型驱动（未实现 MRTR `input_required`） |

> 说明：`server/discover` 中 `capabilities.tools` 为 `{"listChanged": false}`，表示本服务不推送工具列表变更；未声明 `resources` / `prompts`。
>
> 说明：逐项 elicitation 仅在**可发起服务端请求且客户端声明 `elicitation` 能力**时启用（opencode 1.18.x 为 legacy，满足该条件）。2026-07-28 的 modern 连接禁止服务端主动请求，本阶段未实现 MRTR `InputRequiredResult`，会自动回退为模型驱动询问。
>
> 说明：默认采用 SDK 的**双代**循环：`server/discover`（或任何带现代 `_meta` 的请求）开启 2026-07-28 无状态连接；`initialize` 开启 legacy 握手连接。现代路径完全符合 2026-07-28；legacy 仅为客户端兼容。
>
> 说明：`--modern-only` 会直接驱动 SDK 的 modern-only 流循环 `_serve_modern_stream`（私有 API，已用 `mcp==2.2.0` 固定，并由 `tests/test_transport.py` 守护）。opencode 1.18.x 的 MCP 客户端只支持 legacy 握手（无 `server/discover`），因此需要默认的双代模式。

## 测试

```bat
.venv\Scripts\python.exe -m pytest -q
```

- `test_protocol.py`：协议常量与参数校验
- `test_list_pets.py` / `test_add_pet.py`：工具 schema、payload 构建、结果封装、elicitation/回退、错误路径
- `test_transport.py`：双代默认接受 legacy `initialize`、`--modern-only` 拒绝 `initialize`
- `test_stdio_integration.py`：真实 stdin/stdout 端到端（discover / tools/list / tools/call / 错误码）
- `test_elicitation_integration.py`：legacy 客户端逐项 elicitation（每次一个字段）与拒绝取消

需要宠物医院服务在运行的用例（`list_pets` 筛选、`add_pet` 创建）不可达时会跳过，其余用例仍可运行。`add_pet` 集成用例会自动删除它创建的测试档案。

## 目录结构

```text
petmcp/
├── pyproject.toml
├── README.md
├── src/petmcp/
│   ├── __init__.py
│   ├── __main__.py          # stdio 入口 / 参数解析
│   ├── config.py            # ServerConfig
│   ├── protocol.py          # 2026-07-28 常量、错误码、_meta 辅助
│   ├── models.py            # Pet / 病历 / 收费 Pydantic 模型（含 outputSchema）
│   ├── upstream.py          # 上游 REST 客户端（信封解包、错误映射）
│   ├── server.py            # 低阶 Server 接线（仅 tools）
│   ├── transport.py         # stdio 传输（默认双代，可选 modern-only）
│   └── tools/
│       ├── list_pets.py     # list_pets 的 schema 与处理器
│       └── add_pet.py       # add_pet 的 schema 与处理器
└── tests/
```

## 后续迭代（本阶段不做）

- 其余工具：`get_pet`、`search_pets`、`list_pet_records`、`get_pet_summary`、`get_stats`、`list_top_spenders`、`get_meta`
- 其余写操作：`update_pet`、`delete_pet`、`add_pet_record`、`add_pet_charge`
- Resources（`pethospital://pets/{id}` 等）与 `resources/templates/list`
- Resources / Prompts 能力与 `subscriptions/listen`
