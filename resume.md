# 求职简历

## 基本信息

- **求职意向**：大模型 / RAG / Agent 方向工程师
- **一句话定位**：能**手写** RAG 全链路与 Agent 工程化（检索、重排、图谱、Multi-Agent、可靠性、可观测），不只是"调平台/调 API"的候选人。

---

## 技术栈总览（对齐 8 周最终技术栈）

### 语言与后端
- **Python**（3.11）/ **FastAPI** / **Docker** / Linux 基础
- 文件上传建库、SSE 流式输出、CORS、静态资源托管（[`app/main.py`](app/main.py)）

### LLM 与 Agent
- **OpenAI API** / **DeepSeek API**（Function Calling / Tool Calling / 流式）
- **LangGraph**（StateGraph / Conditional Edge / SubGraph / Checkpoint / Interrupt）
- **LangChain**（LCEL 轻量编排，[`app/rag/lcel_rag.py`](app/rag/lcel_rag.py)）
- **Agentic-RAG**（Query Rewrite + Self-Reflection 循环，[`app/agent/agentic_rag.py`](app/agent/agentic_rag.py)）
- **Multi-Agent**：Router / Supervisor（[`app/agent/multi_agent_router.py`](app/agent/multi_agent_router.py)、[`app/agent/supervisor_agent.py`](app/agent/supervisor_agent.py)）
- **Human-in-the-Loop** / Checkpoint（[`app/agent/research_agent_hitl.py`](app/agent/research_agent_hitl.py)）

### RAG 检索与排序
- **FAISS** / **Chroma** 双向量库封装（[`app/rag/vector_store/faiss_store.py`](app/rag/vector_store/faiss_store.py)、[`app/rag/vector_store/chroma_store.py`](app/rag/vector_store/chroma_store.py)）
- 混合检索：**BM25（rank_bm25 + jieba） + 向量 → RRF 融合**（[`app/rag/hybrid_retriever.py`](app/rag/hybrid_retriever.py)）
- **Embedding**：BGE（`BAAI/bge-small-zh-v1.5`）
- **Reranker**：Cross-Encoder（`BAAI/bge-reranker-v2-m3`，[`app/rag/reranker_cross_encoder.py`](app/rag/reranker_cross_encoder.py)）
- **GraphRAG**：实体/关系抽取 + NetworkX 图 + BFS 图增强检索（[`app/rag/graph_rag.py`](app/rag/graph_rag.py)）

### 工具与平台
- **MCP**（Model Context Protocol）：Server / Client（[`app/mcp/server.py`](app/mcp/server.py)、[`app/mcp/client.py`](app/mcp/client.py)）
- **Dify** / **Coze**（低代码平台实践）
- **LangFuse**：全链路追踪 + 质量评估（[`app/observability/tracing.py`](app/observability/tracing.py)、[`app/observability/eval.py`](app/observability/eval.py)）

### 工程化
- **可靠性**：指数退避重试 + jitter、熔断器、超时降级、并发任务队列（[`app/agent/reliability.py`](app/agent/reliability.py)）
- **可观测**：追踪（LangFuse ↔ 本地 JSON 双后端降级）+ LLM-as-Judge 三指标评估
- **Harness**：多轮记忆（滑动窗口 + Session 隔离，[`app/memory/memory.py`](app/memory/memory.py)）
- **前沿概念**：Computer Use / GUI Agent

---

## 项目经历（STAR 结构）

---

### 项目一：企业级 RAG Agent 系统（主项目）

**技术栈**：Python / FastAPI / LangGraph / Agentic-RAG / GraphRAG / FAISS / Chroma / BGE / Cross-Encoder / LangFuse / Docker

> **一句话**：基于 LangGraph 构建企业级 RAG Agent，实现混合检索（BM25+向量 RRF）+ Reranker + 多轮记忆 + LangFuse 全链路可观测，FastAPI 整合 12 条路由，Docker 部署。

#### Situation（背景）
企业内部私有知识（规章制度、产品文档）无法被通用大模型直接访问，业务需要一个"回答可溯源、不编造、能上线服务"的知识库问答系统。难点在于：单一向量检索有盲区（专有名词、精确关键词）、LLM 偶发失败会导致服务不可用、回答质量不可见。

#### Task（任务）
从零构建一个企业级 RAG 问答服务：检索要"既懂语义又命中关键词"、生成要"忠实上下文不编造"、服务要"扛得住 LLM 故障"、质量要"可量化可追踪"。

#### Action（做了什么，对应真实代码）
- **手写混合检索**：实现 BM25 关键词检索 + FAISS 向量检索，用 **RRF（Reciprocal Rank Fusion）** 融合两个排序列表，消除 BM25 分数与向量距离尺度不一致的问题，成为可替换旧检索器的 drop-in 实现（[`app/rag/hybrid_retriever.py`](app/rag/hybrid_retriever.py)）。
- **精排升级**：用 Cross-Encoder（`bge-reranker-v2-m3`）替换字符重合度 Reranker，按"粗召回 10 条 → 精排取 3 条"漏斗设计，懒加载模型避免启动卡顿（[`app/rag/reranker_cross_encoder.py`](app/rag/reranker_cross_encoder.py)）。
- **GraphRAG 增强**：从文档做实体/关系抽取，构建 NetworkX 知识图谱，对"哪个部门负责审批年假"这类跨 chunk 关系问答做 BFS 图遍历增强检索（[`app/rag/graph_rag.py`](app/rag/graph_rag.py)）。
- **LangGraph 编排**：用 `StateGraph` + `Conditional Edge` 构建 LLM↔Tool 循环 Agent（[`app/agent/langgraph_agent.py`](app/agent/langgraph_agent.py)），并实现 **Agentic-RAG**：Query Rewrite 改写模糊问题 + Self-Reflection 自评回答质量、不够则自动重新检索（循环上限防失控）（[`app/agent/agentic_rag.py`](app/agent/agentic_rag.py)）。
- **多轮记忆**：滑动窗口对话记忆 + Session 级隔离，不同用户互不串扰（[`app/memory/memory.py`](app/memory/memory.py)、[`app/memory/session_memory.py`](app/memory/session_memory.py)）。
- **可靠性工程**：手写指数退避重试 + 随机抖动（防"惊群"）、熔断器（连续失败快速失败 + 半开探测）、30s 超时降级、asyncio 并发任务队列，用 `_safe_answer` 统一包装所有接口且不污染业务代码（[`app/agent/reliability.py`](app/agent/reliability.py)、[`app/main.py`](app/main.py)）。
- **可观测工程**：接入 LangFuse 追踪（LLM 输入输出/耗时/token、检索命中/耗时），无外网时自动降级本地 JSON 日志；实现 **LLM-as-Judge 三指标评估**（Faithfulness 忠实度 / Answer Relevance 回答相关性 / Context Precision 上下文精准度）定位生成/意图/检索哪个环节出问题（[`app/observability/tracing.py`](app/observability/tracing.py)、[`app/observability/eval.py`](app/observability/eval.py)）。
- **对外服务**：FastAPI 整合 **12 条路由**（对话、流式、上传建库、Supervisor、Router、前端托管等），文件上传即构建知识库，CORS + Vue 前端联调，Docker 一键部署（[`app/main.py`](app/main.py)、[`dockerfile`](dockerfile)）。

#### Result（结果）
- 召回质量：BM25 命中精确关键词 + 向量覆盖同义改写（如"年假几天"与"带薪休假"互补），RRF 融合消除分数尺度差异，精排后 top3 相关性显著提升。
- 可靠性：LLM/网络偶发失败自动重试（1s→2s→4s+jitter），持续故障熔断快速失败，超时 30s 降级兜底，**任何异常不向上抛 500**。
- 可观测：回答质量三指标可量化打分、可写回 LangFuse 形成 feedback loop；服务 12 条路由、配套 20 项测试全过、Docker 可部署。
- **手写亮点**：全程不用重型框架兜底，检索/重排/可靠性/评估均为手写实现。

#### 技术难点 + 解决方式
- **难点**：BM25 分数与 FAISS 距离量纲不同，无法直接加权相加。**解决**：改用 RRF 只看排名不看绝对分值，天然消除尺度差异（[`app/rag/hybrid_retriever.py`](app/rag/hybrid_retriever.py)）。
- **难点**：LLM"偶发失败"与"持续故障"需不同应对。**解决**：重试（抖动错峰）处理偶发，熔断（冷却 + 半开探测）保护持续故障，超时守护线程兜底，三层串联（[`app/agent/reliability.py`](app/agent/reliability.py)）。
- **难点**：无外网 / 未配置 LangFuse 时不能崩。**解决**：双后端自动探测切换（LangFuse ↔ 本地 JSON），评估 LLM 不可用走 2-gram 规则兜底。

#### 预判面试问题
1. 为什么用 RRF 而不是把 BM25 和向量分数加权相加？RRF 的 k 值（60）怎么来的？
2. Cross-Encoder 和 Bi-Encoder 有什么区别？为什么"粗召回 + 精排"是漏斗结构？
3. 重试、熔断、超时三者分别解决什么问题？jitter 的作用是什么？为什么不能只用重试？
4. 怎么判断 RAG 回答是"检索环节"还是"生成环节"出了问题？（答：三指标定位）

---

### 项目二：Research Agent（Multi-Agent 协作系统）

**技术栈**：LangGraph / MCP / Router / Supervisor / HITL

> **亮点**：Planner→Search→Writer 工作流 + Router 意图分流 + Supervisor 可迭代分发 + MCP 工具标准化 + Human-in-the-Loop 审批门。

#### Situation（背景）
单 Agent 无法同时胜任"企业知识库问答"与"外部实时信息检索"两类任务；研究类问题需要"拆解 → 逐条搜索 → 综合写作"多步流程；完全自动执行在低容错场景下风险高。

#### Task（任务）
搭建多 Agent 协作系统：让不同专长的 Agent 分工协作，意图自动分流，Supervisor 可迭代调度并综合结果，同时提供人工审批门保证关键步骤可控。

#### Action（做了什么，对应真实代码）
- **Research 流水线**：用 LangGraph 构建 **Planner→Search→Writer** DAG，Planner 把用户问题拆解为 2-4 个可独立搜索的子问题，Search 逐条搜索汇总，Writer 综合生成报告（[`app/agent/research_agent.py`](app/agent/research_agent.py)）。
- **Router 意图分流**：`intent_node` 用 LLM 判断意图（企业政策 → rag / 外部实时 → research），LLM 失败或输出非法值时回退规则关键词判断，再用 **Conditional Edge + SubGraph** 分发到两个子 Agent（[`app/agent/multi_agent_router.py`](app/agent/multi_agent_router.py)）。
- **Supervisor 可迭代分发**：`supervisor_node` 每轮用 LLM 决策派谁（rag / research / finish），子 Agent 结果通过 `Annotated[list, operator.add]` 自动收集不覆盖，收尾时综合所有结果；用 `rounds / max_rounds` 计数强制收尾防无限循环（[`app/agent/supervisor_agent.py`](app/agent/supervisor_agent.py)）。
- **Human-in-the-Loop 审批门**：在 search 节点前用 `interrupt_before=["search"]` 暂停图，`MemorySaver` 做 Checkpoint，用户确认/修改子问题后用 `update_state` 注入、`invoke(None)` 恢复——实现"图暂停 + 人工决策 + 图恢复"三步（[`app/agent/research_agent_hitl.py`](app/agent/research_agent_hitl.py)）。
- **MCP 工具标准化**：子 Agent 的检索能力通过 MCP Server 独立进程提供，Client 走"握手 → 工具发现 → 工具调用"协议，Agent 与工具彻底解耦（[`app/mcp/server.py`](app/mcp/server.py)、[`app/mcp/client.py`](app/mcp/client.py)）。

#### Result（结果）
- 多 Agent 分工：Router 一次分发 + Supervisor 可迭代分发（对比单一 RAG 只走知识库），企业政策问题走 rag、实时问题走 research，职责清晰。
- 防失控：Supervisor 任意轮次都有 `max_rounds` 兜底，非法 LLM 决策统一回退，**演示永不无限循环**。
- 安全可控：HITL 审批门让"拆解后的子问题"可人工确认/修改后再执行，低容错场景可用。
- 可复用：Research 流水线作为 SubGraph 被 Router 与 Supervisor 复用，模块化程度高。

#### 技术难点 + 解决方式
- **难点**：LLM 决策不可靠（输出非法值 / 调用失败）。**解决**：决策解析容错 + 关键词规则兜底 + 轮次超限强制收尾三层防护（[`app/agent/supervisor_agent.py`](app/agent/supervisor_agent.py)）。
- **难点**：多 Agent 结果互相覆盖。**解决**：用 `operator.add` reducer 让各子 Agent 结果追加进 `messages` 而非覆盖，收尾时综合全部产出。
- **难点**：HITL 如何在图中间暂停与恢复。**解决**：`interrupt_before` + `MemorySaver` Checkpoint + `update_state` 注入修改 + `invoke(None)` 恢复，thread_id 隔离会话（[`app/agent/research_agent_hitl.py`](app/agent/research_agent_hitl.py)）。

#### 预判面试问题
1. Router 和 Supervisor 的核心区别是什么？（一次分发 vs 可迭代分发 + 收集 + 综合）
2. Human-in-the-Loop 是怎么实现的？（interrupt / checkpoint / update_state / resume）
3. 多 Agent 怎么防止无限循环和状态覆盖？（max_rounds / operator.add）
4. 子 Agent 作为 SubGraph 挂载时，状态是怎么在父子图间传递的？

---

### 项目三：MCP 工具标准化实践（工具即插即用）

**技术栈**：MCP 协议 / Skills / ToolRegistry

> **亮点**：把内部工具按 MCP 协议标准化，设计 Skills 演化路径，实现工具即插即用。

#### Situation（背景）
初版 Agent 的工具（如知识库搜索）是硬编码在进程内的（`app/agent/tools.py`），新增/替换工具必须改 Agent 代码，工具与 Agent 强耦合；且"一个搜索"这类原子操作无法承载"检索 + 精排 + 生成"这类完整能力。

#### Task（任务）
把工具从"进程内硬编码"升级为"协议化、可插拔"：Agent 侧零改动即可新增/替换工具，同时设计一条从"原子 Tool"到"能力模块 Skill"的演化路径。

#### Action（做了什么，对应真实代码）
- **MCP Server 封装**：把知识库检索用 `MCPServer` + `@server.tool()` 注册为独立进程运行的标准化工具 `knowledge_search`，客户端通过协议 `tools/list` 发现、`tools/call` 调用（[`app/mcp/server.py`](app/mcp/server.py)）。
- **MCP Client 实现**：用 `stdio_client` + `ClientSession` 走完整"握手 initialize → 工具发现 list_tools → 工具调用 call_tool"流程，用 `sys.executable` 拉起子进程保证同一 venv（[`app/mcp/client.py`](app/mcp/client.py)）。
- **Skill 协议设计**：定义 `Skill` 基类协议（`name / description / input_schema / declares_tools` + `can_handle()` 能力匹配 + `execute()` 执行），实现 `SkillRegistry` 的"注册 → 发现 → 调用"：用 `can_handle(query)` 做能力发现（模糊匹配），区别于 `ToolRegistry.get(name)` 的精确查找（[`app/agent/skill.py`](app/agent/skill.py)）。
- **RAGSkill 落地**：把"混合检索 + LLM 生成"封装为 `rag_skill`，声明依赖 `knowledge_search`，内部惰性构建检索器并在依赖缺失时优雅回退纯向量检索（[`app/agent/skill.py`](app/agent/skill.py)）。

#### Result（结果）
- 工具与 Agent 解耦：Agent 通过协议发现并调用工具，新增/替换工具 Agent 侧零改动，实现"即插即用"。
- 能力抽象：从原子 Tool 演化到可编排的 Skill，Agent 面对新任务可"自我发现可用能力"，而不是写死调用哪个工具。
- 协议标准：对齐 MCP（Model Context Protocol）行业标准，具备对接外部 MCP Server / 被 Dify / Coze 等平台复用的能力。
- **手写亮点**：MCP Server/Client、Skill 协议、能力发现均为手写实现，非只使用平台可视化拖拽。

#### 技术难点 + 解决方式
- **难点**：MCP 2.0 移除了 FastMCP，API 变化。**解决**：按 `MCPServer` 新接口编写，并保留 1.x 切换说明（[`app/mcp/server.py`](app/mcp/server.py)）。
- **难点**：Tool（原子操作）与 Skill（能力模块）边界模糊。**解决**：明确"Tool = 怎么做一个动作 / Skill = 我能解决哪类问题"，用 `can_handle` 自我发现、`declares_tools` 声明内部依赖，形成 Tool → Skill 演化路径。
- **难点**：直接运行脚本时 `app` 包不可见。**解决**：脚本内把项目根目录补进 `sys.path`，保证 `-m` 与直接运行均可导入（[`app/mcp/server.py`](app/mcp/server.py)、[`app/agent/skill.py`](app/agent/skill.py)）。

#### 预判面试问题
1. MCP 的三层架构是什么？客户端调用一个 MCP 工具的完整流程？
2. Tool 和 Skill 的区别？为什么需要"能力发现"（discover）而不是"精确查找"（get）？
3. 如果给这个系统新增一个工具（如发送邮件），需要改动哪些文件？为什么能做到"零改动"？
4. MCP 与 Dify / Coze 这类平台是什么关系？

---

## 关键技能点（手写能力清单，区分"背概念"与"真实现"）

以下能力均为**亲手实现**，可现场手写 / 讲清原理：

- **手写指数退避重试 + jitter**：`delay = base * 2**attempt + random.uniform(0, 0.5)`，能讲清"惊群/雪崩"问题（[`app/agent/reliability.py`](app/agent/reliability.py)）。
- **手写熔断器**：closed / open / half_open 三态状态机 + 半开探测 + 冷却计时（[`app/agent/reliability.py`](app/agent/reliability.py)）。
- **手写 LLM-as-Judge 三指标评估**：Faithfulness / Answer Relevance / Context Precision 提示词 + 2-gram 规则兜底双通道（[`app/observability/eval.py`](app/observability/eval.py)）。
- **手写 RRF 排序融合**：`RRF(doc) = Σ 1/(k + rank_i(doc))`，k=60（[`app/rag/hybrid_retriever.py`](app/rag/hybrid_retriever.py)）。
- **手写 BM25 + jieba 中文分词检索**（[`app/rag/hybrid_retriever.py`](app/rag/hybrid_retriever.py)）。
- **手写 GraphRAG**：实体/关系抽取 + NetworkX 建图 + BFS 图增强检索（[`app/rag/graph_rag.py`](app/rag/graph_rag.py)）。
- **手写 LangGraph 图**：循环图（llm↔tool）、DAG（Planner→Search→Writer）、带循环的 Agentic-RAG、SubGraph（Router / Supervisor）、HITL（interrupt + checkpoint）。
- **手写 MCP Server / Client**：`MCPServer` + `@tool()` + `ClientSession` 三流程（[`app/mcp/server.py`](app/mcp/server.py)、[`app/mcp/client.py`](app/mcp/client.py)）。
- **手写 Skill 协议**：`Skill` 基类 + `SkillRegistry` 注册/发现/调用（[`app/agent/skill.py`](app/agent/skill.py)）。
- **手写双后端可观测降级**：LangFuse ↔ 本地 JSON 日志自动切换，无外网不崩（[`app/observability/tracing.py`](app/observability/tracing.py)）。
- **手写 FAISS / Chroma 向量库封装**（[`app/rag/vector_store/faiss_store.py`](app/rag/vector_store/faiss_store.py)、[`app/rag/vector_store/chroma_store.py`](app/rag/vector_store/chroma_store.py)）。
- **手写 FastAPI 服务整合**：统一可靠性包装 + 可观测接入点 + 12 条路由（[`app/main.py`](app/main.py)）。

---

## 求职优势总结

1. **全链路手写**：从检索、重排、图谱到 Agent 编排、可靠性、可观测，全程手写实现，能讲清"为什么这么做"，区别于只用平台拖拽的候选人。
2. **工程化思维**：不只是"能跑"，还解决了 LLM 失败、无外网降级、无限循环、状态覆盖、多用户并发等真实生产问题。
3. **面试强绑定**：每条简历经历都能"指向文件、讲清原理、手写核心代码"，预判问题均有代码级答案。
