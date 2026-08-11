# Day 1 笔记：LangGraph 核心概念

## 目标

理解 LangGraph 五大核心概念（State / Node / Edge / Conditional Edge / Checkpoint），并与现有 `agent_executor.py` 手写 Agent Loop 做一一对比。

---

## 一、为什么需要 LangGraph？

当前 Agent 工作流是一个**硬编码的线性流程**（`agent_executor.py`）：

```
LLM 调用 → 判断是否有 tool_calls → 有就执行工具 → 再调 LLM → 返回结果
```

这在单个工具场景下够用，但 Research Agent 的工作流是：

```
Planner → Search(多次) → Writer
```

这不是简单的 while 循环能表达的。LangGraph 的核心价值在于**用图（Graph）来定义 Agent 工作流**，而不是用 if/else 硬编码。

---

## 二、五大核心概念

### 1. State（状态）

**LangGraph 定义：** State 是一个贯穿整个工作流的数据容器，每个 Node 可以读取和修改它。

**已有等价物：** `agent_executor.py` 里的 `messages` 列表。

你现在做的（`agent_executor.py` line 27-78）：
```python
def run(self, messages):          # ← messages 就是"状态"，在函数间传递
    response = chat_with_tools(messages, ...)  # 读取 messages
    messages.append({...})        # 修改 messages（追加 assistant 消息）
    messages.append({...})        # 修改 messages（追加 tool 消息）
    response = chat_with_tools(messages, ...)  # 再次读取更新后的 messages
```

LangGraph 做法：把 `messages` 提升为**类型化的共享状态对象**：
```python
from typing import TypedDict, Annotated
import operator

class AgentState(TypedDict):
    messages: Annotated[list, operator.add]  # ← 自动追加而非覆盖
```

`Annotated[list, operator.add]` 的含义：每个 Node 返回的新消息**自动追加**到已有列表末尾，和你手写的 `messages.append()` 效果一样，但 LangGraph 帮你自动做了。

对于 Research Agent，State 会更复杂：`query`、`sub_queries`、`search_results`、`final_answer` 等都是 State 的一部分。

---

### 2. Node（节点）

**LangGraph 定义：** Node 是一个处理函数，接收 State，返回更新后的 State（或部分更新）。

**已有等价物：** LLM 调用和工具执行都是"处理步骤"。

你现在做的：
```python
# "节点1": LLM 调用
response = chat_with_tools(messages, get_tool_schema())

# "节点2": 工具执行
result = self.executor.execute(name, arguments)

# "节点3": LLM 再次调用（带工具结果）
response = chat_with_tools(messages, get_tool_schema())
```

LangGraph 中，每个步骤被显式声明为一个 Node 函数：
```python
def llm_node(state: AgentState) -> dict:
    """这就是你的 '节点1'"""
    response = chat_with_tools(state["messages"], tools)
    return {"messages": [response]}  # 返回的消息会被 operator.add 自动追加

def tool_node(state: AgentState) -> dict:
    """这就是你的 '节点2'"""
    # 执行工具...
    return {"messages": [tool_result]}
```

| 你现在 | LangGraph |
|--------|-----------|
| 函数调用 `chat_with_tools()` | Node 函数 `llm_node` |
| 函数调用 `executor.execute()` | Node 函数 `tool_node` |
| 手动传递 `messages` 参数 | LangGraph 自动通过 State 传递 |
| 没有显式声明"这是一个步骤" | `graph.add_node("llm", llm_node)` 显式注册 |

---

### 3. Edge（边）

**LangGraph 定义：** Edge 定义了 Node 之间的执行顺序。有**普通边**（固定跳转）和**条件边**（根据 State 决定跳转）。

**已有等价物：** 代码中执行顺序通过代码书写顺序隐式决定。

```
# 隐式流程：
chat_with_tools()  →  [隐式]  →  if tool_calls?  →  executor.execute()  →  [隐式]  →  chat_with_tools()
```

LangGraph 显式声明这个流程：
```python
# 普通边：固定从 A 到 B
graph.add_edge("tool", "llm")        # 工具执行完 → 回到 LLM

# 条件边：根据 State 决定去哪
graph.add_conditional_edges(
    "llm",                           # 从 llm_node 出发
    should_continue,                 # 判断函数：读 state 返回下一个 node 名字
    {
        "tool": "tool",              # 如果返回 "tool" → 跳到 tool_node
        END: END                     # 如果返回 END → 结束
    }
)
```

| 你现在 | LangGraph |
|--------|-----------|
| `if response.tool_calls:` | `should_continue(state)` 条件边 |
| 写完 execute 后手动调 chat_with_tools | `graph.add_edge("tool", "llm")` 声明 |
| 执行路径隐藏在代码逻辑中 | 执行路径在 Graph 中可视化 |

---

### 4. Conditional Edge（条件边）

**LangGraph 定义：** 根据当前 State 决定下一个 Node。

**已有等价物：** `agent_executor.py` line 37 的核心判断逻辑。

你的代码：
```python
# agent_executor.py line 37
if response.tool_calls:       # ← 判断条件
    # 有工具调用 → 执行工具
    messages.append({...})    # 追加 assistant 消息
    tool_call = response.tool_calls[0]
    name = tool_call.function.name
    arguments = json.loads(tool_call.function.arguments)
    result = self.executor.execute(name, arguments)  # 执行工具
    messages.append({...})    # 追加工具结果
    response = chat_with_tools(messages, ...)  # 再次 LLM（第 72 行）
# 无工具调用 → 直接返回（第 78 行）
return response.content
```

LangGraph 等价：
```python
def should_continue(state: AgentState) -> str:
    """决定下一步：继续工具调用 or 结束"""
    last_message = state["messages"][-1]   # 取最后一条消息
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tool"    # → 跳到 tool_node
    return END           # → 结束
```

对比：
```
你的代码                          LangGraph
─────────                        ─────────
if response.tool_calls:          should_continue 返回 "tool"
    ↓                                ↓
执行工具 + 再次 LLM              graph.add_edge("tool", "llm")
    ↓                                ↓
return response.content          should_continue 返回 END
```

---

### 5. Checkpoint（检查点）

**LangGraph 定义：** Checkpoint 在每个 Node 执行后自动保存 State 快照，支持断点恢复、回溯、人机协作。

**已有等价物：** `session_memory.py` + `memory.py` 就是某种形式的"检查点"——保存对话历史，让同一 session 的下一次请求延续上下文。

你现在做的（`session_memory.py`）：
```python
# 每次请求根据 session_id 恢复对话历史
memory = memory_manager.get_memory(req.session_id)  # ← "恢复检查点"
rag_agent.memory = memory                            # 绑定状态
```

LangGraph Checkpoint 更进一步：
- **自动保存：** 每个 Node 执行后自动快照，不需要手动 `add_user_message()` / `add_ai_message()`
- **可中断恢复：** 支持 `interrupt_before=["search"]`，在搜索前暂停等用户批准
- **可回溯：** 可以回到之前的任意状态重新执行

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
app = graph.compile(checkpointer=checkpointer)

# 每个 thread_id 就是一个独立会话
config = {"configurable": {"thread_id": "user-001"}}
app.invoke({"messages": [user_message]}, config)
```

---

## 三、完整对比：agent_executor.py vs LangGraph

把 `agent_executor.py` 中 `run()` 方法的每一步映射到 LangGraph：

```
你的 run(messages):                    LangGraph StateGraph:
─────────────────────                  ─────────────────────

1. chat_with_tools(messages, tools)    llm_node(state)
       ↓                                     ↓
2. if response.tool_calls:             should_continue(state)
       ↓                                     ↓
   YES → messages.append(assistant)    → 返回 "tool"
       → executor.execute(...)              ↓
       → messages.append(tool_result)   tool_node(state)
       → chat_with_tools(...)               ↓
       → return response.content        → graph.add_edge("tool", "llm")
                                            → 自动回到 llm_node
       ↓                                     ↓
   NO → return response.content        → 返回 END
```

---

## 四、流程图：agent_executor.py 的 Agent Loop

```
                   ┌─────────────┐
                   │   START     │
                   │ messages=[] │
                   └──────┬──────┘
                          │
                          ▼
              ┌───────────────────────┐
              │     llm_node          │
              │  chat_with_tools()    │ ← 对应 Node
              │  读取 state["messages"]│
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   should_continue()   │ ← 对应 Conditional Edge
              │  last_message 有      │
              │  tool_calls?          │
              └───┬───────────────┬───┘
                  │               │
          YES (有工具)       NO (无工具)
                  │               │
                  ▼               ▼
    ┌──────────────────┐    ┌──────────┐
    │   tool_node       │    │   END    │
    │ executor.execute()│    └──────────┘
    │ 返回 tool_result  │
    └────────┬─────────┘
             │
             │ graph.add_edge("tool", "llm")
             │ (普通边：自动回到 LLM)
             │
             └──→ 回到 llm_node
```

---

## 五、关键问答

### Q1: 为什么 Research Agent 不能只用 if/else 循环实现？

因为 Research Agent 的工作流不是简单的"判断→执行→再判断"循环，而是：

```
Planner(拆解问题) → Search(每个子问题一次，多次搜索) → Writer(综合生成)
```

- Planner 输出的是**多个**子问题，不是单个 tool_call
- Search 需要**遍历**子问题列表，每个调用搜索工具
- Writer 需要**汇总**所有搜索结果

用 if/else 写会变成嵌套循环 + 大量状态变量，而 LangGraph 用 DAG 图天然表达这种多步骤流水线。

### Q2: `Annotated[list, operator.add]` 解决了什么问题？

解决了 **Node 之间共享可变列表** 问题：

- 不用 `Annotated`：每个 Node 返回整个 messages 会**覆盖**旧值
- 用 `Annotated[list, operator.add]`：每个 Node 返回的新消息**追加**到已有列表

这和你手写 `messages.append()` 效果一样，但声明式更清晰，LangGraph 帮你自动合并。

### Q3: Checkpoint 和 SessionMemoryManager 有什么本质区别？

| | SessionMemoryManager | LangGraph Checkpoint |
|---|---|---|
| 保存内容 | 仅对话消息 | 完整 State（消息 + 中间结果 + 执行位置） |
| 触发时机 | 手动调用 `add_user_message` / `add_ai_message` | 每个 Node 执行后自动保存 |
| 中断恢复 | 不支持 | 支持 `interrupt_before` 在任意步骤暂停 |
| 回溯 | 不支持 | 支持回到任意历史检查点重新执行 |
| 粒度 | Session 级别 | Node 级别（每个步骤） |

本质区别：SessionMemoryManager 只存**数据**，Checkpoint 存**数据 + 执行位置**。

---

## 六、Day 1 总结

| 今天掌握的概念 | 对应已有的代码 |
|----------------|----------------|
| **State** | `messages` 列表 |
| **Node** | `chat_with_tools()` / `executor.execute()` |
| **Edge** | 隐式函数调用顺序 |
| **Conditional Edge** | `if response.tool_calls:` |
| **Checkpoint** | `SessionMemoryManager` |

明天 Day 2 将把这些概念落地为可运行的 LangGraph 代码，用 `StateGraph` 重写现有的 `agent_executor.py`。

---

## 阅读资源

- [LangGraph Quick Start](https://langchain-ai.github.io/langgraph/tutorials/introduction/) — 前 3 小节（Introduction、Setup、StateGraph basics）
