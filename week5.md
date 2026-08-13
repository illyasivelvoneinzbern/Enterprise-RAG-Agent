Agentic-RAG 和传统 RAG 区别？"→ 传统固定 Retrieve→Generate；Agentic 由 Agent 自主决策检索时机/次数，通过 Query Rewrite 处理模糊问题、Self-Reflection 触发重检，并用 retry_count 限循环。
from typing import TypedDict
from langgraph.graph import StateGraph, END

MAX_RETRY = 2

class AgenticRAGState(TypedDict):
    query: str            # 原始问题
    rewritten_query: str  # 改写后问题
    context: str          # 检索上下文
    answer: str           # 回答
    reflection: str       # retry / accept
    retry_count: int      # 重检计数

graph = StateGraph(AgenticRAGState)
graph.add_node("rewrite", query_rewrite_node)
graph.add_node("search", search_node)
graph.add_node("generate", generate_node)
graph.add_node("reflect", reflection_node)
graph.add_edge("__start__", "rewrite")
graph.add_edge("rewrite", "search")
graph.add_edge("search", "generate")
graph.add_edge("generate", "reflect")
graph.add_conditional_edges("reflect", should_retry, {"search": "search", "end": END})
app = graph.compile()
def query_rewrite_node(state):
    prompt = f"结合上下文把问题改写为独立可检索的问题：{state['query']}"
    return {"rewritten_query": chat(prompt).strip()}
def reflection_node(state):
    result = chat(f"判断回答是否充分，输出 accept 或 retry：{state['answer']}")
    return {"reflection": "retry" if "retry" in result.lower() else "accept"}

def should_retry(state):
    if state["reflection"] == "retry" and state["retry_count"] < MAX_RETRY:
        return "search"   # 重检
    return "end"          # 结束
docs = retriever.retrieve(state["rewritten_query"], top_k=3)  # ⭐
Agentic-RAG vs 传统 RAG：传统 RAG 固定 Retrieve→Generate、原文直接检索、只检一次；Agentic-RAG 由 Agent 自主决策检索时机与次数，用 Query Rewrite 消解模糊问题、Self-Reflection 自评质量、不达标自动重检（上限 2 次），实现"检索—生成—反思—再检索"的闭环。
day2:
def extract_entities(text):
    entities = []
    for word in ENTITY_DICT:  # 词典: 部门/制度/时间/文档
        if word in text and word not in entities:
            entities.append(word)
    return entities

def extract_relations(text, entities):
    relations = []
    for sentence in text.split("。"):
        sent_entities = [e for e in entities if e in sentence]
        rel_words = [r for w, r in RELATION_DICT.items() if w in sentence]
        if len(sent_entities) >= 2 and rel_words:
            rel = max(rel_words, key=len)  # 取最长关系词
            relations.append((sent_entities[0], rel, sent_entities[1]))
    return relations
import networkx as nx
G = nx.Graph()
for e in entities:
    G.add_node(e)
for src, rel, dst in relations:
    G.add_edge(src, dst, relation=rel)
def enhanced_retrieve(query, depth=2):
    # 1. 实体命中
    matched = [n for n in G.nodes if n in query]
    if not matched:
        return []
    # 2. BFS 遍历邻居
    results = []
    for entity in matched:
        neighbors = []
        visited = {entity}
        queue = [(entity, 0)]
        while queue:
            node, d = queue.pop(0)
            if d >= depth:
                continue
            for nb in G.neighbors(node):
                if nb not in visited:
                    visited.add(nb)
                    rel = G[node][nb].get("relation", "关联")
                    neighbors.append({"entity": nb, "relation": rel, "depth": d+1})
                    queue.append((nb, d+1))
        results.append({"entity": entity, "neighbors": neighbors})
    return results
GraphRAG 解决什么问题？ 传统 RAG 检索孤立 chunk，丢失实体间关系，答不了多跳问题（"哪个部门负责审批年假？"）；GraphRAG 把实体和关系建成知识图谱，检索时实体命中 + BFS 图遍历找回关联信息，能回答跨 chunk 的多跳关系问题。
day3
class BaseVectorStore(ABC):
    @abstractmethod
    def add(self, vectors, documents, metadatas=None): ...
    @abstractmethod
    def search(self, query_vector, top_k): ...
    def count(self) -> int: ...      # 可选
    def persist(self): ...           # 可选
为什么抽象接口？→ 上层 Retriever 依赖接口而非实现，底层可无缝切换（面向接口编程）
import faiss, numpy as np

class FaissStore(BaseVectorStore):
    def __init__(self, dimension):
        self.index = faiss.IndexFlatL2(dimension)
        self.documents = []

    def add(self, vectors, documents, metadatas=None):
        self.index.add(np.array(vectors).astype("float32"))
        self.documents.extend(documents)

    def search(self, query_vector, top_k):
        k = min(top_k, len(self.documents))
        if k == 0: return []
        _, indexes = self.index.search(
            np.array(query_vector).astype("float32"), k)
        return [self.documents[i] for i in indexes[0] if i != -1]
import chromadb

class ChromaStore(BaseVectorStore):
    def __init__(self, persist_dir):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection("docs")
        self._docs = []

    def add(self, vectors, documents, metadatas=None):
        ids = [str(i) for i in range(len(self._docs), len(self._docs) + len(documents))]
        self.collection.add(
            ids=ids,
            embeddings=[v.tolist() for v in vectors],
            documents=[d["text"] for d in documents],
            metadatas=metadatas or [d.get("metadata", {}) for d in documents])
        self._docs.extend(documents)

    def search(self, query_vector, top_k, where=None):
        result = self.collection.query(
            query_embeddings=query_vector.tolist(),  # ⭐ 已含查询向量
            n_results=min(top_k, len(self._docs)),
            where=where)  # ⭐ metadata 过滤
        ...
PersistentClient 实现持久化（重启不丢）
where= 参数是 Chroma 特有能力（FAISS 做不到）
query_embeddings 不要重复嵌套（实战踩过的坑）
为什么选 Milvus 而不是 FAISS？ FAISS 是内存索引，无持久化、无分布式、metadata 过滤弱；Milvus 支持分布式部署、持久化存储、混合检索，适合生产环境。Chroma vs FAISS vs Milvus？ Chroma 轻量 + 本地持久化 + metadata 过滤，适合开发原型；FAISS 纯向量索引速度快，适合算法实验；Milvus 企业级分布式，适合生产。
pairs = [(query, doc["text"][:512]) for doc in documents]   # 拼接 + 截断
scores = self.model.predict(pairs)                            # 批量打分
scored = sorted(zip(scores, documents), key=lambda x: x[0], reverse=True)
return [doc for _, doc in scored[:top_k]]                     # 取 top_k
你做过重排序吗？效果提升多少？	用 bge-reranker-v2-m3 替换字符重合 Reranker，同一查询"年假"相关文档从"无法区分"变为 0.69/0.28/0.24 分档，不相关文档 0 分
Bi-Encoder 和 Cross-Encoder 区别？	见上面表格 + 漏斗架构话术
为什么重排序只对 top-k 而不对全库？	Cross-Encoder 每次拼接现算，O(N) 且无法预计算，只能对小候选集精排
模型加载很慢怎么办？	懒加载 + 模型缓存（本地缓存 bge-reranker 权重，首次下载后续秒开）
我既能手写完整 Pipeline（Loader→Splitter→Embedding→VectorStore→Hybrid Retriever→Reranker→LLM），也能用 Dify 快速搭一个等价应用验证想法。手写给我深度定制和高性能，Dify 给我快速迭代和可视化——两者我都做过。
Coze 的 Multi-Agent 路由 ≈ 我手写的 LangGraph 条件边（conditional edge）——同一个模式，手写给我精确控制，平台给我快速验证。
你做过 Multi-Agent 吗？"**
- 三种模式：路由 / 编排 / 协作
- 路由模式 = 意图识别 + 条件分发（今天 Coze 实操）