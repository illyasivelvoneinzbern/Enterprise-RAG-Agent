"""
supervisor_agent.py — Week 6 Day 5: Multi-Agent Supervisor（中央协调者，本周重点）

## 一、Supervisor 模式结构图

```
                   用户问题 (query)
                      │
                      ▼
        ┌──────────────────────────────┐
        │      Supervisor Agent        │
        │  (规划 + 分发 + 收集 + 综合)   │
        └──┬────────┬────────┬─────────┘
           ▼        ▼        ▼
     Research     RAG      finish
      Agent      Agent      (收尾/综合)
     (实时搜索)  (知识库)
           └──── 收集结果(messages) ────┘
                      │
                      ▼  Supervisor 综合输出 / 决定是否再迭代
```

## 二、Supervisor vs Router（Day 4）的核心区别（面试必背考点）

| 维度       | Router（Day 4，multi_agent_router.py） | Supervisor（本文件）              |
|-----------|--------------------------------------|----------------------------------|
| 分发次数   | 一次分发：intent_node 判断后只走一个子 Agent，直接到 END | 可迭代分发：子 Agent 完成后回到 Supervisor 重新决策，可多次派不同子 Agent |
| 是否收集   | 不收集，各子 Agent 独立产出 answer    | 收集：messages 用 operator.add 追加所有子 Agent 结果 |
| 是否综合   | 无综合，只返回被分发到的子 Agent 结果 | 综合：finish 时汇总所有子 Agent 结果生成最终综合回答 |
| 决策者     | intent_node 单次 LLM 意图判断         | supervisor_node 每次循环都用 LLM 决策（是否迭代/收尾） |
| 防失控     | 无循环，天然不会无限                 | rounds/max_rounds 计数，超限强制 finish 防无限分发 |
| 本质       | 规则/LLM 的一次条件跳转              | "用 LLM 做决策的 conditional edge"，动态循环协作 |

一句话：Router 是"一次分发"；Supervisor 是"可迭代分发 + 收集 + 综合"，是大厂最常用的 Multi-Agent 架构。

## 三、本文件实现

- SupervisorState：query / messages(Annotated, operator.add) / next_agent / rounds / max_rounds / answer
- supervisor_node：LLM 决定派 research / rag / finish，失败回退规则，轮次超限强制收尾
- rag_node：build_hybrid_retriever(use_cross_encoder=False) 检索 top_k=3 + chat 生成，LLM 失败返回检索原文兜底
- research_node：复用 research_agent.research(query)，try/except 兜底"外部搜索暂不可用"
- 图结构：start → supervisor → (conditional edge) → rag/research → 回到 supervisor（可迭代）→ finish → END
"""

import operator
from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, END

from app.llm import chat


# ============================================
# 1. SupervisorState（共享状态）
# ============================================

class SupervisorState(TypedDict):
    """
    Supervisor 模式的共享状态。

    query:      用户原始问题
    messages:   Annotated[list, operator.add] —— 自动追加收集各子 Agent 结果/中间信息
                （这是"收集"的关键：每个子 Agent 完成后把结果 append 进 messages，
                  不会互相覆盖，Supervisor 收尾时能看到全部子 Agent 产出）
    next_agent: Supervisor 本轮决定派谁（"research" / "rag" / "finish"）
    rounds:     已分发的轮次计数（防止无限循环）
    max_rounds: 最大允许轮次，超限强制收尾
    answer:     最终综合回答（Supervisor 决策 finish 时生成）
    """
    query: str
    messages: Annotated[list, operator.add]
    next_agent: str
    rounds: int
    max_rounds: int
    answer: str


# 规则兜底用关键词
POLICY_KEYWORDS = [
    "年假", "病假", "薪资", "工资", "入职", "报销", "请假",
    "加班", "社保", "公积金", "福利", "考勤", "假期", "休假",
    "制度", "政策", "合同", "体检", "调薪", "晋升",
]
RESEARCH_KEYWORDS = [
    "新闻", "行情", "最新", "实时", "股市", "动态", "搜索", "资讯",
    "科技", "AI", "大模型", "行业", "趋势", "消息",
]


# ============================================
# 2. 工具函数
# ============================================

def _parse_decision(raw: str):
    """
    从 LLM 输出中解析出合法决策（research / rag / finish）。
    LLM 偶发多输出时，按优先级从中提取关键词。
    """
    if raw in ("research", "rag", "finish"):
        return raw
    # finish 优先（"research" 不含 finish/rag，避免误判）
    for key in ("finish", "research", "rag"):
        if key in raw:
            return key
    return None


def _sub_results(messages: list) -> list:
    """从 messages 中筛选出子 Agent 结果条目（带 [rag]/[research] 前缀）。"""
    return [m for m in messages if m.startswith("[rag]") or m.startswith("[research]")]


def _compose_answer(query: str, messages: list) -> str:
    """
    综合生成最终回答：汇总所有子 Agent 结果，让 LLM 综合。
    LLM 失败时，返回子 Agent 结果原文拼接兜底。
    """
    results = _sub_results(messages)
    if not results:
        return "没有收集到足够的子 Agent 结果，暂时无法回答您的问题。"

    joined = "\n\n".join(results)

    try:
        prompt = f"""你是 Multi-Agent 系统的综合者。请综合以下各子 Agent 的结果，给用户一个完整、有条理的回答。
要求：
1. 结构清晰（分点或分段）
2. 整合各子 Agent 提供的关键信息，避免重复
3. 如果信息有缺失或冲突，如实说明

各子 Agent 结果：
{joined}

用户问题：{query}

综合回答："""
        return chat(prompt)
    except Exception as e:
        print(f"[Supervisor] 综合生成失败，返回子Agent结果原文兜底: {e}")
        return "（LLM 暂不可用，以下为各子 Agent 结果原文，仅供参考）\n\n" + joined


# ============================================
# 3. Node: supervisor_node（LLM 决策 + 规则兜底 + 防无限循环 + 综合输出）
# ============================================

def supervisor_node(state: SupervisorState) -> dict:
    """
    Supervisor 核心节点：决定"派谁 / 是否迭代 / 何时收尾"。

    流程：
      1. 轮次超限（rounds >= max_rounds）→ 强制 finish（防无限循环）
      2. 让 LLM 决策：research / rag / finish（把已收集的子 Agent 结果喂给 LLM，
         让它判断是否还需要补充其他子 Agent 或直接收尾）
      3. LLM 失败/非法值 → 规则回退：
           - 已有子 Agent 结果 → finish（信息已足够）
           - 命中企业政策关键词 → rag
           - 命中实时信息关键词 / 其他 → research
      4. 决策 finish → 同步生成综合回答 answer
    """
    query = state["query"]
    messages = state.get("messages", [])
    rounds = state.get("rounds", 0)
    max_rounds = state.get("max_rounds", 3)
    sub_summary = _sub_results(messages)

    print("\n" + "=" * 60)
    print(f"[Supervisor] 第 {rounds + 1} 轮决策 | 已执行 {rounds} 轮 / 上限 {max_rounds} 轮")
    print(f"  问题: {query}")
    if sub_summary:
        print(f"  已收集子Agent结果 {len(sub_summary)} 条（可供判断是否继续迭代）")

    # ---- 1. 轮次超限 → 强制收尾（防无限循环） ----
    if rounds >= max_rounds:
        print(f"[Supervisor] 已达最大轮次 {max_rounds}，强制收尾(finish)")
        return {
            "next_agent": "finish",
            "rounds": rounds,
            "answer": _compose_answer(query, messages),
        }

    # ---- 2. LLM 决策 ----
    decision = None
    try:
        prompt = f"""你是 Multi-Agent 系统的主管(Supervisor)，负责把用户任务分派给合适的子 Agent。

子 Agent 能力：
- rag: 基于企业知识库检索回答（企业政策/制度/薪资/假期等内部知识）
- research: 使用搜索引擎获取外部实时信息（新闻/行情/最新动态）

已收集到的子 Agent 结果（可能为空）：
{sub_summary if sub_summary else '（暂无）'}

请决定下一步动作，只输出一个词：
- 如果还需要企业知识库回答 → rag
- 如果还需要外部实时信息 → research
- 如果已有信息足以回答，或无需再分发 → finish

用户问题：{query}
动作："""
        raw = chat(prompt).strip().lower()
        print(f"[Supervisor] LLM 决策输出: {raw!r}")
        decision = _parse_decision(raw)
    except Exception as e:
        print(f"[Supervisor] LLM 决策失败，回退规则判断: {e}")

    # ---- 3. 规则兜底 ----
    if decision is None:
        if sub_summary:
            # 已有子 Agent 结果，信息足够 → 收尾（体现"迭代后可收尾"）
            decision = "finish"
        elif any(k in query for k in POLICY_KEYWORDS):
            decision = "rag"
        else:
            decision = "research"

    # ---- 4. 决策 finish → 综合输出 ----
    result = {"next_agent": decision, "rounds": rounds + 1}
    if decision == "finish":
        result["answer"] = _compose_answer(query, messages)

    print(f"[Supervisor] 本轮决策 → {decision}")
    return result


# ============================================
# 4. Node: rag_node（RAG Agent 子节点）
# ============================================

_rag_retriever = None  # 懒加载，进程内复用（避免每次重建 FAISS/BM25 索引）


def _get_rag_retriever():
    """懒加载混合检索器（默认参数 use_cross_encoder=False，避免加载大模型）。

    环境说明：embedding 模型 BAAI/bge-small-zh-v1.5 已本地缓存，但
    sentence_transformers 加载时仍会向 HuggingFace 发起 HEAD 检查，
    无外网时反复超时重试导致卡死。这里在 import 前强制离线模式，
    直接从本地缓存加载（不改动项目其他文件）。
    """
    import os
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    global _rag_retriever
    if _rag_retriever is None:
        from app.rag.hybrid_retriever import build_hybrid_retriever
        _rag_retriever = build_hybrid_retriever(
            "data/employee_policy.txt",
            use_cross_encoder=False,
        )
    return _rag_retriever


def rag_node(state: SupervisorState) -> dict:
    """
    RAG Agent 子节点：检索企业知识库 + LLM 生成回答，结果追加到 messages。

    流程：
      1. build_hybrid_retriever 检索 top_k=3
      2. 组装上下文，调用 app.llm.chat 生成回答
      3. LLM 无 key 失败 → 返回检索原文兜底
      4. 结果以 "[rag] ..." 格式追加进 messages（operator.add 自动追加，不覆盖）
    """
    query = state["query"]

    try:
        retriever = _get_rag_retriever()
        docs = retriever.retrieve(query, top_k=3)

        if not docs:
            msg = "[rag] 知识库中未找到与您问题相关的内容。"
            print(f"[RAG Agent] {msg}")
            return {"messages": [msg]}

        context = "\n\n".join(f"[{i + 1}] {d['text']}" for i, d in enumerate(docs))
        print(f"[RAG Agent] 检索到 {len(docs)} 个相关片段")

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
            print(f"[RAG Agent] LLM 生成失败，返回检索原文兜底: {e}")
            answer = "（LLM 暂不可用，以下为知识库检索原文，仅供参考）\n\n" + context

        print(f"[RAG Agent] 回答生成完成，{len(answer)} 字符")
        return {"messages": [f"[rag] {answer}"]}
    except Exception as e:
        print(f"[RAG Agent] 检索过程失败: {e}")
        return {"messages": [f"[rag] RAG 检索失败：{e}"]}


# ============================================
# 5. Node: research_node（Research Agent 子节点）
# ============================================

def research_node(state: SupervisorState) -> dict:
    """
    Research Agent 子节点：复用 research_agent.py 的 research(query)（Planner→Search→Writer）。
    结果以 "[research] ..." 格式追加进 messages。

    若外部搜索 API 不可用（LLM 无 key / 网络受限），try/except 兜底
    "外部搜索暂不可用"，保证演示可跑通。
    """
    query = state["query"]

    try:
        # 延迟 import：避免 research_agent 顶层依赖影响本文件可运行性
        from app.agent.research_agent import research
        answer = research(query)
        print(f"[Research Agent] 返回回答，{len(answer)} 字符")
        return {"messages": [f"[research] {answer}"]}
    except Exception as e:
        print(f"[Research Agent] 外部搜索暂不可用: {e}")
        return {"messages": ["[research] 外部搜索暂不可用，请稍后再试。"]}


# ============================================
# 6. 构建 Supervisor 图
# ============================================

def route_after_supervisor(state: SupervisorState) -> str:
    """
    条件分发函数：按 Supervisor 的 next_agent 分发到子 Agent 或收尾。
    非法值一律回退到 "finish"（最安全：不无限分发）。
    """
    next_agent = state.get("next_agent", "finish")
    return next_agent if next_agent in ("rag", "research") else "finish"


def build_supervisor():
    """
    构建 Supervisor 图（可迭代分发，这是与 Day 4 Router"一次分发"的关键区别）：

    ```
    start → supervisor
              │ conditional edge（按 next_agent）
      ┌───────┼────────┐
      ▼       ▼        ▼
     rag  research   finish → END
      │       │
      └───→ supervisor（子 Agent 完成后回到 Supervisor 重新决策：是否继续迭代 / 收尾）
    ```
    """
    g = StateGraph(SupervisorState)

    # 节点
    g.add_node("supervisor", supervisor_node)
    g.add_node("rag", rag_node)
    g.add_node("research", research_node)

    # 边：start → supervisor
    g.add_edge("__start__", "supervisor")

    # 条件分发：supervisor 按 next_agent 分发；finish 收尾到 END
    g.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {"rag": "rag", "research": "research", "finish": END},
    )

    # ⭐ 关键：子 Agent 完成后回到 supervisor 重新决策（可迭代，不是一次分发到 END）
    g.add_edge("rag", "supervisor")
    g.add_edge("research", "supervisor")

    return g.compile()


# 编译一次，全局复用（懒初始化，避免 import 时立即加载模型）
supervisor_app = None


def supervise(query: str, max_rounds: int = 3) -> str:
    """
    对外入口：编译 Supervisor 图并 invoke，返回最终综合回答。

    参数:
      query:      用户问题
      max_rounds: 最大迭代轮次（默认 3，防无限循环）

    返回:
      str: 最终综合回答（Supervisor 收尾时综合所有子 Agent 结果生成）
    """
    global supervisor_app
    if supervisor_app is None:
        supervisor_app = build_supervisor()

    result = supervisor_app.invoke({
        "query": query,
        "messages": [],
        "next_agent": "",
        "rounds": 0,
        "max_rounds": max_rounds,
        "answer": "",
    })
    return result.get("answer", "")


# ============================================
# 7. 演示入口
# ============================================

if __name__ == "__main__":
    # Windows 终端默认 GBK 编码，强制 UTF-8 输出避免中文乱码
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 64)
    print("Week 6 Day 5 — Multi-Agent Supervisor（中央协调者）演示")
    print("Supervisor: 接收问题 → LLM决定派谁 → 收集结果 → 决策是否迭代 → 综合输出")
    print("对比 Router(Day 4): 一次分发 | Supervisor: 可迭代分发 + 收集 + 综合")
    print("=" * 64)

    test_queries = [
        "公司年假几天？",                              # 期望: rag → finish
        "帮我搜索最新的 AI 新闻",                       # 期望: research → finish
        "病假工资怎么算？顺便查查最近的大模型行业动态",   # 混合: 可能 rag + research 多轮 → finish
    ]

    for q in test_queries:
        print("\n" + "#" * 64)
        print(f"用户问题: {q}")

        # 单独 invoke 以便展示收集到的 messages 与最终综合回答
        demo_app = build_supervisor()
        result = demo_app.invoke({
            "query": q,
            "messages": [],
            "next_agent": "",
            "rounds": 0,
            "max_rounds": 3,
            "answer": "",
        })

        print("\n----- 各子 Agent 收集结果 (messages) -----")
        for m in result.get("messages", []):
            tag = m.split("]", 1)[0] + "]"
            content = m.split("]", 1)[1].strip()
            display = content if len(content) <= 200 else content[:200] + "…"
            print(f"  {tag} {display}")

        print("\n----- 最终综合回答 -----")
        answer = result.get("answer", "")
        print(answer if len(answer) <= 500 else answer[:500] + "…")
        print("#" * 64)
