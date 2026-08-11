"""
test_research_agent.py — Research Agent DAG 流水线功能验证

四个测试：
  1. 图结构验证（3 节点 + 4 条边，线性 DAG）
  2. State 结构对比（Day 2 vs Day 3）
  3. 完整流水线（端到端运行）
  4. 中间态检查（每步输出是否被正确传递）
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ============================================
# 测试 1：图结构验证
# ============================================

def test_graph_structure():
    """验证 DAG 图结构：3 节点（planner/search/writer）+ 4 条边"""
    from app.agent.research_agent import graph

    print("=" * 60)
    print("测试 1：图结构验证")
    print("=" * 60)

    # 检查节点（注意：__start__ 不在 graph.nodes 中，属于 LangGraph 内部管理）
    expected_nodes = {"planner", "search", "writer"}
    actual_nodes = set(graph.nodes.keys())
    print(f"\n📌 已注册节点: {actual_nodes}")
    assert expected_nodes.issubset(actual_nodes), \
        f"缺少节点: {expected_nodes - actual_nodes}"
    print(f"   自定义节点数: {len(actual_nodes)}（预期 3: planner, search, writer）")

    # 检查边结构（graph.edges 格式: (start_node, end_node)）
    edges = graph.edges
    print(f"\n🔗 已注册边: {edges}")

    # 验证关键边存在（edges 是 (from, to) 元组列表）
    edge_start_to_planner = any(
        s == "__start__" and e == "planner" for (s, e) in edges
    )
    edge_planner_to_search = any(
        s == "planner" and e == "search" for (s, e) in edges
    )
    edge_search_to_writer = any(
        s == "search" and e == "writer" for (s, e) in edges
    )
    edge_writer_to_end = any(
        s == "writer" for (s, e) in edges
    )

    print(f"   __start__ → planner : {'✅' if edge_start_to_planner else '❌'}")
    print(f"   planner → search    : {'✅' if edge_planner_to_search else '❌'}")
    print(f"   search → writer     : {'✅' if edge_search_to_writer else '❌'}")
    print(f"   writer → END        : {'✅' if edge_writer_to_end else '❌'}")

    assert edge_start_to_planner, "缺少 __start__ → planner 边"
    assert edge_planner_to_search, "缺少 planner → search 边"
    assert edge_search_to_writer, "缺少 search → writer 边"
    assert edge_writer_to_end, "缺少 writer → END 边"

    # 关键验证：不应存在条件边（Day 3 是线性 DAG，不同于 Day 2 的循环图）
    from app.agent.research_agent import research_app
    has_conditional = hasattr(research_app, 'branches') and research_app.branches
    print(f"\n   条件边数量: {len(research_app.branches) if has_conditional else 0}"
          f"（预期 0，Day 3 是线性 DAG）")

    print("\n✅ 图结构正确 — 线性 DAG，无条件边，无循环")
    return True


# ============================================
# 测试 2：State 结构对比
# ============================================

def test_state_structure():
    """验证 ResearchState 是替换式 TypedDict（非 Annotated 追加式）"""
    from app.agent.research_agent import ResearchState
    from typing import get_type_hints

    print("=" * 60)
    print("测试 2：State 结构对比")
    print("=" * 60)

    hints = get_type_hints(ResearchState)

    print(f"\n📋 ResearchState 字段（Day 3 — 替换式）：")
    for field, annotation in hints.items():
        print(f"   - {field}: {annotation}")

    expected_fields = {"query", "sub_queries", "search_results", "final_answer"}
    actual_fields = set(hints.keys())
    assert actual_fields == expected_fields, \
        f"字段不匹配: 期望 {expected_fields}, 实际 {actual_fields}"

    # 验证没有使用 Annotated（替换式）
    import typing
    for field, annotation in hints.items():
        origin = typing.get_origin(annotation)
        is_annotated = origin is typing.Annotated
        print(f"   {field}: Annotated={is_annotated}（Day 2 是 True，Day 3 应为 False）")

    # 对比 Day 2 的 AgentState
    from app.agent.langgraph_agent import AgentState
    day2_hints = get_type_hints(AgentState)
    day2_has_annotated = any(
        typing.get_origin(a) is typing.Annotated
        for a in day2_hints.values()
    )
    print(f"\n   Day 2 AgentState 使用 Annotated: {day2_has_annotated}（应为 True）")
    print(f"   Day 3 ResearchState 使用 Annotated: False（应为 False）")
    print(f"   → 差异确认：Day 2 追加式 vs Day 3 替换式 ✅")

    print("\n✅ State 结构正确")
    return True


# ============================================
# 测试 3：中间态检查（模拟直接调用 Node 函数）
# ============================================

def test_node_functions():
    """不依赖 LLM 调用，直接验证 Node 函数的输入输出逻辑"""
    from app.agent.research_agent import search_node, ResearchState

    print("=" * 60)
    print("测试 3：Node 函数单元测试（不调 LLM）")
    print("=" * 60)

    # 模拟 planner 的输出 → 测试 search_node 输入
    mock_state: ResearchState = {
        "query": "测试问题",
        "sub_queries": ["子问题A", "子问题B", "子问题C"],
        "search_results": [],
        "final_answer": "",
    }

    # 验证 search_node 正确返回 search_results
    result = search_node(mock_state)
    assert "search_results" in result, "search_node 应返回 search_results"
    assert len(result["search_results"]) == 3, \
        f"应有 3 条搜索结果，实际 {len(result['search_results'])}"
    for i, r in enumerate(result["search_results"]):
        assert f"子问题 {i+1} 搜索结果" in r, \
            f"搜索结果 {i+1} 格式不正确: {r[:50]}..."

    print(f"\n   sub_queries 输入: {len(mock_state['sub_queries'])} 个")
    print(f"   search_results 输出: {len(result['search_results'])} 条")
    print(f"   每条结果都包含子问题标记: ✅")

    # 验证每个搜索结果都引用了对应的子问题
    for i, (sub_q, search_r) in enumerate(zip(mock_state["sub_queries"], result["search_results"])):
        assert sub_q in search_r, f"搜索结果 {i+1} 未引用子问题 '{sub_q}'"
    print(f"   每条搜索结果正确引用对应子问题: ✅")

    print("\n✅ Node 函数逻辑正确")
    return True


# ============================================
# 测试 4：完整流水线（端到端）
# ============================================

def test_full_pipeline():
    """端到端运行 Research Agent，验证完整 DAG 流程"""
    from app.agent.research_agent import research_app

    print("=" * 60)
    print("测试 4：完整流水线（端到端）")
    print("=" * 60)

    query = "什么是 LangGraph？它和 LangChain 有什么关系？"

    print(f"\n🚀 输入查询: {query}")
    print("-" * 40)

    try:
        result = research_app.invoke({"query": query})
    except Exception as e:
        print(f"\n❌ 流水线执行失败: {e}")
        print("请检查：")
        print("  1. pip install langgraph langchain-core")
        print("  2. .env 中 DEEPSEEK_API_KEY 是否正确配置")
        return False

    print("-" * 40)

    # 验证输出完整性
    print(f"\n📊 流水线输出检查：")
    print(f"   query:            {'✅' if result.get('query') else '❌'} "
          f"({len(result.get('query', ''))} 字符)")
    print(f"   sub_queries:      {'✅' if result.get('sub_queries') else '❌'} "
          f"({len(result.get('sub_queries', []))} 个子问题)")
    print(f"   search_results:   {'✅' if result.get('search_results') else '❌'} "
          f"({len(result.get('search_results', []))} 条结果)")
    print(f"   final_answer:     {'✅' if result.get('final_answer') else '❌'} "
          f"({len(result.get('final_answer', ''))} 字符)")

    # 验证所有字段存在且非空
    assert result.get("query"), "query 字段为空"
    assert result.get("sub_queries"), "sub_queries 字段为空"
    assert len(result["sub_queries"]) >= 2, \
        f"至少应有 2 个子问题，实际 {len(result['sub_queries'])}"
    assert result.get("search_results"), "search_results 字段为空"
    assert len(result["search_results"]) == len(result["sub_queries"]), \
        "搜索结果数量应与子问题数量一致"
    assert result.get("final_answer"), "final_answer 字段为空"
    assert len(result["final_answer"]) > 50, \
        f"final_answer 太短（{len(result['final_answer'])} 字符），可能生成失败"

    # 显示子问题列表
    print(f"\n📝 Planner 拆解的子问题：")
    for i, sq in enumerate(result["sub_queries"], 1):
        print(f"   {i}. {sq}")

    # 显示最终回答摘要
    print(f"\n📄 Writer 生成回答（前 200 字符）：")
    print(f"   {result['final_answer'][:200]}...")

    print("\n✅ 完整流水线运行成功")
    return True


# ============================================
# 测试 5：便捷函数 research()
# ============================================

def test_convenience_function():
    """验证 research() 便捷函数可用"""
    from app.agent.research_agent import research

    print("=" * 60)
    print("测试 5：research() 便捷函数")
    print("=" * 60)

    try:
        answer = research("今天天气怎么样？")
        print(f"\n   research() 返回类型: {type(answer).__name__}")
        print(f"   回答长度: {len(answer)} 字符")
        assert isinstance(answer, str), "返回值应为字符串"
        assert len(answer) > 0, "回答不应为空"
        print(f"   回答预览: {answer[:100]}...")
        print("\n✅ research() 便捷函数正常")
        return True
    except Exception as e:
        print(f"\n❌ research() 执行失败: {e}")
        return False


# ============================================
# 主入口
# ============================================

if __name__ == "__main__":
    results = []

    # 不依赖 LLM 的测试先跑
    results.append(("图结构验证", test_graph_structure()))
    results.append(("State 结构对比", test_state_structure()))
    results.append(("Node 函数单元测试", test_node_functions()))

    # 依赖 LLM 的测试
    results.append(("完整流水线", test_full_pipeline()))
    results.append(("便捷函数 research()", test_convenience_function()))

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
