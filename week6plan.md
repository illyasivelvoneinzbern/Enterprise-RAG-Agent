# 第 6 周：MCP/Skills + Multi-Agent

## 🎯 周目标

> 🥉 第三梯队：MCP / Skills / Multi-Agent —— **面试区分度的关键**

前 5 周你已能"手写 RAG Pipeline + 用 Dify/Coze 平台"。第 6 周把 Agent 能力从"工具硬编码"升级到"标准化协议 + 多 Agent 协作"，这是大厂 Agent 岗位**最看重**的能力。本周聚焦三大块：

1. **MCP 协议**：理解 Agent 与工具的标准化通信协议，把 `knowledge_search` 封装为独立 MCP Server
2. **Skills 机制**：Agent 能力的模块化封装（注册→发现→调用），设计 Skill 协议
3. **Multi-Agent**：Router 模式 + Supervisor 模式（大厂最常用架构），用 LangGraph SubGraph 实现

**本周核心叙事线**（面试杀手锏）：

```
硬编码 Tool → MCP 标准化 → Skills 模块化 → Multi-Agent 协作
   (第4周)      (Day 1-2)      (Day 3)       (Day 4-5)
```

你当前的优势：第 4 周已完成 LangGraph（State/Node/Edge）+ `ToolRegistry` + `SearchTool` + `research_agent.py`（Planner→Search→Writer）。第 6 周把这些能力升级——`langgraph_agent.py` 的工具调用链将成为 MCP Client 的入口，`research_agent.py` 的 DAG 结构将成为 Multi-Agent 子 Agent 的骨架。

---

## 📅 前半周（Day 1-3）：MCP 协议 + Skills 机制

### Day 1（周一）：MCP 协议核心概念

**核心概念：** MCP（Model Context Protocol）= Agent 与工具之间的**标准化通信协议**。解决的核心问题：**工具被硬编码在 Agent 内部，无法独立演化、跨语言复用。**

| | 现状（第 4 周） | MCP 化之后 |
|---|---|---|
| 工具位置 | [`SearchTool`](app/agent/tools.py:1) 硬编码在 Agent 进程内 | 工具作为独立服务/进程运行 |
| 注册方式 | [`ToolRegistry`](app/agent/registry.py:1) 在本进程内注册 | Agent 通过协议 `list_tools` **发现**工具 |
| 调用方式 | `tool.run(query)` 直接调用 | 通过协议 `call_tool` 远程调用 |
| 新增工具 | 必须改 Agent 代码 | 新增一个 MCP Server，Agent **零改动** |
| 跨语言 | ❌ 仅 Python | ✅ 任何语言都能提供工具 |

**MCP 三层架构：**

```
┌─────────────────────────────────────────────┐
│  MCP Host (Agent)                           │
│    ┌──────────────────────┐                 │
│    │  LangGraph Agent     │  你的 langgraph_agent.py
│    │  (llm_node + tool)   │                 │
│    └──────────┬───────────┘                 │
│               │ 内嵌 MCP Client             │
└───────────────┼─────────────────────────────┘
                │  ① list_tools (工具发现)
                ▼  ② call_tool  (工具调用)
┌─────────────────────────────────────────────┐
│  MCP Server (工具提供方)                     │
│    knowledge_search  /  calculator  /  db   │
│    作为独立进程运行 (stdio/sse)              │
└─────────────────────────────────────────────┘
```

> 类比：手写 SQL vs ORM（隔离"怎么连数据库"的细节）；USB 协议（设备即插即用）。MCP = Agent 世界的"USB 协议"。

**关键代码提示（概念验证，先理解协议交互）：**

```python
# MCP 协议本质是 JSON-RPC：Client 与 Server 通过消息通信
# ① 初始化
{"jsonrpc": "2.0", "method": "initialize", "params": {"capabilities": {}}}

# ② 工具发现
{"jsonrpc": "2.0", "method": "tools/list", "params": {}}
# → 响应: {"tools": [{"name": "knowledge_search", "description": "...", "inputSchema": {...}}]}

# ③ 工具调用
{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "knowledge_search", "arguments": {"query": "年假几天"}}}
# → 响应: {"content": [{"type": "text", "text": "..."}]}
```

**任务：**
1. 画出 MCP 三层架构图（Host / Client / Server），标注每个组件的职责
2. 对比 [`ToolRegistry`](app/agent/registry.py:1) 的"进程内注册" vs MCP 的"协议发现"，写进 `mcp_notes.md`
3. 理解 `initialize` / `tools/list` / `tools/call` 三个核心方法的作用
4. 回答：为什么说 MCP"解耦了工具和 Agent"？

**产出：** `mcp_notes.md`（三层架构图 + Host/Client/Server 名词表 + 与现有 ToolRegistry 对比表）

---

### Day 2（周二）：MCP Server 实战

**核心任务：** 把你现有的 `knowledge_search` 工具封装为独立 MCP Server，再让 LangGraph Agent 通过 MCP Client 调用它。**这一步让你真正理解"工具标准化"。**

**关键代码提示（`mcp` Python SDK）：**

```python
# app/mcp/server.py —— 把 SearchTool 暴露为 MCP Server
from mcp.server.fastmcp import FastMCP
from app.rag.hybrid_retriever import build_hybrid_retriever
import json

retriever = build_hybrid_retriever("data/employee_policy.txt")

mcp = FastMCP("knowledge")

@mcp.tool()
def knowledge_search(query: str) -> str:
    """查询企业知识库（年假/病假/薪资/入职政策）"""
    docs = retriever.retrieve(query, top_k=3)
    return json.dumps(docs, ensure_ascii=False)

if __name__ == "__main__":
    mcp.run()          # stdio 方式启动（默认传输）
```

```python
# app/mcp/client.py —— LangGraph Agent 通过 MCP Client 调用
import asyncio, json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="python", args=["app/mcp/server.py"]
)

async def call_knowledge_search(query: str) -> str:
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()                          # ① 握手
            tools = await session.list_tools()                  # ② 工具发现
            result = await session.call_tool(
                "knowledge_search", {"query": query}            # ③ 工具调用
            )
            return result.content[0].text

if __name__ == "__main__":
    print(asyncio.run(call_knowledge_search("年假几天")))
```

**工具调用链变化（对比 Day 1 手写的调用）：**

```
旧（第4周）:   langgraph_agent.py → SearchTool.run() → retriever.retrieve()
新（Day 2）:   langgraph_agent.py → MCP Client → 协议调用 → MCP Server → retriever.retrieve()
```

**任务：**
1. 安装 `mcp` 库（`pip install mcp`）
2. 编写 `server.py`，用 `@mcp.tool()` 装饰 `knowledge_search`
3. 编写 `client.py`，用 `stdio_client` + `ClientSession` 调用
4. 分别打印 `list_tools` 返回的工具列表和 `call_tool` 的检索结果
5. 回答：工具从"import 进来用"变成"协议发现+调用"，带来了什么好处？

**产出：** `app/mcp/server.py` + `app/mcp/client.py` + 端到端调用验证

> ⚠️ 若 `mcp` 安装或网络受限，可先用"伪 MCP"（自己实现 JSON-RPC 收发 `tools/list` / `tools/call`）理解协议，再替换为官方 SDK。

---

### Day 3（周三）：Skills 机制

**核心概念：** Skills = Agent 能力的**模块化封装**（可插拔能力模块）。对比你的 `ToolRegistry`：

| | Tool（现有 `SearchTool`） | Skill |
|---|---|---|
| 粒度 | 原子操作（搜索、计算） | 能力模块（多个 Tool + 内部逻辑 + 状态） |
| 组成 | 单个 `run()` 函数 | 注册 → 发现 → 调用 + 子工具编排 |
| 是否独立 | 单点能力 | 完整可复用模块（含描述/参数/副作用） |
| 类比 | 一个 API | 一个微服务 |

**Skill 协议设计（核心任务）：**

```python
# app/agent/skill.py —— Skill 注册协议
class Skill:
    name: str                 # 唯一标识，如 "rag_skill"
    description: str          # 能力描述（供 Agent 发现）
    input_schema: dict        # 入参 JSON Schema
    declares_tools: list      # 该 Skill 内部用到的子工具

    def can_handle(self, query: str) -> bool: ...   # 能力匹配
    def execute(self, state: dict) -> dict: ...     # 执行并返回结果/状态

# 示例：把"检索+精排+生成"封装为 RAG Skill
class RAGSkill(Skill):
    name = "rag_skill"
    description = "基于企业知识库的检索增强生成"
    declares_tools = ["knowledge_search"]

    def can_handle(self, query):
        # 涉及企业政策/制度/流程 → 走 RAG
        return any(k in query for k in ["年假", "病假", "薪资", "入职", "报销"])

    def execute(self, state):
        docs = knowledge_search(state["query"])   # 复用 Day 2 的 MCP 工具
        return {"answer": generate_from(docs, state["query"])}

# SkillRegistry：注册→发现
class SkillRegistry:
    def __init__(self): self.skills = {}
    def register(self, skill): self.skills[skill.name] = skill
    def discover(self, query): 
        return [s for s in self.skills.values() if s.can_handle(query)]
```

**任务：**
1. 定义 `Skill` 基类协议（name / description / input_schema / can_handle / execute）
2. 实现 `SkillRegistry`（register / discover 两个方法）
3. 把一个"多步能力"封装为 Skill（示例：RAG Skill = 检索 + 精排 + 生成）
4. 对比：`Skill.can_handle`（能力发现）vs 现有 `ToolRegistry.get`（精确查找）的区别
5. 理解：Skill 让 Agent 面对新任务时"自我发现可用能力"

**产出：** `app/agent/skill.py`（Skill 协议 + SkillRegistry + RAG Skill 示例）

---

## 📅 后半周（Day 4-7）：Multi-Agent + 平台回顾 + 收尾

### Day 4（周四）：Multi-Agent 架构设计

**三种模式：**

| 模式 | 结构 | 类比 | 你已有的参照 |
|---|---|---|---|
| ① 顺序流水线 | A → B → C | 工厂流水线 | `research_agent.py` Planner→Search→Writer |
| ② 路由器 | 意图 → 分发到专长 Agent | 前台客服分诊 | Coze 客服路由（Day 6 体验过） |
| ③ 辩论/协作 | 多 Agent 并行输出 → 综合 | 评审委员会 | 待实现 |

**核心任务：** 用 LangGraph **SubGraph** 实现双 Agent 协作：`Research Agent`（搜索，已有 `research_agent.py`）+ `RAG Agent`（查知识库，已有），由 `Router Agent` 按意图分发。

**关键代码提示（Router 分发）：**

```python
from langgraph.graph import StateGraph, END

class RouterState(TypedDict):
    query: str
    intent: str          # "research" | "rag"
    answer: str

def intent_node(state: RouterState) -> dict:
    # 让 LLM 判断问题意图：外部实时信息 → research；企业政策 → rag
    intent = llm(f"判断意图(只回 research 或 rag)：{state['query']}")
    return {"intent": intent.strip().lower()}

def build_router():
    g = StateGraph(RouterState)
    g.add_node("intent", intent_node)
    # 子 Agent 作为 SubGraph 节点
    g.add_node("research", research_subgraph)
    g.add_node("rag", rag_subgraph)
    g.add_edge("__start__", "intent")
    # 条件分发：意图决定走哪个子 Agent
    g.add_conditional_edges(
        "intent",
        lambda s: s["intent"] if s["intent"] in ("research", "rag") else "rag",
    )
    return g.compile()
```

**任务：**
1. 理解 Multi-Agent 三种模式，画三张结构图
2. 复习 `research_agent.py`（已是顺序流水线模式 ①）
3. 定义 `RouterState`（query / intent / answer）
4. 实现 `intent_node`，用 LLM 判断问题意图
5. 用 LangGraph conditional edge 按意图分发到两个子 Agent

**产出：** `app/agent/multi_agent_router.py` + 三种模式架构图

---

### Day 5（周五）：Multi-Agent 实战：Supervisor 模式（本周重点）

**核心概念：** Supervisor（主管）作为中央协调者，接收任务 → 分发子 Agent → 收集结果 → 决策是否迭代 → 综合输出。**这是大厂最常用的 Multi-Agent 架构。**

```
                   用户问题
                      │
                      ▼
        ┌──────────────────────────────┐
        │      Supervisor Agent        │
        │  (规划 + 分发 + 收集 + 综合)   │
        └──┬────────┬────────┬─────────┘
           ▼        ▼        ▼
     Research     RAG      Code/兜底
      Agent      Agent       Agent
     (实时搜索)  (知识库)   (计算/兜底)
           └──── 收集结果 ────┘
                      │
                      ▼   Supervisor 综合输出 / 决定是否再迭代
```

**核心理解：** Supervisor 决定"派谁、是否迭代、何时收尾"。对比 Day 1 手写的 LangGraph conditional edge——**Supervisor 就是"用 LLM 做决策的 conditional edge"**，是 Day 1 到 Day 5 的能力自然升级。

**关键代码提示：**

```python
from langgraph.graph import StateGraph, END

class SupervisorState(TypedDict):
    query: str
    messages: Annotated[list, operator.add]   # 收集各子 Agent 结果
    next_agent: str                            # Supervisor 决定派谁
    max_rounds: int
    rounds: int

def supervisor_node(state) -> dict:
    # 让 LLM 决定：派 research / rag / 收尾(END)
    decision = llm(f"你是主管，分配任务给子Agent(只回 research/rag/finish)：{state['query']}")
    return {"next_agent": decision.strip().lower()}

def build_supervisor():
    g = StateGraph(SupervisorState)
    g.add_node("supervisor", supervisor_node)
    g.add_node("research", research_subgraph)
    g.add_node("rag", rag_subgraph)
    g.add_edge("__start__", "supervisor")
    g.add_conditional_edges(
        "supervisor",
        lambda s: s["next_agent"] if s["next_agent"] in ("research", "rag") else END,
    )
    return g.compile()
```

**任务：**
1. 实现 `supervisor_node`（LLM 决定派哪个子 Agent / 是否收尾）
2. 把 `research_agent.py` 和 RAG Agent 作为 SubGraph 挂到 Supervisor 下
3. 加入 `rounds` 计数，防止 Supervisor 无限分发
4. 对比 Day 4 Router：**Router 是"一次分发"，Supervisor 是"可迭代分发+收集+综合"**——记下来，这是面试考点
5. 用 `app/main.py` 暴露一个 `/rag/supervisor` 接口测试效果

**产出：** `app/agent/supervisor_agent.py` + Router vs Supervisor 对比表

---

### Day 6（周六）：Dify + Coze 回顾

**任务：** 用 Dify/Coze 分别搭建 Day 4-5 手写的 Multi-Agent 工作流，对比**低代码 vs 手写**的开发效率差异。

**操作步骤：**
1. 在 Dify 用"工作流"编排一个 2 分支路由（复用 `dify_notes.md` 模板）
2. 在 Coze 用 Multi-Agent 模式搭建客服分流（复用 `coze_notes.md` 模板）
3. 体验 Dify/Coze 自带的 Supervisor 类能力（如 Coze 的 Multi-Agent 编排）
4. 更新 `dify_notes.md` / `coze_notes.md`：补充"Multi-Agent 场景"对比
5. 记录：同样一个"意图分流"，手写（Day 4-5）vs 平台（Day 6）的时间/成本/灵活性差异

**产出：** `dify_notes.md` / `coze_notes.md` 补充 Multi-Agent 章节

> 重点是对比手写 vs 低代码的**取舍**，不必重复搭建全部功能。

---

### Day 7（周日）：周回顾 + "Agent 工具演化史"总结

**任务：**
1. **代码整理：** 提交本周所有代码到 GitHub（`app/mcp/`、`app/agent/skill.py`、`app/agent/multi_agent_router.py`、`app/agent/supervisor_agent.py`）
2. **写"Agent 工具演化史"文档（本周核心产出）：** 完整链路：

```
第4周  硬编码 Tool      SearchTool + ToolRegistry（进程内）
  ↓
Day1-2 MCP 标准化      knowledge_search → 独立 MCP Server（协议发现/调用）
  ↓
Day3   Skills 模块化   Skill 协议：注册 → 发现 → 执行（能力模块）
  ↓
Day4-5 Multi-Agent     Router（一次分发）→ Supervisor（可迭代协作）
```

3. **面试问答准备：** 重点掌握下方 5 个面试问题

**产出：** `week6_review.md`（演化史图 + Router vs Supervisor 对比 + 面试题精讲）

---

## 📝 第 6 周面试必会问题

| 问题 | 参考答案要点 |
|------|-------------|
| **什么是 MCP？解决了什么问题？** | Model Context Protocol，标准化 Agent-工具通信协议。解决工具硬编码问题：工具独立服务化、跨语言复用、Agent 通过协议发现/调用而非 import |
| **Tool Calling vs MCP？** | Tool Calling 是 LLM 层（OpenAI Function Calling，让模型选择工具）；MCP 是架构层（工具服务标准协议）。两者互补：MCP 提供工具，Function Calling 决定调用哪个 |
| **Skills 和 Tools 的区别？** | Tool 是原子操作（搜索/计算）；Skill 是能力模块（包含多个 Tool + 内部逻辑 + 状态），通过 can_handle 自我发现 |
| **Multi-Agent 的 Supervisor 模式怎么工作？** | Supervisor 中央协调：接收任务 → 分发子 Agent → 收集结果 → 决策是否迭代 → 综合输出。本质是 LLM 驱动的 conditional edge |
| **为什么需要 Multi-Agent？** | 单 Agent 上下文窗口不够、推理能力受限；Multi-Agent 分工协作、各司其职，复杂任务由多个专长 Agent 并行/协作完成 |

---

## 📊 本周时间分配（按每日 5h × 7 天 = 35h）

| 天 | 重点 | 预估时间 | 定位 |
|----|------|---------|------|
| Day 1 | MCP 协议概念（三层架构） | 5h | 概念核心 |
| Day 2 | MCP Server 实战（knowledge_search 封装） | 5h | **手写核心** |
| Day 3 | Skills 机制 + Skill 协议设计 | 5h | **手写核心** |
| Day 4 | Multi-Agent Router + SubGraph | 5h | **手写核心** |
| Day 5 | Supervisor 模式（本周重点） | 5h | **手写核心** |
| Day 6 | Dify/Coze Multi-Agent 对比 | 5h | 平台回顾 |
| Day 7 | 演化史总结 + 面试准备 | 5h | 收尾 |

---

## 🔗 本周关键资源

1. [MCP 官方文档](https://modelcontextprotocol.io/) — 协议规范与 SDK
2. [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — `mcp` 库（FastMCP / ClientSession）
3. [Anthropic MCP 介绍](https://www.anthropic.com/news/model-context-protocol) — MCP 设计初衷
4. [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/) — SubGraph / StateGraph / conditional edge
5. [Claude Skills 官方文档](https://docs.claude.com/en/docs/agents/skills) — Skills 机制参考
6. [Dify](https://dify.ai/) / [Coze](https://www.coze.cn/) — Multi-Agent 工作流编排

---

## ⚠️ 注意事项

- **MCP 是本周核心中的核心**：面试高频题，务必能手画三层架构图 + 讲清"解耦了什么"
- Day 2 的 `mcp` 库是**本周唯一新依赖**；若安装/网络受限，可用"伪 MCP"（自实现 JSON-RPC 的 tools/list + tools/call）先理解协议再升级
- Day 3 的 Skills 是**概念理解 + 协议设计**为主，重点是"注册→发现→调用"模式，不必实现复杂内部逻辑
- Day 5 Supervisor 是**面试必背**：务必能手画架构图 + 讲清"为什么需要 Supervisor"（对比 Router）
- Day 6 是平台回顾，重点是**对比手写 vs 低代码的取舍**，不必重复搭建全部功能
- Day 7 的"Agent 工具演化史"是 Week 6 收官的**核心产出**——它是 8 周学习的主线叙事，面试时串起"硬编码→MCP→Skills→Multi-Agent"的完整逻辑链
