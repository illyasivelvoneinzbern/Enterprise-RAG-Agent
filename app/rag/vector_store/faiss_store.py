"""
faiss_store.py — FAISS 向量库实现（内存索引）

定位：算法实验 / 小规模数据。纯内存，进程重启数据丢失。

注意：本实现与 app/rag/vectorstore.py 的 VectorStore 等价，
但它遵循 BaseVectorStore 接口，可与其他 store 无缝切换。
"""

import faiss
import numpy as np

from app.rag.vector_store.base import BaseVectorStore


class FaissStore(BaseVectorStore):
    """
    基于 FAISS IndexFlatL2 的向量库实现。

    用法:
      store = FaissStore(dimension=384)
      store.add(vectors, documents)             # vectors: (N, dim)
      docs = store.search(query_vector, top_k=3)  # query_vector: (1, dim)
    """

    def __init__(self, dimension: int):
        # IndexFlatL2 = 暴力精确检索（L2 距离）
        self.index = faiss.IndexFlatL2(dimension)
        self.documents = []

    def add(self, vectors, documents, metadatas=None):
        """
        写入向量和文档。

        参数:
          vectors:   np.ndarray (N, dim) 或 list
          documents: list[dict]，与 vectors 一一对应
          metadatas: 可选（FAISS 本身不支持 metadata 过滤，这里忽略）
        """
        # 确保是 float32 的 numpy 数组（FAISS 要求）
        if not isinstance(vectors, np.ndarray):
            vectors = np.array(vectors)
        vectors = vectors.astype("float32")

        self.index.add(vectors)
        self.documents.extend(documents)

    def search(self, query_vector, top_k):
        """
        检索与查询向量最相似的 top_k 个文档。

        参数:
          query_vector: np.ndarray (1, dim) 或 list
          top_k:        返回数量

        返回:
          list[dict]，按 L2 距离升序（越近越相似）
        """
        if not isinstance(query_vector, np.ndarray):
            query_vector = np.array(query_vector)
        query_vector = query_vector.astype("float32")

        # 实际检索数不超过已存储数量
        k = min(top_k, len(self.documents))
        if k == 0:
            return []

        distances, indexes = self.index.search(query_vector, k)

        results = []
        for idx in indexes[0]:
            if idx == -1:  # FAISS 对不足 k 的情况返回 -1
                continue
            results.append(self.documents[idx])

        return results

    def count(self) -> int:
        return len(self.documents)
