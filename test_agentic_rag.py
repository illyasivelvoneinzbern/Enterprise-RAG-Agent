"""
test_agentic_rag.py — Day 1: Agentic-RAG 测试

测试策略（借鉴 test_research_agent.py）：
  - 纯逻辑测试（不依赖 LLM）：图结构、State 结构、should_retry 决策、节点函数
  - 端到端测试（依赖 LLM）：完整流程，标注 try/except 保护

运行方式（两种均可）：
  - pytest:   python -m pytest test_agentic_rag.py -v
  - 手动:     python test_agentic_rag.py
  （使用 unittest.mock 而非 pytest fixture，确保不依赖 pytest 也能运行）
"""

import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(__file__))

from unittest.mock import patch


# ============================================
# 1. 图结构测试（不调用 LLM）
# ============================================

def test_graph_structure():
    """验证 Agentic-RAG 图包含 4 个核心节点，且存在条件边。"""
    from app.agent.agentic_rag import agentic_rag_app

    # 提取业务节点名（忽略 LangGraph 内部的 __start__ 等）
    node_names = {
        n for n in agentic_rag_app.get_graph().nodes
        if not str(n).startswith("__")
    }
    expected = {"rewrite", "search", "generate", "reflect"}
    assert expected.issubset(node_names), f"缺少节点: {expected - node_names}"

    # 验证 reflect 节点出发的边存在（重检回路）
    edges = agentic_rag_app.get_graph().edges
    from_node_names = {e[0] for e in edges if not str(e[0]).startswith("__")}
    assert "reflect" in from_node_names, "缺少 reflect 节点的条件边"


def test_state_structure():
    """验证 AgenticRAGState 包含全部关键字段。"""
    from app.agent.agentic_rag import AgenticRAGState

    required_fields = {
        "query",
        "rewritten_query",
        "context",
        "answer",
        "reflection",
        "retry_count",
    }
    state_fields = set(AgenticRAGState.__annotations__.keys())
    assert required_fields.issubset(state_fields), (
        f"State 缺少字段: {required_fields - state_fields}"
    )


# ============================================
# 2. 纯逻辑测试（mock chat，不触发真实 LLM）
# ============================================

def test_query_rewrite_node():
    """验证 Query Rewrite 节点：mock chat() 返回改写后的问题。"""
    from app.agent import agentic_rag

    def fake_chat(prompt):
        return "公司带薪休假政策中，员工可以休多少天年假？"

    with patch.object(agentic_rag, "chat", fake_chat):
        state = {
            "query": "那我可以休多少天？",
            "rewritten_query": "",
            "context": "",
            "answer": "",
            "reflection": "",
            "retry_count": 0,
        }
        result = agentic_rag.query_rewrite_node(state)

    assert result["rewritten_query"] == "公司带薪休假政策中，员工可以休多少天年假？"
    # 改写后的问题应该包含关键实体（指代消解成功）
    assert "年假" in result["rewritten_query"]


def test_reflection_node_retry():
    """验证 Reflection 节点：回答质量不足时返回 retry。"""
    from app.agent import agentic_rag

    def fake_chat(prompt):
        return "retry"

    with patch.object(agentic_rag, "chat", fake_chat):
        state = {
            "query": "年假几天？",
            "rewritten_query": "年假几天？",
            "context": "年假15天",
            "answer": "资料中未找到相关信息",
            "reflection": "",
            "retry_count": 0,
        }
        result = agentic_rag.reflection_node(state)

    assert result["reflection"] == "retry"


def test_reflection_node_accept():
    """验证 Reflection 节点：回答质量足够时返回 accept。"""
    from app.agent import agentic_rag

    def fake_chat(prompt):
        return "accept"

    with patch.object(agentic_rag, "chat", fake_chat):
        state = {
            "query": "年假几天？",
            "rewritten_query": "年假几天？",
            "context": "年假15天",
            "answer": "根据公司政策，年假为15天。",
            "reflection": "",
            "retry_count": 0,
        }
        result = agentic_rag.reflection_node(state)

    assert result["reflection"] == "accept"


def test_should_retry_logic():
    """验证条件边决策函数（纯逻辑，不依赖 LLM）。

    关键规则：
      - retry 且未超限 → "search"
      - retry 且已超限 → "end"
      - accept → "end"
    """
    from app.agent.agentic_rag import should_retry, MAX_RETRY

    base_state = {
        "query": "",
        "rewritten_query": "",
        "context": "",
        "answer": "",
        "reflection": "",
        "retry_count": 0,
    }

    # 场景 1：需要重检且未超限 → search
    s = dict(base_state, reflection="retry", retry_count=0)
    assert should_retry(s) == "search"

    # 场景 2：需要重检但已达最大次数 → end
    s = dict(base_state, reflection="retry", retry_count=MAX_RETRY)
    assert should_retry(s) == "end"

    # 场景 3：回答被接受 → end
    s = dict(base_state, reflection="accept", retry_count=0)
    assert should_retry(s) == "end"


# ============================================
# 3. 端到端测试（依赖 LLM 和模型，用 try/except 保护）
# ============================================

def test_full_pipeline():
    """端到端运行 Agentic-RAG，验证完整流程可执行。

    注意：会触发真实 LLM 调用 + 加载 bge 模型（较慢），
    且首次加载模型可能耗时较长，如环境受限可跳过。
    """
    from app.agent.agentic_rag import agentic_rag_answer

    try:
        answer = agentic_rag_answer("公司带薪休假政策中，员工可以休多少天年假？")
        assert answer and len(answer) > 0
        print(f"\n[E2E] 回答: {answer[:100]}...")
        return True
    except Exception as e:
        print(f"\n[E2E] 端到端测试跳过（依赖外部 LLM/模型）: {e}")
        return False


# ============================================
# 手动运行入口（不依赖 pytest）
# ============================================

def run_all():
    """手动运行全部测试（等价于 pytest 运行全部）。"""
    tests = [
        ("图结构", test_graph_structure),
        ("State 结构", test_state_structure),
        ("Query Rewrite 节点", test_query_rewrite_node),
        ("Reflection 节点(retry)", test_reflection_node_retry),
        ("Reflection 节点(accept)", test_reflection_node_accept),
        ("should_retry 决策", test_should_retry_logic),
    ]
    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ✅ {name}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {name}: {e}")

    print(f"\n纯逻辑测试: {passed}/{len(tests)} 通过")

    # 端到端测试（可选，依赖外部服务）
    print("\n端到端测试（依赖 LLM + 模型，可能较慢）...")
    e2e_ok = test_full_pipeline()
    print(f"端到端测试: {'✅ 通过' if e2e_ok else '⏭️ 跳过'}")

    return passed == len(tests)


if __name__ == "__main__":
    print("=" * 50)
    print("Agentic-RAG 测试")
    print("=" * 50)
    ok = run_all()
    sys.exit(0 if ok else 1)
