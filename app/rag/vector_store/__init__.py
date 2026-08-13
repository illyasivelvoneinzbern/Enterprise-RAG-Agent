"""
vector_store/ — Day 3: 向量库抽象层

统一 add/search 接口，支持 FAISS / Chroma / Milvus 三种底层切换。

用法（上层 Retriever 只依赖 BaseVectorStore 接口，不感知底层实现）：
    from app.rag.vector_store import FaissStore, ChromaStore

    # 切换底层只需改这一行
    store = FaissStore(dimension=384)     # 内存索引（算法实验）
    store = ChromaStore(persist_dir="./data/chroma_db")  # 本地磁盘（开发）
    # store = MilvusStore(...)            # 分布式（生产）
"""

from app.rag.vector_store.base import BaseVectorStore
from app.rag.vector_store.faiss_store import FaissStore
from app.rag.vector_store.chroma_store import ChromaStore

__all__ = ["BaseVectorStore", "FaissStore", "ChromaStore"]
