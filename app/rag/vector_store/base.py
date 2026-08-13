"""
base.py — 向量库抽象基类（接口契约）

所有向量库实现（FAISS / Chroma / Milvus）都必须实现这两个方法：
    add(vectors, documents, metadatas=None)   # 写入
    search(query_vector, top_k)               # 检索

上层 Retriever 只依赖这个接口，因此可以无缝切换底层向量库。
"""

from abc import ABC, abstractmethod


class BaseVectorStore(ABC):
    """
    向量库抽象接口。

    接口设计（与现有 VectorStore 保持兼容）：
      add(vectors, documents):
        vectors:    np.ndarray，shape=(N, dim) 的 embedding
        documents:  list[dict]，与 vectors 一一对应的文档（含 text/metadata）
        metadatas:  list[dict]（可选），额外的 metadata 过滤字段

      search(query_vector, top_k):
        query_vector: np.ndarray，shape=(1, dim) 的查询 embedding
        top_k:       返回数量
        返回: list[dict]，按相似度排序的文档列表
    """

    @abstractmethod
    def add(self, vectors, documents, metadatas=None):
        """写入向量和文档。"""
        raise NotImplementedError

    @abstractmethod
    def search(self, query_vector, top_k):
        """检索与查询向量最相似的 top_k 个文档。"""
        raise NotImplementedError

    # ---------- 可选能力（非抽象，实现可覆盖） ----------

    def count(self) -> int:
        """返回已存储的文档数量（默认实现，子类可覆盖）。"""
        return 0

    def persist(self):
        """持久化到磁盘（Chroma 默认持久化；FAISS 内存实现为空操作）。"""
        pass
