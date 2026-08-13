# Day 5 笔记：Dify 实战（低代码 RAG）

> 目标：用 [Dify](https://dify.ai/) 搭建一个和手写 RAG Agent **功能等价**的知识库问答应用，
> 理解"平台把哪些脏活累活替我做了"，形成"手写 RAG ↔ Dify"映射表。

## 1. 手写 RAG ↔ Dify 映射表（核心产出）

| 手写组件（我的代码） | 功能 | Dify 等价配置项 |
|---|---|---|
| [`get_loader`](app/rag/loader/loader_factory.py:10) + [`split_documents`](app/rag/splitter.py:1) | 读取文档 + 切块 | 知识库导入（自动分段，可调分段长度/重叠） |
| [`embed_texts`](app/rag/embedding.py:9) | 文本向量化 | 设置中选择 Embedding 模型（内置/可配置） |
| [`BaseVectorStore`](app/rag/vector_store/base.py:1) (FAISS/Chroma) | 向量存储 + 检索 | Dify 托管向量库（无需自建索引） |
| [`HybridRetriever.retrieve`](app/rag/hybrid_retriever.py:222) | 混合检索 + RRF 融合 | 检索设置：TopK / Score 阈值 / 检索模式 |
| [`Reranker`](app/rag/reranker_cross_encoder.py:1) | 精排（Cross-Encoder） | Rerank 模型配置（可选） |
| [`build_prompt`](app/rag/prompt.py:1) | 提示词模板 | Prompt 编排界面（`{{#context#}}` 占位符） |
| [`RAGAgent.answer`](app/rag_agent.py:18) | 生成回答 | 应用发布 → 聊天界面 / API |
| [`main.py`](app/main.py:1) FastAPI `/rag/chat` | 提供 HTTP 接口 | 应用发布后自动生成 API 端点 |

## 2. 操作步骤（已完成打 ✓）

- [ ] **部署 Dify**：Cloud 版 [dify.ai](https://dify.ai/) 或 Docker 本地部署
- [ ] **创建知识库**：上传 `data/employee_policy.txt` → 确认分段 + 向量化完成
- [ ] **创建聊天助手应用**：关联知识库 → 配置检索 TopK=3 → 编写提示词
- [ ] **测试问答**：与手写 RAG Agent 对比（见下方测试清单）
- [ ] **发布应用**：记录 API 端点

### 2.1 Dify 提示词模板（含 `{{#context#}}` 占位符）

在聊天助手应用的"提示词（Prompt）"输入框粘贴：

```text
你是企业知识库助手。

你的任务是根据【知识库资料】回答用户问题。

严格要求：
1. 只能使用下面提供的资料回答。
2. 如果资料中存在答案，必须回答。
3. 不要回答不知道，除非资料完全没有相关信息。

知识库资料:
{{#context#}}

用户问题:
{{#sys.query#}}

请直接回答：
```

**占位符对照**（理解"平台替你做了什么"）：

| Dify 占位符 | 含义 | 等价手写代码 |
|---|---|---|
| `{{#context#}}` | 检索到的知识库内容（自动填充） | [`build_prompt`](app/rag/prompt.py:7) 拼接的 `context` |
| `{{#sys.query#}}` | 用户当前问题 | [`build_prompt`](app/rag/prompt.py:39) 的 `query` |
| `{{#histories#}}` | 历史对话（需开启对话前功能） | [`build_prompt`](app/rag/prompt.py:11) 的 `history` |

**操作步骤**：左侧选模型（需在"设置→模型供应商"配 API Key）→ 粘贴模板 → 保存 →
右侧"添加功能→知识库"选建好的库 → 检索模式 + TopK=3 + Score 阈值 → 调试框测试。

## 3. 对比测试清单（手写 RAG vs Dify）

用同样的 5 个问题分别问手写 RAG Agent 和 Dify 应用，对比回答质量：

| 测试问题 | 标准答案（来自 employee_policy.txt） | 手写 RAG 回答 | Dify 回答 | 差异心得 |
|---|---|---|---|---|
| 普通员工年假几天？ | 10 天（高级员工 15 天） | | | |
| 工资什么时候发？ | 每月 15 日 | | | |
| 病假需要什么材料？ | 医院相关证明 | | | |
| 连续病假超过几天需审批？ | 7 天，部门负责人审批 | | | |
| 入职需要哪些资料？ | 身份证明、学历证明、银行卡信息 | | | |
| 试用期多长？ | 三个月 | | | |

> 手写 RAG Agent 启动方式：`uvicorn app.main:app` 后调 `/rag/chat`，或直接跑 `test_agentic_rag.py` 的 e2e。

## 4. 差异心得（实操后填写）

### 4.1 Dify 帮你省了什么

- （如：不用写 Splitter，自动分段）
- （如：不用管向量库细节，托管）
- （如：自带聊天界面 + 可发布的 API）

### 4.2 手写代码的优势

- （如：检索链路可深度定制 —— 混合检索 + RRF + Cross-Encoder 精排）
- （如：可精确控制每个环节，调试透明）
- （如：不依赖第三方平台，数据自主可控）

### 4.3 Dify 的局限（哪些做不了/做得不够好）

- （如：检索策略是黑盒，RRF 融合细节不可控）
- （如：深度 Agentic 逻辑（Query Rewrite / Self-Reflection）要自己编排）
- （如：高并发/生产级性能、成本，自托管更可控）

## 4.4 实战调试案例：工作流里 context 为空（重点）

**现象**：知识检索正常（score 0.93 命中"普通员工每年享有10天带薪年假。"），
但大模型回答"资料中未提供普通员工年假的天数信息"。

**排查铁证**：查看大模型实际收到的 prompts，`知识库资料:` 后面是**空白**；
API 返回 `prompt_tokens: 103`（≈只有系统提示词长度，说明 context 未注入）。

**根因**：创建的是**工作流/对话流**应用（有节点连线图）。
- 聊天助手的 `{{#context#}}` 是**自动注入**的内置魔法变量
- 工作流的 LLM 节点**没有**这个魔法变量，必须手动用"插入变量"
  引用**知识检索节点的输出**（如 `{{#知识检索节点.result#}}`）
- 没引用 → `{{#context#}}` 渲染为空 → 大模型"看不到"资料

**修复**（二选一）：
1. 工作流：LLM 节点提示词里点"插入变量"→ 选知识检索节点的 `result` 输出
2. 换回聊天助手应用：提示词直接写 `{{#context#}}` + "添加功能→知识库"，自动注入

**排查方法论（面试可复用）**：RAG 答不上来时，先拆"检索"和"注入"两段——
看检索结果有没有命中正确 chunk（召回测试），再看 prompt_tokens 是否太短
（太短 = context 没进提示词），逐段定位。

## 5. 面试话术（背熟）

> "我既能手写完整 RAG Pipeline（Loader→Splitter→Embedding→VectorStore→Hybrid Retriever→Reranker→LLM），
> 也能用 Dify 快速搭一个等价应用验证想法。**手写给我深度定制和高性能，Dify 给我快速迭代和可视化**。"

对应面试题：**"Dify 和手写 RAG 各自适用场景？"**
- Dify 适合：快速验证、内部 Demo、低代码迭代、非工程师协作
- 手写适合：深度定制、高并发、生产级系统、数据自主可控
- 加分点："两者我都做过，知道什么时候该用哪个"
