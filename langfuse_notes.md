# Day 1 笔记：LangFuse 接入 —— 让 Agent 从"黑盒"变"玻璃盒"

> 目标：理解 LangFuse = 开源 LLM 可观测平台（类比 LangSmith，但**免费可自托管**），
> 解决"Agent 是黑盒，无法定位回答质量差的原因"这一核心问题，
> 并用 `@observe()` 装饰器（对现有代码侵入最小）把 [`app/llm.py`](app/llm.py:17) 的 `chat` 和
> 混合检索 [`build_hybrid_retriever()`](app/rag/hybrid_retriever.py:260) 接入追踪链路。
>
> ⚠️ 本环境可能无外网：若 `langfuse` 无法安装或连不上云端，**退化为本地版**——
> 用 `@observe()` 打印 JSON 日志 + 手写打分函数，概念与流程完全一致（见「七、降级方案」）。

---

## 一、LangFuse 是什么？解决什么问题？

**LangFuse = 开源 LLM 可观测平台（LLM Observability Platform）**，追踪、调试、评估你的 Agent 系统每次调用。

**解决的核心问题**：Agent 是**黑盒**——用户抱怨"回答不对"，你**无法定位**是哪个环节出了问题：

| 现象 | 可能原因 | 没追踪时怎么排查？ |
|------|---------|-------------------|
| 回答胡说八道 | LLM 硬编（检索没召回内容） | ❌ 只能靠猜 |
| 回答太慢 | LLM 首 token 慢？还是检索慢？ | ❌ 无耗时数据 |
| 成本暴涨 | token 消耗异常？哪个环节狂烧 token？ | ❌ 无消耗数据 |
| 工具没生效 | MCP `knowledge_search` 调用失败/超时？ | ❌ 无调用记录 |

LangFuse 接入后，你能看到**每次请求的完整链路**：LLM 输入/输出、token 数、成本估算、每一步耗时、工具调用参数与结果。**"发生了什么"一目了然**——这是"工程化"与"玩具项目"的分水岭。

> 面试必问：**"你怎么监控 Agent 性能？"** → 答案 = LangFuse 全链路追踪 + 指标看板（Day 2 再加评估打分）。

---

## 二、三层观测点：追踪什么？

LangFuse 把一次 Agent 请求拆成一条 **Trace（整条请求）**，下面挂多个 **Span / Generation（每个环节）**。本项目聚焦三个核心观测点：

| 观测点 | 观测什么 | 怎么观测 | 对应的项目代码 |
|--------|---------|---------|---------------|
| **LLM token 消耗** | 输入/输出 token 数、成本估算、模型名、温度 | `@observe()` 自动记录 `chat` 的入参/出参，LangFuse 按 token 数估算成本 | [`app/llm.py`](app/llm.py:17) 的 `chat` / `chat_with_tools`（openai 客户端返回 `usage` 字段） |
| **工具调用耗时** | 每次工具调用花了几毫秒、参数、返回值、是否成功 | `@observe()` 包住工具函数，自动记录起止时间与输入输出 | MCP `knowledge_search`（[`app/mcp/server.py`](app/mcp/server.py:63)）、[`ToolExecutor`](app/agent/executor.py:13) |
| **检索耗时** | 混合检索各环节耗时：FAISS 向量检索 / BM25 关键词 / RRF 融合 / 重排 | `@observe()` 包住 `retrieve`，可再拆子 span 细化到每个步骤 | [`app/rag/hybrid_retriever.py`](app/rag/hybrid_retriever.py:222) 的 `HybridRetriever.retrieve` |

**关键洞察**：这三个观测点正好对应 RAG 的三个环节——**检索（耗时）→ 生成（token）→ 工具（调用）**。哪个环节掉了，看哪一层的观测数据就能定位。

---

## 三、`@observe()` 装饰器：5 行核心代码 + 隐藏工作

对现有代码**侵入最小**的方案：不改造 [`app/llm.py`](app/llm.py:17) 内部，而是在外面套一层 `@observe()` 包装函数（Day 2 的 [`app/observability/tracing.py`](app/observability/tracing.py) 就长这样）：

```python
# app/observability/tracing.py —— 接入 LangFuse（原生 openai 客户端方案）
from langfuse.decorators import observe

@observe()                                  # ← ① 装饰器，自动记录调用
def llm_chat(messages, **kwargs):
    from app.llm import chat                # ← ② 复用你已有的 LLM 封装
    return chat(messages)                   # ← ③ 输入/输出/token/耗时自动入 trace

@observe()                                  # ← ④ 同样包住检索
def retrieve_with_trace(query, top_k=3):
    from app.rag.hybrid_retriever import build_hybrid_retriever
    retriever = build_hybrid_retriever("data/employee_policy.txt")
    return retriever.retrieve(query, top_k=top_k)   # ← ⑤ 检索耗时自动入 trace
```

### `@observe()` 的"隐藏工作"（你在业务代码里看不到的）

| # | 你写的代码 | 装饰器替你隐藏的工作 |
|---|-----------|---------------------|
| ① | `@observe()` | 创建 Span/Generation，**自动取名**（默认函数名 `llm_chat` / `retrieve_with_trace`）并挂到当前 Trace 上 |
| ② | `from app.llm import chat` | 复用已有封装，**零侵入**——不改 [`app/llm.py`](app/llm.py:17) 一行 |
| ③ | `return chat(messages)` | 捕获**入参**（messages）与**返回值**（回答文本），记录**耗时**；若内部调了 openai，还能自动解析 `usage` → **token 数 / 成本** |
| ④ | `@observe()` | 新建**独立 Span**，与 LLM 的 Generation 平级，共享同一条 Trace |
| ⑤ | `return retriever.retrieve(...)` | 记录检索耗时 + 检索到的文档（可作为后续评估的 context） |

> 一句话：**`@observe()` = "别改我的业务函数，只在外面贴个标签，它自己会记录"。**
> 若你后续想用 LangChain，官方还提供 `LangfuseCallbackHandler` 一键挂到 Agent 上；本项目用原生 openai 客户端，`@observe()` 是最轻量方案。

---

## 四、LangFuse vs LangSmith 对比

| 维度 | LangFuse | LangSmith |
|------|----------|-----------|
| 开源 | ✅ 开源（Apache 2.0） | ❌ 闭源 |
| 自托管 | ✅ 可本地自托管（Docker `langfuse/langfuse`） | ❌ 仅云端 |
| 价格 | 免费（自托管）+ 免费档云端 | 收费（按量/订阅） |
| 数据隐私 | ✅ 数据留在自己服务器 | 数据上云 |
| 核心能力 | Trace + Evaluate（RAG 指标打分） | Trace + Prompt 管理 + Dataset |
| 与 LangChain 集成 | ✅ `LangfuseCallbackHandler` | ✅ 原生集成（LangSmith 出品） |
| 本项目选择 | ✅ **选它**（开源免费可自托管，契合"企业级/私有化"叙事） | 可作为面试对比谈资 |

> 面试话术：**"我选 LangFuse 而不是 LangSmith，因为开源 + 可自托管，企业知识库数据不出内网，符合私有化部署要求。"**

---

## 五、接入步骤（安装 / 配置 / 包装 / 看板）

### ① 安装

```bash
pip install langfuse
```

### ② 配置（注册 LangFuse Cloud 或本地自托管）

- 云端：注册 [cloud.langfuse.com](https://cloud.langfuse.com) 拿 key。
- 自托管：`docker run -d --name langfuse -p 3000:3000 langfuse/langfuse`（本地跑看板）。

在项目 `.env`（与 [`app/config/settings.py`](app/config/settings.py:14) 的 `env_file=".env"` 一致）加三行：

```env
LANGFUSE_PUBLIC_KEY=你的公钥
LANGFUSE_SECRET_KEY=你的私钥
LANGFUSE_HOST=https://cloud.langfuse.com   # 自托管则填 http://localhost:3000
```

> 提示：这些 key 走 `LANGFUSE_*` 标准环境变量，LangFuse SDK 启动时自动读取，**无需手写配置类**（与 `settings.py` 用 pydantic 读 `.env` 是同一套机制）。

### ③ 包装（用 `@observe()` 包住 `chat` 和 `retrieve`）

见「三」的 [`app/observability/tracing.py`](app/observability/tracing.py)，把 [`app/llm.py`](app/llm.py:17) 的 `chat` 和混合检索的 `retrieve` 各包一层即可，**不改原函数一行**。

### ④ 跑真实查询 + 看板观察

跑 3 个真实查询（政策类 / 新闻类 / 混合类），在 LangFuse 看板（Traces 页面）逐个点开：
- **Token 数 / 成本**：LLM 环节的 `usage` 列
- **耗时**：每个 Span 的 `duration` 列（对比 LLM 与检索谁慢）
- **工具调用**：`knowledge_search` / `retrieve` 的入参出参
- **链路**：整条 Trace 的树状图（`用户请求 → LLM → 检索 → LLM → 回答`）

---

## 六、追踪链路示意图

```
┌───────────────────────────────────────────────────────────────┐
│  Trace（整条请求 = 用户的一次提问）                              │
│                                                               │
│  用户请求                                                        │
│    │  @observe() 记录：问题文本（input）                         │
│    ▼                                                          │
│  ┌─────────────────┐                                          │
│  │ LLM ① 生成检索词   │  ← Generation：token 数 / 成本 / 耗时     │
│  │ (app/llm.py chat) │     观测点：LLM token 消耗               │
│  └────────┬────────┘                                          │
│           ▼                                                   │
│  ┌─────────────────┐                                          │
│  │ 检索 retrieve     │  ← Span：FAISS/BM25/RRF/重排 各环节耗时    │
│  │ (hybrid_retriever)│     观测点：检索耗时                       │
│  └────────┬────────┘                                          │
│           ▼                                                   │
│  ┌─────────────────┐                                          │
│  │ 工具调用           │  ← Span：knowledge_search 参数/返回值/耗时 │
│  │ (MCP / Executor) │     观测点：工具调用耗时                    │
│  └────────┬────────┘                                          │
│           ▼                                                   │
│  ┌─────────────────┐                                          │
│  │ LLM ② 生成回答    │  ← Generation：token 数 / 成本 / 耗时       │
│  │ (app/llm.py chat)│     观测点：LLM token 消耗                 │
│  └────────┬────────┘                                          │
│           ▼                                                   │
│  回答                                                          │
│    │  @observe() 记录：回答文本（output）                        │
└───────────────┬───────────────────────────────────────────────┘
                ▼
        LangFuse 看板（指标 / 耗时分布 / 成本趋势）
```

> 排障心法：用户说"回答慢" → 看 Trace 里**哪个 Span 耗时最长**；用户说"回答不对" → 看**检索是否召回**（Day 2 用评估打分）。

---

## 七、降级方案（无外网 / 连不上云端时）

本环境可能无外网，若 `pip install langfuse` 失败或连不上云端，**退化为本地版**，概念与流程完全一致（Week 6 Day 2 用"伪 MCP"验证协议的先例）：

- `@observe()` 的作用 = **打印 JSON 日志**：包装函数里手动 `print(json.dumps({"event": ..., "input": ..., "output": ..., "elapsed_ms": ...}))`，一样能拿到 token / 耗时 / 输入输出。
- 打分函数 = **手写 LLM-as-Judge**（Day 2 的 `score_faithfulness` 等），把分数写进日志，替代 `langfuse.score()`。
- **结论**：即使没有 LangFuse 服务，**"追踪 + 评估"的工程思路完整保留**，只是输出载体从"看板"变成"JSON 日志"。

---

## 八、Day 1 任务自检

- [x] 讲清 LangFuse 是什么 / 解决什么问题（可观测性，Agent 黑盒 → 玻璃盒）
- [x] 三层观测点表格：token 消耗 / 工具耗时 / 检索耗时，各对应项目哪段代码
- [x] `@observe()` 5 行核心代码 + 隐藏工作（零侵入原理）
- [x] LangFuse vs LangSmith 对比（开源免费可自托管）
- [x] 接入步骤：安装 / 配置 / 包装 / 看板
- [x] 追踪链路示意图：`用户请求 → LLM → 检索 → LLM → 回答`，标注每个环节观测点
- [x] 能回答面试题：**"你怎么监控 Agent 性能？"** → 全链路追踪（token/耗时/工具）+ 看板指标（Day 2 加评估打分）

> 下一步（Day 2）：实现 `score_faithfulness` / `score_answer_relevance` / `score_context_precision` 三个打分函数（LLM-as-Judge），把 RAG 质量评估挂到每条 trace 上，建立 feedback loop。
