# dAgent

基于 DeepSeek 的 Function Calling 助手，采用 **core（业务核心）+ tui（界面）** 分层架构，core 与界面完全解耦，便于后续扩展 Web / Desktop 等界面。

## 目录结构

```
dAgent/
├── core/                     # 业务核心（不依赖任何 UI）
│   ├── config.py             # 配置加载
│   ├── events.py             # core 与 UI 之间的事件契约
│   ├── models.py             # 数据结构
│   ├── llm.py                # LLMClient 协议 + DeepSeekClient
│   ├── agent.py              # 对话编排、工具分发
│   └── tools/
│       ├── registry.py       # @tool 注册表 + dispatch
│       ├── shell.py          # PowerShell 调用封装
│       ├── system.py         # getData / isLeapYear
│       └── fileops.py        # 10 个文件操作
├── tui/                      # Textual 界面层
│   ├── app.py                # App：布局 + 事件桥接
│   ├── widgets.py            # ConversationView 流式展示
│   └── __main__.py           # python -m tui
├── main.py                   # 启动入口（默认 TUI）
├── config.ini                # 接口配置
├── requirements.txt
└── tests/                    # 核心逻辑测试（不联网）
```

## 安装

```powershell
py -3.13 -m pip install -r requirements.txt
```

## 配置

`config.ini`：

```ini
[default]
base_url = https://api.deepseek.com/
model = deepseek-chat
api_key = 你的 API Key
```

## 运行

```powershell
cd E:\LLM\Agent\dAgent
py -3.13 main.py
```

或：

```powershell
py -3.13 -m tui
```

Enter 发送，Ctrl+B 收起/展开侧边栏，Ctrl+Q 退出。

## 界面布局

整体采用低饱和深色主题（深炭黑背景、浅灰白文字），仅用低饱和色做角色区分。

- **顶部标题栏**：项目名 xAgent、当前模型、工作目录；右上角弱化展示的实时时钟。
- **全局信息提示栏**：标题栏下方通栏，低饱和灰蓝背景，展示工具总数、模型、工作目录与快捷键。
- **对话主视图（左侧）**：低暖橙用户消息、低灰蓝 xAgent 流式回答；暗茶绿工具卡片（无入参默认折叠、有入参展开，展开后显示格式化入参 JSON、执行耗时与返回结果，可点击切换）。
- **侧边面板（右侧）**：上部会话元信息（模型地址、会话 ID、轮次、调用上限），下部 12 个工具名称与简述，细线分隔；`Ctrl+B` 隐藏/显示，窗口宽度小于 90 列时自动收起。
- **输入区与状态栏**：中等深灰输入框与细微聚焦边框；底部状态栏左侧显示运行状态、轮次、工具调用次数、耗时，右侧平铺快捷键提示。

## 分层设计

- **core** 只通过「事件生成器」对外输出，不 import textual：
  - `TokenEvent`：流式 token
  - `ToolCallEvent`：开始调用工具
  - `ToolResultEvent`：工具结果
  - `DoneEvent`：本轮完成
  - `ErrorEvent`：错误
- **tui** 消费 `core.Agent.send()` 生成的事件，负责渲染与输入，不接触 HTTP、工具实现细节。
- **工具** 通过 `@tool` 装饰器注册，自动生成给模型用的 JSON Schema，并在 `dispatch` 中统一异常处理。

## 工具清单

| 工具 | 实现 |
|------|------|
| getData / getCurrentDirectory / listDirectory / getFileType / createFile / createDirectory / deleteDirectory / deleteFile / renamePath | PowerShell |
| isLeapYear / readTextFile / editTextFile | Python |

## 扩展新界面

新增 `web/` 或 `desktop/` 作为 `tui/` 的兄弟目录，复用同一个 `core.create_agent()`，按需渲染 `TokenEvent / ToolCallEvent / ...` 即可；`main.py` 可作为入口选择器。

## 测试

```powershell
cd E:\LLM\Agent\dAgent
py -3.13 -m unittest discover -s tests -v
```

## 注意事项

- `config.ini` 中 API Key 为明文，请勿提交公开仓库。
- `deleteDirectory`（递归删除）、`createFile`（覆盖同名）为高危操作。
- 工具中的 PowerShell 输出按系统 ANSI 编码读取；文本读写已改用 Python 以正确处理 Unicode。
