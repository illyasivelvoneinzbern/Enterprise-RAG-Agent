Q1: 为什么 Research Agent 不能只用 if/else 循环实现？

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
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator

# ① State 定义（1 行）
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]

# ② 图构建（4 行）
graph = StateGraph(AgentState)
graph.add_node("llm", llm_node)                          # 注册节点
graph.add_node("tool", tool_node)
graph.add_edge("__start__", "llm")                       # 起始边
graph.add_conditional_edges("llm", should_continue,      # 条件边
    {"tool": "tool", END: END})
graph.add_edge("tool", "llm")                            # 循环边
app = graph.compile()                                    # 编译
from typing import TypedDict
from langgraph.graph import StateGraph, END

# 1. State：替换式 TypedDict（非 Annotated，区别于 Day 2）
class ResearchState(TypedDict):
    query: str
    sub_queries: list[str]
    search_results: list[str]
    final_answer: str

# 2. 三个 Node 函数签名（逻辑可以 Mock，签名必须对）
def planner_node(state: ResearchState) -> dict: ...
def search_node(state: ResearchState) -> dict: ...
def writer_node(state: ResearchState) -> dict: ...

# 3. 构建线性 DAG（无条件边、无循环）
graph = StateGraph(ResearchState)
graph.add_node("planner", planner_node)
graph.add_node("search", search_node)
graph.add_node("writer", writer_node)
graph.add_edge("__start__", "planner")
graph.add_edge("planner", "search")
graph.add_edge("search", "writer")
graph.add_edge("writer", END)
app = graph.compile()

from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

# 这是 LCEL 的唯一骨架 — 所有 RAG 链都是这个模式的变体
rag_chain = (
    {
        "context": retriever | format_docs,    # 检索结果 → 格式化
        "question": RunnablePassthrough(),      # 原问题透传
    }
    | ChatPromptTemplate.from_messages([...])   # 填入模板
    | llm                                       # 调 LLM
    | StrOutputParser()                         # 输出纯文本
)

"我主要用 LCEL 的管道符模式。核心就一个模式：RunnableParallel 注入 context 和 question → 填入 prompt 模板 → LLM → 输出解析。用 | 声明数据流，替代手写 '调函数 → 取结果 → 传参数' 的样板代码。"

如果追问"为什么不用 LangChain 的 RetrievalQA 封装？"：

"RetrievalQA 是黑盒，LCEL 链我可以看到每一步的输入输出，调试更直观。而且 LCEL 链可以无缝嵌入 LangGraph 的 Node 中，RetrievalQA 做不到。"
| 的本质	不是 shell pipe，是 Runnable.__or__()，返回新的 RunnableSequence。A | B = "把 A 的输出作为 B 的输入"	
dict 注入模式	{"context": X, "question": Y} — 这是 LCEL 的参数路由机制，不同字段可以来自不同 Runnable，框架自动并行/串行执行	
RunnablePassthrough 为什么必须？	如果没有它，原始 question 会被 retriever 的输出"吃掉"。dict 注入模式中，必须有一个字段透传原始输入	
RunnableLambda vs 直接调函数	直接调函数不能链入 |，包装后才是"一等公民"。相当于给普通函数发了一张 LCEL 护照	
ChatPromptTemplate.from_messages 替代手写 f-string	你的 build_prompt() 是手写 f"...{query}...{context}..."，LCEL 用模板变量 {question} {context} 声明式注入	
StrOutputParser 做了什么？	确保输出是纯 str。如果 LLM 返回 AIMessage，它提取 .content；如果已经是 str，原样返回
from langgraph.checkpoint.memory import MemorySaver

# ── 改动 1：创建 Checkpointer ──
checkpointer = MemorySaver()

# ── 改动 2：compile 时注入两个参数 ──
app = graph.compile(
    checkpointer=checkpointer,         # 自动存档每步状态
    interrupt_before=["search"],       # 在 search 节点前刹车
)

# ── 三步调用模式 ──
config = {"configurable": {"thread_id": "user-123"}}

# 步骤 1：启动 → 自动暂停在 search 前
result = app.invoke({"query": "..."}, config)

# 步骤 2：人类修改状态
app.update_state(config, {"sub_queries": ["新子问题1", "新子问题2"]})

# 步骤 3：从暂停点恢复
final = app.invoke(None, config)
"用 LangGraph 的 Human-in-the-Loop。两个改动：compile() 时加 interrupt_before=["search"] 让图在搜索前暂停，加 MemorySaver 做 Checkpoint。然后三步走：invoke 触发暂停 → update_state 注入人工修改 → invoke(None) 恢复执行。"
"Checkpointer 要求必须传 thread_id，否则会报 ValueError。每个 thread_id 对应独立的对话会话，跟 session_id 的概念一样。"
# 核心 1：RRF 融合公式（3 行，面试手写这个）
def rrf_score(rank, k=60):
    return 1.0 / (k + rank)

# 对每个文档：
# rrf_total = rrf_score(faiss_rank) + rrf_score(bm25_rank)
# 按 rrf_total 降序排列，取 top_k

# ────────────────────────────────────────

# 核心 2：HybridRetriever.retrieve() 四步流程
def retrieve(self, query, top_k=3):
    # 步骤 1：向量检索（语义）
    query_vec = self.model.encode([query])
    faiss_results = self.vectorstore.search(query_vec, top_k=10)

    # 步骤 2：BM25 检索（关键词）
    bm25_results = self.bm25.search(query, top_k=10)

    # 步骤 3：RRF 融合
    fused = rrf_fusion(faiss_results, bm25_results, k=60, final_top_k=top_k)

    # 步骤 4：可选重排序
    if self.reranker:
        fused = self.reranker.rerank(query, fused, top_k)

    return fused
"用混合检索。FAISS 向量检索覆盖语义相近的内容，BM25 关键词检索覆盖精确匹配，然后用 RRF（Reciprocal Rank Fusion）融合两个排序列表。RRF 的核心是只看排名不看绝对分值，公式是 1/(k+rank)，k=60。"
"BM25 只能做字面匹配，用户问'带薪休假'，BM25 找不到'年假'相关文档。FAISS 的 embedding 能把'年假'和'带薪休假'映射到相近向量。两者互补，不是替代关系。"

