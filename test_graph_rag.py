"""
test_graph_rag.py — Day 2: GraphRAG 测试

测试策略：
  - 纯逻辑测试（不依赖 LLM/模型）：
    · 实体抽取（extract_entities）
    · 关系抽取（extract_relations）
    · 图构建（build_from_text / 图结构）
    · 图增强检索（enhanced_retrieve / BFS 遍历）
    · 从文件构建（build_from_file）

运行方式（两种均可）：
  - pytest:   python -m pytest test_graph_rag.py -v
  - 手动:     python test_graph_rag.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.rag.graph_rag import (
    KnowledgeGraph,
    build_knowledge_graph,
    extract_entities,
    extract_relations,
)


# ============================================
# 1. 实体抽取测试
# ============================================

def test_extract_entities():
    """验证能从文本中抽取词典中的实体。"""
    text = "员工入职满一年后，可以享受带薪年假。普通员工每年享有10天带薪年假。"
    entities = extract_entities(text)

    # 应包含制度类实体
    assert "带薪年假" in entities
    assert "年假" in entities
    # 时间类实体（"一年"）应被抽取
    assert "一年" in entities


def test_extract_entities_no_duplicate():
    """验证实体去重。"""
    text = "年假制度规定年假为15天。"
    entities = extract_entities(text)
    # 同一个实体只出现一次
    assert entities.count("年假") == 1


# ============================================
# 2. 关系抽取测试
# ============================================

def test_extract_relations():
    """验证能从同一句话中抽取实体关系。"""
    text = "连续病假超过7天，需要经过部门负责人审批。病假需要提供医院证明。"
    entities = ["病假", "部门负责人", "医院证明"]
    relations = extract_relations(text, entities)

    # 应存在病假与部门负责人之间的关系
    assert len(relations) > 0
    # 至少一个关系包含病假
    assert any("病假" in rel for rel in relations)


# ============================================
# 3. 图构建测试
# ============================================

def test_build_graph_from_text():
    """验证能从文本构建知识图谱（有节点和边）。"""
    text = """公司员工福利政策手册
人事部负责审批年假。年假为15天。
财务部负责发放工资。工资每月15日发放。"""

    kg = KnowledgeGraph().build_from_text(text)
    stats = kg.stats()

    # 有节点
    assert stats["nodes"] > 0
    # 实体类型统计存在
    assert "部门" in stats["node_types"]


def test_build_graph_from_file():
    """验证能从 employee_policy.txt 构建知识图谱。"""
    kg = build_knowledge_graph("data/employee_policy.txt")
    stats = kg.stats()

    print(f"\n[统计] 节点={stats['nodes']}, 边={stats['edges']}, 类型={stats['node_types']}")
    # 至少能抽取出关键制度实体
    assert stats["nodes"] >= 5
    # 关键实体存在
    assert "年假" in kg.graph.nodes
    assert "病假" in kg.graph.nodes
    assert "工资" in kg.graph.nodes


# ============================================
# 4. 图增强检索测试
# ============================================

def test_enhanced_retrieve():
    """验证图增强检索能命中实体并扩展邻居。"""
    text = """人事部负责审批年假。年假为15天。
财务部负责发放工资。工资每月15日发放。"""

    kg = KnowledgeGraph().build_from_text(text)

    # 查询命中"年假"实体
    results = kg.enhanced_retrieve("哪个部门负责审批年假？")
    assert len(results) > 0
    assert results[0]["entity"] == "年假"
    assert results[0]["type"] == "制度"

    # 图遍历应能找到关联邻居（人事部）
    neighbor_entities = [n["entity"] for n in results[0]["neighbors"]]
    assert "人事部" in neighbor_entities
    # 关系应为"负责审批"
    relations = [n["relation"] for n in results[0]["neighbors"]]
    assert "负责审批" in relations


def test_enhanced_retrieve_no_match():
    """验证未命中实体时返回空列表。"""
    kg = KnowledgeGraph().build_from_text("人事部负责审批年假。")
    results = kg.enhanced_retrieve("今天天气怎么样？")
    assert results == []


def test_bfs_depth_limit():
    """验证 BFS 深度限制（depth=1 不遍历 2 跳邻居）。"""
    # 构造链式图: A-B-C
    text = """A规定B。B规定C。"""
    kg = KnowledgeGraph().build_from_text(text)
    kg.graph.add_edge("A", "B", relation="规定")
    kg.graph.add_edge("B", "C", relation="规定")

    # depth=1 只找到 B
    neighbors = kg._bfs_neighbors("A", depth=1)
    entities = {n["entity"] for n in neighbors}
    assert "B" in entities
    assert "C" not in entities  # 2 跳邻居被限制

    # depth=2 能到 C
    neighbors2 = kg._bfs_neighbors("A", depth=2)
    entities2 = {n["entity"] for n in neighbors2}
    assert "C" in entities2


# ============================================
# 手动运行入口（不依赖 pytest）
# ============================================

def run_all():
    tests = [
        ("实体抽取", test_extract_entities),
        ("实体去重", test_extract_entities_no_duplicate),
        ("关系抽取", test_extract_relations),
        ("文本建图", test_build_graph_from_text),
        ("文件建图", test_build_graph_from_file),
        ("图增强检索", test_enhanced_retrieve),
        ("无命中返回空", test_enhanced_retrieve_no_match),
        ("BFS 深度限制", test_bfs_depth_limit),
    ]
    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ✅ {name}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {name}: {e}")

    print(f"\n测试: {passed}/{len(tests)} 通过")
    return passed == len(tests)


if __name__ == "__main__":
    print("=" * 50)
    print("GraphRAG 测试")
    print("=" * 50)
    ok = run_all()
    sys.exit(0 if ok else 1)
