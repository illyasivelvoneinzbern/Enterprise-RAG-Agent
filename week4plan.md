# 第 4 周：LangGraph 落地 + LangChain LCEL 速通 + 混合检索

## 🎯 周目标

> 🥇 第一梯队：LangGraph（重点）+ LangChain（速通基础）+ 混合检索

**掌握 LangGraph 核心概念（State / Node / Edge / Checkpoint），将手写 Agent Loop 迁移至 LangGraph，构建 Research Agent，并补齐 LangChain LCEL 和混合检索两项关键技能。**

你当前的优势：已经在 `agent_executor.py` 中手写了一个完整的 Tool Calling 循环（LLM 判断 → 工具执行 → 结果反馈 → LLM 再生成），这在概念上就是 LangGraph 的简化版。第 4 周的核心任务是把这套心智模型转移到 LangGraph 上，并扩展为多步推理工作流，同时补齐 LangChain 基础能力。

---

## 📅 前半周（Day 1-3）：LangGraph 为主线

### Day 1（周一）：LangGraph 核心概念学习 ✅ 已完成

**学习内容：**

| 概念 | 类比你已经写的代码 |
|------|-------------------|
| **State** | 你的 `messages` 列表（维护对话和工具调用状态） |
| **Node** | 你的 `chat_with_tools()` 调用、`executor.execute()` 调用 — 每个 Node 就是一个处理步骤 |
| **Edge** | 你的 `if response.tool_calls:` 分支判断 — 决定下一步走哪个流程 |
| **Conditional Edge** | 工具调用后"回到 LLM 还是结束"的判断逻辑 |
| **Checkpoint** | 你的 `SessionMemoryManager` 机制 — 保存和恢复会话状态 |

**必做任务：**

1. 通读 [LangGraph 官方 Quick Start](https://langchain-ai.github.io/langgraph/tutorials/introduction/)
2. 理解 `StateGraph`、`add_node`、`add_edge`、`add_conditional_edges` 四个核心 API
3. 手写笔记：对比 LangGraph 的 State-Node-Edge 与你现有 `agent_executor.py` 的 messages-if-tool-loop 结构

**产出：** `day1_notes.md` — LangGraph vs 手写 Agent Loop 对比笔记 ✅

---

### Day 2（周二）：将现有 Agent 迁移到 LangGraph

**任务：用 LangGraph 重写你的 Tool Calling Agent**

用 LangGraph 重新实现你现有的 `agent_executor.py` 逻辑。

**目标架构：**

```
     ┌──────────┐
     │  START   │
     └────┬─────┘
          │
          ▼
   ┌──────────────┐
   │   llm_node   │  ← 调用 chat_with_tools()
   └──────┬───────┘
          │
          ▼ (conditional edge)
   ┌──────────────┐    有 tool_calls    ┌──────────────┐
   │  should_call │ ──────────────────→ │  tool_node   │
   │   _tools?    │                     │ (执行工具)    │
   └──────┬───────┘                     └──────┬───────┘
          │ 无 tool_calls                      │
          │                                    │
          ▼                                    │
   ┌──────────────┐                            │
   │    END       │ ←──────────────────────────┘
   └──────────────┘         (回到 llm_node)
```

**关键代码提示：**

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    messages: Annotated[list, operator.add]  # 自动追加消息

def llm_node(state: AgentState):
    # 替换你现有的 chat_with_tools 调用
    ...

def tool_node(state: AgentState):
    # 替换你现有的 executor.execute 调用
    ...

def should_continue(state: AgentState):
    # 替换你现有的 if response.tool_calls 判断
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tool_node"
    return END

# 构建图
graph = StateGraph(AgentState)
graph.add_node("llm", llm_node)
graph.add_node("tool", tool_node)
graph.add_edge("__start__", "llm")
graph.add_conditional_edges("llm", should_continue, {"tool_node": "tool", END: END})
graph.add_edge("tool", "llm")
app = graph.compile()
```

**产出：** 一个能用 LangGraph 运行的 `langgraph_agent.py`（功能与现有 `/rag/chat` 接口等价）

---

### Day 3（周三）：Research Agent（Planner → Search → Writer 完整链路）

将 Day 3-4 合并为一天，完成 Research Agent 的完整链路。

**核心概念：** Research Agent 不止是一次 Tool Calling，而是 **Plan → Search → Read → Write** 的多步工作流。

**目标架构：**

```
        用户问题: "LangGraph相比ReAct有什么优势？"
              │
              ▼
      ┌──────────────┐
      │   Planner    │  ← LLM 拆解子问题
      │   Node       │     输出: ["LangGraph核心概念",
      └──────┬───────┘            "ReAct核心概念",
              │                  "两者架构对比"]
              ▼
      ┌──────────────┐
      │   Search     │  ← 循环调用搜索工具（每个子问题一次）
      │   Node       │     收集所有搜索结果
      └──────┬───────┘
              │
              ▼
      ┌──────────────┐
      │   Writer     │  ← 综合所有搜索结果，生成最终回答
      │   Node       │
      └──────┬───────┘
              │
              ▼
            END
```

**任务：**

1. 设计 AgentState（包含：query、sub_queries、search_results、final_answer）
2. 实现 Planner Node：LLM 接收用户问题，输出 2-4 个子问题列表
3. 接入搜索工具（推荐 [Tavily Search API](https://tavily.com/) 或 [SerpAPI](https://serpapi.com/)，也可先用 Mock 数据）
4. 实现 Search Node：遍历子问题列表，每个调用搜索工具，汇总结果写入 state
5. 实现 Writer Node：综合原始问题 + 所有搜索结果 + 子问题分解，生成最终回答

```python
graph = StateGraph(ResearchState)

graph.add_node("planner", planner_node)
graph.add_node("search", search_node)
graph.add_node("writer", writer_node)

graph.add_edge("__start__", "planner")
graph.add_edge("planner", "search")
graph.add_edge("search", "writer")
graph.add_edge("writer", END)
```

**产出：** 完整的 Research Agent 能端到端回答问题

---

## 📅 后半周（Day 4-6）：新增内容 + 收尾

### Day 4（周四）：LangChain LCEL 速通 🆕

> 🥇 第一梯队新增：LangChain 基础（LCEL 编程范式）

**学习内容：**

| 概念 | 说明 |
|------|------|
| `RunnablePassthrough` | 透传数据，不做任何处理 |
| `RunnableLambda` | 包装自定义函数为 Runnable |
| `\|` 管道符 | 声明式链式调用，自动处理输入输出传递 |
| `RunnableParallel` | 并行执行多个 Runnable |

**核心任务：** 用 LCEL 把你现有的 RAG Pipeline 重写一遍：

```python
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

# 你手写的流程：
# Loader → Splitter → Embedding → VectorStore → Retriever → LLM

# LCEL 等价：
rag_chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt_template
    | llm
    | StrOutputParser()
)
```

**核心理解：** 感受声明式链式调用和你手写过程的区别——
- 手写：每一步手动调函数、手动传参数、手动处理输出
- LCEL：用 `|` 声明"数据从 A 流向 B"，框架自动处理传递

**产出：** 一个 LCEL 版本的 RAG Pipeline（`lcel_rag.py`），与你手写的 `build_index.py` + `retriever.py` 做对比

---

### Day 5（周五）：Human-in-the-Loop + Checkpoint 持久化

**任务：**

1. **Human Approval：** 在 Planner 和 Search 之间加入 `interrupt`，让用户确认子问题拆解是否正确再继续
2. **Checkpoint：** 使用 `MemorySaver` 或 `SqliteSaver` 持久化状态，支持断点恢复
3. **Streaming：** 将 Writer Node 的输出改为流式（LangGraph 的 `stream()` 模式），对标你现有的 `stream_answer()`

**关键代码提示：**

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
app = graph.compile(checkpointer=checkpointer, interrupt_before=["search"])
```

**产出：** 带 Human Approval + Checkpoint 的完整 Research Agent

---

### Day 6（周六）：混合检索 Hybrid Search 🆕

> 🥇 第一梯队新增：BM25 + FAISS 混合召回

**为什么需要混合检索？**

你现有的 [`retriever.py`](app/rag/retriever.py) 只做向量检索（语义相似度），但：
- 用户问"年假几天"→ 向量能匹配到"带薪年假"相关内容
- 用户问"工资什么时候发"→ 向量可能漏掉，但 BM25 关键词"工资"+"发"能精确命中

**BM25 + 向量检索互补关系：**

| | BM25 | 向量检索 |
|------|------|------|
| 擅长 | 关键词精确匹配 | 语义相似泛化 |
| 原理 | 词频统计 | Embedding 距离 |
| 互补点 | 召回精确关键词 | 覆盖同义表达 |

**任务：**

1. 安装 `rank_bm25` 库，实现 BM25 检索器
2. 在 Retriever 层做融合排序（RRF — Reciprocal Rank Fusion）：
   - FAISS 返回 top_k=10（按 L2 距离排序）
   - BM25 返回 top_k=10（按 BM25 分数排序）
   - RRF 融合两个排序结果，取最终 top_k=3
3. 对比纯向量检索 vs 混合检索的召回效果

**产出：** `hybrid_retriever.py` + 对比测试结果

---

### Day 7（周日）：回顾 + 面试问答准备 + README 初稿

**任务：**

1. **代码整理：** 确保所有代码提交到 GitHub，目录结构清晰
2. **写 README：** 参考你刚完成的 `README.md` 格式，为 Research Agent 项目写文档（架构图、技术栈、API 文档、核心难点）
3. **面试问答准备：** 重点关注以下问题

---

## 📝 第 4 周面试必会问题

| 问题 | 参考答案要点 |
|------|-------------|
| **LangGraph 相比 ReAct 有什么优势？** | ReAct 是固定的 Think→Act→Observe 循环；LangGraph 支持自定义 DAG 工作流（Plan→Search→Write 可以不是循环），State 管理更灵活，支持 Checkpoint 断点恢复，支持 Human-in-the-Loop |
| **Agent State 如何设计？** | TypedDict + Annotated reducer（如 `operator.add` 自动合并消息列表），包含 messages、中间结果、最终答案等字段 |
| **Conditional Edge 怎么用？** | 根据 State 的某个字段判断下一步走哪个 Node（对比你手写的 `if response.tool_calls`） |
| **Checkpoint 解决什么问题？** | 持久化工作流快照，支持断点恢复、回溯、人机协作审批后继续执行 |
| **Research Agent 和 RAG Agent 的区别？** | RAG 是 Retrieve→Generate 两阶段；Research Agent 是多步规划+多轮搜索+综合生成，适合开放性/对比性问题 |
| **LCEL 的 `\|` 管道符做了什么？** 🆕 | 声明式链式调用，自动处理输入输出传递，减少样板代码 |
| **BM25 + 向量检索为什么互补？** 🆕 | BM25 擅长关键词精确匹配（召回），向量擅长语义相似（泛化），混合后兼顾精度和覆盖面 |

---

## 📊 本周时间分配（按每日 5h × 7 天 = 35h）

| 天 | 重点 | 预估时间 | 变化 |
|----|------|---------|------|
| Day 1 | LangGraph 概念学习 | 5h | ✅ 已完成 |
| Day 2 | 手写 Agent 迁移到 LangGraph | 5h | 不变 |
| Day 3 | Research Agent 完整链路 | 5h | 🔄 合并原 Day 3+4 |
| Day 4 | LangChain LCEL 速通 | 5h | 🆕 新增 |
| Day 5 | Human-in-the-Loop + Checkpoint | 5h | 不变 |
| Day 6 | 混合检索 Hybrid Search | 5h | 🆕 替换原 FastAPI 服务化 |
| Day 7 | 回顾 + README + 面试准备 | 5h | 不变（新增面试题） |

---

## 🔗 本周关键资源

1. [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
2. [LangGraph Quick Start Tutorial](https://langchain-ai.github.io/langgraph/tutorials/introduction/)
3. [LangChain LCEL 文档](https://python.langchain.com/docs/concepts/lcel/) 🆕
4. [Tavily Search API](https://tavily.com/) — 搜索工具推荐
5. [rank_bm25 库](https://github.com/dorianbrown/rank_bm25) — BM25 算法 🆕
6. [LangGraph Agent 示例](https://github.com/langchain-ai/langgraph/tree/main/examples)

---

## ⚠️ 注意事项

- **不要从头学 LangChain 全部 API**，LangGraph 是其独立模块，LCEL 只学管道符链式调用即可
- Day 3 如果 Research Agent 完整链路时间太紧，Search + Writer 可以拆到 Day 4 上午半天，LCEL 压缩到 Day 4 下午
- Day 6 的混合检索是补齐 RAG 进阶的关键一步，不要跳过
- 每完成一天的代码，当天就 Git commit，保持提交记录清晰
