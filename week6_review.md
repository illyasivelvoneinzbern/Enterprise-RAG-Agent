# Week 6 周回顾：MCP / Skills + Multi-Agent（Agent 工具演化史）

> 本周目标：把 Agent 能力从"工具硬编码"升级到"标准化协议 + 多 Agent 协作"——这是大厂 Agent 岗位**最看重**的能力。
> 核心收获：**"我不仅能手写工具，还能讲清工具从硬编码到 MCP → Skills → Multi-Agent 的完整演化史"**。
> 本周主线叙事（面试杀手锏）：**硬编码 Tool → MCP 标准化 → Skills 模块化 → Multi-Agent 协作**。

---

## 1. Week 6 周总结表（Day 1-7 一览）

| 天 | 主题 | 完成内容 | 产出文件 | 状态 |
|----|------|---------|---------|------|
| Day 1 | MCP 协议核心概念 | 三层架构图 + Host/Client/Server 名词表 + 与 ToolRegistry 对比 + 三个核心方法（initialize / tools/list / tools/call） | [`mcp_notes.md`](mcp_notes.md:1) | ✅ 已完成 |
| Day 2 | MCP Server 实战 | `knowledge_search` 封装为独立 MCP Server（mcp 2.0 MCPServer），Client 端 `stdio_client + ClientSession` 端到端调用验证通过；踩坑 stdio + sys.path | [`app/mcp/server.py`](app/mcp/server.py:1) + [`app/mcp/client.py`](app/mcp/client.py:1) | ✅ 已完成 |
| Day 3 | Skills 机制 | `Skill` 基类协议 + `RAGSkill`（检索+精排+生成能力模块）+ `SkillRegistry`（register/discover） | [`app/agent/skill.py`](app/agent/skill.py:1) | ✅ 已完成 |
| Day 4 | Multi-Agent Router | `intent_node` LLM 意图判断 + conditional edge 分发到 RAG/Research 子图（SubGraph），三种模式对比 | [`app/agent/multi_agent_router.py`](app/agent/multi_agent_router.py:1) | ✅ 已完成 |
| Day 5 | Supervisor 模式（本周重点） | `supervisor_node` 每轮 LLM 决策 + 可迭代分发 + `messages` 收集（operator.add）+ `rounds` 防失控 + `finish` 综合输出 | [`app/agent/supervisor_agent.py`](app/agent/supervisor_agent.py:1) | ✅ 已完成 |
| Day 6 | Dify + Coze 回顾 | 创建 [`day6_multiagent_notes.md`](day6_multiagent_notes.md:1) 模板（手写组件↔Dify↔Coze 概念映射 + 实操记录清单 + 对比表已预填） | [`day6_multiagent_notes.md`](day6_multiagent_notes.md:1) | 实操待补，模板已建 |
| Day 7 | 周回顾 + 演化史总结 | "Agent 工具演化史"总结 + Router vs Supervisor 对比 + 面试精讲 | 本文件 | ✅ 已完成 |

> 一句话本周：**Day 1-2 解决"工具怎么标准化"，Day 3 解决"能力怎么模块化"，Day 4-5 解决"多个 Agent 怎么协作"，Day 6 用平台验证，Day 7 串成一条主线。**

---

## 2. "Agent 工具演化史"总结（本周核心产出）

### 2.1 完整链路图

```
第4周  硬编码 Tool      SearchTool + ToolRegistry（进程内）
  ↓
Day1-2 MCP 标准化      knowledge_search → 独立 MCP Server（协议发现/调用）
  ↓
Day3   Skills 模块化   Skill 协议：注册 → 发现 → 执行（能力模块）
  ↓
Day4-5 Multi-Agent     Router（一次分发）→ Supervisor（可迭代协作）
```

**一句话主线**：工具从"写死在 Agent 里"（硬编码）→ "独立成服务、协议通信"（MCP）→ "封装成可自我发现的能力模块"（Skill）→ "多个专长 Agent 分工协作"（Multi-Agent）。每一步都是上一步"能力变强"和"复杂度变高"之间的权衡，面试讲这条线能串起 Week 4-6 全部内容。

### 2.2 每阶段详解（表格：代表文件 | 解决什么问题 | 局限/驱动下一步 | 面试话术）

#### 阶段① 硬编码 Tool（第 4 周）

| 维度 | 内容 |
|------|------|
| **代表文件** | [`app/agent/tools.py`](app/agent/tools.py:1)（`SearchTool`）+ [`app/agent/registry.py`](app/agent/registry.py:1)（`ToolRegistry`）+ [`app/agent/tool_schema.py`](app/agent/tool_schema.py:1)（手写 schema）+ [`app/agent/executor.py`](app/agent/executor.py:1)（`ToolExecutor`） |
| **解决什么问题** | 让 Agent 能调用工具：`ToolRegistry` 进程内注册工具，`ToolExecutor.execute(name, arguments)` 按名调用，`tool_schema` 生成 JSON Schema 喂给 LLM |
| **局限 / 驱动下一步** | 工具**硬编码在 Agent 进程内**：加工具/改工具必须改 Agent 代码；只能 Python；每次都要手写 schema + 注册 + executor。→ 驱动 MCP"把工具拆出去" |
| **面试话术** | "第 4 周我用 `ToolRegistry` + `SearchTool` 实现了进程内工具调用：`tool_schema` 生成 JSON Schema 让 LLM 选工具，`ToolExecutor.execute(name, arguments)` 按名字调用。这套流程能跑，但**工具和 Agent 强耦合**——工具是 Python 类，改一个工具就要改 Agent 代码，这就是我接下来用 MCP 解决的问题。" |

#### 阶段② MCP 标准化（Day 1-2）

| 维度 | 内容 |
|------|------|
| **代表文件** | [`app/mcp/server.py`](app/mcp/server.py:1)（`MCPServer` + `@server.tool()` 暴露 `knowledge_search`）+ [`app/mcp/client.py`](app/mcp/client.py:1)（`stdio_client + ClientSession`：initialize → list_tools → call_tool） |
| **解决什么问题** | **工具标准化**：工具独立成服务、协议发现（`tools/list`）/协议调用（`tools/call`）、跨语言、Agent **零改动**加工具。4 个红利 = 解耦 / 跨语言 / 自描述（input_schema 即说明书）/ 可组合 |
| **局限 / 驱动下一步** | MCP 提供的是**原子工具**（一次检索、一次调用），粒度是"操作"不是"能力"；没有"这个问题我能不能处理"的判断。→ 驱动 Skills"把能力封装成模块" |
| **面试话术** | "Day 2 我把 `knowledge_search` 封装成独立 MCP Server，Client 端 5 行核心代码：`stdio_client` 拉起子进程 → `ClientSession` 转 JSON-RPC → `initialize` 握手 → `list_tools` 发现工具 → `call_tool` 远程调用。**工具从 'import 进来用' 变成 '协议发现 + 调用'**——新增工具只需加一个 Server，Agent 零改动，这就是'工具标准化'的红利。" |

#### 阶段③ Skills 模块化（Day 3）

| 维度 | 内容 |
|------|------|
| **代表文件** | [`app/agent/skill.py`](app/agent/skill.py:1)（`Skill` 基类协议 + `RAGSkill` + `SkillRegistry`） |
| **解决什么问题** | 把**多步能力**（如"检索 + 精排 + 生成"）封装成能力模块：`can_handle(query)` 自我发现是否适合处理该问题（区别于 `ToolRegistry.get(name)` 精确查找）；Skill 是"能力模块"，Tool 是"原子操作" |
| **局限 / 驱动下一步** | Skill 解决的是"单个 Agent 怎么组织能力"；当问题复杂到需要多个专长 Agent 各司其职时，单 Agent 上下文/能力不够。→ 驱动 Multi-Agent"多个 Agent 协作" |
| **面试话术** | "Day 3 我设计了 Skill 协议：`Skill` 基类定义 `name/description/input_schema/can_handle/execute`，`SkillRegistry.discover(query)` 按 `can_handle` 做**能力发现**——Agent 面对新任务时'自我发现可用能力'，而不是写死调用哪个工具。我把'检索+精排+生成'封装成 `RAGSkill`，它内部复用 Day 2 的 `knowledge_search`。**Tool 是原子操作，Skill 是能力模块**，这是两者本质区别。" |

#### 阶段④ Multi-Agent（Day 4-5）

| 维度 | 内容 |
|------|------|
| **代表文件** | [`app/agent/multi_agent_router.py`](app/agent/multi_agent_router.py:1)（Router：`intent_node` + conditional edge 一次分发）+ [`app/agent/supervisor_agent.py`](app/agent/supervisor_agent.py:1)（Supervisor：`supervisor_node` 可迭代分发 + 收集 + 综合） |
| **解决什么问题** | 复杂任务由多个专长 Agent 分工协作：Router 按意图一次分发到 Research/RAG；Supervisor 作为中央协调者，**每轮 LLM 决策派谁、是否迭代、何时收尾**，收集各子 Agent 结果后综合输出 |
| **局限 / 驱动下一步** | Multi-Agent 引入协调成本（谁来决策、如何防失控）；→ 驱动 Day 6 用 Dify/Coze 验证"低代码 vs 手写"的取舍 |
| **面试话术** | "Day 4-5 我用 LangGraph SubGraph 实现了两种 Multi-Agent 架构。**Router 是'一次分发'**：`intent_node` 判断意图后用 conditional edge 派一个子 Agent，直接到 END，不收集不综合。**Supervisor 是'可迭代分发+收集+综合'**：`supervisor_node` 每轮用 LLM 决策派 research/rag/finish，用 `operator.add` 收集子 Agent 结果、`rounds` 防失控、`finish` 时综合输出——**本质是'用 LLM 做决策的 conditional edge'**，这是大厂最常用的 Multi-Agent 架构。" |

### 2.3 演化史记忆锚点（一句话背法）

```
硬编码 = 工具写死在代码里（改工具=改 Agent）
MCP    = 工具独立成服务，协议发现/调用（改工具≠改 Agent）
Skill  = 能力封装成模块，can_handle 自我发现（Agent 自己找能力）
Multi  = 多个专长 Agent 协作（Router 一次分发 / Supervisor 可迭代）
```

---

## 3. Router vs Supervisor 对比表（面试必背考点）

| 维度 | Router（Day 4） | Supervisor（Day 5，大厂最常用） |
|------|----------------|-------------------------------|
| **分发方式** | 一次分发：`intent_node` 判断后**只走一个子 Agent**，直接到 END | 可迭代分发：子 Agent 完成后**回到 Supervisor 重新决策**，可多次派不同子 Agent |
| **收集** | 不收集，各子 Agent 独立产出 `answer` | 收集：`messages` 用 `Annotated[list, operator.add]` **自动追加**所有子 Agent 结果 |
| **综合** | 无综合，只返回被分发到的子 Agent 结果 | 综合：`finish` 时汇总所有子 Agent 结果，LLM 生成最终综合回答 |
| **决策者** | `intent_node` 单次 LLM 意图判断 + 规则兜底 | `supervisor_node` **每轮循环都用 LLM 决策**（是否迭代 / 收尾） |
| **防失控** | 无循环，天然不会无限 | `rounds / max_rounds` 计数，超限强制 `finish` 防无限分发 |
| **本质** | 规则/LLM 的一次条件跳转 | "用 LLM 做决策的 conditional edge"，动态循环协作 |
| **代表文件** | [`multi_agent_router.py`](app/agent/multi_agent_router.py:1) | [`supervisor_agent.py`](app/agent/supervisor_agent.py:1) |

**一句话记忆**（背熟）：
> **"Router 是'一次分发'；Supervisor 是'可迭代分发 + 收集 + 综合'，是大厂最常用的 Multi-Agent 架构。"**

**代码对照**（两处关键差异点）：
- Router 分发后直连 END：`g.add_edge("research", END)` / `g.add_edge("rag", END)`（[multi_agent_router.py:284](app/agent/multi_agent_router.py:284)）
- Supervisor 子 Agent 完成后**回到 supervisor**：`g.add_edge("rag", "supervisor")` / `g.add_edge("research", "supervisor")`（[supervisor_agent.py:375](app/agent/supervisor_agent.py:375)）——这一行就是"可迭代"和"一次"的本质区别

---

## 4. 第 6 周面试必会问题精讲（5 题）

### Q1. 什么是 MCP？解决了什么问题？

**参考答案要点**：MCP（Model Context Protocol）= Agent 与工具之间的**标准化通信协议**。解决的核心问题：**工具被硬编码在 Agent 内部，无法独立演化、无法跨语言复用。**

**展开话术**：
- "MCP 把工具从 Agent 里拆出去，变成独立服务，通过协议通信。三层架构：**Host（Agent 运行环境）→ 内嵌 Client → 协议调用 → Server（工具提供方）**。三个核心方法：`initialize` 握手、`tools/list` 工具发现、`tools/call` 工具调用（JSON-RPC 2.0 消息）。"
- "对比我第 4 周的 `ToolRegistry`（进程内注册 + `tool.run()` 直调）：MCP 化之后工具**独立服务化、协议发现/调用、跨语言**，新增工具只需加一个 MCP Server，Agent 零改动。"
- "类比：MCP = Agent 世界的 **USB 协议**——设备（工具）即插即用，不用改主板（Agent）。"

### Q2. Tool Calling vs MCP？

**参考答案要点**：Tool Calling 是 **LLM 层**（OpenAI Function Calling，让模型"选择"调用哪个工具）；MCP 是**架构层**（工具服务的标准通信协议）。两者**互补**：MCP 提供工具，Function Calling 决定调用哪个。

**展开话术**：
- "Tool Calling 解决'模型怎么选工具'：把工具 schema 喂给 LLM，LLM 输出结构化的函数调用参数。我第 4 周的 `tool_schema.py` 生成 JSON Schema、`ToolExecutor.execute(name, arguments)` 就是这套流程。"
- "MCP 解决'工具怎么提供'：工具独立成服务、协议发现/调用，与 LLM 无关。"
- "一句话：**MCP 是工具的服务化标准（后端怎么暴露工具），Tool Calling 是 LLM 的调用机制（模型怎么选工具）**，一个管'有没有、怎么接'，一个管'选哪个、怎么调'，两者配合使用。"

### Q3. Skills 和 Tools 的区别？

**参考答案要点**：Tool 是**原子操作**（一次搜索/一次计算）；Skill 是**能力模块**（编排多个 Tool + 内部逻辑 + 状态），通过 `can_handle` **自我发现**。

**展开话术**：
- "Tool = 原子操作，'怎么做一个动作'，由 LLM/Agent 直接调用，对应 `ToolRegistry.get(name)` 精确查找。"
- "Skill = 能力模块，'我能解决哪类问题'，内部可编排多个 Tool + 业务逻辑，对应 `SkillRegistry.discover(query)` 按 `can_handle` 做**能力发现**——Agent 面对新任务时'自我发现可用能力'，而不是写死调用哪个工具。"
- "类比：**Tool 是一个 API，Skill 是一个微服务**。我把'检索+精排+生成'封装成 `RAGSkill`，它 `declares_tools = ["knowledge_search"]` 内部复用 MCP 工具——Skill 是比 Tool 更高一层的抽象。"

### Q4. Multi-Agent 的 Supervisor 模式怎么工作？

**参考答案要点**：Supervisor（主管）= 中央协调者：**接收任务 → 分发子 Agent → 收集结果 → 决策是否迭代 → 综合输出**。本质是"用 LLM 做决策的 conditional edge"。

**展开话术**：
- "我用 LangGraph 实现了：`SupervisorState` 里 `messages` 用 `Annotated[list, operator.add]` 自动收集子 Agent 结果；`supervisor_node` **每轮让 LLM 决策**派 research/rag/finish，失败时规则兜底；子 Agent 完成后**回到 Supervisor 重新决策**（这是可迭代分发）；`rounds/max_rounds` 防无限循环；`finish` 时汇总所有子 Agent 结果 LLM 综合输出。"
- "对比 Router：Router 是**一次分发**（intent 判断后只走一个子 Agent 就到 END，不收集不综合）；Supervisor 是**可迭代分发 + 收集 + 综合**，能处理需要多个 Agent 配合的复杂任务（比如'查病假政策 + 顺便查行业动态'会依次派 rag 和 research）。"
- "一句话：**Supervisor 就是'用 LLM 做决策的 conditional edge'，从 Day 1 手写的条件跳转自然升级而来**。"

### Q5. 为什么需要 Multi-Agent？

**参考答案要点**：单 Agent 上下文窗口不够、推理能力受限；Multi-Agent **分工协作、各司其职**，复杂任务由多个专长 Agent 并行/协作完成。

**展开话术**：
- "单 Agent 的局限：①**上下文窗口有限**，塞不进所有领域知识；②**推理能力受限**，一个模型难以同时精通检索、搜索、代码等多类任务；③**职责不分**，知识库问答和实时搜索混在一起，prompt 互相干扰。"
- "Multi-Agent 的价值：每个子 Agent 只做一件事（Research 管实时搜索、RAG 管企业知识库），**专才优于通才**；Supervisor 负责编排，能处理复杂任务、分而治之。"
- "代价也要讲：引入**协调成本**（谁来决策、如何防失控），所以需要 `rounds` 防循环、`finish` 收尾。'为什么需要'和'代价是什么'一起讲，比单方面吹 Multi-Agent 更有深度。"

---

## 5. 本周必会手写的代码（面试手撕清单）

> 用户学习模式：**每天都要会手写当天核心代码**。以下是 Week 6 各 Day 的"必会手写能力 + 关键代码要点 + 对应文件 + 代码骨架"，面试前对着这一节默写即可。

### 5.1 手写 MCP Server：`@server.tool()` 暴露工具（Day 2）

**手写要点**：`MCPServer` 创建服务 → `@server.tool()` 装饰器把函数暴露为工具 → **docstring 自动生成 description**、**类型注解自动生成 input_schema** → `server.run(transport="stdio")` 以标准输入输出方式启动（MCP 2.0 用 `MCPServer`，旧版 1.x 是 `FastMCP`，用法一致）。对应文件：[`app/mcp/server.py`](app/mcp/server.py:60)（`knowledge_search`）。

```python
from mcp.server.mcpserver import MCPServer

server = MCPServer("knowledge")            # 1. 服务名 = 工具提供方身份

@server.tool()                              # 2. 装饰器 = 注册为 MCP 工具
def knowledge_search(query: str) -> str:   # 3. docstring → description，类型注解 → input_schema
    """查询企业知识库，返回政策片段。"""
    return json.dumps(retriever.retrieve(query, top_k=3), ensure_ascii=False)

if __name__ == "__main__":
    server.run(transport="stdio")          # 4. stdio 启动，等待 Client 通信
```

**面试可能追问**：
- description / input_schema 是怎么来的？——**装饰器自动从 docstring 和类型注解生成**，不用手写 JSON Schema。
- MCP 2.0 和 1.x 的 API 差异？——`FastMCP` 已移除，改用 `MCPServer`。

### 5.2 手写 MCP Client 三流程（Day 2）

**手写要点**：`stdio_client` 拉起 Server 子进程（`StdioServerParameters` 指定命令）→ `ClientSession` 建立会话 → **initialize（握手）/ list_tools（工具发现）/ call_tool（工具调用）** 三个方法，配合 `async with` 上下文管理。对应文件：[`app/mcp/client.py`](app/mcp/client.py:44)（`call_knowledge_search`）。

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async with stdio_client(StdioServerParameters(
        command=sys.executable, args=["app/mcp/server.py"])) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()                       # ① 握手：协商协议版本/能力
        tools = await session.list_tools()               # ② 工具发现：Server 暴露了哪些工具
        result = await session.call_tool(                # ③ 工具调用：远程调用
            "knowledge_search", {"query": query})
        return result.content[0].text
```

**面试可能追问**：
- 为什么用 `stdio_client`？——默认 stdio 传输，Client 与 Server 走标准输入/输出管道，无需网络端口。
- 对比第 4 周硬编码调用？——`SearchTool().run(...)` 进程内直调 → `session.call_tool(...)` 协议远程调用独立进程。

### 5.3 手写 Skill 协议设计（Day 3）

**手写要点**：`Skill` 基类定义统一协议字段（`name / description / input_schema / declares_tools`）+ 两个方法（`can_handle` 能力匹配 / `execute` 执行能力）；`SkillRegistry` 实现 **register（注册）→ discover（能力发现）→ get（精确获取）**。对应文件：[`app/agent/skill.py`](app/agent/skill.py:67)（`Skill` 基类）+ [`app/agent/skill.py`](app/agent/skill.py:228)（`SkillRegistry`）。

```python
class Skill:
    name: str = ""; description: str = ""      # 协议字段（子类覆盖）
    input_schema: dict = {}; declares_tools: list = []
    def can_handle(self, query: str) -> bool:  # 能力匹配：这个 Skill 能否处理该问题
        return False
    def execute(self, state: dict) -> dict:    # 执行能力，返回 {"answer": ...}
        raise NotImplementedError

class SkillRegistry:
    def __init__(self): self.skills: dict[str, Skill] = {}
    def register(self, skill): self.skills[skill.name] = skill   # 注册
    def discover(self, query) -> list:         # 能力发现：返回 can_handle(query) 为 True 的
        return [s for s in self.skills.values() if s.can_handle(query)]
    def get(self, name): return self.skills.get(name)            # 精确获取
```

**面试可能追问**：
- Skill 和 Tool 的本质区别？——**Tool 是原子操作（精确查找），Skill 是能力模块（`can_handle` 自我发现）**。
- `RAGSkill` 怎么体现"能力模块"？——把"检索+精排+生成"封装为一个 Skill，`declares_tools = ["knowledge_search"]` 声明内部复用 Day 2 的 MCP 工具。

### 5.4 手写 Multi-Agent Router（Day 4）

**手写要点**：`RouterState`（query / intent / answer）→ `intent_node` LLM 意图判断（失败回退规则）→ `route_by_intent` 条件分发函数 → `add_conditional_edges` 分发到子图（SubGraph）→ 分发后 **直接到 END**（一次分发）。对应文件：[`app/agent/multi_agent_router.py`](app/agent/multi_agent_router.py:87)（`intent_node`）+ [`app/agent/multi_agent_router.py`](app/agent/multi_agent_router.py:256)（`route_by_intent`）。

```python
def intent_node(state) -> dict:                     # 意图判断：LLM 输出 rag / research，失败回退规则
    intent = chat(prompt).strip().lower()
    if intent not in ("rag", "research"):
        intent = "rag" if any(k in state["query"] for k in POLICY_KEYWORDS) else "research"
    return {"intent": intent}

def route_by_intent(state) -> str:                  # 条件分发函数：返回目标节点名
    return state.get("intent", "rag") if state.get("intent") in ("rag", "research") else "rag"

g = StateGraph(RouterState)
g.add_node("intent", intent_node)
g.add_node("rag", rag_subgraph)                     # 子 Agent 作为 SubGraph 节点
g.add_node("research", research_subgraph)
g.add_edge("__start__", "intent")
g.add_conditional_edges("intent", route_by_intent,
                        {"research": "research", "rag": "rag"})
g.add_edge("research", END); g.add_edge("rag", END)  # ⭐ 一次分发：直接到 END，不收集不综合
```

**面试可能追问**：
- Router 和 Supervisor 分发有什么区别？——**Router 一次分发后到 END**，Supervisor 子 Agent 完成后**回到 supervisor 重新决策**（[supervisor_agent.py:375](app/agent/supervisor_agent.py:375)）。
- 意图判断失败怎么办？——**规则兜底**：命中企业政策关键词 → rag，否则 → research。

### 5.5 手写 Supervisor 模式（Day 5，本周重点）

**手写要点**：`SupervisorState` 的 `messages` 用 `Annotated[list, operator.add]` **自动追加收集**子 Agent 结果 → `supervisor_node` 每轮 LLM 决策派 research / rag / finish（失败回退规则）→ 子 Agent 完成后**回到 supervisor**（可迭代）→ `rounds / max_rounds` 防失控 → `finish` 综合输出。对应文件：[`app/agent/supervisor_agent.py`](app/agent/supervisor_agent.py:57)（`SupervisorState`）+ [`app/agent/supervisor_agent.py`](app/agent/supervisor_agent.py:147)（`supervisor_node`）+ [`app/agent/supervisor_agent.py`](app/agent/supervisor_agent.py:334)（`route_after_supervisor`）。

```python
from typing import Annotated, TypedDict
from langgraph.graph import END, StateGraph
import operator

class SupervisorState(TypedDict):
    query: str
    messages: Annotated[list, operator.add]   # ⭐ 收集：子 Agent 结果自动追加，不覆盖
    next_agent: str                            # 本轮派谁：research / rag / finish
    rounds: int; max_rounds: int; answer: str

def supervisor_node(state) -> dict:            # 每轮 LLM 决策
    if state["rounds"] >= state["max_rounds"]: # 防失控：超限强制收尾
        return {"next_agent": "finish", "answer": _compose_answer(...)}
    decision = chat(prompt)                    # LLM 决策派 rag / research / finish
    result = {"next_agent": decision, "rounds": state["rounds"] + 1}
    if decision == "finish":                   # finish：综合所有子 Agent 结果
        result["answer"] = _compose_answer(state["query"], state["messages"])
    return result

def route_after_supervisor(state) -> str:      # 条件分发函数
    return state.get("next_agent", "finish") \
        if state.get("next_agent") in ("rag", "research") else "finish"

g = StateGraph(SupervisorState)
g.add_node("supervisor", supervisor_node)
g.add_node("rag", rag_node); g.add_node("research", research_node)
g.add_edge("__start__", "supervisor")
g.add_conditional_edges("supervisor", route_after_supervisor,
                        {"rag": "rag", "research": "research", "finish": END})
g.add_edge("rag", "supervisor")                # ⭐ 关键：子 Agent 完成后回到 supervisor
g.add_edge("research", "supervisor")           #     = 可迭代分发（区别于 Router 一次分发）
```

**面试可能追问**：
- `messages` 为什么用 `operator.add`？——**自动追加**各子 Agent 结果而不覆盖，实现"收集"。
- 怎么防无限循环？——**`rounds / max_rounds` 计数**，超限强制 finish（[supervisor_agent.py:174](app/agent/supervisor_agent.py:174)）。

> **总结**：这 5 块（MCP Server / MCP Client / Skill 协议 / Multi-Agent Router / Supervisor）是 Week 6 面试手撕的**"最小可写集合"**——能默写它们，就能讲清 **"硬编码 → MCP → Skills → Multi-Agent"** 的完整演化史。

---

## 6. Git 提交清单

### 6.1 本周新文件清单（相对路径）

**文档类：**
- `week6plan.md`（周计划）
- `mcp_notes.md`（Day 1-2 MCP 笔记：三层架构 + 4 红利 + 踩坑记录）
- `day6_multiagent_notes.md`（Day 6 模板：手写↔Dify↔Coze 映射 + 实操清单）
- `week6_review.md`（本文件）

**MCP 模块：**
- `app/mcp/__init__.py`
- `app/mcp/server.py`（MCPServer 暴露 `knowledge_search`）
- `app/mcp/client.py`（stdio_client + ClientSession 端到端调用）

**Skills 模块：**
- `app/agent/skill.py`（Skill 协议 + RAGSkill + SkillRegistry）

**Multi-Agent 模块：**
- `app/agent/multi_agent_router.py`（Router：intent_node + conditional edge 分发）
- `app/agent/supervisor_agent.py`（Supervisor：可迭代分发 + 收集 + 综合）

### 6.2 建议的 git commit 命令序列（分组提交）

```bash
# ① 计划文档
git add week6plan.md
git commit -m "Week6: 周计划——MCP/Skills + Multi-Agent（第三梯队，面试区分度）"

# ② MCP 标准化（Day 1-2）：概念笔记 + Server/Client 实战
git add mcp_notes.md
git commit -m "Week6 Day1: MCP 概念笔记（三层架构 + 与 ToolRegistry 对比）"

git add app/mcp/__init__.py app/mcp/server.py app/mcp/client.py
git commit -m "Week6 Day2: knowledge_search 封装为独立 MCP Server，Client 端到端调用验证通过"

# ③ Skills 模块化（Day 3）
git add app/agent/skill.py
git commit -m "Week6 Day3: Skill 协议 + RAGSkill + SkillRegistry（注册→发现→执行）"

# ④ Multi-Agent（Day 4-5）：Router + Supervisor
git add app/agent/multi_agent_router.py
git commit -m "Week6 Day4: Multi-Agent Router——intent_node + conditional edge 分发到 RAG/Research 子图"

git add app/agent/supervisor_agent.py
git commit -m "Week6 Day5: Supervisor 模式——可迭代分发+收集+综合，rounds 防失控"

# ⑤ Day 6 平台回顾模板 + 周回顾收尾
git add day6_multiagent_notes.md
git commit -m "Week6 Day6: Dify/Coze Multi-Agent 对比模板（手写↔平台概念映射预填）"

git add week6_review.md
git commit -m "Week6 Day7: 周回顾——Agent 工具演化史（硬编码→MCP→Skills→Multi-Agent）"
```

---

## 7. 自检清单（面试前逐条勾选）

- [ ] 能手画 MCP 三层架构图（Host / Client / Server），标注各组件职责与三个核心方法（initialize / tools/list / tools/call）
- [ ] 能讲清"工具标准化"的 4 个红利（解耦 / 跨语言 / 自描述 / 可组合），并结合 [`mcp_notes.md`](mcp_notes.md:206) 举代码例子
- [ ] 能讲清 Skill vs Tool 区别（原子操作 vs 能力模块，`can_handle` 自我发现 vs `ToolRegistry.get` 精确查找），并结合 [`skill.py`](app/agent/skill.py:1) 的 `RAGSkill`
- [ ] 能画 Supervisor 架构图 + 讲清与 Router 区别（一次分发 vs 可迭代分发+收集+综合，rounds 防失控），并结合 [`supervisor_agent.py`](app/agent/supervisor_agent.py:1) / [`multi_agent_router.py`](app/agent/multi_agent_router.py:1)
- [ ] 能完整讲出"Agent 工具演化史"（硬编码 → MCP → Skills → Multi-Agent），每阶段能说清"代表文件 / 解决什么问题 / 局限 / 面试话术"

**最后自我评估**：能不看笔记，把上面 5 个勾选项**口头讲一遍**（对着镜子或录音），每条 30 秒内讲完，就算过关。
