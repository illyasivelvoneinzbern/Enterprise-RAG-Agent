# Enterprise-RAG-Agent

基于 **FastAPI + FAISS + Sentence-Transformers + DeepSeek LLM** 构建的企业级 RAG 知识库问答 Agent，支持 Tool Calling、多轮对话 Memory 和流式输出。

---

## 项目简介

传统 LLM 无法直接访问企业内部私有知识（规章制度、产品文档、技术手册等）。本项目通过 **RAG（Retrieval-Augmented Generation）** 技术，将企业文档向量化存储，在用户提问时自动检索相关内容并生成精准回答。

核心特性：

- ✅ 完整的手写 RAG Pipeline（不含 LangChain 等重型框架依赖）
- ✅ 多格式文档支持（TXT / PDF / Markdown）
- ✅ FAISS 向量检索 + 轻量 Reranker
- ✅ DeepSeek API Tool Calling Agent 架构
- ✅ Session 级别的多轮对话 Memory
- ✅ 流式输出（SSE / Streaming）
- ✅ 文件上传即构建知识库
- ✅ Docker 一键部署

---

## 系统架构

```
                          User
                            │
                        FastAPI
                            │
                     ┌──────┴──────┐
                     │  RAG Agent  │
                     └──────┬──────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
         AgentExecutor  SessionMemory  Retriever
              │                           │
         ToolExecutor              ┌──────┴──────┐
              │                    │             │
        ToolRegistry          VectorStore    Reranker
              │               (FAISS L2)
        ┌─────┴─────┐             │
   knowledge_search  ...     Sentence-Transformers
                             (BGE-small-zh-v1.5)
                                   │
                               Documents
                             (TXT/PDF/MD)
```

---

## RAG Pipeline 数据流

```
  Document (TXT/PDF/MD)
       │
       ▼
  LoaderFactory ─── 根据文件后缀选择 Loader
       │
       ▼
  Text Splitter ─── chunk_size=100, overlap=20
       │
       ▼
  Embedding ─────── BAAI/bge-small-zh-v1.5
       │
       ▼
  FAISS VectorStore ─── IndexFlatL2 索引
       │
       ▼
  Retriever ─────── 向量检索 top_k=10 → Reranker 精排 → top_k=3
       │
       ▼
  Prompt Augmentation ─── 拼接上下文 + 历史对话
       │
       ▼
  DeepSeek LLM ──── Tool Calling / Streaming 生成回答
       │
       ▼
  Answer + Sources
```

---

## 项目结构

```
Enterprise-RAG-Agent/
├── app/
│   ├── main.py                    # FastAPI 入口，路由定义
│   ├── llm.py                     # DeepSeek API 封装（chat / tool_calling / stream）
│   ├── rag_agent.py               # RAG Agent 核心协调层
│   ├── config/
│   │   └── settings.py            # 配置管理（pydantic-settings，.env 文件）
│   ├── rag/
│   │   ├── build_index.py         # 知识库构建入口（编排 Load → Split → Embed → Store）
│   │   ├── embedding.py           # Sentence-Transformers 向量化
│   │   ├── vectorstore.py         # FAISS 向量存储封装
│   │   ├── retriever.py           # 检索器（embedding 检索 + 可选 reranker）
│   │   ├── reranker.py            # 轻量字符重合度重排序
│   │   ├── splitter.py            # 滑动窗口文本切分
│   │   ├── prompt.py              # RAG Prompt 模板构造
│   │   ├── init_db.py             # 旧版初始化脚本（保留参考）
│   │   └── loader/
│   │       ├── base.py            # Loader 抽象基类
│   │       ├── loader_factory.py  # Loader 工厂（按后缀分发）
│   │       ├── txt_loader.py      # TXT 文档加载器
│   │       ├── pdf_loader.py      # PDF 文档加载器（基于 pypdf）
│   │       └── markdown_loader.py # Markdown 文档加载器
│   ├── agent/
│   │   ├── tools.py               # 工具定义（knowledge_search）
│   │   ├── tool_schema.py         # OpenAI Function Calling Schema
│   │   ├── registry.py            # 工具注册中心
│   │   ├── executor.py            # 工具执行器
│   │   └── agent_executor.py      # Agent 执行循环（Tool Calling + 流式）
│   ├── memory/
│   │   ├── memory.py              # 对话 Memory（滑动窗口）
│   │   └── session_memory.py      # Session 级别 Memory 管理器
│   └── utils/
│       └── logger.py              # 日志模块
├── data/
│   └── employee_policy.txt        # 示例企业政策文档
├── dockerfile                     # Docker 构建文件
├── requirements.txt               # Python 依赖
├── test_memory.py                 # Memory 模块测试
├── test_retriever.py              # Retriever 模块测试
└── README.md
```

---

## 技术栈

| 技术                       | 用途                     |
| -------------------------- | ------------------------ |
| Python 3.11                | 后端开发语言             |
| FastAPI                    | HTTP API 服务            |
| Uvicorn                    | ASGI 服务器              |
| FAISS (faiss-cpu)          | 向量相似度检索           |
| Sentence-Transformers      | 文本 Embedding 向量化    |
| BAAI/bge-small-zh-v1.5     | 中文 Embedding 模型      |
| DeepSeek API (OpenAI SDK)  | LLM 生成 & Tool Calling  |
| pypdf                      | PDF 文档解析             |
| Pydantic / pydantic-settings | 数据校验 & 配置管理    |
| python-dotenv              | 环境变量加载             |

---

## 快速开始

### 1. 环境准备

```bash
# Python 3.11+
python --version

# 克隆项目
git clone <your-repo-url>
cd Enterprise-RAG-Agent
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

在项目根目录创建 `.env` 文件：

```env
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MODEL_PROVIDER=deepseek
MODEL_NAME=deepseek-chat
BASE_URL=https://api.deepseek.com
```

### 4. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

服务启动后访问 [http://localhost:8000](http://localhost:8000) 确认运行状态。

### 5. Docker 部署（可选）

```bash
docker build -t enterprise-rag-agent .
docker run -d -p 8000:8000 --env-file .env enterprise-rag-agent
```

---

## API 接口

### 根路径

```http
GET /
```

响应：

```json
{
  "message": "Enterprise RAG Agent Running"
}
```

---

### 上传知识库文档

上传文件后系统自动完成：**加载 → 切分 → Embedding → 建立 FAISS 索引**。

```http
POST /upload
Content-Type: multipart/form-data
```

| 参数 | 类型   | 说明                      |
| ---- | ------ | ------------------------- |
| file | File   | 上传文档（.txt / .pdf / .md） |

示例（curl）：

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@./data/employee_policy.txt"
```

响应：

```json
{
  "filename": "employee_policy.txt"
}
```

---

### RAG 对话问答

```http
POST /rag/chat
Content-Type: application/json
```

请求体：

```json
{
  "session_id": "user-001",
  "question": "员工每年有多少天年假？"
}
```

| 字段       | 类型   | 必填 | 说明                              |
| ---------- | ------ | ---- | --------------------------------- |
| session_id | string | 是   | 会话 ID，同一 session 共享对话历史 |
| question   | string | 是   | 用户提问                          |

响应：

```json
{
  "answer": {
    "answer": "根据公司政策，普通员工每年享有10天带薪年假，高级员工每年享有15天带薪年假。",
    "sources": []
  }
}
```

---

### RAG 流式对话

```http
POST /rag/chat/stream
Content-Type: application/json
```

请求体格式同 `/rag/chat`。响应为 `text/plain` 流式输出，逐 chunk 返回 LLM 生成内容。

---

## 核心模块详解

### 1. 文档加载（Loader）

[`loader_factory.py`](app/rag/loader/loader_factory.py) 根据文件后缀自动选择对应的 Loader：

| 后缀     | Loader            | 依赖            |
| -------- | ----------------- | --------------- |
| `.txt`   | `TxtLoader`       | 内置 `open()`   |
| `.pdf`   | `PdfLoader`       | `pypdf`         |
| `.md`    | `MarkdownLoader`  | 内置 `open()`   |

所有 Loader 返回统一格式：`[{"text": "...", "metadata": {"source": "...", "page": 1}}]`

### 2. 文本切分（Splitter）

[`splitter.py`](app/rag/splitter.py) 使用滑动窗口策略：

- `chunk_size`：100 字符
- `overlap`：20 字符重叠
- 保留原始 metadata（来源、页码）

### 3. Embedding

[`embedding.py`](app/rag/embedding.py) 使用 `BAAI/bge-small-zh-v1.5` 模型，通过 `sentence-transformers` 加载，首次运行会自动下载模型文件。

### 4. 向量存储（VectorStore）

[`vectorstore.py`](app/rag/vectorstore.py) 封装 FAISS `IndexFlatL2`（L2 欧氏距离），支持：

- `add(vectors, documents)` — 批量添加向量及元数据
- `search(query_vector, top_k)` — 相似度检索

### 5. 检索 + 重排序

[`retriever.py`](app/rag/retriever.py) 检索流程：

1. 将 query 向量化（Sentence-Transformers）
2. FAISS 初检 top_k=10
3. [`reranker.py`](app/rag/reranker.py) 基于字符重合度重排序，取 top_k=3

### 6. Agent Tool Calling

[`agent/`](app/agent/) 目录实现了完整的 OpenAI Function Calling Agent 循环：

```
User Question
     │
     ▼
LLM (with tools schema) ─── 判断是否需要调用工具
     │
     ├── 不需要 ──→ 直接生成回答
     │
     └── 需要 ──→ knowledge_search(query)
                    │
                    ▼
              Retriever.retrieve()
                    │
                    ▼
              LLM (结合检索结果生成最终回答)
```

- [`tool_schema.py`](app/agent/tool_schema.py)：定义 `knowledge_search` 工具的 Function Calling Schema
- [`registry.py`](app/agent/registry.py)：工具注册中心
- [`executor.py`](app/agent/executor.py)：根据工具名分发执行
- [`agent_executor.py`](app/agent/agent_executor.py)：编排 LLM 调用 → 工具执行 → 结果反馈 的完整循环，支持普通和流式两种模式

### 7. 多轮对话 Memory

[`memory/`](app/memory/) 实现了 Session 级别的对话管理：

- [`memory.py`](app/memory/memory.py)：`ConversationMemory` 类，滑动窗口保存最近 `max_messages=10` 条消息
- [`session_memory.py`](app/memory/session_memory.py)：`SessionMemoryManager` 类，以 `session_id` 为 key 管理多个独立会话

不同用户的 session 相互隔离，每个 session 内保持多轮对话上下文。

---

## 日志

项目使用 Python `logging` 模块，日志输出至 [`app.log`](app.log)，格式为：

```
2026-01-01 12:00:00,000 - INFO - user query: 员工有多少年假?
2026-01-01 12:00:02,000 - INFO - agent finished cost=2.00s
```

---

## 后续优化方向

- [ ] Hybrid Search（BM25 稀疏检索 + 向量稠密检索）
- [ ] 接入 Cross-Encoder Reranker 模型（如 `bge-reranker-v2-m3`）
- [ ] Query Rewrite（多轮对话中的指代消解与查询改写）
- [ ] 升级至 Milvus / Qdrant 向量数据库（支持大规模数据）
- [ ] LangGraph 工作流编排（多步推理 Agent）
- [ ] 知识库管理 API（删除、更新、列表查询）
- [ ] 前端对话界面

---

## License

MIT
