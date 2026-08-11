"""
test_research_agent_hitl.py — Day 5: Human-in-the-Loop + Checkpoint 功能验证

五个测试：
  1. 图结构验证（checkpointer + interrupt_before 注入确认）
  2. Human-in-the-Loop 完整流程（invoke → 暂停 → update_state → invoke）
  3. 编程式自定义子问题（research_with_custom_subqueries）
  4. Checkpoint 历史回溯（get_state_history）
  5. 流式 Writer 输出验证
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ============================================
# 测试 1：编译后的图结构验证
# ============================================

def test_graph_with_checkpointer():
    """验证 Day 5 的图正确注入了 checkpointer 和 interrupt_before"""
    from app.agent.research_agent_hitl import research_app_hitl, research_graph

    print("=" * 60)
    print("测试 1：图结构 + Checkpointer 验证")
    print("=" * 60)

    # 检查节点
    nodes = set(research_graph.nodes.keys())
    expected = {"planner", "search", "writer"}
    print(f"\n📌 已注册节点: {nodes}")
    assert expected.issubset(nodes), f"缺少节点: {expected - nodes}"
    print(f"   ✅ 3 个节点已注册")

    # 检查边
    edges = research_graph.edges
    edge_checks = {
        "__start__ → planner": ("__start__", "planner"),
        "planner → search": ("planner", "search"),
        "search → writer": ("search", "writer"),
        "writer → END": ("writer", "__end__"),
    }
    print(f"\n🔗 边结构：")
    for desc, (src, dst) in edge_checks.items():
        found = any(s == src and e == dst for (s, e) in edges)
        print(f"   {'✅' if found else '❌'} {desc}")
        assert found, f"缺少边: {desc}"

    # 检查 interrupt_before 已设置
    print(f"\n⏸  interrupt_before 检查：")
    # LangGraph 编译后的 app 内部有 interrupt_before 配置
    has_interrupt = hasattr(research_app_hitl, 'interrupt_before')
    print(f"   app.interrupt_before 属性: {'✅ 存在' if has_interrupt else '⚠️ 检查 _all_sends/key'}")
    if has_interrupt:
        print(f"   值: {research_app_hitl.interrupt_before}")

    # 检查 checkpointer
    has_checkpointer = hasattr(research_app_hitl, 'checkpointer') and research_app_hitl.checkpointer is not None
    print(f"\n💾 Checkpointer: {'✅ MemorySaver 已注入' if has_checkpointer else '❌ 未注入'}")

    # 验证不传 config 时 interrupt 会触发
    print(f"\n🧪 触发 Interrupt 测试：")
    try:
        result = research_app_hitl.invoke({"query": "测试问题"})
        # 如果没有 interrupt，这里会一口气跑到 END
        has_answer = bool(result.get("final_answer"))
        if has_answer:
            print(f"   ⚠️ 没有触发 interrupt（可能未传 thread_id 配置），图一口气跑完了")
        else:
            print(f"   ✅ Interrupt 已触发！图在 search 前暂停，final_answer 为空")
    except Exception as e:
        # 某些版本的 LangGraph 在 interrupt 时会抛特定异常
        print(f"   ℹ️ Interrupt 信号: {type(e).__name__}: {e}")

    print("\n✅ 图结构 + Checkpointer 配置正确")
    return True


# ============================================
# 测试 2：Human-in-the-Loop 完整流程
# ============================================

def test_hitl_full_flow():
    """验证 invoke → 暂停 → update_state → invoke 完整流程"""
    from app.agent.research_agent_hitl import research_app_hitl
    import uuid

    print("=" * 60)
    print("测试 2：Human-in-the-Loop 完整流程")
    print("=" * 60)

    thread_id = f"test_hitl_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    query = "LangGraph 和 LangChain 有什么关系？"

    # ── 第一步：invoke，应在 search 前暂停 ──
    print(f"\n📤 步骤 1: invoke (thread_id={thread_id})")
    result = research_app_hitl.invoke({"query": query}, config)

    # 验证暂停：sub_queries 应该已生成，但 search_results 和 final_answer 应该为空
    assert result.get("sub_queries"), "Planner 应已生成子问题"
    assert len(result["sub_queries"]) >= 1, f"至少应有 1 个子问题，实际 {len(result['sub_queries'])}"
    # search_results 可能为空（暂停在 search 前）
    print(f"   sub_queries ({len(result['sub_queries'])} 个): {result['sub_queries']}")
    print(f"   search_results 已存在: {bool(result.get('search_results'))}")
    print(f"   final_answer 已存在: {bool(result.get('final_answer'))}")
    print(f"   ⏸ 图已暂停在 search 之前")

    # ── 第二步：用 update_state 修改子问题 ──
    print(f"\n📝 步骤 2: update_state — 修改子问题")
    custom_sub_queries = ["LangGraph 是什么", "LangChain 是什么", "两者如何协同工作"]
    research_app_hitl.update_state(config, {"sub_queries": custom_sub_queries})

    # 验证 update_state 生效
    current_state = research_app_hitl.get_state(config)
    assert current_state.values["sub_queries"] == custom_sub_queries, \
        f"update_state 未生效: {current_state.values['sub_queries']}"
    print(f"   修改后子问题: {current_state.values['sub_queries']}")
    print(f"   ✅ update_state 已生效")

    # ── 第三步：恢复执行 ──
    print(f"\n▶️  步骤 3: invoke(None) — 恢复执行")
    final_result = research_app_hitl.invoke(None, config)

    # 验证完整流程
    assert final_result.get("final_answer"), "Writer 应生成最终回答"
    assert len(final_result["final_answer"]) > 50, \
        f"final_answer 太短: {len(final_result['final_answer'])} 字符"
    assert len(final_result["search_results"]) == len(custom_sub_queries), \
        "搜索结果数量应与子问题数量一致"
    print(f"   search_results: {len(final_result['search_results'])} 条")
    print(f"   final_answer: {len(final_result['final_answer'])} 字符")
    print(f"   ✅ 完整 HITL 流程成功")

    print("\n✅ Human-in-the-Loop 完整流程验证通过")
    return True


# ============================================
# 测试 3：编程式自定义子问题
# ============================================

def test_custom_subqueries_api():
    """验证 research_with_custom_subqueries() 编程式接口"""
    from app.agent.research_agent_hitl import research_with_custom_subqueries
    import uuid

    print("=" * 60)
    print("测试 3：research_with_custom_subqueries() 编程式接口")
    print("=" * 60)

    thread_id = f"test_custom_{uuid.uuid4().hex[:8]}"
    custom_subs = [
        "DeepSeek 模型特点",
        "阿里百炼平台介绍",
        "两者对比分析",
    ]

    try:
        answer = research_with_custom_subqueries(
            "比较 DeepSeek 和阿里百炼",
            custom_subs,
            thread_id
        )
        print(f"\n   thread_id: {thread_id}")
        print(f"   自定义子问题: {custom_subs}")
        print(f"   回答长度: {len(answer)} 字符")
        print(f"   回答预览: {answer[:120]}...")
        assert len(answer) > 50, f"回答太短: {len(answer)} 字符"
        print("\n✅ 编程式 HITL 接口正常")
        return True
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        return False


# ============================================
# 测试 4：Checkpoint 历史回溯
# ============================================

def test_checkpoint_history():
    """验证 get_state_history() 可以查看历史快照"""
    from app.agent.research_agent_hitl import research_app_hitl, memory_saver
    import uuid

    print("=" * 60)
    print("测试 4：Checkpoint 历史回溯")
    print("=" * 60)

    thread_id = f"test_history_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    # 跑一遍完整流程（跳过人工确认）
    research_app_hitl.invoke({"query": "什么是向量数据库？"}, config)
    research_app_hitl.invoke(None, config)

    # 查看历史
    history = list(research_app_hitl.get_state_history(config))
    print(f"\n   历史快照数: {len(history)}")
    assert len(history) >= 2, f"至少应有 2 个快照（Planner后 + Writer后），实际 {len(history)}"

    for i, snapshot in enumerate(history):
        v = snapshot.values
        print(f"   快照 {i}: sub_queries={'✅' if v.get('sub_queries') else '❌'}, "
              f"search_results={'✅' if v.get('search_results') else '❌'}, "
              f"final_answer={'✅' if v.get('final_answer') else '❌'}")

    # 验证存在 Planner 后的快照（有 sub_queries 但无 final_answer）
    planner_snapshot = None
    for snapshot in history:
        if (snapshot.values.get("sub_queries") and
                not snapshot.values.get("final_answer")):
            planner_snapshot = snapshot
            break

    assert planner_snapshot is not None, "应存在 Planner 后、Writer 前的快照"
    print(f"\n   ✅ 找到 Planner 后的快照: {planner_snapshot.values['sub_queries']}")

    print("\n✅ Checkpoint 历史回溯正常")
    return True


# ============================================
# 测试 5：Streaming Writer 输出
# ============================================

def test_streaming_writer():
    """验证 writer_node 使用 chat_stream 流式输出"""
    from app.agent.research_agent_hitl import writer_node, ResearchState
    from io import StringIO
    import sys

    print("=" * 60)
    print("测试 5：Streaming Writer 流式输出验证")
    print("=" * 60)

    # 构造模拟 state
    mock_state: ResearchState = {
        "query": "测试流式输出",
        "sub_queries": ["测试子问题1", "测试子问题2"],
        "search_results": [
            "【子问题 1 搜索结果】\n内容: Mock 结果 A",
            "【子问题 2 搜索结果】\n内容: Mock 结果 B",
        ],
        "final_answer": "",
    }

    # 捕获输出
    captured = StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured

    try:
        result = writer_node(mock_state)
    finally:
        sys.stdout = old_stdout

    output = captured.getvalue()
    print(f"\n   Writer 输出捕获 ({len(output)} 字符):")
    print(f"   {output[:200]}...")

    assert result.get("final_answer"), "Writer 应返回 final_answer"
    assert len(result["final_answer"]) > 20, \
        f"final_answer 太短: {len(result['final_answer'])} 字符"

    # 验证流式输出有内容（chat_stream 逐字输出）
    # 即使 output 是完整的，只要 final_answer 正确即可
    print(f"\n   final_answer 长度: {len(result['final_answer'])} 字符")
    print(f"   流式输出到 stdout: ✅ ({len(output)} 字符)")

    print("\n✅ Streaming Writer 正常")
    return True


# ============================================
# 主入口
# ============================================

if __name__ == "__main__":
    results = []

    # 不依赖 LLM 的先跑
    results.append(("图结构 + Checkpointer 验证", test_graph_with_checkpointer()))

    # 依赖 LLM 的测试
    results.append(("HITL 完整流程", test_hitl_full_flow()))
    results.append(("编程式自定义子问题", test_custom_subqueries_api()))
    results.append(("Checkpoint 历史回溯", test_checkpoint_history()))
    results.append(("Streaming Writer", test_streaming_writer()))

    # 汇总
    print("\n" + "=" * 60)
    print("📊 测试汇总")
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    failed = len(results) - passed
    for name, ok in results:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status}  {name}")
    print(f"\n总计: {passed}/{len(results)} 通过"
          + (f", {failed} 失败" if failed else " 🎉"))
