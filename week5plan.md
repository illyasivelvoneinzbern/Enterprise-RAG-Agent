# 第 5 周：Agentic-RAG + GraphRAG + 向量库 + 平台工具

## 🎯 周目标

> 🥇 第一梯队：RAG 深度 + 🥈 第二梯队：Milvus / Chroma / Dify / Coze

**让你的 RAG 项目从"基础可用"升级到"大厂水准"。** 第 5 周聚焦三大块：

1. **RAG 进阶**：Agentic-RAG（Agent 自主决策检索）+ GraphRAG（知识图谱多跳检索）
2. **工程升级**：向量库从 FAISS 扩展到 Chroma/Milvus，Reranker 从字符重合度升级为 Cross-Encoder
3. **平台工具**：Dify / Coze 低代码实战，理解"我既能手写 RAG Pipeline，也能用 Dify 快速验证想法"

你当前的优势：第 4 周已完成 LangGraph（State/Node/Edge/Checkpoint）、LCEL、混合检索。第 5 周把这些能力应用到 RAG 深度改造上——`research_agent.py` 的 Planner→Search→Writer 模式将成为 Agentic-RAG 的骨架，`vectorstore.py` 的抽象层将成为对接多向量库的入口。

---

## 📅 前半周（Day 1-3）：RAG 深度进阶

### Day 1（周一）：Agentic-RAG 概念 + 实现

**核心概念：** RAG 不只是 Retrieve→Generate 两阶段。Agentic-RAG = Agent **自主决定**"是否需要检索、检索什么、检索多少次"。

| 传统 RAG | Agentic-RAG |
|---------|-------------|
| 固定 Retrieve → Generate | Agent 决策是否检索 |
| 一次检索一次生成 | 可多次检索（迭代） |
| 问题原文直接检索 | Query Rewrite 改写后再检索 |
| 检索结果直接用 | Self-Reflection 判断质量，不够则重检 |

**目标架构（基于你已有的 `research_agent.py` 改造）：**

```
        用户问题: "它的年假是几天？"（前面聊过"带薪休假政策"）
              │
              ▼
   ┌──────────────────┐
   │  Query Rewrite   │  ← 新 Node：结合多轮对话上下文改写模糊问题
   │      Node        │     输出: "公司带薪休假政策中年假的天数规定"
   └──────┬───────────┘
          ▼
   ┌──────────────────┐
   │     Search       │  ← 复用你 Day 6 的 HybridRetriever（BM25 + 向量）
   │      Node        │
   └──────┬───────────┘
          ▼
   ┌──────────────────┐
   │     Generate     │  ← 生成初步回答
   │      Node        │
   └──────┬───────────┘
          ▼ (conditional edge: 质量足够?)
   ┌──────────────────┐   否（重新检索，最多 N 次）   ┌──────────────────┐
   │ Self-Reflection  │ ──────────────────────────→ │     Search       │
   │      Node        │                             │     (重检)       │
   └──────┬───────────┘                             └──────────────────┘
          │ 是
          ▼
        END
```

**关键代码提示：**

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class AgenticRAGState(TypedDict):
    query: str                    # 原始问题
    rewritten_query: str          # Query Rewrite 后的问题
    context: str                  # 检索到的上下文
    answer: str                   # 生成/反思后的答案
    reflection: str               # 反思结果（够不够）
    retry_count: int              # 已重检次数（防止无限循环）

def query_rewrite_node(state):
    # 结合对话历史 + 当前问题，让 LLM 输出改写后的问题
    rewritten = llm(f"结合上下文改写问题，使其独立可检索：{state['query']}")
    return {"rewritten_query": rewritten}

def generate_node(state):
    # 基于改写后的问题检索 + 生成
    ...

def reflection_node(state):
    # 让 LLM 判断 answer 是否完整回答了 query
    # 不够 → 返回 "retry"；足够 → 返回 "accept"
    ...

# 构建图：加入 conditional edge，用 retry_count 限制循环次数
graph = StateGraph(AgenticRAGState)
graph.add_node("rewrite", query_rewrite_node)
graph.add_node("search", search_node)
graph.add_node("generate", generate_node)
graph.add_node("reflect", reflection_node)

graph.add_edge("__start__", "rewrite")
graph.add_edge("rewrite", "search")
graph.add_edge("search", "generate")
graph.add_edge("generate", "reflect")
# 反思通过 → END；不通过且未超限 → 重新检索
graph.add_conditional_edges(
    "reflect",
    lambda s: "search" if s["reflection"] == "retry" and s["retry_count"] < 2 else END,
)
```

**任务：**
1. 复习第 4 周 `research_agent.py` 的 DAG 结构，理解 State 驱动流转
2. 实现 Query Rewrite Node（核心：多轮对话中模糊指代消解）
3. 复用 `hybrid_retriever.py` 作为 Search Node 的检索器
4. 实现 Self-Reflection Node（核心：LLM 自评回答质量，不够则重检）
5. 用 `retry_count` 控制循环上限，防止无限重检

**产出：** `agentic_rag.py` + 测试（对比"模糊问题"在传统 RAG 与 Agentic-RAG 下的回答质量）

---

### Day 2（周二）：GraphRAG 概念 + 知识图谱构建

**核心概念：**

| | 传统 RAG | GraphRAG |
|---|---------|----------|
| 检索单位 | 孤立 chunk（文本片段） | 实体 + 关系（知识图谱） |
| 检索方式 | 向量相似度 | 图遍历（实体关联扩展） |
| 擅长 | 单点事实问答 | 多跳关系问答（"和 X 合作过、又负责 Y 的部门是哪个？"） |

**知识图谱构建流程：**

```
employee_policy.txt 原始文本
      │
      ▼  (LLM 或规则抽取)
实体抽取: "财务部"、"人事部"、"年假"、"15天"、"报销"
      │
      ▼
关系抽取: ("人事部", "负责", "年假审批"), ("年假", "标准", "15天")
      │
      ▼
构建图:  NetworkX Graph
      │
      ▼
图增强检索: 命中一个实体 → 图遍历其 1-2 跳邻居 → 一并作为上下文
```

**关键代码提示：**

```python
import networkx as nx

# 1. 建图：节点 = 实体，边 = 关系
G = nx.Graph()
G.add_node("人事部", type="部门")
G.add_node("年假", type="制度")
G.add_edge("人事部", "年假", relation="负责审批")

# 2. 图增强检索：命中实体后做 BFS 扩展
def graph_enhanced_retrieve(query, top_k=3):
    matched = match_entities_to_query(query, G.nodes)   # 问题中命中的实体
    context = []
    for entity in matched:
        # 取该实体 1-2 跳邻居，作为关联上下文
        for neighbor in nx.bfs_tree(G, entity, depth_limit=2):
            context.append(node_to_text(G, neighbor))
    return context
```

**任务：**
1. 安装 `networkx` 库
2. 从 `data/employee_policy.txt` 抽取实体和关系（可用 LLM 输出 JSON，或先用规则）
3. 用 NetworkX 构建知识图谱，可视化验证
4. 实现"实体命中 → BFS 图遍历 → 关联上下文"的增强检索
5. 对比：同一问题在"纯 chunk 检索"vs"图增强检索"下的召回差异

**产出：** `graph_rag.py` + 知识图谱构建可视化 + 测试

---

### Day 3（周三）：Milvus / Chroma 向量库实战

**核心概念：** 不要只用 FAISS。三种向量库的定位：

| | FAISS | Chroma | Milvus |
|---|-------|--------|--------|
| 定位 | 内存索引库 | 轻量本地向量库 | 企业级分布式向量数据库 |
| 持久化 | ❌ 无（纯内存） | ✅ 本地磁盘 | ✅ 分布式存储 |
| metadata 过滤 | ❌ 弱 | ✅ 原生支持 | ✅ 强大 |
| 分布式/高并发 | ❌ | ❌ | ✅ |
| 适用场景 | 算法实验/小规模 | 本地开发/原型 | 生产/大规模 |

**核心任务：** 抽象一层 `VectorStore` 接口，让 `retriever.py` 不感知底层是 FAISS 还是 Chroma。

**目标架构：**

```python
# 抽象层（接口统一）
class BaseVectorStore:
    def add(self, embeddings, texts, metadatas): ...
    def search(self, query_embedding, top_k): ...

# 三个实现，接口一致，可随时切换
class FaissStore(BaseVectorStore): ...   # 你现有的 vectorstore.py
class ChromaStore(BaseVectorStore): ...  # 基于 chromadb
class MilvusStore(BaseVectorStore): ...  # 基于 pymilvus
```

**Chroma 关键代码提示：**

```python
import chromadb
from chromadb.config import Settings

client = chromadb.PersistentClient(path="./data/chroma_db")  # 本地持久化
collection = client.get_or_create_collection("employee_policy")

# 写入
collection.add(
    ids=[str(i) for i in range(len(texts))],
    documents=texts,
    metadatas=[{"source": "employee_policy.txt"} for _ in texts],
)

# 查询（Chroma 内部自动做 embedding）
results = collection.query(query_texts=[query], n_results=3)
```

**任务：**
1. 安装 `chromadb`（本地优先，无需服务器）和 `pymilvus`（Milvus 可选，可先装依赖理解接口）
2. 定义 `BaseVectorStore` 抽象接口
3. 把现有 `vectorstore.py`（FAISS）包成 `FaissStore` 实现
4. 实现 `ChromaStore`，实现 `add` / `search`
5. 验证：同一数据写入两种 store，检索结果一致性

**产出：** `vector_store/` 抽象层（含 `base.py`、`faiss_store.py`、`chroma_store.py`）+ 切换验证

---

## 📅 后半周（Day 4-7）：精排升级 + 平台实战 + 收尾

### Day 4（周四）：Reranker 模型升级

**核心概念：** 你现有的 [`reranker.py`](app/rag/reranker.py) 是**字符重合度打分**（轻量但效果差）。升级为 **Cross-Encoder 模型**（`BAAI/bge-reranker-v2-m3`），让模型"真正阅读"查询和文档的关系。

| | 字符重合度 Reranker（现有） | Cross-Encoder Reranker（升级） |
|---|---------------------------|-------------------------------|
| 原理 | 字符重叠统计 | Transformer 联合编码 query+doc |
| 速度 | 极快 | 较慢（需 GPU/较长耗时） |
| 精度 | 差（同义词失效） | 好（理解语义） |
| 定位 | 快速粗排 | 精排（top_k 少量文档） |

**关键代码提示：**

```python
from sentence_transformers import CrossEncoder

# CrossEncoder：把 (query, doc) 拼接输入，输出一个相关性分数
reranker = CrossEncoder("BAAI/bge-reranker-v2-m3")

def rerank(query, documents, top_k=3):
    pairs = [(query, doc["text"][:512]) for doc in documents]
    scores = reranker.predict(pairs)                 # 每个 pair 一个分数
    ranked = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in ranked[:top_k]]
```

**任务：**
1. 安装 `sentence-transformers`（如未装）并下载 `BAAI/bge-reranker-v2-m3`
2. 实现 `CrossEncoderReranker`，接口保持与现有 `Reranker.rerank()` 一致（**兼容替换**）
3. 在 `hybrid_retriever.py` 中把 Reranker 换成 CrossEncoder 版本
4. 对比测试：同一批召回结果，字符重合 vs CrossEncoder 的精排顺序差异

**产出：** `reranker_cross_encoder.py` + 精排效果对比

> ⚠️ 提醒：模型首次加载较慢（类似 Day 6 的 bge-small-zh 加载问题），测试时先预热加载，避免误判"卡住"。

---

### Day 5（周五）：Dify 实战

**任务：** 用 [Dify](https://dify.ai/) 搭建一个和你的 RAG Agent **功能等价**的知识库问答应用。

**操作路径（理解低代码平台抽象层次）：**

```
你的手写 RAG Agent                     Dify 等价物
─────────────────                    ─────────────────
Loader / Splitter          →   知识库导入（Dify 自动切分）
Embedding                  →   Dify 内置/可配置 Embedding 模型
VectorStore                →   Dify 托管向量库
Retriever                  →   检索设置（TopK / Score 阈值）
Prompt 模板                →   Prompt 编排界面
RAGAgent.answer()          →   应用发布 → API 调用 / 聊天界面
```

**目标产出笔记：** 记录每个手写组件在 Dify 中对应哪个配置项，形成"手写 RAG ↔ Dify"映射表。

**操作步骤：**
1. 注册/部署 Dify（可用 cloud 版或 Docker 本地部署）
2. 创建知识库 → 上传 `data/employee_policy.txt` → 自动切分向量化
3. 创建聊天助手应用 → 关联知识库 → 配置检索 TopK、提示词
4. 测试问答效果，与你的手写 RAG Agent 对比
5. 记录映射表 + 差异心得

**产出：** `dify_notes.md`（含"手写组件 ↔ Dify 配置项"映射表）

---

### Day 6（周六）：Coze 扣子实战

**任务：** 用 [Coze](https://www.coze.cn/) 搭建一个 **Multi-Agent 客服工作流**。

**核心概念（4 个必懂名词）：**

| 概念 | 说明 | 类比你的代码 |
|------|------|-------------|
| **Bot** | 一个完整的 AI 应用（面向用户的入口） | 你的 FastAPI 应用 |
| **Plugin** | 可复用的能力插件（搜索、天气、数据库等） | 你的 `SearchTool` |
| **Workflow** | 可视化编排的多步流程 | 你的 LangGraph 工作流 |
| **Knowledge** | 知识库（文档向量化） | 你的 FAISS/Chroma |

**Multi-Agent 客服工作流（示例）：**

```
用户问题
   │
   ▼
┌─────────────┐   是 HR 问题    ┌─────────────────┐
│ 意图识别 Agent │ ───────────→ │ 知识库 Agent     │ → 回答
└──────┬──────┘                └─────────────────┘
       │ 非 HR 问题
       ▼
┌─────────────┐
│ 转人工 Agent │ → 转人工/兜底话术
└─────────────┘
```

**任务：**
1. 在 Coze 创建 Bot，理解 4 大核心概念
2. 创建 Knowledge 知识库，导入 `employee_policy.txt`
3. 用 Workflow 编排"意图识别 → 知识库问答 / 转人工"分支
4. 体验 Multi-Agent 模式（多 Agent 协作），理解与 Day 1 手写 LangGraph 的差异

**产出：** `coze_notes.md`（含工作流截图/描述 + 4 大概念理解）

---

### Day 7（周日）：周回顾 + 三角对比表 + 面试准备

**任务：**
1. **代码整理：** 提交本周所有代码到 GitHub（`agentic_rag.py`、`graph_rag.py`、`vector_store/`、`reranker_cross_encoder.py`）
2. **写三角对比表：** Dify vs Coze vs 手写代码，覆盖：开发效率 / 定制深度 / 部署成本 / 适用场景 / 面试价值
3. **面试问答准备：** 重点掌握下方 5 个面试问题

---

## 📝 第 5 周面试必会问题

| 问题 | 参考答案要点 |
|------|-------------|
| **Agentic-RAG 和传统 RAG 区别？** | 传统 RAG 固定 Retrieve→Generate；Agentic-RAG 由 Agent 自主决策检索时机、次数、策略（Query Rewrite / Self-Reflection / 迭代检索） |
| **GraphRAG 解决什么问题？** | 传统 RAG 检索孤立 chunk，丢失实体间关系；GraphRAG 保留知识图谱结构，支持多跳关系问答 |
| **为什么选 Milvus 而不是 FAISS？** | FAISS 是内存索引（无持久化/分布式/无 metadata 过滤）；Milvus 支持分布式、持久化、混合检索、生产级高可用 |
| **Dify 和手写 RAG 各自适用场景？** | Dify 适合快速验证/内部 Demo/低代码迭代；手写代码适合深度定制、高并发、生产级系统（可回答"我两者都做过"） |
| **Chroma vs FAISS vs Milvus？** | Chroma 轻量 + 自带 metadata 过滤，适合本地开发；FAISS 纯向量索引速度快，适合算法实验；Milvus 企业级分布式，适合生产 |

---

## 📊 本周时间分配（按每日 5h × 7 天 = 35h）

| 天 | 重点 | 预估时间 | 变化 |
|----|------|---------|------|
| Day 1 | Agentic-RAG（Query Rewrite + Self-Reflection） | 5h | 手写核心 |
| Day 2 | GraphRAG + NetworkX 知识图谱 | 5h | 手写核心 |
| Day 3 | Chroma / Milvus 向量库对接 | 5h | 工程升级 |
| Day 4 | Cross-Encoder Reranker 升级 | 5h | 模型升级 |
| Day 5 | Dify 实战 | 5h | 低代码平台 |
| Day 6 | Coze Multi-Agent 实战 | 5h | 低代码平台 |
| Day 7 | 回顾 + 三角对比表 + 面试准备 | 5h | 收尾 |

---

## 🔗 本周关键资源

1. [Agentic-RAG 论文（Self-RAG / CRAG）](https://arxiv.org/abs/2310.11511) — 反思式检索概念源头
2. [Microsoft GraphRAG 文档](https://microsoft.github.io/graphrag/) — 工业级 GraphRAG 参考
3. [NetworkX 官方文档](https://networkx.org/documentation/stable/) — 图构建与遍历
4. [Chroma 官方文档](https://docs.trychroma.com/) — 轻量向量库
5. [Milvus 官方文档](https://milvus.io/docs) — 生产级向量库
6. [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) — Cross-Encoder 精排模型
7. [Dify](https://dify.ai/) / [Coze](https://www.coze.cn/) — 低代码平台

---

## ⚠️ 注意事项

- **Agentic-RAG 是本周重点中的重点**：面试高频题，务必能手写 Query Rewrite Node + Self-Reflection Node 的 LangGraph 结构
- Day 2 的实体抽取若用 LLM 太慢/太贵，可先用**规则 + 关键词**抽取，理解流程后再升级
- Day 3 的 Milvus 需要 Docker 部署（`docker compose up milvus`）；若环境受限，先完成 Chroma（本地零配置），Milvus 理解接口即可
- Day 4 模型首次加载慢属正常（如之前 bge-small-zh 卡住问题），先预热再测
- Day 5-6 是低代码平台，**重点是理解抽象层次和对比差异**，不必深究每个配置项
- 手写（Day 1-4）与低代码（Day 5-6）都要做——面试时"既能手写又能用平台"才有区分度
- 每完成一天的代码，当天就 Git commit，保持提交记录清晰
