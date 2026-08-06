# Enterprise-RAG-Agent

基于 FastAPI + FAISS + Embedding + LLM 构建的企业知识库问答 Agent。

该项目实现了从文档加载、文本切分、向量检索到大语言模型生成回答的完整 RAG Pipeline。

---

## 项目介绍

传统 LLM 无法直接理解企业内部私有知识，例如：

* 企业规章制度
* 产品文档
* 技术文档
* 员工手册

本项目通过 RAG（Retrieval Augmented Generation）技术，将企业文档转换为向量知识库，在用户提问时检索相关内容，并结合 LLM 生成准确回答。

---

## 系统架构

```
              User

                |

             FastAPI

                |

           RAG Agent

          /          \

    Retriever        LLM

        |

   Vector Database

        |

    Documents
```

---

## 核心流程

```
Document

↓

Loader

↓

Text Splitter

↓

Embedding

↓

FAISS Vector Store

↓

Retriever

↓

Prompt Augmentation

↓

LLM

↓

Answer + Source
```

---

## 项目功能

* [x] 文档加载
* [x] 文本切分 Chunk
* [x] Embedding向量化
* [x] FAISS向量检索
* [x] RAG问答
* [x] Metadata来源追踪
* [x] 文件上传动态构建知识库

---

## 技术栈

| 技术                   | 用途          |
| -------------------- | ----------- |
| Python               | 后端开发        |
| FastAPI              | API服务       |
| FAISS                | 向量数据库       |
| Sentence Transformer | Embedding模型 |
| DeepSeek API         | LLM生成       |
| Pydantic             | 数据校验        |

---

## API

### 上传知识库

POST

```
/upload
```

上传：

```
employee_policy.txt
```

系统自动：

```
读取文件

↓

切分

↓

Embedding

↓

建立索引
```

---

### 知识问答

POST

```
/rag/chat
```

请求：

```json
{
 "question":"员工有多少年假?"
}
```

返回：

```json
{
 "answer":
 "普通员工一年10天年假",

 "sources":[
 {
  "source":"employee_policy.txt"
 }
 ]
}
```

---

## 项目特点

### 1. 手写RAG Pipeline

没有直接依赖高级RAG框架，实现：

* Chunk
* Embedding
* Retrieval
* Prompt构造

### 2. 向量检索

使用FAISS实现：

```
Query Vector

↓

Similarity Search

↓

Top-K Documents
```

### 3. 企业知识库能力

支持：

* 私有文档问答
* 来源追踪
* 动态知识更新

---

## 启动方式

安装依赖：

```bash
pip install -r requirements.txt
```

配置环境变量：

```
DEEPSEEK_API_KEY=xxx
```

启动：

```bash
uvicorn app.main:app --reload
```

---

## 后续优化方向

* Hybrid Search(BM25 + Vector)
* Rerank模型
* Query Rewrite
* 多轮对话Memory
* Milvus向量数据库
* LangGraph Agent Workflow
