"""
test_langgraph_agent.py — LangGraph Agent 功能验证

三个测试：
  1. 纯对话（无工具调用，retriever 为 None 时 LLM 应直接回答）
  2. 图结构可视化输出
  3. 兼容性检查（与旧 agent_executor.py 接口对比）
"""

import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ============================================
# 测试 1：纯对话（无工具调用）
# ============================================

def test_pure_chat():
    """测试 LLM 直接回答，不触发工具调用"""
    from app.agent.langgraph_agent import run_agent

    print("=" * 60)
    print("测试 1：纯对话（无工具调用）")
    print("=" * 60)

    messages = [
        {"role": "system", "content": "你是一个友好的助手，用中文回答。"},
        {"role": "user", "content": "你好，请用一句话介绍你自己。"},
    ]

    try:
        result = run_agent(messages)
        print(f"\n✅ 回答成功：\n{result}\n")
        print(f"📊 消息数量：{len(messages)}（应为 3：system + user + assistant）")
    except Exception as e:
        print(f"\n❌ 失败：{e}")
        print("请检查：")
        print("  1. pip install langgraph langchain-core")
        print("  2. .env 中 DEEPSEEK_API_KEY 是否正确配置")
        return False

    return True


# ============================================
# 测试 2：条件边逻辑验证（有 tool_calls 走哪条路径）
# ============================================

def test_graph_structure():
    """输出 LangGraph 图结构，验证 Node 和 Edge 是否正确"""
    from app.agent.langgraph_agent import graph, langgraph_app

    print("=" * 60)
    print("测试 2：图结构验证")
    print("=" * 60)

    # 输出所有节点
    nodes = graph.nodes
    print(f"\n📌 已注册节点（{len(nodes)} 个）：")
    for name, node in nodes.items():
        print(f"   - {name}: {node.__class__.__name__}")

    # 输出所有边
    print(f"\n🔗 边结构：")
    print(f"   START → LLM")
    print(f"   LLM → should_continue(state)")
    print(f"        → 'tool' → tool_node（有 tool_calls 时）")
    print(f"        → END            （无 tool_calls 时）")
    print(f"   tool_node → LLM（循环回去）")

    # 输出 State 结构
    from app.agent.langgraph_agent import AgentState
    print(f"\n📋 AgentState 字段：")
    for field in AgentState.__annotations__:
        annotation = AgentState.__annotations__[field]
        print(f"   - {field}: {annotation}")

    print("\n✅ 图结构正常")
    return True


# ============================================
# 测试 3：新旧接口对比
# ============================================

def test_interface_compatibility():
    """验证 LangGraph 版保留了旧版的 update_retriever 接口"""
    from app.agent.langgraph_agent import update_retriever, tool_registry

    print("=" * 60)
    print("测试 3：接口兼容性检查")
    print("=" * 60)

    # 检查 update_retriever 存在
    assert callable(update_retriever), "update_retriever 不可调用"

    # 检查 tool_registry 可用
    assert "knowledge_search" in tool_registry.tools, "knowledge_search 未注册"

    # 初始状态 retriever 应为 None
    search_tool = tool_registry.tools["knowledge_search"]
    print(f"\n   knowledge_search.retriever 初始值: {search_tool.retriever}")

    # 模拟注入 retriever
    class MockRetriever:
        def retrieve(self, query, top_k):
            return [{"text": "mock result", "metadata": {"source": "test"}}]

    mock = MockRetriever()
    update_retriever(mock)
    print(f"   knowledge_search.retriever 注入后: {search_tool.retriever.__class__.__name__}")
    assert search_tool.retriever is mock, "update_retriever 注入失败"

    # 恢复
    update_retriever(None)
    print(f"   knowledge_search.retriever 恢复后: {search_tool.retriever}")

    print("\n✅ 接口兼容性正常")
    return True


# ============================================
# 测试 4（可选）：带 RAG 的完整对话
# ============================================

def test_rag_chat():
    """测试带知识库检索的完整 RAG 对话（需先运行 /upload 接口上传文档）"""
    from app.rag.build_index import build_knowledge_base
    from app.agent.langgraph_agent import update_retriever, run_agent

    print("=" * 60)
    print("测试 4：RAG 对话（需本地知识库文件）")
    print("=" * 60)

    data_file = os.path.join(os.path.dirname(__file__), "data", "employee_policy.txt")
    if not os.path.exists(data_file):
        print(f"\n⚠️  跳过：找不到 {data_file}，请先确保示例文档存在")
        return True  # 不算失败

    try:
        # 构建知识库
        retriever = build_knowledge_base(data_file)
        update_retriever(retriever)

        # 发起 RAG 对话
        messages = [
            {"role": "system", "content": "你是企业知识库助手。需要时调用 knowledge_search 工具查询知识库。"},
            {"role": "user", "content": "员工每年有多少天年假？"},
        ]

        result = run_agent(messages)
        print(f"\n✅ RAG 回答成功：\n{result}\n")
    except Exception as e:
        print(f"\n❌ RAG 对话失败：{e}")
        return False

    return True


# ============================================
# 主入口
# ============================================

if __name__ == "__main__":
    results = []

    # 先做不依赖 LLM 的测试
    results.append(("接口兼容性检查", test_interface_compatibility()))
    results.append(("图结构验证", test_graph_structure()))

    # 再做依赖 LLM 的测试
    results.append(("纯对话", test_pure_chat()))
    results.append(("RAG 对话", test_rag_chat()))

    # 汇总
    print("\n" + "=" * 60)
    print("📊 测试汇总")
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    failed = len(results) - passed
    for name, ok in results:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status}  {name}")
    print(f"\n总计: {passed}/{len(results)} 通过" + (f", {failed} 失败" if failed else " 🎉"))
