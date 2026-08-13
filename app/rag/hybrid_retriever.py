"""
hybrid_retriever.py — Day 6: 混合检索（BM25 + FAISS + RRF 融合）

你的现有 retriever.py 只做向量检索（语义相似度），但存在盲区：
  - 用户问"年假几天" → 向量能匹配到"带薪年假"相关内容 ✅
  - 用户问"工资什么时候发" → 向量可能漏掉，但 BM25 关键词"工资"+"发"能精确命中 ✅

BM25 + 向量检索互补关系：

           BM25                      向量检索 (FAISS)
     ┌──────────────┐           ┌──────────────────┐
     │ 关键词精确匹配  │           │  语义相似泛化      │
     │ 词频统计       │           │  Embedding 距离    │
     │ 擅长：专有名词  │           │  擅长：同义改写     │
     │ 短板：同义词    │           │  短板：精确关键词   │
     └──────┬───────┘           └────────┬─────────┘
            │                            │
            └──────────┬─────────────────┘
                       ▼
               ┌──────────────┐
               │  RRF 融合     │  ← Reciprocal Rank Fusion
               │  合并排序     │     两个排序列表 → 一个最终排序
               └──────────────┘
                       │
                       ▼
                 final top_k=3

用法（与现有 Retriever 接口兼容）：
    from app.rag.hybrid_retriever import HybridRetriever

    hr = HybridRetriever(vectorstore, documents, model)
    results = hr.retrieve("员工年假几天？", top_k=3)
"""

from rank_bm25 import BM25Okapi
import jieba


# ============================================
# 1. BM25 检索器（关键词精确匹配）
# ============================================

class BM25Retriever:
    """
    基于 BM25 算法的关键词检索器。

    BM25 原理：
      对每个文档中的每个词计算 TF（词频）× IDF（逆文档频率），
      得分 = 词在文档中出现越多、在整个语料中出现越少 → 得分越高。

    为什么能和 FAISS 互补：
      - FAISS 把"年假"和"带薪休假"映射到相近的向量 → 语义泛化
      - BM25 精确匹配"年假"这个词 → 关键词精确
      - 用户问"年假几天"，BM25 直接命中含"年假"的 chunk，
        FAISS 能额外召回含"带薪休假"的近义 chunk
    """

    def __init__(self, documents: list[dict]):
        """
        初始化 BM25 检索器。

        参数:
          documents: 与 FAISS vectorstore 中相同的文档列表
                     [{"text": "...", "metadata": {...}}, ...]

        ⭐ 关键设计：BM25 和 FAISS 共享同一份 documents 列表，
          用相同的索引位置对应相同文档，确保融合时不会错位。
        """
        self.documents = documents

        # jieba 分词 + BM25 建索引
        # 中文必须分词，否则 BM25 会把每个汉字当作一个"词"
        tokenized = [
            list(jieba.cut(doc["text"]))
            for doc in documents
        ]
        self.bm25 = BM25Okapi(tokenized)

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """
        BM25 关键词检索。

        参数:
          query: 查询文本
          top_k: 返回数量

        返回:
          [{"text": "...", "metadata": {...}, "score": 0.85}, ...]
        """
        tokenized_query = list(jieba.cut(query))
        scores = self.bm25.get_scores(tokenized_query)

        # 按分数降序排列，取 top_k
        # enumerate: (index, score) → 按 score 排序
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for idx, score in ranked:
            doc = self.documents[idx].copy()
            doc["score"] = float(score)
            results.append(doc)

        return results


# ============================================
# 2. RRF 融合算法（Reciprocal Rank Fusion）
# ============================================

def rrf_fusion(
    faiss_results: list[dict],
    bm25_results: list[dict],
    k: int = 60,
    final_top_k: int = 3
) -> list[dict]:
    """
    RRF (Reciprocal Rank Fusion) 融合两个排序列表。

    公式: RRF(doc) = Σ 1/(k + rank_i(doc))

    其中:
      - k: 平滑常数，默认 60（防止 rank=1 的文档得分过高）
      - rank_i(doc): 文档在第 i 个排序列表中的排名（从 1 开始）
      - Σ: 对两个列表的得分求和

    举例:
      "年假" 相关文档在 FAISS 中排第 2，在 BM25 中排第 1
      FAISS 得分: 1/(60+2) = 0.0161
      BM25 得分: 1/(60+1) = 0.0164
      RRF 总分:  0.0161 + 0.0164 = 0.0325

      "带薪休假" 相关文档在 FAISS 中排第 1，但 BM25 中没进 top-10（排名视为无穷大，贡献 0）
      FAISS 得分: 1/(60+1) = 0.0164
      BM25 得分: 0（未入榜）
      RRF 总分:  0.0164

      → "年假" 文档得分更高，排在前面 ✅

    为什么用 RRF 而不是简单拼接？
      - FAISS 和 BM25 的分数尺度不同（L2 距离 vs BM25 分数）
      - 不能直接加权相加
      - RRF 只看排名不看绝对分值，天然消除尺度差异

    参数:
      faiss_results: FAISS 向量检索结果列表
      bm25_results: BM25 关键词检索结果列表
      k: RRF 平滑常数（默认 60，来自论文）
      final_top_k: 最终返回数量

    返回:
      融合后排好序的文档列表
    """
    # 用 doc 的 text 内容作为唯一标识（实际生产建议用 doc_id）
    # 这里用 text 前 200 字符做 key
    def _make_key(doc: dict) -> str:
        return doc["text"][:200]

    # 第一步：对所有文档计算 RRF 得分
    scores = {}     # key → RRF 总得分
    doc_map = {}    # key → 原始文档（用于最后返回）

    # 处理 FAISS 结果
    for rank, doc in enumerate(faiss_results, start=1):
        key = _make_key(doc)
        rrf_score = 1.0 / (k + rank)
        scores[key] = scores.get(key, 0) + rrf_score
        if key not in doc_map:
            doc_map[key] = doc

    # 处理 BM25 结果
    for rank, doc in enumerate(bm25_results, start=1):
        key = _make_key(doc)
        rrf_score = 1.0 / (k + rank)
        scores[key] = scores.get(key, 0) + rrf_score
        if key not in doc_map:
            doc_map[key] = doc

    # 第二步：按 RRF 总得分降序排列
    sorted_keys = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    sorted_keys = sorted_keys[:final_top_k]

    # 第三步：构建最终结果
    fused_results = []
    for key in sorted_keys:
        doc = doc_map[key].copy()
        doc["rrf_score"] = round(scores[key], 6)
        fused_results.append(doc)

    return fused_results


# ============================================
# 3. 混合检索器（对外接口兼容现有 Retriever）
# ============================================

class HybridRetriever:
    """
    混合检索器：BM25 + FAISS → RRF 融合。

    接口与现有 app.rag.retriever.Retriever 完全兼容：
      retrieve(query, top_k=3) → list[dict]

    因此可以作为 drop-in replacement：
      旧: retriever = Retriever(store, model, reranker)
      新: retriever = HybridRetriever(store, documents, model, reranker)

    参数:
      vectorstore:  现有的 FAISS VectorStore 实例
      documents:    与 vectorstore 中相同顺序的文档列表
      model:        SentenceTransformer 模型实例
      reranker:     可选的重排序器（同现有 Retriever）
    """

    def __init__(self, vectorstore, documents: list[dict], model, reranker=None):
        self.vectorstore = vectorstore
        self.model = model
        self.reranker = reranker

        # ⭐ 核心：创建 BM25 检索器（与 FAISS 共享同一份 documents）
        self.bm25 = BM25Retriever(documents)

    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        """
        混合检索：FAISS + BM25 → RRF 融合 → 可选重排序。

        流程:
          1. query → model.encode() → FAISS.search(top_k=10)
          2. query → jieba.cut() → BM25.search(top_k=10)
          3. rrf_fusion(FAISS结果, BM25结果, k=60, final_top_k=top_k)
          4. 可选 reranker.rerank()

        参数:
          query: 查询文本
          top_k: 最终返回数量（默认 3）

        返回:
          [{"text": "...", "metadata": {...}, "rrf_score": 0.032, ...}, ...]
        """
        # 步骤 1：FAISS 向量检索（语义相似）
        query_vector = self.model.encode([query])
        faiss_results = self.vectorstore.search(query_vector, top_k=10)

        # 步骤 2：BM25 关键词检索（精确匹配）
        bm25_results = self.bm25.search(query, top_k=10)

        # 步骤 3：RRF 融合
        fused_results = rrf_fusion(faiss_results, bm25_results, k=60, final_top_k=top_k)

        # 步骤 4：可选重排序（复用现有 Reranker）
        if self.reranker and len(fused_results) > 1:
            fused_results = self.reranker.rerank(query, fused_results, top_k)

        return fused_results


# ============================================
# 4. 便捷构建函数（替代 build_knowledge_base）
# ============================================

def build_hybrid_retriever(file_path: str, use_cross_encoder: bool = False) -> HybridRetriever:
    """
    一键构建混合检索器。

    等价于 build_knowledge_base() 但返回 HybridRetriever 而非 Retriever。

    参数:
      file_path:          知识库文件路径
      use_cross_encoder:  True 用 CrossEncoderReranker（bge-reranker-v2-m3，慢但准）
                          False 用旧字符重合 Reranker（默认，保持兼容）

    用法:
      hr = build_hybrid_retriever("data/employee_policy.txt")
      results = hr.retrieve("员工年假几天？")

      # 升级精排（Day 4）:
      hr = build_hybrid_retriever("data/employee_policy.txt", use_cross_encoder=True)
    """
    from app.rag.loader.loader_factory import get_loader
    from app.rag.splitter import split_documents
    from app.rag.embedding import model
    from app.rag.vectorstore import VectorStore
    from app.rag.reranker import Reranker
    from app.rag.reranker_cross_encoder import CrossEncoderReranker

    # 1. 读取 + 切块
    loader = get_loader(file_path)
    documents = loader.load(file_path)
    chunks = split_documents(documents)

    # 2. Embedding + FAISS
    vectors = model.encode([c["text"] for c in chunks])
    store = VectorStore(dimension=len(vectors[0]))
    store.add(vectors, chunks)

    # 3. 构建混合检索器（chunks 同时传给 BM25），可插拔切换重排序器
    reranker = CrossEncoderReranker() if use_cross_encoder else Reranker()
    return HybridRetriever(store, chunks, model, reranker)
