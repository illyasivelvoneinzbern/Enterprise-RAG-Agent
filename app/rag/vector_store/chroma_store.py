"""
chroma_store.py — Chroma 向量库实现（本地持久化）

定位：轻量本地向量数据库。原生支持 metadata 过滤 + 磁盘持久化，
适合本地开发和原型验证。

与 FAISS 的关键差异：
  - Chroma 自动持久化到磁盘（PersistentClient）
  - Chroma 支持 metadata 过滤（where 条件）
  - Chroma 内部自己管理 id / 文档
"""

import chromadb

from app.rag.vector_store.base import BaseVectorStore


class ChromaStore(BaseVectorStore):
    """
    基于 Chroma 的向量库实现。

    用法:
      store = ChromaStore(persist_dir="./data/chroma_db")
      store.add(vectors, documents)               # 自动持久化
      docs = store.search(query_vector, top_k=3)

    说明：
      - 本实现用 Chroma 的 add(embeddings=..., documents=...)
        显式传入向量（复用项目统一的 embedding 模型），
        而非让 Chroma 内部自动 embedding。
    """

    def __init__(self, persist_dir: str = "./data/chroma_db", collection_name: str = "documents"):
        # PersistentClient：数据落盘到 persist_dir，重启不丢失
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(collection_name)
        self._docs = []  # 内存副本，与 FAISS 接口返回格式一致

    def add(self, vectors, documents, metadatas=None):
        """
        写入向量和文档。

        参数:
          vectors:   list/np.ndarray，shape=(N, dim)
          documents: list[dict]，与 vectors 一一对应（含 text/metadata）
          metadatas: list[dict]（可选），Chroma 原生支持的过滤字段
        """
        # 转成 list（Chroma API 要求）
        embeddings = [v.tolist() if hasattr(v, "tolist") else list(v) for v in vectors]

        ids = [str(i) for i in range(len(self._docs), len(self._docs) + len(documents))]
        texts = [doc["text"] for doc in documents]
        metas = metadatas or [doc.get("metadata", {}) for doc in documents]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metas,
        )
        self._docs.extend(documents)

    def search(self, query_vector, top_k, where=None):
        """
        检索与查询向量最相似的 top_k 个文档。

        参数:
          query_vector: np.ndarray (1, dim) 或 list
          top_k:        返回数量
          where:        可选 metadata 过滤条件（Chroma 特有能力）
                        e.g. {"source": "employee_policy.txt"}

        返回:
          list[dict]，按距离升序（越近越相似）
        """
        # query_vector 是 shape (1, dim) 的数组，转成 list 后是 [[...]]
        # Chroma 的 query_embeddings 期望"查询向量列表"，直接传即可
        if hasattr(query_vector, "tolist"):
            query_vector = query_vector.tolist()
        elif hasattr(query_vector, "__iter__") and not isinstance(query_vector, list):
            query_vector = list(query_vector)

        # 兼容：若传入的是单向量（一维），包成列表
        if query_vector and isinstance(query_vector[0], (int, float)):
            query_vector = [query_vector]

        k = min(top_k, len(self._docs))
        if k == 0:
            return []

        result = self.collection.query(
            query_embeddings=query_vector,
            n_results=k,
            where=where,
        )

        # 解析 Chroma 返回结果
        # result["documents"]: [[text1, text2, ...]]
        # result["metadatas"]: [[{...}, {...}]]
        # result["distances"]: [[0.1, 0.3, ...]]
        docs_texts = result.get("documents", [[]])[0]
        docs_metas = result.get("metadatas", [[]])[0]

        # 与内部 _docs 对齐，返回与 FAISS 一致的 dict 格式
        results = []
        for text, meta in zip(docs_texts, docs_metas):
            results.append({"text": text, "metadata": meta})

        return results

    def count(self) -> int:
        return len(self._docs)
