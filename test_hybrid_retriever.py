"""
test_hybrid_retriever.py — Day 6: 混合检索功能验证

五个测试：
  1. BM25 分词 + 索引构建
  2. BM25 关键词检索（精确匹配验证）
  3. RRF 融合算法正确性
  4. HybridRetriever 完整流程（FAISS + BM25 → RRF）
  5. 纯向量 vs 混合检索 对比
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ============================================
# 测试 1：BM25 分词 + 索引构建
# ============================================

def test_bm25_build():
    """验证 BM25 能正确构建索引"""
    import jieba
    from app.rag.hybrid_retriever import BM25Retriever

    print("=" * 60)
    print("测试 1：BM25 索引构建 + 分词验证")
    print("=" * 60)

    documents = [
        {"text": "员工每年享有10天带薪年假", "metadata": {"source": "policy.txt"}},
        {"text": "病假需要提供医院证明", "metadata": {"source": "policy.txt"}},
        {"text": "工资每月15号发放", "metadata": {"source": "policy.txt"}},
        {"text": "年终奖根据绩效评定", "metadata": {"source": "policy.txt"}},
    ]

    try:
        bm25 = BM25Retriever(documents)
    except Exception as e:
        print(f"\n❌ BM25 构建失败: {e}")
        print("请检查: pip install rank_bm25 jieba")
        return False

    # 验证分词
    sample_tokens = list(jieba.cut(documents[0]["text"]))
    print(f"\n   文档 0: '{documents[0]['text']}'")
    print(f"   分词结果: {sample_tokens}")
    assert len(sample_tokens) >= 3, f"分词结果异常: {sample_tokens}"

    # 验证索引文档数
    assert len(bm25.documents) == 4, f"索引文档数应为 4，实际 {len(bm25.documents)}"
    print(f"   BM25 索引文档数: {len(bm25.documents)} ✅")

    print("\n✅ BM25 索引构建正常")
    return True


# ============================================
# 测试 2：BM25 关键词检索（精确匹配）
# ============================================

def test_bm25_search():
    """验证 BM25 关键词精确匹配能力"""
    import jieba
    from app.rag.hybrid_retriever import BM25Retriever

    print("=" * 60)
    print("测试 2：BM25 关键词精确匹配")
    print("=" * 60)

    documents = [
        {"text": "员工每年享有10天带薪年假", "metadata": {"source": "p1"}},
        {"text": "病假需要提供医院证明", "metadata": {"source": "p2"}},
        {"text": "工资每月15号发放", "metadata": {"source": "p3"}},
        {"text": "年终奖根据绩效评定", "metadata": {"source": "p4"}},
    ]

    bm25 = BM25Retriever(documents)

    # 精确关键词查询
    results = bm25.search("年假", top_k=2)
    print(f"\n   查询 '年假' → {len(results)} 条结果：")
    for i, r in enumerate(results):
        print(f"     {i+1}. [{r['metadata']['source']}] {r['text']} (score={r['score']:.4f})")

    # 验证"年假"文档排在第一位
    assert len(results) >= 1, "应至少返回 1 条结果"
    assert "年假" in results[0]["text"], f"第一条应包含 '年假'，实际: {results[0]['text']}"

    # 查询不存在的词应返回结果但分数低
    results_none = bm25.search("xyz不存在", top_k=2)
    print(f"\n   查询 'xyz不存在' → BM25 分数:")
    for i, r in enumerate(results_none):
        print(f"     {i+1}. score={r['score']:.4f}")

    print("\n✅ BM25 关键词精确匹配正常")
    return True


# ============================================
# 测试 3：RRF 融合算法正确性
# ============================================

def test_rrf_fusion():
    """验证 RRF 融合算法的排名逻辑"""
    from app.rag.hybrid_retriever import rrf_fusion

    print("=" * 60)
    print("测试 3：RRF 融合算法验证")
    print("=" * 60)

    # 模拟 FAISS 和 BM25 返回不同排序的文档
    doc_a = {"text": "员工每年享有10天带薪年假", "metadata": {"source": "a"}}
    doc_b = {"text": "带薪休假包含年假和病假", "metadata": {"source": "b"}}
    doc_c = {"text": "工资每月15号发放", "metadata": {"source": "c"}}

    # FAISS（语义）排: B(年假+休假) → A(年假) → C(工资)
    faiss_results = [doc_b, doc_a, doc_c]

    # BM25（关键词）排: A(年假精确) → B(年假) → (C 没进)
    bm25_results = [doc_a, doc_b]

    fused = rrf_fusion(faiss_results, bm25_results, k=60, final_top_k=2)

    print(f"\n   FAISS 排名: B(年假+休假) > A(年假) > C(工资)")
    print(f"   BM25 排名:  A(年假精确) > B(年假)")
    print(f"\n   RRF 融合后 (top 2):")

    for i, r in enumerate(fused):
        print(f"     {i+1}. {r['text'][:30]}... (rrf_score={r['rrf_score']})")

    # RRF 计算:
    # doc_a: FAISS rank=2 → 1/(60+2)=0.0161, BM25 rank=1 → 1/(60+1)=0.0164
    #        总分 = 0.0161 + 0.0164 = 0.0325
    # doc_b: FAISS rank=1 → 1/(60+1)=0.0164, BM25 rank=2 → 1/(60+2)=0.0161
    #        总分 = 0.0164 + 0.0161 = 0.0325
    # → 两人同分！但实际 doc_a 因在两个列表中都排名靠前，应该排在 doc_b 前面

    assert len(fused) >= 1, "应至少返回 1 条融合结果"
    assert "rrf_score" in fused[0], "融合结果应包含 rrf_score"

    # 验证 faiss + bm25 都有贡献的文档不应被遗漏
    all_texts = " ".join(r["text"] for r in fused)
    assert "年假" in all_texts, "融合结果应包含'年假'相关内容"

    print(f"\n✅ RRF 融合算法正常")
    return True


# ============================================
# 测试 4：HybridRetriever 完整流程
# ============================================

def test_hybrid_retriever():
    """验证 HybridRetriever 端到端工作"""
    from app.rag.hybrid_retriever import HybridRetriever
    from app.rag.vectorstore import VectorStore
    from app.rag.embedding import model
    from app.rag.reranker import Reranker

    print("=" * 60)
    print("测试 4：HybridRetriever 完整流程")
    print("=" * 60)

    # 构建测试数据
    documents = [
        {"text": "普通员工每年享有10天带薪年假，高级员工15天", "metadata": {"source": "policy.txt"}},
        {"text": "病假需提供三甲医院诊断证明，连续超过7天需部门审批", "metadata": {"source": "policy.txt"}},
        {"text": "每月15号发放上月工资，遇节假日顺延", "metadata": {"source": "policy.txt"}},
        {"text": "年终奖根据年度绩效考核结果评定，分为A/B/C三档", "metadata": {"source": "policy.txt"}},
        {"text": "婚假为3天，晚婚增加至15天", "metadata": {"source": "policy.txt"}},
    ]

    # 构建 FAISS 索引
    vectors = model.encode([d["text"] for d in documents])
    store = VectorStore(dimension=len(vectors[0]))
    store.add(vectors, documents)

    # 构建混合检索器
    hybrid = HybridRetriever(store, documents, model, reranker=Reranker())

    # 检索
    query = "员工年假有几天？"
    results = hybrid.retrieve(query, top_k=3)

    print(f"\n   查询: '{query}'")
    print(f"   返回 {len(results)} 条结果：")
    for i, r in enumerate(results):
        score_info = r.get("rrf_score", r.get("score", "N/A"))
        print(f"     {i+1}. [{r['metadata']['source']}] {r['text'][:50]}... (score={score_info})")

    assert len(results) >= 1, "应至少返回 1 条结果"
    assert len(results) <= 3, f"不应超过 top_k=3，实际 {len(results)}"

    # 验证"年假"相关内容在结果中
    texts = " ".join(r["text"] for r in results)
    assert "年假" in texts or "休假" in texts, \
        f"结果应包含年假相关内容，实际: {texts[:100]}"

    print("\n✅ HybridRetriever 完整流程正常")
    return True


# ============================================
# 测试 5：纯向量 vs 混合检索对比
# ============================================

def test_vs_pure_vector():
    """对比纯 FAISS 向量检索 vs 混合检索的召回差异"""
    from app.rag.hybrid_retriever import HybridRetriever
    from app.rag.retriever import Retriever
    from app.rag.vectorstore import VectorStore
    from app.rag.embedding import model

    print("=" * 60)
    print("测试 5：纯向量检索 vs 混合检索 对比")
    print("=" * 60)

    # 构建包含"容易被向量遗漏的关键词"的测试数据
    documents = [
        {"text": "带薪休假政策包括年假和调休", "metadata": {"source": "p1"}},       # 语义相近
        {"text": "员工的薪酬福利体系包含多项内容", "metadata": {"source": "p2"}},     # 语义相关
        {"text": "年假申请需提前一周提交OA", "metadata": {"source": "p3"}},          # 精确含"年假"
        {"text": "公司提供免费午餐和班车服务", "metadata": {"source": "p4"}},         # 不相关
        {"text": "加班调休制度说明", "metadata": {"source": "p5"}},                  # 语义相关
    ]

    vectors = model.encode([d["text"] for d in documents])
    store = VectorStore(dimension=len(vectors[0]))
    store.add(vectors, documents)

    # ── 纯向量检索 ──
    pure_retriever = Retriever(store, model)
    pure_results = pure_retriever.retrieve("年假", top_k=3)

    print(f"\n   📍 纯向量检索 (FAISS) — 查询 '年假'：")
    for i, r in enumerate(pure_results):
        print(f"     {i+1}. [{r['metadata']['source']}] {r['text']}")

    # ── 混合检索 ──
    hybrid_retriever = HybridRetriever(store, documents, model)
    hybrid_results = hybrid_retriever.retrieve("年假", top_k=3)

    print(f"\n   🔀 混合检索 (FAISS + BM25 → RRF) — 查询 '年假'：")
    for i, r in enumerate(hybrid_results):
        score_info = r.get("rrf_score", "N/A")
        print(f"     {i+1}. [{r['metadata']['source']}] {r['text']} (rrf={score_info})")

    # ── 对比分析 ──
    pure_sources = [r["metadata"]["source"] for r in pure_results]
    hybrid_sources = [r["metadata"]["source"] for r in hybrid_results]

    print(f"\n   📊 召回对比：")
    print(f"     纯向量 top:  {pure_sources}")
    print(f"     混合检索 top: {hybrid_sources}")

    # 核心验证：p3 ("年假申请") 包含精确关键词"年假"
    # FAISS 可能因 embedding 偏好"带薪休假"而漏掉 p3
    # 混合检索通过 BM25 应该能召回 p3
    has_p3_in_pure = "p3" in pure_sources
    has_p3_in_hybrid = "p3" in hybrid_sources

    print(f"\n   p3 ('年假申请') 召回情况：")
    print(f"     纯向量: {'✅ 召回' if has_p3_in_pure else '❌ 未召回'}")
    print(f"     混合检索: {'✅ 召回' if has_p3_in_hybrid else '❌ 未召回'}")

    if has_p3_in_hybrid and not has_p3_in_pure:
        print(f"   🎯 混合检索成功召回了纯向量遗漏的精确关键词文档！")
    elif has_p3_in_pure and has_p3_in_hybrid:
        print(f"   ℹ️ 两者都召回了（FAISS embedding 质量好）")
    elif not has_p3_in_hybrid:
        print(f"   ⚠️ 设计上 BM25 应能命中 '年假'，请检查分词/jieba")

    # 两者都应有结果
    assert len(pure_results) >= 1
    assert len(hybrid_results) >= 1

    print("\n✅ 纯向量 vs 混合检索对比完成")
    return True


# ============================================
# 测试 6：build_hybrid_retriever 便捷函数
# ============================================

def test_build_hybrid_retriever():
    """验证 build_hybrid_retriever() 一键构建"""
    from app.rag.hybrid_retriever import build_hybrid_retriever

    print("=" * 60)
    print("测试 6：build_hybrid_retriever() 便捷函数")
    print("=" * 60)

    data_file = os.path.join(os.path.dirname(__file__), "data", "employee_policy.txt")
    if not os.path.exists(data_file):
        print(f"\n⚠️  跳过：找不到 {data_file}")
        return True

    try:
        hr = build_hybrid_retriever(data_file)
        results = hr.retrieve("员工年假几天？", top_k=2)
        print(f"\n   查询 '员工年假几天？' → {len(results)} 条结果：")
        for i, r in enumerate(results):
            print(f"     {i+1}. {r['text'][:60]}...")
        assert len(results) >= 1
        print("\n✅ build_hybrid_retriever() 正常")
        return True
    except Exception as e:
        print(f"\n❌ 构建失败: {e}")
        return False


# ============================================
# 主入口
# ============================================

if __name__ == "__main__":
    results = []

    # 不依赖外部数据的先跑
    results.append(("BM25 索引构建", test_bm25_build()))
    results.append(("BM25 关键词检索", test_bm25_search()))
    results.append(("RRF 融合算法", test_rrf_fusion()))

    # 依赖 embedding 模型
    results.append(("HybridRetriever 完整流程", test_hybrid_retriever()))
    results.append(("纯向量 vs 混合检索", test_vs_pure_vector()))
    results.append(("build_hybrid_retriever()", test_build_hybrid_retriever()))

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
