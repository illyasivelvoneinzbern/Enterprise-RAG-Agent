"""
research_agent_hitl.py — Day 5: Human-in-the-Loop + Checkpoint + Streaming

在 Day 3 research_agent.py 基础上扩展三个新能力：

         Day 3: 全自动流水线              Day 5: 带人工审批的流水线
   ┌─────────────────────────┐    ┌─────────────────────────────┐
   │  Planner（拆解子问题）    │    │  Planner（拆解子问题）        │
   │         ↓               │    │         ↓                   │
   │  Search（逐子问题搜索）   │    │  ⏸ interrupt_before=["search"]│
   │         ↓               │    │  用户确认/修改子问题后继续    │
   │  Writer（综合生成答案）   │    │         ↓                   │
   │         ↓               │    │  Search（逐子问题搜索）       │
   │  END                    │    │         ↓                   │
   └─────────────────────────┘    │  Writer（综合生成答案）       │
                                  │         ↓                   │
                                  │  END                        │
                                  └─────────────────────────────┘

三个新概念：
  1. interrupt_before=["search"]  — 在 search 节点前暂停，等待人工输入
  2. MemorySaver                  — 内存级 Checkpoint，保存每步快照
  3. stream() 模式                — 逐个 Node 产出，支持流式输出

⭐ 核心认知：Human-in-the-Loop 就是"图暂停 + 外部输入 + 图恢复"三步
"""

from typing import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.llm import chat, chat_stream


# ============================================
# 1. 定义 State（与 Day 3 完全相同）
# ============================================

class ResearchState(TypedDict):
    """与 Day 3 的 ResearchState 完全一致"""
    query: str
    sub_queries: list[str]
    search_results: list[str]
    final_answer: str


# ============================================
# 2. Node 1: Planner（同 Day 3）
# ============================================

def planner_node(state: ResearchState) -> dict:
    """同 Day 3，拆解用户问题为子问题列表"""
    prompt = f"""你是一个研究规划助手。请将用户问题拆解为 2-4 个可以独立搜索的子问题。

要求：
- 每个子问题简洁明确，适合作为搜索引擎查询
- 每行一个子问题，不要编号、不要前缀符号
- 子问题之间不要重复

用户问题：{state["query"]}

子问题："""

    response = chat(prompt)

    sub_queries = [
        line.strip().lstrip("- ").lstrip("0123456789. ")
        for line in response.split("\n")
        if line.strip() and not line.startswith("#")
    ]

    print(f"\n[Planner] 拆解出 {len(sub_queries)} 个子问题：")
    for i, q in enumerate(sub_queries, 1):
        print(f"  {i}. {q}")
    print(f"\n⏸  [工作流已暂停] 请确认以上子问题是否正确，输入 'y' 继续，或输入修改后的子问题列表")

    return {"sub_queries": sub_queries}


# ============================================
# 3. Node 2: Search（同 Day 3，Mock 数据）
# ============================================

def search_node(state: ResearchState) -> dict:
    """同 Day 3，遍历子问题列表，逐个搜索并汇总结果"""
    results = []

    for i, sub_q in enumerate(state["sub_queries"], 1):
        print(f"\n[Search] 正在搜索子问题 {i}/{len(state['sub_queries'])}: {sub_q}")

        # TODO Day 5-6: 替换为真实搜索 API
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
# 4. Node 3: Writer（升级为流式输出）
# ============================================

def writer_node(state: ResearchState) -> dict:
    """
    综合生成最终回答。

    Day 5 新增：使用 chat_stream() 实现流式输出，
    让用户看到答案逐字生成的过程。
    """
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

    print("\n[Writer] 正在综合生成最终回答（流式）...")
    full_answer = ""
    for chunk in chat_stream([{"role": "user", "content": prompt}]):
        print(chunk, end="", flush=True)
        full_answer += chunk
    print(f"\n[Writer] 生成完成，共 {len(full_answer)} 字符")

    return {"final_answer": full_answer}


# ============================================
# 5. 构建图（最终编译时注入 Checkpoint + Interrupt）
# ============================================

def create_research_graph():
    """
    ⭐ 核心差异（对比 Day 3）：

    Day 3:
      graph = StateGraph(ResearchState)
      ...
      research_app = graph.compile()

    Day 5:
      graph = StateGraph(ResearchState)
      ...
      # 注入两个新能力！
      checkpointer = MemorySaver()
      research_app = graph.compile(
          checkpointer=checkpointer,
          interrupt_before=["search"]   # ← 在 search 前暂停！
      )

    interrupt_before=["search"] 的含义：
      Planner 执行完毕后，图自动暂停，等待外部输入。
      用户可以在此时查看/修改 sub_queries，然后恢复执行。
    """
    graph = StateGraph(ResearchState)

    graph.add_node("planner", planner_node)
    graph.add_node("search", search_node)
    graph.add_node("writer", writer_node)

    graph.add_edge("__start__", "planner")
    graph.add_edge("planner", "search")
    graph.add_edge("search", "writer")
    graph.add_edge("writer", END)

    return graph


# ============================================
# 6. 编译（带 Checkpoint + Interrupt）
# ============================================

# 创建全局 checkpointer 实例（所有会话共享）
memory_saver = MemorySaver()

# 编译图
research_graph = create_research_graph()
research_app_hitl = research_graph.compile(
    checkpointer=memory_saver,
    interrupt_before=["search"]  # ← 关键！在 search 节点前暂停
)


# ============================================
# 7. 交互式运行（演示 Human-in-the-Loop 流程）
# ============================================

def research_interactive(query: str, thread_id: str = "default") -> str:
    """
    Human-in-the-Loop 交互式研究流程。

    三步走：
      1. invoke() → 图在 search 前自动暂停
      2. 用户检查/修改 sub_queries，用 update_state() 注入修改
      3. invoke(None, thread_id) → 从暂停点恢复执行

    参数:
      query: 用户问题
      thread_id: 会话 ID（不同 ID = 不同对话 = 独立 Checkpoint）

    ⭐ 这就是 Human-in-the-Loop 的完整生命周期：
      暂停(interrupt) → 人工决策 → 状态修改(update_state) → 恢复(invoke)
    """
    config = {"configurable": {"thread_id": thread_id}}

    # ── 第一步：invoke，图会自动在 search 前暂停 ──
    print("=" * 60)
    print("步骤 1/3: 启动研究，Planner 拆解子问题...")
    print("=" * 60)

    initial_state = {"query": query}
    result = research_app_hitl.invoke(initial_state, config)

    # 此时图已暂停，sub_queries 已生成但 search 未执行
    print(f"\n📋 Planner 生成的子问题：")
    for i, sq in enumerate(result["sub_queries"], 1):
        print(f"  {i}. {sq}")

    # ── 第二步：人工确认（实际项目用 UI，这里用 input 模拟）──
    print("\n" + "=" * 60)
    print("步骤 2/3: 人工确认子问题")
    print("=" * 60)

    user_input = input(
        "\n输入 'y' 确认并继续，"
        "或输入修改后的子问题（每行一个）: "
    ).strip()

    if user_input != "y":
        # 用户提供了修改后的子问题
        modified_sub_queries = [
            line.strip()
            for line in user_input.split("\n")
            if line.strip()
        ]
        # 使用 update_state 注入修改后的子问题
        research_app_hitl.update_state(
            config,
            {"sub_queries": modified_sub_queries}
        )
        print(f"\n✅ 已更新为 {len(modified_sub_queries)} 个自定义子问题")

    # ── 第三步：恢复执行（传入 None 表示从当前 Checkpoint 继续）──
    print("\n" + "=" * 60)
    print("步骤 3/3: 恢复执行，Search → Writer...")
    print("=" * 60)

    final_result = research_app_hitl.invoke(None, config)

    print("\n" + "=" * 60)
    print("✅ 研究完成")
    print("=" * 60)

    return final_result["final_answer"]


# ============================================
# 8. 编程式运行（带人工干预的完整流程）
# ============================================

def research_with_custom_subqueries(
    query: str,
    sub_queries: list[str],
    thread_id: str = "default"
) -> str:
    """
    编程式 Human-in-the-Loop：
    调用方直接提供修改后的 sub_queries，跳过交互式 input。

    适用场景：前端 UI 展示 Planner 结果 → 用户点击"确认"或"修改"按钮 → 后端调用此函数

    流程：
      1. invoke({"query": query}) → 图暂停在 search 前
      2. update_state({"sub_queries": sub_queries}) → 注入修改
      3. invoke(None) → 恢复执行

    参数:
      query: 用户问题
      sub_queries: 自定义的子问题列表
      thread_id: 会话 ID
    """
    config = {"configurable": {"thread_id": thread_id}}

    # 第一步：启动（会暂停在 search 前）
    research_app_hitl.invoke({"query": query}, config)

    # 第二步：注入自定义子问题
    research_app_hitl.update_state(config, {"sub_queries": sub_queries})

    # 第三步：恢复执行
    result = research_app_hitl.invoke(None, config)
    return result["final_answer"]


# ============================================
# 9. Checkpoint 回溯演示
# ============================================

def demo_checkpoint_replay(thread_id: str = "replay_demo"):
    """
    演示 Checkpoint 的核心能力：回到历史状态重新执行。

    场景：用户对最终答案不满意，想回到 search 之前换个搜索策略重新来。

    ⭐ Checkpoint 三步：
      1. get_state_history() → 查看所有历史快照
      2. get_state() → 获取特定快照的完整状态
      3. invoke(None) → 从该快照恢复执行
    """
    config = {"configurable": {"thread_id": thread_id}}

    # 先跑一遍完整的流程
    print("=" * 60)
    print("演示 1: 先完整运行一次研究")
    print("=" * 60)
    research_app_hitl.invoke({"query": "什么是RAG？"}, config)
    # 跳过人工确认（模拟用户点了 "y"）
    research_app_hitl.invoke(None, config)
    print("\n✅ 第一次运行完成")

    # 查看历史 Checkpoint
    print("\n" + "=" * 60)
    print("演示 2: 查看所有历史 Checkpoint")
    print("=" * 60)

    history = list(research_app_hitl.get_state_history(config))
    print(f"\n共 {len(history)} 个历史快照：")
    for i, snapshot in enumerate(history):
        # snapshot 包含 config、values、next 等信息
        state_values = snapshot.values
        has_sub_queries = bool(state_values.get("sub_queries"))
        has_results = bool(state_values.get("search_results"))
        has_answer = bool(state_values.get("final_answer"))
        print(f"  快照 {i}: sub_queries={has_sub_queries}, "
              f"search_results={has_results}, final_answer={has_answer}")

    # 回到 Planner 之后、Search 之前的快照
    # 找到 sub_queries 已存在但 search_results 为空的快照
    print("\n" + "=" * 60)
    print("演示 3: 回溯到 search 之前，修改子问题重新运行")
    print("=" * 60)

    # 直接用编程式方式：用新的 sub_queries 调用 research_with_custom_subqueries
    # 但这里演示的是"从历史快照回顾状态"
    for snapshot in history:
        if snapshot.values.get("sub_queries") and not snapshot.values.get("search_results"):
            print(f"\n找到 Planner 后的快照：")
            print(f"  子问题: {snapshot.values['sub_queries']}")
            print(f"  可从此处注入新的子问题并恢复执行")
            break

    print("\n✅ Checkpoint 回溯演示完成")


# ============================================
# 10. 总结：Day 3 → Day 5 核心差异
# ============================================

"""
┌──────────────────┬─────────────────────┬────────────────────────────┐
│      能力         │     Day 3           │        Day 5               │
├──────────────────┼─────────────────────┼────────────────────────────┤
│ compile()        │ graph.compile()     │ graph.compile(             │
│                  │                     │   checkpointer=MemorySaver()│
│                  │                     │   interrupt_before=["search"]│
│                  │                     │ )                           │
├──────────────────┼─────────────────────┼────────────────────────────┤
│ 执行方式          │ invoke() 一口气跑完  │ invoke() → 暂停 →         │
│                  │                     │ update_state() → invoke()  │
├──────────────────┼─────────────────────┼────────────────────────────┤
│ 状态持久化        │ 无                   │ MemorySaver 自动保存每步   │
├──────────────────┼─────────────────────┼────────────────────────────┤
│ 历史回溯          │ 不支持               │ get_state_history() 查看   │
├──────────────────┼─────────────────────┼────────────────────────────┤
│ Writer 输出       │ chat() 一次性返回     │ chat_stream() 流式输出     │
├──────────────────┼─────────────────────┼────────────────────────────┤
│ thread_id         │ 无                   │ 每个会话独立 Checkpoint    │
└──────────────────┴─────────────────────┴────────────────────────────┘

面试要点：
  Q: "Human-in-the-Loop 是如何实现的？"
  A: "三步：interrupt_before 指定暂停节点 → invoke 触发暂停 →
      update_state 注入人类反馈 → invoke(None) 恢复执行。
      本质是图执行引擎的外挂中断机制。"

  Q: "Checkpoint 和 session_memory 有什么关系？"
  A: "Checkpoint 是 LangGraph 框架级的自动状态快照，
      你的 SessionMemoryManager 是应用级的对话管理。
      Checkpoint 更底层，可以替代 SessionMemoryManager 的存储部分。"
"""
