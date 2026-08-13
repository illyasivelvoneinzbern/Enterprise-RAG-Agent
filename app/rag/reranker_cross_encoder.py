"""
Day 4: Cross-Encoder Reranker（精排）

用 BAAI/bge-reranker-v2-m3 替换旧的字符重合度 Reranker。

对比旧的 app.rag.reranker.Reranker:
  旧: score = len(set(query) & set(text))       # 字符重合，看不懂语义
  新: score = CrossEncoder 对 (query, text) 深度交互打分  # 语义精排

设计要点（面试要会讲）:
  1. Bi-Encoder（召回）: query/doc 分开编码成向量，可离线预计算 → 快但浅
  2. Cross-Encoder（精排）: query 和 doc 拼接一起编码，attention 深度交互 → 慢但准
  3. 所以标准 RAG 流水线是漏斗: 粗召回 100 条 → 精排取 3 条

接口兼容:
  rerank(query, documents, top_k) -> list[dict]  与旧 Reranker 完全一致
  因此 HybridRetriever.retrieve() 第 250 行一行不用改，直接换实例即可。
"""

from sentence_transformers import CrossEncoder


# 模型名（bge-reranker-v2-m3: 多语言 + 多粒度，中文效果好）
DEFAULT_MODEL_NAME = "BAAI/bge-reranker-v2-m3"

# Cross-Encoder 输入拼接后截断长度，防止超长文本导致显存/耗时爆炸
MAX_CHARS = 512


class CrossEncoderReranker:
    """
    Cross-Encoder 重排序器。

    用法（替换旧 Reranker）:
      from app.rag.hybrid_retriever import HybridRetriever
      from app.rag.reranker_cross_encoder import CrossEncoderReranker

      hr = HybridRetriever(store, chunks, model, CrossEncoderReranker())
      results = hr.retrieve("员工年假几天？")
    """

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME):
        # 延迟加载: 模型只在第一次用到时才加载（大模型加载耗时）
        self.model_name = model_name
        self._model = None

    def _get_model(self) -> CrossEncoder:
        """懒加载 CrossEncoder（首次调用时下载/加载模型）。"""
        if self._model is None:
            self._model = CrossEncoder(self.model_name)
        return self._model

    def rerank(self, query: str, documents: list[dict], top_k: int = 3) -> list[dict]:
        """
        对候选文档精排。

        参数:
          query:     查询文本
          documents: 候选文档列表 [{"text": "...", "metadata": {...}, ...}, ...]
          top_k:     精排后返回前几条（默认 3）

        返回:
          按 Cross-Encoder 分数降序排列的 documents（每个附加 rerank_score 字段）
        """
        if not documents:
            return []

        # 1. 构造 (query, doc) 拼接对，截断防超长
        pairs = [(query, doc["text"][:MAX_CHARS]) for doc in documents]

        # 2. CrossEncoder 批量打分（越相关分越高，0~1 或 sigmoid 分数）
        model = self._get_model()
        scores = model.predict(pairs)

        # 3. 分数与文档绑定，降序排序
        scored = [(float(score), doc) for score, doc in zip(scores, documents)]
        scored.sort(key=lambda x: x[0], reverse=True)

        # 4. 取 top_k，附加 rerank_score 便于调试/展示
        results = []
        for score, doc in scored[:top_k]:
            copy = dict(doc)          # 复制避免污染原文档
            copy["rerank_score"] = round(score, 4)
            results.append(copy)

        return results

    def score(self, query: str, text: str) -> float:
        """
        单条打分（兼容旧 Reranker 的 score 方法，便于单条调试）。
        """
        model = self._get_model()
        result = model.predict([(query, text[:MAX_CHARS])])
        return float(result[0])


def build_cross_encoder_reranker(model_name: str = DEFAULT_MODEL_NAME) -> CrossEncoderReranker:
    """便捷构建函数。"""
    return CrossEncoderReranker(model_name=model_name)


def demo_compare_rerankers():
    """
    对比演示: 旧字符重合 Reranker vs 新 CrossEncoder Reranker。

    用同一查询，展示两者排序差异 —— 正是面试题
    "你做过重排序吗？效果提升多少？" 的回答素材。
    """
    from app.rag.reranker import Reranker

    query = "我有几天年假？"
    documents = [
        {"text": "员工享有带薪年假，工作满一年可休 5 天。", "metadata": {"source": "a"}},
        {"text": "年假申请需提前三天在系统提交。", "metadata": {"source": "b"}},
        {"text": "每月 10 号发放上个月工资。", "metadata": {"source": "c"}},
    ]

    print("查询:", query)
    print("-" * 50)

    # 旧: 字符重合
    old = Reranker()
    old_rank = old.rerank(query, documents, top_k=3)
    print("旧 Reranker（字符重合）排序:")
    for i, doc in enumerate(old_rank, 1):
        print(f"  {i}. {doc['text']}")

    print("-" * 50)

    # 新: CrossEncoder
    new = CrossEncoderReranker()
    new_rank = new.rerank(query, documents, top_k=3)
    print("新 CrossEncoderReranker 排序:")
    for i, doc in enumerate(new_rank, 1):
        print(f"  {i}. [score={doc.get('rerank_score')}] {doc['text']}")


if __name__ == "__main__":
    demo_compare_rerankers()
