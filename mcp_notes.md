# Day 1 笔记：MCP 协议核心概念

> 目标：理解 MCP（Model Context Protocol）= Agent 与工具之间的**标准化通信协议**，
> 把第 4 周"工具硬编码在 Agent 内"升级为"工具独立演化、跨语言复用"，
> 并与现有 `ToolRegistry` / `SearchTool` 做一一对比。

---

## 一、MCP 是什么？解决什么问题？

**MCP = Model Context Protocol（模型上下文协议）**，Agent 与工具之间的标准化通信协议。

**解决的核心问题**：工具被硬编码在 Agent 内部，无法独立演化、无法跨语言复用。

- 加一个工具 / 改一个工具 → 必须改 Agent 代码
- 换一种语言写工具 → Agent 接不了（只有 Python）

MCP 把"工具"从 Agent 里**拆出去**，变成一个个独立服务，通过**协议**通信，实现"工具即插即用"。

---

## 二、对比表：现有代码 vs MCP 化

| 维度 | 现状（第 4 周，进程内硬编码） | MCP 化之后 |
|---|---|---|
| 工具位置 | [`SearchTool`](app/agent/tools.py:1) 硬编码在 Agent 进程内 | 工具作为**独立服务/进程**运行（knowledge_search / calculator / db） |
| 注册方式 | [`ToolRegistry`](app/agent/registry.py:10) 在本进程内 `register(tool)` | Agent 通过协议 `tools/list` **动态发现**工具 |
| 调用方式 | [`ToolExecutor`](app/agent/executor.py:13) `tool.run(**arguments)` 直接调用 | 通过协议 `tools/call` **远程调用**（JSON-RPC 消息） |
| 新增工具 | 必须改 Agent 代码（[`tool_schema.py`](app/agent/tool_schema.py:1) + 注册 + executor） | 新增一个 MCP Server，Agent **零改动** |
| 跨语言 | ❌ 仅 Python | ✅ 任何语言（Go/Rust/Java/JS…）都能提供工具 |

**关键洞察**：[`langgraph_agent.py`](app/agent/langgraph_agent.py:91) 的 `tool_executor.execute(name, arguments)` 已经是"按名字 + 参数调用工具"，是最接近 MCP Client 的地方，只是调用目标从本地换成远程协议。

---

## 三、MCP 三层架构

```
┌─────────────────────────────────────────────┐
│  MCP Host (Agent)                           │
│    ┌──────────────────────┐                 │
│    │  LangGraph Agent     │   langgraph_agent.py
│    │  (llm_node + tool)   │   (llm_node→tool_node 循环)
│    └──────────┬───────────┘                 │
│               │ 内嵌 MCP Client             │
│               │  (相当于 ToolExecutor 换成协议调用器)
└───────────────┼─────────────────────────────┘
                │  ① tools/list (工具发现)
                ▼  ② tools/call (工具调用)
┌─────────────────────────────────────────────┐
│  MCP Server (工具提供方)                     │
│    knowledge_search  /  calculator  /  db   │
│    作为独立进程运行 (stdio / sse)            │
└─────────────────────────────────────────────┘
```

### Host / Client / Server 名词表

| 角色 | 是什么 | 职责 | 你项目里的对应 |
|---|---|---|---|
| **MCP Host** | Agent 运行环境 | 编排 LLM 与工具调用 | [`langgraph_agent.py`](app/agent/langgraph_agent.py:125) 编译的 `StateGraph` |
| **MCP Client** | Host 内嵌的"通信器" | 连接 Server、发协议消息 | 现在是 [`ToolExecutor`](app/agent/executor.py:1)（本地直连），未来替换为 MCP Client |
| **MCP Server** | 工具的实际提供方（独立进程） | 暴露工具、执行工具并返回结果 | 现在是 [`SearchTool`](app/agent/tools.py:1)（Python 类），未来变成独立进程 |

---

## 四、三个核心方法（JSON-RPC 消息）

MCP 底层用 **JSON-RPC 2.0**（轻量 JSON 远程调用协议）。

### ① initialize —— 握手初始化

```json
{"jsonrpc": "2.0", "method": "initialize", "params": {"capabilities": {}}}
```

Client 连上 Server 先握手，互报能力（协议版本、支持特性）。类比：先交换名片，确认"怎么配合"。

### ② tools/list —— 工具发现

```json
{"jsonrpc": "2.0", "method": "tools/list", "params": {}}
```

```json
{"tools": [{"name": "knowledge_search", "description": "查询企业知识库", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}]}
```

**和手写 [`get_tool_schema()`](app/agent/tool_schema.py:3) 几乎一模一样**：`name` = 名字、`description` = 描述、`inputSchema` = `parameters`。**发现 = 从"写死在代码里"变成"运行时问一下"**。

### ③ tools/call —— 工具调用

```json
{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "knowledge_search", "arguments": {"query": "年假几天"}}}
```

```json
{"content": [{"type": "text", "text": "..."}]}
```

**等价于 [`executor.py`](app/agent/executor.py:13) 的 `execute(name, arguments)` → `tool.run(**arguments)`**：入参结构一致（名字 + 参数字典），只是返回值包进统一 `content` 结构。一句话：**`tools/call` 就是 `ToolExecutor.execute()` 的"网络版"**。

---

## 五、类比帮你消化

| 类比 | 说明 |
|---|---|
| **手写 SQL vs ORM** | ORM 隔离"怎么连数据库/解析结果"的细节；MCP 隔离"怎么连工具/传参/解析"——Agent 只关心工具名字和参数 |
| **USB 协议** | 鼠标、U盘插上即用，不用改主板；MCP = Agent 世界的"USB 协议"，新工具即插即用 |
| **餐厅点菜** | 你看菜单（tools/list）→ 点菜（tools/call）→ 后厨（Server）上菜；不需要认识厨师、也不需要进后厨 |

---

## 六、为什么说 MCP"解耦了工具和 Agent"？

Agent 不再持有工具的**实现**（类、进程、语言），只依赖工具的**协议描述**（名字 + schema）。

工具实现可以随便换（升级、换语言、换机器），只要协议不变，Agent 完全无感知——这就是"解耦"。

```
硬编码 Tool → MCP 标准化 → Skills 模块化 → Multi-Agent 协作
  (第4周)      (Day 1-2)      (Day 3)       (Day 4-5)
```

---

## 七、Day 1 任务自检

- [x] 画出 MCP 三层架构图（Host / Client / Server），标注职责
- [x] 对比 `ToolRegistry` 的"进程内注册" vs MCP 的"协议发现"
- [x] 理解 `initialize` / `tools/list` / `tools/call` 三个核心方法
- [x] 回答：为什么说 MCP"解耦了工具和 Agent"？（见第六节）

> 下一步（Day 2）：把 `knowledge_search` 封装为独立 MCP Server，再让 LangGraph Agent 通过 MCP Client 调用。

---

# Day 2 笔记：mcp 2.0 的 MCPServer 细节与工具标准化深入解析

> 目标：深入 Day 2 已落地的 [`app/mcp/server.py`](app/mcp/server.py:1) + [`app/mcp/client.py`](app/mcp/client.py:1)，
> 拆解 mcp 2.0 的 MCPServer API 细节，理解"工具标准化"到底带来哪 4 个红利，
> 以及真实踩过的坑（stdio 传输 + sys.path）。

## 一、MCPServer 与 FastMCP 的区别（1.x → 2.0）

> 项目 venv 中安装的是 **mcp 2.0.0**，官方已移除 FastMCP，改用 `MCPServer`。

| 维度 | FastMCP（1.x） | MCPServer（2.0） |
|---|---|---|
| 导入 | `from mcp.server.fastmcp import FastMCP` | `from mcp.server.mcpserver import MCPServer`（[server.py:29](app/mcp/server.py:29)） |
| 实例化 | `mcp = FastMCP("knowledge")` | `server = MCPServer("knowledge")`（[server.py:60](app/mcp/server.py:60)） |
| 注册工具 | `@mcp.tool()` | `@server.tool()`（[server.py:63](app/mcp/server.py:63)） |
| 启动 | `mcp.run()` | `server.run(transport="stdio")`（[server.py:84](app/mcp/server.py:84)） |
| Schema 字段 | `inputSchema`（JSON-RPC 消息里的驼峰名） | `input_schema`（Python 对象属性，见 [client.py:60](app/mcp/client.py:60)） |

一句话：**2.0 只是换了类名，用法几乎 1:1 平移**，"装饰器注册 + run 启动"的思维完全一致。

## 二、MCPServer 三个关键点

### ① name 是"服务身份标识"，不是工具名

```python
server = MCPServer("knowledge")        # ← "knowledge" 是服务名（身份标识）
@server.tool()
def knowledge_search(query: str) -> str: ...   # ← "knowledge_search" 才是工具名
```

一个 Server 可以暴露**多个工具**（多个 `@server.tool()`），它们共用同一个服务名。

### ② @server.tool() 装饰器自动做三件事

把"手写 schema + 手动注册"压缩成一行装饰器：

| 自动做的事 | 来源 | 对比第 4 周手写 |
|---|---|---|
| 提取**工具名** | 函数名 `knowledge_search` | 手写 `name`（[`tool_schema.py`](app/agent/tool_schema.py:1)） |
| 解析 **description** | 函数 docstring 第一段 | 手写 `description` 字段 |
| 生成 **input_schema** | 函数类型注解 `query: str`（[server.py:64](app/mcp/server.py:64)） | 手写 `parameters` 结构（[`get_tool_schema()`](app/agent/tool_schema.py:3)） |

即：`tools/list` 返回的 `name / description / input_schema` 全是从 Python 函数**自动推导**出来的，不再需要维护一份手写 JSON。

### ③ server.run(transport=...) 三种传输

| transport | 通道 | 适用场景 |
|---|---|---|
| `"stdio"` | 标准输入/输出管道（子进程） | **本地**、测试、Client 拉起 Server（本项目） |
| `"sse"` | HTTP + Server-Sent Events | 跨进程/远程、浏览器 |
| `"streamable-http"` | 纯 HTTP 双向流 | **生产**环境部署（一个 HTTP 端点即可） |

## 三、Client 侧 5 行核心代码的"隐藏工作"

[`call_knowledge_search()`](app/mcp/client.py:44) 只有 5 个异步步骤，每一行背后都藏了不少协议细节：

| # | 代码 | 隐藏的工作 |
|---|---|---|
| ① | `async with stdio_client(...)`（[client.py:48](app/mcp/client.py:48)） | **拉起子进程** + 建立**双向管道**（read/write 分别对应 Server 的 stdout/stdin）+ 进程生命周期管理（`async with` 退出自动清理） |
| ② | `async with ClientSession(read, write)`（[client.py:50](app/mcp/client.py:50)） | 把 Python 调用转成 **JSON-RPC 消息**收发；内部用 **id 匹配 request/response**，支持并发 |
| ③ | `await session.initialize()`（[client.py:52](app/mcp/client.py:52)） | **握手**：协商协议版本与能力（对应 Day 1 的 `initialize`） |
| ④ | `await session.list_tools()`（[client.py:55](app/mcp/client.py:55)） | **工具发现**：返回 `tool.name / description / input_schema`（对应 `tools/list`） |
| ⑤ | `await session.call_tool("knowledge_search", {...})`（[client.py:64](app/mcp/client.py:64)） | **远程调用**：把 `name + arguments` 发出去，等回包并解析 `content`（对应 `tools/call`） |

> 这 5 步 = Day 1 笔记里 `initialize / tools/list / tools/call` 三个核心方法的**完整落地**；
> 且 `async with` 同时把"建连、拆连、异常清理"都管好了，业务代码只需关心查询本身。

## 四、"工具标准化"的 4 个红利

| 红利 | 说明 | 本项目证据 |
|---|---|---|
| **解耦** | 新增/替换工具 → Agent 代码**零改动**，只改 Server | 换检索器（BM25→混合检索）只改 [server.py:38](app/mcp/server.py:38)，Client 无感知 |
| **跨语言** | 任何语言都能实现 Server，协议与语言无关 | Server 是 Python，但换 Go/Rust/JS 写 Client 照常调 |
| **自描述** | `input_schema` 本身就是"说明书"，LLM 读了自动学会用 | `list_tools` 打印出 schema（[client.py:60](app/mcp/client.py:60)）即"喂给 LLM 的菜谱" |
| **可组合** | Agent 可同时连多个 MCP Server，像拼积木 | 一个 Client 可开多个 session，各连一个服务 |

## 五、真实踩坑记录：stdio 传输 + 直接运行脚本

**现象**：直接用 `python app/mcp/server.py` 启动时，`import app.rag.*` 报 `ModuleNotFoundError`。

**原因**：Python 直接运行脚本时，只把**脚本所在目录** `app/mcp` 加入 `sys.path`，项目根目录不在路径里，`app` 包自然不可见。

**解决**：在脚本顶部手动把项目根目录补进 `sys.path`（[server.py:31-36](app/mcp/server.py:31)）：

```python
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
```

**教训**：
- 用 `python -m app.mcp.server` 启动时 `sys.path` 已含项目根，无需此 hack；但**直接运行**时就必须补——而 `stdio_client` 拉起子进程用的正是 `args=["app/mcp/server.py"]`（[client.py:40](app/mcp/client.py:40)），所以这个 hack 是必须的。
- 排查这类问题第一眼看 `sys.path`，别先怀疑代码逻辑。

> 下一步（Day 3）：在 LangGraph Agent 中真正接入 MCP Client，让 Agent 通过协议调用 MCP Server。
