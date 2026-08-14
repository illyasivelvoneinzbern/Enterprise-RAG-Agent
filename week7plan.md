# 第 7 周：工程化闭环

## 🎯 周目标

> 🥈 第二梯队：LangFuse 可观测 + 🥉 第三梯队：Harness 概念

前 6 周你已能"手写 RAG Pipeline + Agent（LangGraph / Router / Supervisor）+ MCP 工具标准化"，项目已具备**"能跑"**的能力。第 7 周把它从 demo 升级到**企业级**：可观测（LangFuse 追踪/评估）+ 可靠性（重试/调度/熔断）+ 安全（权限沙箱）。这是"工程化"与"玩具项目"的**分水岭**，也是面试必问的 **"你怎么监控 Agent 性能？"**。

本周核心叙事线：

```
功能实现（前6周）→ 可观测 → 可靠性 → 安全 → 项目整合
  RAG/Agent/MCP   (Day1-2) (Day3-4) (Day5)  (Day6-7)
```

**你当前的基础：**

- 第 4 周：LangGraph Agent（[`langgraph_agent.py`](app/agent/langgraph_agent.py:1)）+ [`ToolRegistry`](app/agent/registry.py:1) + [`research_agent.py`](app/agent/research_agent.py:1)（Planner→Search→Writer）
- 第 5 周：Agentic-RAG + 混合检索 + 重排序 + LCEL（[`agentic_rag.py`](app/agent/agentic_rag.py)、[`lcel_rag.py`](app/rag/lcel_rag.py:1)）
- 第 6 周：MCP 标准化（[`app/mcp/`](app/mcp/server.py:1)）+ Skills（[`skill.py`](app/agent/skill.py:1)）+ Router / Supervisor（[`multi_agent_router.py`](app/agent/multi_agent_router.py:1)、[`supervisor_agent.py`](app/agent/supervisor_agent.py:1)）
- 已有基础：[`ConversationMemory`](app/memory/memory.py:1)（Memory 管理）、[`research_agent_hitl.py`](app/agent/research_agent_hitl.py)（HITL）、`dockerfile`（沙箱基础）

第 7 周把这些组装成"企业级 Agent 系统"，并**用手画出一张完整的架构图**——这是你 8 周学习的**终极面试作品**。

---

## 📅 前半周（Day 1-3）：LangFuse 可观测 + Harness 概念

### Day 1（周一）：LangFuse 接入

**核心概念：** LangFuse = 开源 LLM 可观测平台（类比 LangSmith，但**免费可自托管**）。解决的核心问题：**Agent 是"黑盒"——用户抱怨回答不对，你无法定位是 LLM 的问题、检索的问题还是工具的问题。**

接入后你能追踪每次调用的：
- **LLM token 消耗**（输入/输出 token 数、成本估算）
- **工具调用耗时**（MCP `knowledge_search` 花了几毫秒）
- **检索耗时**（混合检索 + 重排各环节耗时）

> 面试必问：**"你怎么监控 Agent 性能？"** → 答案 = LangFuse 全链路追踪 + 指标看板。

**关键代码提示（用 `@observe()` 装饰器，对现有代码侵入最小）：**

```python
# app/observability/tracing.py —— 接入 LangFuse（原生 openai 客户端方案）
from langfuse.decorators import observe

@observe()
def llm_chat(messages, **kwargs):
    from app.llm import chat          # 复用你已有的 LLM 封装
    return chat(messages)             # @observe 自动记录输入/输出/token/耗时

@observe()
def retrieve_with_trace(query, top_k=3):
    from app.rag.hybrid_retriever import build_hybrid_retriever
    retriever = build_hybrid_retriever("data/employee_policy.txt")
    return retriever.retrieve(query, top_k=top_k)
```

> 若你后续想用 LangChain，官方还提供 `LangfuseCallbackHandler` 一键挂到 Agent 上。本项目用原生 openai 客户端，`@observe()` 装饰器是最轻量方案。

**任务：**
1. 安装 LangFuse（`pip install langfuse`），注册 LangFuse Cloud 或本地自托管（Docker `langfuse/langfuse`）
2. 配置环境变量 `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST`
3. 用 `@observe()` 包装 `app/llm.py` 的 `chat` 和混合检索的 `retrieve`
4. 跑 3 个真实查询（政策类 / 新闻类 / 混合类），在 LangFuse 看板上观察：token 数、耗时、工具调用
5. 画出"追踪链路"示意图：`用户请求 → LLM → 检索 → LLM → 回答`，标注每个环节的观测点

**产出：** `app/observability/tracing.py` + `langfuse_notes.md`（接入步骤 + 看板截图 + 观测点图）

---

### Day 2（周二）：LangFuse Evaluation（RAG 质量自动评估）

**核心概念：** 追踪只能告诉你"发生了什么"，评估才能告诉你"**回答得好不好**"。LangFuse 支持把 RAG 三大指标挂到每次 trace 上，建立 **feedback loop**：

| 指标 | 含义 | 简单判断法 |
|------|------|-----------|
| **Faithfulness（忠实度）** | 回答是否忠于检索到的上下文（有没有胡编） | 回答里的每个事实是否都能在 context 中找到依据 |
| **Answer Relevance（回答相关性）** | 回答是否真的回答了用户问题 | 不看 context 只看"问题 vs 回答"是否对题 |
| **Context Precision（上下文精准度）** | 检索到的上下文是否足够且不多余 | 正确答案是否出现在检索结果靠前的位置 |

> 三个指标对应 RAG 三个环节：**检索（Context Precision）→ 生成（Faithfulness）→ 对齐用户意图（Answer Relevance）**。排查回答质量问题时，先看哪个指标掉了，就能定位是哪个环节出了问题。

**关键代码提示（LLM-as-Judge 手动打分，无需装 ragas）：**

```python
# app/observability/eval.py —— LLM 给 RAG 回答打 Faithfulness 分
from app.llm import chat

FAITHFULNESS_PROMPT = """你是评估员。判断"回答"是否忠于"上下文"。
若回答中的每个事实都能在上下文中找到依据，输出 1；否则输出 0。
上下文：{context}
回答：{answer}
只输出 0 或 1。"""

def score_faithfulness(context: str, answer: str) -> int:
    result = chat(FAITHFULNESS_PROMPT.format(context=context, answer=answer))
    return 1 if "1" in result else 0

# 把分数写回 LangFuse trace
from langfuse import Langfuse
langfuse = Langfuse()
langfuse.score(
    name="faithfulness",
    trace_id=trace_id,          # 来自 @observe 的 trace
    value=score_faithfulness(context, answer),
)
```

**任务：**
1. 实现 `score_faithfulness` / `score_answer_relevance` / `score_context_precision` 三个打分函数（LLM-as-Judge）
2. 跑 5 组问题-回答样本，记录三个指标分数
3. 观察：哪些场景 Faithfulness 掉分？（通常是检索不到内容时 LLM 硬编 → 需要"诚实回答"兜底）
4. 把分数通过 `langfuse.score()` 写回 trace，在看板看评估趋势
5. 思考：评估结果如何反过来优化系统？（feedback loop：低分样本 → 调检索 top_k / 改 prompt）

**产出：** `app/observability/eval.py` + `langfuse_notes.md` 补充"评估指标 + LLM-as-Judge"章节

> ⚠️ 本环境可能无外网：若 `langfuse` 无法安装或连不上云端，**退化为本地版**——用 `@observe()` 打印 JSON 日志 + 手写三个打分函数，概念与流程完全一致（Week 6 Day 2 用"伪 MCP"验证协议的先例）。

---

### Day 3（周三）：Harness 概念体系

**核心概念：** Harness（智能体驾驭工程）= 让 Agent 在**生产环境稳定、安全、可控运行**的基础设施层。完整框架四件套：

```
┌─────────────────────────────────────────────────────┐
│                 Harness（智能体驾驭层）                 │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────┐ │
│  │ Memory 管理 │ │ 权限沙箱    │ │ 任务调度    │ │ 重试 │ │
│  │ 对话/状态   │ │ 安全边界    │ │ 优先级队列  │ │ 退避 │ │
│  └────────────┘ └────────────┘ └────────────┘ └────┘ │
│                    你的 Agent（LLM + Tools）           │
└─────────────────────────────────────────────────────┘
```

| 组件 | 解决什么问题 | 你已有的基础 | 本周动作 |
|------|------------|-------------|---------|
| **Memory 管理** | Agent 记住上下文，不越跑越偏 | ✅ [`ConversationMemory`](app/memory/memory.py:1) + SessionMemory | 回顾即可，不重写 |
| **权限沙箱** | Agent 只能做"允许做的事"，防恶意/误操作 | ✅ HITL（[`research_agent_hitl.py`](app/agent/research_agent_hitl.py)）+ dockerfile | Day 5 深化概念 |
| **任务调度** | 多用户/多任务并发不打架，优先级可控 | ❌ 未实现 | Day 4 实战 `asyncio.Queue` |
| **异常重试** | LLM/网络偶发失败不崩，自动恢复 | ❌ 未实现 | Day 4 实战 exponential backoff |

> **面试核心观点：** Harness 是 Agent 的"基础设施"，如同操作系统之于应用。面试官问"Agent 工程中 Harness 做什么？"——你就答这四个组件 + 每个组件你做了什么。

**任务：**
1. 阅读 [`memory.py`](app/memory/memory.py:1) 和 [`research_agent_hitl.py`](app/agent/research_agent_hitl.py)，确认已有的两个组件
2. 画出上面 Harness 架构图（手画 + 标注每个组件的输入/输出）
3. 为每个组件写"一句话职责 + 你已做的/将做的"对照表
4. 思考：四个组件中，**哪两个是你项目当前最缺、最容易翻车的？**（提示：网络不稳定时 LLM 调用失败怎么办？）

**产出：** `harness_notes.md`（Harness 四件套架构图 + 组件对照表 + 与现有代码的映射）

> 白板架构图是本周面试准备重点——Day 3 画的这张图，Day 7 要能升级成"企业级 Agent 系统全链路架构图"。

---

## 📅 后半周（Day 4-7）：可靠性实战 + 安全 + 项目整合

### Day 4（周四）：异常重试 + 任务调度实战

**核心任务：** 把你的 Agent 从"能跑"升级到"**扛得住**"。三个硬技能：**① 指数退避重试 ② 并发任务队列 ③ 超时熔断降级**。

**关键代码提示（`app/agent/reliability.py`）：**

```python
# ① 指数退避重试（LLM 调用失败自动恢复）
import time, random

def retry_with_backoff(func, max_retries=3, base_delay=1.0):
    """LLM/网络偶发失败自动重试：1s → 2s → 4s（+抖动）"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise                       # 最后失败直接抛，交给上层降级
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(delay)

# ② 并发任务队列（多用户请求排队处理，不再互相阻塞）
import asyncio

class TaskQueue:
    def __init__(self, maxsize=10):
        self.queue = asyncio.Queue(maxsize=maxsize)
        self.worker = asyncio.create_task(self._worker())
    async def submit(self, fn, *args):      # 生产：提交任务
        await self.queue.put((fn, args))
    async def _worker(self):                # 消费：逐个执行
        while True:
            fn, args = await self.queue.get()
            try:
                await fn(*args)
            finally:
                self.queue.task_done()

# ③ 超时熔断降级（超过 30s 返回降级回答，不挂死用户）
async def run_with_timeout(coro, timeout=30, fallback="系统繁忙，请稍后再试。"):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        return fallback
```

**任务：**
1. 实现 `app/agent/reliability.py`：`retry_with_backoff` / `TaskQueue` / `run_with_timeout`
2. 把 `app/llm.py` 的 `chat` 调用包上 `retry_with_backoff`（模拟 LLM 偶发失败）
3. 用 `TaskQueue` 模拟 10 个并发用户请求，验证排队顺序与不阻塞
4. 用 `run_with_timeout` 给 RAG 回答加 30s 超时，超时返回降级话术
5. 写测试：故意让函数抛异常 / 故意 sleep 超 30s，验证重试和降级生效

**产出：** `app/agent/reliability.py` + 测试脚本（`test_reliability.py`）

> 面试追问准备："指数退避为什么要加抖动（jitter）？" → 避免多个请求同时重试形成"惊群"，叠加随机量错开重试时间。

---

### Day 5（周五）：权限沙箱概念

**核心概念：** Agent 越强，越危险。Agent 安全三原则：

| 原则 | 含义 | 你的落地 |
|------|------|---------|
| **① 工具权限最小化** | Agent 只能调用"完成当前任务所需的最小工具集"，不能滥用 | 工具白名单 + 按意图只暴露对应工具（Day 4 Router 已按意图分流） |
| **② 用户审批门（HITL）** | 高风险操作必须人工确认后才执行 | ✅ 已有 [`research_agent_hitl.py`](app/agent/research_agent_hitl.py) |
| **③ 沙箱隔离** | 不可信代码在隔离环境（Docker）运行，无法破坏宿主机 | 项目已有 `dockerfile`，深化理解 |

**关键代码提示（工具白名单 + 审批门概念）：**

```python
# ① 工具权限最小化：白名单注册，未注册工具一律拒绝
ALLOWED_TOOLS = {"knowledge_search", "safe_web_search"}   # 白名单

def call_tool_safe(name: str, args: dict):
    if name not in ALLOWED_TOOLS:
        raise PermissionError(f"工具 {name} 不在白名单，已拦截")
    return execute(name, args)

# ② 用户审批门（HITL）：高风险工具先挂起，等人工确认
PENDING_APPROVAL = {"execute_code", "send_email", "delete_data"}

def call_tool_hitl(name: str, args: dict, approve=None):
    if name in PENDING_APPROVAL:
        if approve is None or not approve():       # 无人确认 → 拒绝
            return "已拦截：该操作需要用户确认"
    return execute(name, args)
```

**任务：**
1. 阅读 [`research_agent_hitl.py`](app/agent/research_agent_hitl.py) 的审批实现，理解 HITL 模式
2. 为你的工具定义"风险分级"：只读工具（检索/查询）→ 直接放行；写操作（发消息/改数据）→ 需审批
3. 实现 `call_tool_safe` 白名单拦截（给 `knowledge_search` 之外的"危险"工具演示被拦）
4. 画一张"Agent 安全边界"图：Agent → 权限层 → 工具，标注三个防线
5. 理解 `dockerfile`：为什么沙箱要在 Docker 里跑（资源隔离 + 进程隔离）

**产出：** `security_notes.md`（安全三原则 + 工具风险分级表 + 安全边界图）

---

### Day 6（周六）：项目整合

**核心任务：** 把第 4-7 周所有改进**整合进 [`app/main.py`](app/main.py:1)（FastAPI）**，形成一个完整的企业级 RAG Agent 服务。

**目标架构（FastAPI 对外暴露的接口）：**

```
                    ┌────────────────── FastAPI ──────────────────┐
                    │  /rag/chat         → RAGAgent（第4周）        │
用户请求 ──HTTP──▶   │  /rag/agent        → LangGraph Agent（第4周）  │
                    │  /rag/supervisor   → Supervisor（第6周）      │
                    │  /upload           → 文档上传 + 重建索引（第4周）│
                    └───────────────────────┬─────────────────────┘
                                            ▼
                    统一加装：reliability（重试/队列/超时）← Day 4
                             observability（LangFuse追踪） ← Day 1-2
```

**任务：**
1. 梳理 Week 4-7 所有新增模块，列出"已在 main.py / 未接入"清单
2. 为每个接口统一加装：`retry_with_backoff` + `run_with_timeout`（Day 4）+ `@observe()` 追踪（Day 1）
3. 新增 `/rag/supervisor` 接口（复用 [`supervisor_agent.py`](app/agent/supervisor_agent.py:1)），暴露 Supervisor 多 Agent 能力
4. 整合后跑一遍完整链路：上传文档 → 检索 → Agent 回答 → 看 LangFuse trace
5. 更新 `README.md`：写清楚服务架构、接口列表、启动方式

**产出：** 整合后的 [`app/main.py`](app/main.py:1) + 更新的 `README.md`

> 这是 8 周工程的"装机时刻"：所有模块从"各自 Demo"变成"一个可对外服务的完整系统"。面试时可直接演示。

---

### Day 7（周日）：周回顾 + 完整架构图

**任务：**
1. **代码整理：** 提交本周所有代码到 GitHub（`app/observability/`、`app/agent/reliability.py`、`harness_notes.md`、`security_notes.md`）
2. **画"企业级 Agent 系统架构图"（本周核心产出）：** 全链路，从外到内：

```
用户 → FastAPI（HTTP 网关）
         │
         ▼
      Router（意图分流，第6周）
         │  ├─→ RAG Agent（LangGraph + 混合检索 + 重排，第4-5周）
         │  └─→ Supervisor（分发 research/RAG 子 Agent，第6周）
         ▼
      MCP Server（knowledge_search 工具标准化，第6周）
         │
         ▼
      Vector Store（Milvus/Chroma + FAISS，第2/4周）
         │
    ════ 横切层（贯穿所有请求）════
    LangFuse 可观测（追踪+评估，本周Day1-2）
    Harness：重试/队列/超时/权限沙箱（本周Day3-5）
```

3. **面试问答准备：** 重点掌握下方 3 个面试问题
4. **写周回顾（必须含"本周必会手写的代码"清单）：** 重试/队列/熔断的骨架代码 + LangFuse `@observe()` 用法 + 安全白名单拦截

**产出：** `week7_review.md`（完整架构图 + 3 面试题精讲 + **本周必会手写的代码** + Git 清单 + 自检清单）

> 这张架构图就是你的**终极面试作品**：从"手写 RAG"到"企业级 Agent 系统"，8 周的所有技术栈都在这张图里串成了一条线。

---

## 📝 第 7 周面试必会问题

| 问题 | 参考答案要点 |
|------|-------------|
| **你怎么监控 Agent 性能？** | LangFuse 全链路追踪：每个 trace 记录 LLM token 消耗、工具调用耗时、检索耗时；再用 RAG 三指标（Faithfulness / Answer Relevance / Context Precision）自动评估回答质量，形成 feedback loop |
| **Agent 工程中 Harness 做什么？** | 智能体驾驭层（基础设施）：① Memory 管理（对话状态，已用 ConversationMemory）② 权限沙箱（工具最小化 + HITL + Docker 隔离）③ 任务调度（asyncio.Queue 并发排队）④ 异常重试（指数退避 + 超时熔断降级） |
| **怎么降低 LLM 调用成本？** | ① 模型路由：简单任务用便宜小模型，复杂任务用强模型 ② 缓存：相同 query 命中缓存不重复调 LLM；embedding 缓存 ③ 减少 context：精简 prompt、只传必要检索片段 ④ 工具调用次数控制（Supervisor 的 max_rounds 防无效循环） |

---

## 📊 本周时间分配（按每日 5h × 7 天 = 35h）

| 天 | 重点 | 预估时间 | 定位 |
|----|------|---------|------|
| Day 1 | LangFuse 接入（@observe 追踪） | 5h | **手写核心** |
| Day 2 | LangFuse Evaluation（三指标 + LLM-as-Judge） | 5h | **手写核心** |
| Day 3 | Harness 概念体系（四件套架构图） | 5h | 概念核心 |
| Day 4 | 异常重试 + 任务调度 + 超时熔断（reliability.py） | 5h | **手写核心** |
| Day 5 | 权限沙箱概念（三原则 + 白名单拦截） | 5h | 概念核心 |
| Day 6 | 项目整合（Week 4-7 全链路进 main.py） | 5h | **整合重点** |
| Day 7 | 周回顾 + 完整架构图 + 面试准备 | 5h | 收尾 |

---

## 🔗 本周关键资源

1. [LangFuse 官方文档](https://langfuse.com/docs) — 接入 / 追踪 / 评估 / 自托管
2. [LangFuse Python SDK](https://github.com/langfuse/langfuse-python) — `@observe()` / `LangfuseCallbackHandler` / `langfuse.score()`
3. [RAGAS 文档](https://docs.ragas.io/) — Faithfulness / Answer Relevance / Context Precision 指标定义（参考，不一定装）
4. [LangChain 可观测性指南](https://docs.langchain.com/ops/) — Agent 监控最佳实践
5. [FastAPI 官方文档](https://fastapi.tiangolo.com/) — 异步接口整合（Day 6）
6. [Docker 官方文档](https://docs.docker.com/) — 沙箱隔离（Day 5 概念）

---

## ⚠️ 注意事项

- **LangFuse 是本周核心中的核心**：面试高频题"怎么监控 Agent 性能"就靠它。务必能手画追踪链路 + 讲清三个评估指标
- **网络受限时退化为本地版**：LangFuse 云连不上就自托管 Docker；连 Docker 也不行就用 `@observe()` 打印 JSON 日志 + 手写 LLM-as-Judge 打分，**概念与流程完全一致**
- Day 3 Harness 是**概念理解为主**：必须能白板画出四件套架构图，但 Day 4 只实现"重试 + 队列 + 超时"三个最关键的
- Day 4 的 exponential backoff 是**面试手撕高频题**：务必能徒手写出重试函数，并讲清"为什么加 jitter"
- Day 5 安全三原则中，**工具权限最小化 + HITL 是你项目真实拥有的**，面试时是加分点（不是只背概念）
- Day 6 整合是**验收时刻**：Week 4-7 所有模块最终汇成一个 FastAPI 服务，务必跑通全链路
- Day 7 的周回顾**必须列出"本周必会手写的代码"**（沿用 Week 6 的反馈要求）：重试/队列/熔断 + LangFuse 接入 + 白名单拦截的骨架代码
- 本周是**"工程化能力"的展示周**：面试官最想听的不是"我调了 API"，而是"我监控了它、重试了它、保护了它"——这三点是区分中级和高级的标尺
