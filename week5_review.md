# Week 5 周回顾：RAG 深度 + 低代码平台

> 本周目标：从"基础可用"升级到"面试可讲"——手写 Agentic-RAG / GraphRAG / 向量库抽象 / Cross-Encoder 精排，
> 外加 Dify / Coze 低代码实战。核心收获：**"我既能手写完整 RAG Pipeline，也能用平台快速验证"**。

## 1. 本周做了什么（Day 1-7 一览）

| 天 | 内容 | 产出文件 | 验证 |
|----|------|---------|------|
| Day 1 | Agentic-RAG（Query Rewrite + Self-Reflection） | [`app/agent/agentic_rag.py`](app/agent/agentic_rag.py:1) | 6/6 + e2e ✅ |
| Day 2 | GraphRAG + NetworkX 知识图谱 | [`app/rag/graph_rag.py`](app/rag/graph_rag.py:1) | 8/8 ✅ |
| Day 3 | 向量库抽象层（FAISS/Chroma） | [`app/rag/vector_store/`](app/rag/vector_store/base.py:1) | 6/6 ✅ |
| Day 4 | Cross-Encoder Reranker 升级 | [`app/rag/reranker_cross_encoder.py`](app/rag/reranker_cross_encoder.py:1) | 8/8 ✅ |
| Day 5 | Dify 实战（含 context 为空调试） | [`dify_notes.md`](dify_notes.md:1) | ✅ |
| Day 6 | Coze Multi-Agent 实战 | [`coze_notes.md`](coze_notes.md:1) | 实操中 |
| Day 7 | 周回顾 + 三角对比表 + 面试准备 | 本文件 | ✅ |

## 2. 三角对比表：Dify vs Coze vs 手写代码（核心产出）

| 维度 | 手写代码（LangGraph/FAISS/...） | Dify | Coze（扣子） |
|------|-------------------------------|------|-------------|
| **开发效率** | 低（要写代码+调试） | 高（可视化，分钟级出 Demo） | 高（Bot/插件生态丰富） |
| **定制深度** | 极高（每个环节可精确控制） | 中（检索是黑盒，RRF 不可控） | 中（Multi-Agent 编排可视化） |
| **部署成本** | 自建（服务器/向量库/模型） | 低（云版免部署/Docker 自托管） | 低（云平台托管） |
| **适用场景** | 高并发/生产级/深度定制/数据自主 | 快速验证/内部 Demo/低代码迭代 | Bot 应用/客服/插件生态 |
| **面试价值** | 最高（展示原理和工程能力） | 中（展示工具广度和抽象理解） | 中（展示 Multi-Agent 理解） |
| **核心能力** | Hybrid Retriever+RRF+Cross-Encoder+RAG 全链路 | 知识库问答/RAG 应用 | Multi-Agent/插件/多轮客服 |

**一句话总结**：
- **手写** = 深度（能讲清每个环节原理，面试区分度最高）
- **Dify** = RAG 快速验证（知识库问答）
- **Coze** = Multi-Agent 快速验证（客服/Bot 分流）

**面试话术**："三者我都做过。手写给我精确控制和性能，Dify 给我 RAG 快速验证，Coze 给我 Multi-Agent 快速验证——我知道什么场景该用什么。"

## 3. 第 5 周面试必会问题（精讲）

### Q1. Agentic-RAG 和传统 RAG 区别？

| | 传统 RAG | Agentic-RAG |
|---|---|---|
| 流程 | 固定 Retrieve → Generate | Agent 自主决策检索时机/次数/策略 |
| 典型能力 | 一次性检索 | Query Rewrite / Self-Reflection / 迭代检索 |
| 我的实现 | [`lcel_rag.py`](app/rag/lcel_rag.py:1) | [`agentic_rag.py`](app/agent/agentic_rag.py:1)（rewrite→search→generate→reflect，`should_retry` 循环 + MAX_RETRY=2） |

### Q2. GraphRAG 解决什么问题？

- 传统 RAG 检索**孤立 chunk**，丢失实体间关系 → 无法回答多跳问题（"哪个部门负责审批超过 7 天的病假？"）
- GraphRAG 先抽实体+关系建图（NetworkX），再 **BFS 图遍历**增强检索
- 我的实现：[`graph_rag.py`](app/rag/graph_rag.py:1)（`_bfs_neighbors` + 深度限制 + visited 去重）

### Q3. 为什么选 Milvus 而不是 FAISS？

| | FAISS | Milvus |
|---|---|---|
| 存储 | 内存索引 | 持久化 |
| 扩展性 | 单机 | 分布式 |
| 过滤 | 无 metadata 过滤 | 支持 metadata 过滤 + 混合检索 |
| 生产 | 实验/算法验证 | 生产级高可用 |

### Q4. Dify 和手写 RAG 各自适用场景？

- **Dify**：快速验证 / 内部 Demo / 低代码迭代 / 非工程师协作
- **手写**：深度定制 / 高并发 / 生产级 / 数据自主可控
- **加分点**："两者我都做过"（Day 5 实际踩过 context 为空的坑，知道排查方法）

### Q5. Chroma vs FAISS vs Milvus？

- **Chroma**：轻量 + 自带 metadata 过滤 + 持久化，适合本地开发（Day 3 已实现 [`chroma_store.py`](app/rag/vector_store/chroma_store.py:1)）
- **FAISS**：纯向量索引，速度快，适合算法实验（内存型，无过滤）
- **Milvus**：企业级分布式，适合生产

## 4. 本周代码整理清单（Git 提交）

```bash
# 本周新增/修改的核心文件
git add app/agent/agentic_rag.py        # Day 1
git add app/rag/graph_rag.py            # Day 2
git add app/rag/vector_store/           # Day 3
git add app/rag/reranker_cross_encoder.py  # Day 4
git add test_agentic_rag.py test_graph_rag.py test_vector_store.py test_reranker_cross_encoder.py
git add dify_notes.md coze_notes.md week5_review.md
git commit -m "Week 5: Agentic-RAG + GraphRAG + 向量库抽象 + CrossEncoder精排 + Dify/Coze实战"
```

## 5. 本周关键收获（自我复盘）

- [ ] 能手写 Agentic-RAG 的 LangGraph 结构（State + Query Rewrite Node + Reflection + should_retry）
- [ ] 能手写 GraphRAG 的实体/关系抽取 + NetworkX 建图 + BFS 检索
- [ ] 理解向量库抽象层（BaseVectorStore → FAISS/Chroma 可插拔切换）
- [ ] 理解 Bi-Encoder（召回）vs Cross-Encoder（精排）漏斗架构
- [ ] 理解 Dify `{{#context#}}` 注入机制 + 工作流/聊天助手区别
- [ ] 理解 Coze Multi-Agent 路由模式 ≈ LangGraph 条件边
- [ ] 能讲清 Dify vs Coze vs 手写代码的适用场景
