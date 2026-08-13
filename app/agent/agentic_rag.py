"""
agentic_rag.py — Day 1: Agentic-RAG（Query Rewrite + Self-Reflection 循环）

对比 Day 3 的 research_agent.py（固定 DAG：Planner → Search → Writer）：

       Day 3: 固定 DAG                     Day 1: Agentic-RAG（自主决策）
  ┌─────────────────────┐          ┌────────────────────────────┐
  │  Planner（拆解子问题）  │          │  Query Rewrite（改写问题）   │
  │      ↓               │          │      ↓                    │
  │  Search（搜索）       │          │  Search（检索）            │
  │      ↓               │          │      ↓                    │
  │  Writer（生成答案）    │          │  Generate（生成）          │
  │      ↓               │          │      ↓                    │
  │  END                 │          │  Reflect（自评质量）──┐    │
  └─────────────────────┘          │      ↓（够好）         │    │
                                    │  END                 │    │
                                    │   ↑（不够，重检）←────┘    │
                                    └────────────────────────────┘

核心差异：
  - Day 3 是线性流水线，无反馈回路
  - Day 1 有 Conditional Edge（Reflect 节点判断是否重新检索）
  - Day 1 有循环边（Reflect → Search），用 retry_count 限制循环次数
  - Day 1 比 Day 3 多两个能力：Query Rewrite（改写模糊问题）+ Self-Reflection（自评质量）

传统 RAG vs Agentic-RAG：
  - 传统 RAG: 固定 Retrieve → Generate（一次检索一次生成）
  - Agentic-RAG: Agent 自主决策是否需要检索、检索什么、检索多少次
    · Query Rewrite: 多轮对话中模糊问题 → 独立可检索问题
    · Self-Reflection: 回答质量不够 → 自动重新检索再生成
"""

from typing import TypedDict
from langgraph.graph import StateGraph, END

from app.llm import chat

# 最大重检次数（防止无限循环）
MAX_RETRY = 2


# ============================================
# 1. 定义 AgenticRAGState
# ============================================

class AgenticRAGState(TypedDict):
    """
    对比 Day 3 的 ResearchState：多出 rewritten_query / reflection / retry_count。

    query:          用户原始问题（"它有多少天？"）
    rewritten_query: Query Rewrite 改写后的独立问题（"公司带薪年假多少天？"）
    context:        Search 节点检索到的上下文（拼接字符串）
    answer:         Generate 节点生成的回答
    reflection:     Reflect 节点的自评结果（"retry" / "accept"）
    retry_count:    已重检次数（达到 MAX_RETRY 强制接受）
    """
    query: str
    rewritten_query: str
    context: str
    answer: str
    reflection: str
    retry_count: int


# ============================================
# 2. Node 1: Query Rewrite（查询改写）
# ============================================

def query_rewrite_node(state: AgenticRAGState) -> dict:
    """
    结合多轮对话上下文，把模糊问题改写为独立可检索的问题。

    示例：
      上下文: 用户之前问过"公司的带薪休假政策"
      当前问题: "那我可以休多少天？"
      改写后:  "公司带薪休假政策中，员工可以休多少天？"

    输入: state["query"]
    输出: {"rewritten_query": "改写后的独立问题"}
    """
    prompt = f"""你是一个查询改写助手。请把用户问题改写为一个独立、完整、可直接检索知识库的问题。

要求：
1. 补全缺失的指代（"它"、"这个"、"那个"等）和上下文信息
2. 保留原问题的关键信息（实体、数字、时间等）
3. 只输出改写后的问题，不要任何解释或前缀
4. 如果问题本身已经完整明确，则原样输出

用户问题：{state["query"]}

改写后的问题："""

    rewritten = chat(prompt).strip()

    print(f"\n[QueryRewrite] 原问题: {state['query']}")
    print(f"[QueryRewrite] 改写后: {rewritten}")

    return {"rewritten_query": rewritten}


# ============================================
# 3. Node 2: Search（检索，复用混合检索器）
# ============================================

# 全局混合检索器（惰性初始化，避免每次导入都加载模型）
_hybrid_retriever = None


def _get_retriever():
    """惰性加载混合检索器（首次调用才构建，复用已构建实例）。"""
    global _hybrid_retriever
    if _hybrid_retriever is None:
        from app.rag.hybrid_retriever import build_hybrid_retriever
        _hybrid_retriever = build_hybrid_retriever("data/employee_policy.txt")
        print("[Search] 混合检索器构建完成（BM25 + FAISS + RRF）")
    return _hybrid_retriever


def search_node(state: AgenticRAGState) -> dict:
    """
    用改写后的问题检索知识库，返回检索到的上下文。

    输入: state["rewritten_query"]
    输出: {"context": "拼接的检索上下文"}

    ⭐ 关键：这里检索的是 rewritten_query（改写后的问题），
      而不是原始 query —— 这是 Agentic-RAG 与传统 RAG 的核心区别。
    """
    retriever = _get_retriever()

    # 用改写后的问题检索（top_k=3）
    docs = retriever.retrieve(state["rewritten_query"], top_k=3)

    # 拼接上下文
    context = "\n\n".join(
        f"[文档{i + 1}] {doc['text']}"
        for i, doc in enumerate(docs)
    )

    print(f"\n[Search] 检索到 {len(docs)} 篇文档")
    for i, doc in enumerate(docs, 1):
        print(f"  → 文档{i}: {doc['text'][:60]}...")

    return {"context": context}


# ============================================
# 4. Node 3: Generate（生成回答）
# ============================================

def generate_node(state: AgenticRAGState) -> dict:
    """
    基于检索到的上下文，生成对原始问题的回答。

    输入: state["query"] + state["rewritten_query"] + state["context"]
    输出: {"answer": "生成的回答"}
    """
    prompt = f"""你是一个知识库问答助手。请根据以下检索到的资料，回答用户问题。

用户原始问题：
{state["query"]}

（该问题被改写为：{state["rewritten_query"]} 进行检索）

检索到的资料：
{state["context"]}

请基于资料回答用户问题。要求：
1. 只依据检索到的资料回答，不要编造
2. 如果资料不足以回答，明确说明"资料中未找到相关信息"
3. 回答简洁准确

回答："""

    print("\n[Generate] 正在生成回答...")
    answer = chat(prompt)
    print(f"[Generate] 回答生成完成，共 {len(answer)} 字符")

    return {"answer": answer}


# ============================================
# 5. Node 4: Self-Reflection（自我反思）
# ============================================

def reflection_node(state: AgenticRAGState) -> dict:
    """
    自评回答质量，决定是否需要重新检索。

    输入: state["query"] + state["answer"] + state["context"]
    输出: {"reflection": "retry" 或 "accept"}

    ⭐ 这是 Agentic-RAG 的"反馈回路"核心：
      - 回答足够好 → "accept" → 结束
      - 回答不够好 → "retry" → 重新检索再生成
    """
    prompt = f"""你是一个回答质量评审员。请判断下面的回答是否充分回答了用户问题。

用户问题：
{state["query"]}

检索到的资料：
{state["context"]}

当前回答：
{state["answer"]}

请判断：
- 如果回答完整、准确、有依据，输出：accept
- 如果回答缺失关键信息、含糊不清、或"资料中未找到"但资料其实包含答案，输出：retry

只输出一个词（accept 或 retry）："""

    result = chat(prompt).strip().lower()

    # 解析结果（容错处理：只要包含 "retry" 就视为重检）
    reflection = "retry" if "retry" in result else "accept"

    print(f"\n[Reflection] 自评结果: {reflection}")

    return {"reflection": reflection}


# ============================================
# 6. 条件边：判断是否重检
# ============================================

def should_retry(state: AgenticRAGState) -> str:
    """
    Conditional Edge 的决策函数。
    返回 "search"（重新检索）或 "end"（接受回答）。

    逻辑：
      - 反思结果为 "retry" 且未超过最大重检次数 → 重新检索
      - 否则 → 结束
    """
    if state["reflection"] == "retry" and state["retry_count"] < MAX_RETRY:
        print(f"[Route] 需要重检（第 {state['retry_count'] + 1}/{MAX_RETRY} 次）")
        return "search"
    if state["reflection"] == "retry":
        print(f"[Route] 已达最大重检次数 {MAX_RETRY}，接受当前回答")
    return "end"


# ============================================
# 7. 构建 Agentic-RAG 图（含循环）
# ============================================

graph = StateGraph(AgenticRAGState)

# 注册节点
graph.add_node("rewrite", query_rewrite_node)
graph.add_node("search", search_node)
graph.add_node("generate", generate_node)
graph.add_node("reflect", reflection_node)

# 声明边
graph.add_edge("__start__", "rewrite")
graph.add_edge("rewrite", "search")
graph.add_edge("search", "generate")
graph.add_edge("generate", "reflect")

# ⭐ 条件边：Reflect 判断是否重新检索（循环的入口）
#   对比 Day 3 的固定 DAG —— 这里多了一条"反馈回路"
graph.add_conditional_edges(
    "reflect",
    should_retry,
    {"search": "search", "end": END},
)

# 编译
agentic_rag_app = graph.compile()


# ============================================
# 8. 便捷调用函数
# ============================================

def agentic_rag_answer(query: str) -> str:
    """
    执行 Agentic-RAG 流程并返回最终回答。

    等价于:
      result = agentic_rag_app.invoke({"query": query, "retry_count": 0})
      return result["answer"]
    """
    result = agentic_rag_app.invoke({
        "query": query,
        "rewritten_query": query,  # 初始默认
        "context": "",
        "answer": "",
        "reflection": "accept",    # 初始默认，防止无检索直接结束
        "retry_count": 0,
    })
    return result["answer"]


def demo_agentic_rag():
    """演示：对比传统 RAG 与 Agentic-RAG 的完整流程。"""
    query = "公司带薪休假政策中，员工可以休多少天年假？"

    print("=" * 60)
    print("Agentic-RAG 演示")
    print("=" * 60)
    print(f"用户问题: {query}")

    result = agentic_rag_app.invoke({
        "query": query,
        "rewritten_query": query,
        "context": "",
        "answer": "",
        "reflection": "accept",
        "retry_count": 0,
    })

    print("\n" + "=" * 60)
    print("最终回答:")
    print(result["answer"])
    print("=" * 60)


if __name__ == "__main__":
    demo_agentic_rag()
