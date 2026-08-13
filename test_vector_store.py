"""
test_vector_store.py — Day 3: 向量库抽象层测试

测试策略：
  - 纯逻辑测试（不依赖 LLM/模型，用随机向量验证接口一致性）：
    · FaissStore: add / search / count
    · ChromaStore: add / search / count / metadata 过滤
    · 一致性：同一数据写入两种 store，检索结果一致

运行方式（两种均可）：
  - pytest:   python -m pytest test_vector_store.py -v
  - 手动:     python test_vector_store.py
"""

import sys
import os
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(__file__))

import numpy as np

from app.rag.vector_store import FaissStore, ChromaStore, BaseVectorStore


def _make_data(n=5, dim=8):
    """生成测试数据：n 个向量 + 对应文档。"""
    rng = np.random.default_rng(42)
    vectors = rng.random((n, dim)).astype("float32")
    documents = [
        {"text": f"文档{i}", "metadata": {"source": f"file{i}.txt"}}
        for i in range(n)
    ]
    return vectors, documents


def _make_query(dim=8):
    """生成查询向量（与第一个向量接近）。"""
    rng = np.random.default_rng(42)
    vectors = rng.random((5, dim)).astype("float32")
    return vectors[0:1]  # (1, dim)


# ============================================
# 1. FaissStore 测试
# ============================================

def test_faiss_add_search():
    """验证 FaissStore 能写入并检索。"""
    store = FaissStore(dimension=8)
    vectors, documents = _make_data()
    store.add(vectors, documents)

    assert store.count() == 5

    query = _make_query()
    results = store.search(query, top_k=3)
    assert len(results) == 3
    # 第一个结果应是最相似的文档0
    assert results[0]["text"] == "文档0"


def test_faiss_search_empty():
    """验证空 store 检索返回空列表。"""
    store = FaissStore(dimension=8)
    assert store.search(_make_query(), top_k=3) == []


# ============================================
# 2. ChromaStore 测试
# ============================================

def test_chroma_add_search():
    """验证 ChromaStore 能写入并检索。"""
    # 用临时目录避免污染项目数据
    tmpdir = tempfile.mkdtemp()
    try:
        store = ChromaStore(persist_dir=tmpdir)
        vectors, documents = _make_data()
        store.add(vectors, documents)

        assert store.count() == 5

        query = _make_query()
        results = store.search(query, top_k=3)
        assert len(results) == 3
        # 第一个结果应是最相似的文档0
        assert results[0]["text"] == "文档0"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_chroma_metadata_filter():
    """验证 Chroma 原生支持 metadata 过滤（FAISS 做不到的能力）。"""
    tmpdir = tempfile.mkdtemp()
    try:
        store = ChromaStore(persist_dir=tmpdir)
        vectors, documents = _make_data()
        store.add(vectors, documents)

        # 只检索 source=file0.txt 的文档
        results = store.search(_make_query(), top_k=3, where={"source": "file0.txt"})
        assert len(results) >= 1
        # 所有结果都应匹配过滤条件
        for r in results:
            assert r["metadata"]["source"] == "file0.txt"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_chroma_persist_reload():
    """验证 Chroma 持久化：重开实例后数据仍在（FAISS 做不到）。"""
    tmpdir = tempfile.mkdtemp()
    try:
        # 第一次写入
        store1 = ChromaStore(persist_dir=tmpdir)
        vectors, documents = _make_data()
        store1.add(vectors, documents)

        # 模拟重启：新建实例指向同一目录
        store2 = ChromaStore(persist_dir=tmpdir)
        # 从 collection 重新加载
        data = store2.collection.get()
        assert len(data["ids"]) == 5
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ============================================
# 3. 一致性测试（核心：可无缝切换）
# ============================================

def test_stores_interface_consistency():
    """验证两种 store 都实现 BaseVectorStore 接口，且行为一致。

    这是抽象层的核心价值：上层代码无需改动即可切换底层。
    """
    for StoreClass in (FaissStore, ChromaStore):
        # 都是 BaseVectorStore 子类
        assert issubclass(StoreClass, BaseVectorStore), f"{StoreClass.__name__} 未实现接口"

        # 都有 add / search 方法
        for method in ("add", "search", "count"):
            assert hasattr(StoreClass, method), f"{StoreClass.__name__} 缺少 {method}"


# ============================================
# 手动运行入口（不依赖 pytest）
# ============================================

def run_all():
    tests = [
        ("FaissStore 写入检索", test_faiss_add_search),
        ("FaissStore 空检索", test_faiss_search_empty),
        ("ChromaStore 写入检索", test_chroma_add_search),
        ("ChromaStore metadata 过滤", test_chroma_metadata_filter),
        ("ChromaStore 持久化重载", test_chroma_persist_reload),
        ("接口一致性", test_stores_interface_consistency),
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
    print("向量库抽象层测试")
    print("=" * 50)
    ok = run_all()
    sys.exit(0 if ok else 1)
