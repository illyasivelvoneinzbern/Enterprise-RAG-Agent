"""
research_agent.py — Day 3: Research Agent（Planner → Search → Writer DAG 流水线）

对比 Day 2 的 langgraph_agent.py（循环图 llm ↔ tool）：

       Day 2: 循环图                       Day 3: DAG 流水线
  ┌─────────────────────┐          ┌─────────────────────────┐
  │  LLM ←──────────┐   │          │  Planner（拆解子问题）    │
  │   │              │   │          │         ↓               │
  │   ▼              │   │          │  Search（逐子问题搜索）   │
  │  should_continue │   │          │         ↓               │
  │   │  │           │   │          │  Writer（综合生成答案）   │
  │   │  ▼           │   │          │         ↓               │
  │   │ tool ────────┘   │          │  END                    │
  │   ▼                  │          └─────────────────────────┘
  │  END                 │
  └─────────────────────┘

关键差异：
  - Day 2 State: Annotated[list, operator.add]（自动追加消息）
  - Day 3 State: 普通 TypedDict（替换式，每步输出覆盖上一步）
  - Day 2 需要 Conditional Edge + 循环边
  - Day 3 只需普通 Edge（固定顺序）
"""

from typing import TypedDict
from langgraph.graph import StateGraph, END

from app.llm import chat


# ============================================
# 1. 定义 ResearchState（替换式，非追加式）
# ============================================

class ResearchState(TypedDict):
    """
    对比 Day 2 的 AgentState：
      Day 2: messages: Annotated[list, operator.add]  ← 自动追加
      Day 3: 每个字段是普通类型                        ← 覆盖替换

    原因：Research Agent 是流水线，每步的输出是下一步的输入，
         不存在"追加消息"的需求。
    """
    query: str                # 用户原始问题
    sub_queries: list[str]    # Planner 拆解的子问题列表
    search_results: list[str] # 每个子问题的搜索结果
    final_answer: str         # Writer 综合生成的最终回答


# ============================================
# 2. Node 1: Planner（拆解问题）
# ============================================

def planner_node(state: ResearchState) -> dict:
    """
    LLM 接收用户问题，拆解为 2-4 个可独立搜索的子问题。

    输入: state["query"] = "LangGraph 相比 ReAct 有什么优势？"
    输出: {"sub_queries": ["LangGraph核心概念", "ReAct核心概念", "两者对比"]}
    """
    prompt = f"""你是一个研究规划助手。请将用户问题拆解为 2-4 个可以独立搜索的子问题。

要求：
- 每个子问题简洁明确，适合作为搜索引擎查询
- 每行一个子问题，不要编号、不要前缀符号
- 子问题之间不要重复

用户问题：{state["query"]}

子问题："""

    response = chat(prompt)

    # 解析 LLM 返回的子问题列表（过滤空行和 markdown 标题）
    sub_queries = [
        line.strip().lstrip("- ").lstrip("0123456789. ")
        for line in response.split("\n")
        if line.strip() and not line.startswith("#")
    ]

    print(f"\n[Planner] 拆解出 {len(sub_queries)} 个子问题：")
    for i, q in enumerate(sub_queries, 1):
        print(f"  {i}. {q}")

    return {"sub_queries": sub_queries}


# ============================================
# 3. Node 2: Search（逐子问题搜索）
# ============================================

def search_node(state: ResearchState) -> dict:
    """
    遍历 Planner 生成的子问题列表，每个调用搜索工具，汇总结果。

    输入: state["sub_queries"] = ["子问题1", "子问题2", "子问题3"]
    输出: {"search_results": ["结果1", "结果2", "结果3"]}

    当前使用 Mock 数据跑通流程。
    Day 5 接入真实搜索 API（Tavily / SerpAPI）。
    """
    results = []

    for i, sub_q in enumerate(state["sub_queries"], 1):
        print(f"\n[Search] 正在搜索子问题 {i}/{len(state['sub_queries'])}: {sub_q}")

        # TODO Day 5: 替换为真实搜索
        # from tavily import TavilyClient
        # result = TavilyClient(api_key="...").search(sub_q)

        # 当前用 Mock 数据
        mock_result = (
            f"【子问题 {i} 搜索结果】\n"
            f"查询: {sub_q}\n"
            f"内容: 这是关于「{sub_q}」的模拟搜索结果。"
            f"实际使用时这里会是搜索引擎返回的真实内容片段。"
        )
        results.append(mock_result)
        print(f"  → 获取到 {len(mock_result)} 字符的搜索结果")

    return {"search_results": results}


# ============================================
# 4. Node 3: Writer（综合生成）
# ============================================

def writer_node(state: ResearchState) -> dict:
    """
    综合原始问题 + 子问题 + 搜索结果，生成最终回答。

    输入: state["query"] + state["sub_queries"] + state["search_results"]
    输出: {"final_answer": "完整回答"}
    """
    # 拼接所有搜索结果
    all_results = "\n\n---\n\n".join(
        f"### 子问题: {q}\n{r}"
        for q, r in zip(state["sub_queries"], state["search_results"])
    )

    prompt = f"""你是一个研究报告撰写助手。请根据以下搜索结果，综合回答用户的原始问题。

用户原始问题：
{state["query"]}

该问题被拆解为以下子问题分别搜索：
{chr(10).join(f"{i}. {q}" for i, q in enumerate(state['sub_queries'], 1))}

各子问题的搜索结果：
{all_results}

请综合以上信息，给出一个完整、有条理的回答。要求：
1. 结构清晰（分点或分段）
2. 引用搜索结果中的关键信息
3. 如果搜索结果不完整，明确指出哪些信息缺失

回答："""

    print("\n[Writer] 正在综合生成最终回答...")
    answer = chat(prompt)
    print(f"[Writer] 生成完成，共 {len(answer)} 字符")

    return {"final_answer": answer}


# ============================================
# 5. 构建 DAG 图（与 Day 2 图结构对比）
# ============================================

graph = StateGraph(ResearchState)

# 注册节点
graph.add_node("planner", planner_node)
graph.add_node("search", search_node)
graph.add_node("writer", writer_node)

# 声明边 —— 线性 DAG，无条件跳转，无循环
# 对比 Day 2: add_conditional_edges + add_edge("tool", "llm")
graph.add_edge("__start__", "planner")
graph.add_edge("planner", "search")
graph.add_edge("search", "writer")
graph.add_edge("writer", END)

# 编译
research_app = graph.compile()


# ============================================
# 6. 便捷调用函数
# ============================================

def research(query: str) -> str:
    """
    执行研究流程并返回最终回答。

    等价于:
      result = research_app.invoke({"query": query})
      return result["final_answer"]
    """
    result = research_app.invoke({"query": query})
    return result["final_answer"]
