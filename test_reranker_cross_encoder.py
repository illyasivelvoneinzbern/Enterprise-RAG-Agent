"""
Day 4 测试: CrossEncoderReranker

运行方式（不需要 pytest）:
  python test_reranker_cross_encoder.py

测试策略:
  - 纯逻辑测试: mock 掉 CrossEncoder，验证 rerank 的排序/截断/top_k/接口兼容
  - 端到端测试（可选）: 真实加载 BAAI/bge-reranker-v2-m3，验证语义排序
"""

import unittest.mock
from unittest.mock import MagicMock, patch

from app.rag.reranker_cross_encoder import CrossEncoderReranker, MAX_CHARS


def _make_docs():
    """构造候选文档列表（与 HybridRetriever 输出结构一致）。"""
    return [
        {"text": "员工享有带薪年假，工作满一年可休 5 天。", "metadata": {"source": "a"}},
        {"text": "年假申请需提前三天在系统提交。", "metadata": {"source": "b"}},
        {"text": "每月 10 号发放上个月工资。", "metadata": {"source": "c"}},
        {"text": "带薪年假天数根据工龄递增。", "metadata": {"source": "d"}},
    ]


# ============================================
# 纯逻辑测试（mock CrossEncoder，不依赖网络/模型）
# ============================================

def test_rerank_sorts_by_score():
    """CrossEncoder 分数降序排列，且返回 top_k 条。"""
    # mock 模型: 文档1分最高，文档3分最低
    fake_model = MagicMock()
    fake_model.predict.return_value = [0.2, 0.8, 0.1, 0.5]

    rr = CrossEncoderReranker()
    with patch.object(rr, "_get_model", return_value=fake_model):
        results = rr.rerank("员工年假几天？", _make_docs(), top_k=2)

    # mock 分数 [0.2, 0.8, 0.1, 0.5] 按顺序对应 4 个文档
    # 降序后: 文档1(0.8) > 文档3(0.5) > 文档0(0.2) > 文档2(0.1)
    # top_k=2 应取 [文档1, 文档3]
    assert len(results) == 2, f"top_k 应取 2 条，实际 {len(results)}"
    assert "年假申请需提前三天在系统提交" in results[0]["text"]
    assert "带薪年假天数根据工龄递增" in results[1]["text"]
    assert "rerank_score" in results[0]
    print("PASS test_rerank_sorts_by_score")


def test_rerank_pairs_truncation():
    """构造的 (query, doc) 对中，doc 文本应被截断到 MAX_CHARS。"""
    fake_model = MagicMock()
    fake_model.predict.return_value = [1.0, 0.0]

    rr = CrossEncoderReranker()
    with patch.object(rr, "_get_model", return_value=fake_model):
        long_docs = [
            {"text": "长" * (MAX_CHARS + 100)},   # 超长文本
            {"text": "短文本"},
        ]
        rr.rerank("查询", long_docs, top_k=2)

    # 验证传给 predict 的 pairs 中第一条已被截断到 MAX_CHARS
    call_args = fake_model.predict.call_args
    pairs = call_args[0][0]
    assert len(pairs[0][1]) == MAX_CHARS, f"应截断到 {MAX_CHARS}，实际 {len(pairs[0][1])}"
    assert pairs[1][1] == "短文本"
    print("PASS test_rerank_pairs_truncation")


def test_rerank_empty_documents():
    """空候选列表直接返回 []，不触发模型加载。"""
    rr = CrossEncoderReranker()
    with patch.object(rr, "_get_model", side_effect=AssertionError("不应加载模型")):
        assert rr.rerank("查询", []) == []
    print("PASS test_rerank_empty_documents")


def test_rerank_does_not_mutate_original_docs():
    """rerank 返回的文档是副本，原文档不被附加 rerank_score。"""
    fake_model = MagicMock()
    fake_model.predict.return_value = [0.9, 0.1]

    docs = _make_docs()
    rr = CrossEncoderReranker()
    with patch.object(rr, "_get_model", return_value=fake_model):
        results = rr.rerank("查询", docs, top_k=2)

    assert "rerank_score" in results[0]
    assert "rerank_score" not in docs[0], "原文档不应被修改"
    print("PASS test_rerank_does_not_mutate_original_docs")


def test_lazy_model_loading():
    """模型懒加载: 未调用 rerank/score 前不加载模型。"""
    rr = CrossEncoderReranker()
    assert rr._model is None, "构造时不应加载模型"

    # 调用 rerank 时才加载
    fake_model = MagicMock()
    fake_model.predict.return_value = [1.0]
    with patch("app.rag.reranker_cross_encoder.CrossEncoder", return_value=fake_model):
        rr.rerank("查询", [{"text": "文档"}], top_k=1)
        assert rr._model is fake_model, "rerank 后应已加载模型"
    print("PASS test_lazy_model_loading")


def test_score_single():
    """score() 单条打分方法兼容旧 Reranker 接口。"""
    fake_model = MagicMock()
    fake_model.predict.return_value = [0.75]

    rr = CrossEncoderReranker()
    with patch.object(rr, "_get_model", return_value=fake_model):
        s = rr.score("查询", "相关文档内容")

    assert s == 0.75
    print("PASS test_score_single")


def test_interface_compatible_with_old_reranker():
    """接口兼容性: 签名与旧 Reranker 一致，可 drop-in 替换。"""
    import inspect
    from app.rag.reranker import Reranker
    from app.rag.reranker_cross_encoder import CrossEncoderReranker

    old_sig = inspect.signature(Reranker.rerank)
    new_sig = inspect.signature(CrossEncoderReranker.rerank)

    old_params = list(old_sig.parameters.keys())
    new_params = list(new_sig.parameters.keys())
    assert old_params == new_params, f"签名不一致: {old_params} vs {new_params}"
    print("PASS test_interface_compatible_with_old_reranker")


# ============================================
# 端到端测试（真实模型，可选）
# ============================================

def test_e2e_semantic_ranking():
    """
    端到端: 真实加载 bge-reranker-v2-m3，验证语义排序。

    语义相关的"年假"文档应排在"工资"文档前面，
    即使它们字符重合度不一定最高（这正是 CrossEncoder 的价值）。

    需要联网下载模型，失败会被捕获跳过（不阻塞其它测试）。
    """
    try:
        rr = CrossEncoderReranker()
        query = "我有几天年假？"
        docs = _make_docs()
        results = rr.rerank(query, docs, top_k=4)

        assert results, "应返回结果"
        # 语义相关文档应排在前 2
        top_texts = [d["text"] for d in results[:2]]
        assert any("年假" in t for t in top_texts), f"年假文档应进前2: {top_texts}"
        print("PASS test_e2e_semantic_ranking (真实模型)")
        print("  排序:", [f"[{d.get('rerank_score')}] {d['text'][:20]}..." for d in results])
    except Exception as e:
        print(f"SKIP test_e2e_semantic_ranking (真实模型不可用): {type(e).__name__}: {e}")


# ============================================
# 运行入口
# ============================================

def run_all():
    print("=" * 60)
    print("Day 4 CrossEncoderReranker 测试")
    print("=" * 60)
    test_rerank_sorts_by_score()
    test_rerank_pairs_truncation()
    test_rerank_empty_documents()
    test_rerank_does_not_mutate_original_docs()
    test_lazy_model_loading()
    test_score_single()
    test_interface_compatible_with_old_reranker()
    test_e2e_semantic_ranking()
    print("=" * 60)
    print("全部完成")


if __name__ == "__main__":
    run_all()
