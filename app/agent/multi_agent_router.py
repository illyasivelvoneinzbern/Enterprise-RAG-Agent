"""
multi_agent_router.py — Week 6 Day 4: Multi-Agent Router（路由器模式）+ SubGraph

## 一、Multi-Agent 三种模式对比

| 模式       | 结构                  | 类比             | 项目参照                              |
|-----------|----------------------|-----------------|--------------------------------------|
| ① 顺序流水线 | A → B → C           | 工厂流水线        | research_agent.py（Planner→Search→Writer）|
| ② 路由器    | 意图判断 → 分发到专长 Agent | 前台客服分诊      | 本文件（Router Agent 分发）           |
| ③ 辩论/协作 | 多 Agent 并行输出 → 综合  | 评审委员会        | 待实现（Week 6 Day 5 Supervisor 延伸）|

关键差异：
  - 顺序流水线：固定链路，无分支，每步输出喂给下一步
  - 路由器：一个"分发者"根据意图做一次条件跳转，被分发到的子 Agent 独立完成
  - 辩论/协作：多个子 Agent 同时工作，最终由协调者（如 Supervisor）综合结果、决定是否迭代

## 二、Router 模式结构图

```
                用户问题（query）
                     │
                     ▼
        ┌────────────────────────┐
        │   Router Agent         │
        │   intent_node          │   ← LLM 判断意图（规则兜底）
        └───────────┬────────────┘
                    │  conditional edge（条件分发）
        ┌───────────┴────────────┐
        ▼                        ▼
┌───────────────┐          ┌───────────────┐
│ Research Agent│          │   RAG Agent   │
│  (SubGraph)   │          │   (SubGraph)  │
│  实时/外部信息  │          │   企业知识库    │
│ research(query)│          │  混合检索+LLM  │
└───────┬───────┘          └───────┬───────┘
        └───────────┬──────────────┘
                    ▼
              answer（最终回答）
```

本文件用 LangGraph 实现：
  - RouterState（父图状态）
  - intent_node（意图判断，LLM + 规则兜底）
  - Research Agent 子图（research_subgraph，复用 research_agent.research）
  - RAG Agent 子图（rag_subgraph，用 build_hybrid_retriever 检索 + chat 生成）
  - 父图用 conditional edge 按 intent 分发到两个子图
"""

from typing import TypedDict

from langgraph.graph import StateGraph, END

from app.llm import chat


# ============================================
# 1. RouterState（父图状态）
# ============================================

class RouterState(TypedDict):
    """
    Multi-Agent Router 的共享状态。

    query:    用户原始问题
    intent:   意图（"research" = 外部实时信息 / "rag" = 企业知识库）
    answer:   最终回答
    messages: 可选，收集上下文/调试信息（普通 list，覆盖式）
    """
    query: str
    intent: str
    answer: str
    messages: list[str]


# 企业政策关键词（规则兜底用）
POLICY_KEYWORDS = [
    "年假", "病假", "薪资", "工资", "入职", "报销", "请假",
    "加班", "社保", "公积金", "福利", "考勤", "假期", "休假",
    "制度", "政策", "合同", "体检", "调薪", "晋升",
]


# ============================================
# 2. Node: intent_node（意图判断）
# ============================================

def intent_node(state: RouterState) -> dict:
    """
    让 LLM 判断问题意图：
      - 涉及企业政策/知识库（年假/病假/薪资/入职/报销/请假…）→ "rag"
      - 需要外部实时信息/网络搜索（新闻/行情/最新动态…）     → "research"

    为稳定起见：
      1. 先尝试 LLM 判断
      2. LLM 判断失败或返回非法值时，回退到规则判断（关键词命中 → rag）
    """
    query = state["query"]
    intent = None

    # ---- 第 1 步：LLM 判断 ----
    try:
        prompt = f"""你是一个意图识别器。请判断用户问题属于哪一类：

- 涉及企业政策 / 内部知识库（如年假、病假、薪资、入职、报销、请假等企业制度）→ 输出 rag
- 需要外部实时信息 / 网络搜索（如新闻、市场行情、最新科技动态、实时数据）→ 输出 research

要求：只输出一个词：rag 或 research，不要输出其他任何内容。

用户问题：{query}

意图："""
        raw = chat(prompt).strip().lower()
        # 直接命中
        if raw in ("rag", "research"):
            intent = raw
        # LLM 偶发多输出内容时，尝试从中提取
        elif "rag" in raw and "research" not in raw:
            intent = "rag"
        elif "research" in raw and "rag" not in raw:
            intent = "research"
        else:
            print(f"[intent] LLM 返回非法值: {raw!r}，回退规则判断")
    except Exception as e:
        print(f"[intent] LLM 判断失败，回退规则判断: {e}")

    # ---- 第 2 步：规则兜底 ----
    if intent is None:
        intent = "rag" if any(k in query for k in POLICY_KEYWORDS) else "research"

    print(f"[Router] 意图判断 → {intent}   |  问题: {query}")
    return {
        "intent": intent,
        "messages": state.get("messages", []) + [f"intent={intent}"],
    }


# ============================================
# 3. RAG Agent 子图（rag_subgraph）
# ============================================

_rag_retriever = None  # 懒加载，进程内复用（避免每次重建 FAISS/BM25 索引）


def _get_rag_retriever():
    """懒加载混合检索器（默认参数，use_cross_encoder=False 避免加载大模型）。"""
    global _rag_retriever
    if _rag_retriever is None:
        from app.rag.hybrid_retriever import build_hybrid_retriever
        _rag_retriever = build_hybrid_retriever(
            "data/employee_policy.txt",
            use_cross_encoder=False,
        )
    return _rag_retriever


def rag_node(state: RouterState) -> dict:
    """
    RAG Agent 子图节点：检索知识库 + LLM 生成回答。

    流程：
      1. build_hybrid_retriever 构建 BM25+FAISS 混合检索器
      2. retrieve(query, top_k=3) 检索最相关的 3 个片段
      3. 组装上下文，调用 app.llm.chat 生成回答
      4. LLM 无 key 失败时，返回检索原文拼接作为兜底
    """
    query = state["query"]

    try:
        retriever = _get_rag_retriever()
        docs = retriever.retrieve(query, top_k=3)

        if not docs:
            print("[RAG] 未检索到相关知识库内容")
            return {"answer": "知识库中未找到与您问题相关的内容。", "messages": state.get("messages", [])}

        context = "\n\n".join(f"[{i + 1}] {d['text']}" for i, d in enumerate(docs))
        print(f"[RAG] 检索到 {len(docs)} 个相关片段")

        prompt = f"""你是一个企业知识库助手。请仅依据以下检索到的知识库内容回答用户问题。
要求：
1. 基于知识库内容作答，不要编造知识库中没有的信息
2. 如果知识库内容不足以回答，请如实说明
3. 回答简洁、有条理

知识库内容：
{context}

用户问题：{query}

回答："""

        try:
            answer = chat(prompt)
        except Exception as e:
            print(f"[RAG] LLM 生成失败，返回检索原文兜底: {e}")
            answer = "（LLM 暂不可用，以下为知识库检索原文，仅供参考）\n\n" + context

        return {"answer": answer, "messages": state.get("messages", [])}
    except Exception as e:
        print(f"[RAG] 检索过程失败: {e}")
        return {"answer": f"RAG 检索失败：{e}", "messages": state.get("messages", [])}


def build_rag_subgraph():
    """构建 RAG Agent 子图（作为一个 SubGraph 挂到 Router 父图下）。"""
    g = StateGraph(RouterState)
    g.add_node("rag_worker", rag_node)
    g.add_edge("__start__", "rag_worker")
    g.add_edge("rag_worker", END)
    return g.compile()


# ============================================
# 4. Research Agent 子图（research_subgraph）
# ============================================

def research_node(state: RouterState) -> dict:
    """
    Research Agent 子图节点：复用 research_agent.py 的 research(query) 函数。

    research() 内部已实现 Planner → Search → Writer 顺序流水线（模式 ①），
    这里把整个流水线当作一个"子 Agent 能力"复用。

    若外部搜索 API 不可用（如 LLM 无 key / 网络受限），try/except 兜底，
    返回"外部搜索暂不可用"的占位回答，保证演示可跑通。
    """
    query = state["query"]

    try:
        # 延迟 import：避免 research_agent 顶层依赖影响本文件可运行性
        from app.agent.research_agent import research
        answer = research(query)
        print("[Research] Research Agent 返回回答")
        return {"answer": answer, "messages": state.get("messages", [])}
    except Exception as e:
        print(f"[Research] 外部搜索暂不可用: {e}")
        return {
            "answer": "外部搜索暂不可用，请稍后再试。",
            "messages": state.get("messages", []),
        }


def build_research_subgraph():
    """构建 Research Agent 子图（作为一个 SubGraph 挂到 Router 父图下）。"""
    g = StateGraph(RouterState)
    g.add_node("research_worker", research_node)
    g.add_edge("__start__", "research_worker")
    g.add_edge("research_worker", END)
    return g.compile()


# ============================================
# 5. 构建 Router 父图（conditional edge 分发）
# ============================================

def route_by_intent(state: RouterState) -> str:
    """
    条件分发函数：返回目标节点名。
    非法 intent 值一律回退到 "rag"（企业知识库更安全）。
    """
    intent = state.get("intent", "rag")
    return intent if intent in ("research", "rag") else "rag"


def build_router():
    """构建 Router 图：intent 按意图用 conditional edge 分发到两个子 Agent 子图。"""
    research_subgraph = build_research_subgraph()
    rag_subgraph = build_rag_subgraph()

    g = StateGraph(RouterState)

    # 注册节点（子 Agent 作为 SubGraph 节点）
    g.add_node("intent", intent_node)
    g.add_node("research", research_subgraph)   # Research Agent 子图
    g.add_node("rag", rag_subgraph)             # RAG Agent 子图

    # 边：start → intent → (条件分发) → research / rag → END
    g.add_edge("__start__", "intent")
    g.add_conditional_edges(
        "intent",
        route_by_intent,
        {"research": "research", "rag": "rag"},  # 非法值由 route_by_intent 回退到 "rag"
    )
    g.add_edge("research", END)
    g.add_edge("rag", END)

    return g.compile()


# 编译一次，全局复用（懒初始化，避免 import 时立即加载模型）
router_app = None


def route(query: str) -> str:
    """
    对外入口：编译 Router 图并 invoke，返回最终回答。

    参数:
      query: 用户问题

    返回:
      str: 最终回答（来自 Research Agent 或 RAG Agent）
    """
    global router_app
    if router_app is None:
        router_app = build_router()

    result = router_app.invoke({"query": query, "messages": []})
    return result.get("answer", "")


# ============================================
# 6. 演示入口
# ============================================

if __name__ == "__main__":
    # Windows 终端默认 GBK 编码，强制 UTF-8 输出避免中文乱码
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 64)
    print("Week 6 Day 4 — Multi-Agent Router 演示")
    print("模式对比: ①顺序流水线 ②路由器(本演示) ③辩论/协作")
    print("=" * 64)

    test_queries = [
        "公司年假几天？",                 # 期望 → rag
        "帮我搜索最新的 AI 新闻",          # 期望 → research
        "病假工资怎么算？",                # 期望 → rag
        "今天股市行情怎么样？",            # 期望 → research
    ]

    for q in test_queries:
        print("\n" + "-" * 64)
        print(f"用户问题: {q}")
        answer = route(q)
        # 截断展示，避免回答过长刷屏
        display = answer if len(answer) <= 300 else answer[:300] + "…"
        print(f"最终回答: {display}")
        print("-" * 64)
