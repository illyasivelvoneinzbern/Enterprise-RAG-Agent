# 第 8 周：前沿方向 + 求职冲刺

## 🎯 周目标

> 🥉 第三梯队：Computer Use（GUI 智能体）+ 简历/面试

前 7 周你已完成从"手写 RAG"到"企业级 Agent 系统"的完整闭环：RAG Pipeline（[`app/rag/`](app/rag/vector_store/base.py:1)）→ LangGraph Agent → Agentic-RAG + 混合检索 + Reranker → MCP + Multi-Agent → LangFuse 可观测 + Harness 可靠性/安全（[`app/main.py`](app/main.py:1) 已整合 12 条 FastAPI 路由）。项目已具备**"能面试"**的实力。第 8 周是**收官周**，做两件事：**① 打开眼界**（Computer Use 前沿方向，只讲概念不写代码）**② 把 8 周成果变成可讲的面试作品**（简历 / README / 模拟面试）。

本周核心叙事线：

```
打开眼界 → 成果外化 → 面试闭环
 Computer Use  简历/README   模拟面试
 (Day1-2)      (Day3-4)      (Day5-7)
```

**你当前的基础（前 7 周衔接）：**
- 第 4 周：手写 RAG Pipeline（加载/切分/embedding/FAISS+Chroma）+ LangGraph Agent + [`ToolRegistry`](app/agent/registry.py:1)
- 第 5 周：Agentic-RAG + 混合检索（BM25+向量 RRF）+ Reranker + LCEL + HITL
- 第 6 周：MCP 标准化 + Skills + Multi-Agent（Router / Supervisor）
- 第 7 周：LangFuse 可观测 + Harness 可靠性/安全 + 项目整合（12 条 FastAPI 路由）
- 已备作品：`week4-7` 周回顾 + 可演示的完整 FastAPI 服务

**本周核心产出物：** `week8plan.md`（本计划）、`computer_use_notes.md`、`resume.md`、`README.md`（精修版）、`interview_questions.md`（题库）、`week8_review.md`（收官周回顾 + 最终版技术栈）。

---

## 📅 前半周（Day 1-2）：前沿方向 Computer Use（Ask 模式，概念为主）

> 这两天**只讲概念、不写业务代码**，模式分工全部走 **Ask 模式**（论文速览 / 原理讲解），最多在 Day 2 结尾写一个几行的"认知梳理 md"。不涉及 `app/` 代码改动。

### Day 1（周一）：Computer Use 概念 — Ask 模式

**核心概念：** GUI Agent（计算机使用智能体）让 LLM 直接"操作电脑界面"，工作闭环：

```
截图 → 视觉模型理解界面 → 输出操作指令（点击/输入/滚动/键盘）→ 执行 → 再截图
```

**三要素（与你的 RAG/Agent 知识对照）：**
| GUI Agent 要素 | 说明 | 与你已有知识的关联 |
|---------------|------|------------------|
| **视觉理解** | 多模态模型把"像素"变成"界面语义"（按钮/输入框/列表） | 类比你的 embedding 把文本变成向量 |
| **动作空间** | 定义 Agent 能做的原子操作（click / type / scroll / press） | 类比你的 MCP Tool Schema（[`tool_schema.py`](app/agent/tool_schema.py:1)）——**动作空间 = 工具的另一种形态** |
| **记忆** | 跨步骤记住"点过哪里、进行到哪一步"（状态/截图历史） | 类比你的 [`ConversationMemory`](app/memory/memory.py:1) + LangGraph Checkpoint |

**需了解的代表项目：** Claude Computer Use（Anthropic）、OpenAI Operator、UFO（微软）。

**局限（面试关键）：** 视觉理解准确率有限、操作不可靠（需要 self-correct 循环）、安全风险高（Agent 操控真实桌面）、执行速度慢。

**任务：**
1. 用 Ask 模式让 AI 讲解 GUI Agent 工作闭环 + 三要素，画出闭环图
2. 了解 Claude Computer Use / OpenAI Operator / UFO 三个项目各一句定位
3. 思考连线题：**MCP 工具调用 vs GUI 动作空间** 的异同（都定义"Agent 能做什么"，区别是文本参数 vs 屏幕坐标/像素）
4. 产出 `computer_use_notes.md`：闭环图 + 三要素对照表 + 局限清单

**产出：** `computer_use_notes.md`（概念日产出文档）｜模式：Ask

> 💡 面试话术模板："Computer Use 本质是把 Agent 的动作空间从'文本工具调用'扩展到'屏幕操作'，三要素是视觉理解、动作空间、记忆。"

---

### Day 2（周二）：Computer Use 前沿论文速览 — Ask 模式

**核心概念：** 用论文架构图补全三要素的工程化细节。**不用细读公式，看懂"架构图 + 三要素 + 创新点"即可。**

| 论文/项目 | 一句话定位 | 对应三要素 |
|-----------|-----------|-----------|
| OS-Copilot | 提出 FRIDAY，把操作系统变成可交互环境，含自建"能力库"（generalist→specialist 演化） | 动作空间 + 记忆（能力库） |
| UFO | 聚焦 Windows 应用操作，双智能体：AppAgent（决策）+ ActionAgent（生成操作），UI 元素直接交互 | 视觉理解 + 多 Agent 分工 |
| CogAgent | 180 亿参数视觉语言模型，可理解 GUI 截图并定位点击坐标 | 视觉理解（模型侧） |

**任务：**
1. 用 Ask 模式让 AI 逐一讲解三篇论文的架构图（每篇 3 步：解决了什么问题 / 架构图长什么样 / 三要素如何体现）
2. 对比"UFO 双 Agent 分工"与你的 [`supervisor_agent.py`](app/agent/supervisor_agent.py:1) / Router 模式——**你会发现 Multi-Agent 思想是通用的**（决策 Agent 分发 + 执行 Agent 干活）
3. 提炼"Computer Use 想做好需要什么"：视觉模型 + 可靠动作执行 + 错误恢复 + 安全边界（呼应 Week 7 的 Harness/安全）
4. 在 `computer_use_notes.md` 补"论文速览 + 与 Multi-Agent/Harness 的呼应"章节

**产出：** `computer_use_notes.md` 补充章节｜模式：Ask

> 连接点：这一天的真正价值不是"了解 GUI"，而是**用前沿论文反刍你已经会的 Multi-Agent / Harness / MCP 概念**——面试时能"向上兼容"聊前沿。

---

## 📅 后半周（Day 3-7）：求职冲刺（产出文件为主，混合模式）

> Day 3-7 从"学"转向"**卖**"：把 8 周工程变成简历、README、面试题库。Code 模式负责产出/精修文件，Ask 模式负责模拟面试与题目讲解。

### Day 3（周三）：简历包装 — Code 模式（产出 `resume.md`）

**核心任务：** 把 8 周项目浓缩成 3 条简历 STAR 描述。

**简历项目骨架（对齐 [`计划.md`](计划.md:199) 最终技术栈）：**

1. **企业级 RAG Agent 系统**（主项目）
   - 技术栈：Python / FastAPI / LangGraph / Agentic-RAG / GraphRAG / FAISS / Chroma / BGE / Cross-Encoder / LangFuse / Docker
   - 一句话："基于 LangGraph 构建企业级 RAG Agent，实现混合检索（BM25+向量 RRF）+ Reranker + 多轮记忆 + LangFuse 全链路可观测，FastAPI 整合 12 条路由，Docker 部署"
2. **Research Agent（Multi-Agent）**
   - 技术栈：LangGraph / MCP / Router / Supervisor / HITL
   - 亮点："Planner→Search→Writer 工作流 + Router 意图分流 + Supervisor 分发 + MCP 工具标准化 + Human-in-the-Loop 审批门"
3. **MCP 工具标准化实践**
   - 技术栈：MCP 协议 / Skills / ToolRegistry
   - 亮点："把内部工具按 MCP 协议标准化，设计 Skills 演化路径，实现工具即插即用"

**任务：**
1. 用 Code 模式按"STAR 结构"起草 `resume.md`：Situation / Task / Action / Result，**每个 Action 必须能对应到真实代码文件**（链接式描述）
2. 为每个项目写 1-2 行"技术难点 + 你怎么解决的"（例：混合检索如何融合 → RRF 排序融合）
3. 按 [`计划.md`](计划.md:199) 的"最终技术栈"清单核对简历关键词覆盖，缺的补上
4. 反推"面试官会针对这条简历问什么"——每个项目下写 2-3 个预判问题

**产出：** `resume.md`｜模式：Code

---

### Day 4（周四）：GitHub README 精修 — Code 模式

**核心任务：** 把 [`README.md`](README.md:1) 从"能用"精修成"面试作品级"。

**README 必须包含的 6 块：**
1. **架构图（mermaid）**：`用户 → FastAPI → Router → Supervisor → RAG Agent → MCP → VectorStore` + 横切 LangFuse / Harness（沿用 Week 7 画的全链路图）
2. **技术栈**：按 [`计划.md`](计划.md:199) 的"最终技术栈"分类列出
3. **核心难点**：混合检索 RRF、Reranker 重排、多 Agent 分工、HITL 审批、可靠性重试
4. **优化方案**：向量库演进（FAISS→Chroma→Milvus）、成本优化（模型路由/缓存，Week 7 面试题）
5. **Demo 截图/示例**：至少 1 个真实查询输出（政策类 / 新闻类 / 混合类）
6. **快速启动**：venv + `pip install -r requirements.txt` + 启动 FastAPI + 环境变量清单

**任务：**
1. 用 Code 模式重写 [`README.md`](README.md:1)，先补 mermaid 架构图（这是灵魂）
2. 逐条核对 6 块是否齐全，缺失的补
3. 写"项目亮点 3 条"放 README 顶部（面试官第一屏看到的就是它）
4. 顺带检查 [`requirements.txt`](requirements.txt:1) 与启动文档是否一致

**产出：** 精修后的 `README.md`｜模式：Code

> 提示：README 是"面试官在 GitHub 上对你的第一印象"，宁可少而精，不要堆砌。

---

### Day 5（周五）：面试模拟 Day 1 — RAG 专题（Ask 模式为主）

**核心任务：** RAG 全专题口述过关。**每道题做到：能讲原理 → 能画图 → 能连到自己的代码。**

**RAG 专题题库（对齐 Week 4-5 内容）：**
| 题目 | 要点 | 对应代码 |
|------|------|---------|
| 怎么分块（chunk）？有哪些策略 | 固定/滑动窗口/语义切分；chunk 大小与 overlap 权衡 | [`splitter.py`](app/rag/splitter.py:1) |
| embedding 怎么选？为什么 | BGE 中文优势；维度/相似度度量选择 | [`embedding.py`](app/rag/embedding.py:1) |
| 为什么用 rerank？怎么做 | 先召回 top-50 再精排 top-3；Cross-Encoder | [`reranker_cross_encoder.py`](app/rag/reranker_cross_encoder.py:1) |
| 混合检索怎么融合 | BM25+向量 → RRF 排序融合 | [`hybrid_retriever.py`](app/rag/hybrid_retriever.py:1) |
| Agentic-RAG 是什么 | 检索失败→改写/重检索/多跳，Agent 决策检索 | [`agentic_rag.py`](app/agent/agentic_rag.py:1) |
| GraphRAG 解决什么 | 实体关系图谱、全局性问题、多跳推理 | [`graph_rag.py`](app/rag/graph_rag.py:1) |

**任务：**
1. 用 Ask 模式，让 AI 按"原理 → 图 → 代码"三件套逐题模拟提问，你口述作答
2. 每答完一题，确认能否**指向对应代码文件**说出实现（这是"真会"与"背会"的分界）
3. 挑 1 题（推荐"混合检索怎么融合"）写进 `interview_questions.md` 的精讲区

**产出：** `interview_questions.md`（RAG 专题章节）｜模式：Ask 为主

---

### Day 6（周六）：面试模拟 Day 2 — Agent 专题（Ask 模式为主）

**核心任务：** Agent / 工程化全专题口述过关，**重点复述 Week 7 三题**。

**Agent 专题题库（对齐 Week 6-7 内容）：**
| 题目 | 要点 | 对应代码 |
|------|------|---------|
| LangGraph 是什么？怎么用 | 状态机 + 图工作流 + Checkpoint | [`langgraph_agent.py`](app/agent/langgraph_agent.py:1) |
| MCP 解决什么问题 | 工具协议标准化，工具即插即用 | [`app/mcp/`](app/mcp/server.py:1) |
| Multi-Agent 有哪些模式 | Router 分流 / Supervisor 分发 / 对比 | [`multi_agent_router.py`](app/agent/multi_agent_router.py:1)、[`supervisor_agent.py`](app/agent/supervisor_agent.py:1) |
| 怎么监控 Agent 性能（Week 7） | LangFuse 追踪 + RAG 三指标评估 | [`app/observability/`](app/observability/tracing.py:1) |
| Harness 做什么（Week 7） | Memory / 权限沙箱 / 任务调度 / 异常重试 | [`app/agent/reliability.py`](app/agent/reliability.py:1) |
| 怎么降低 LLM 成本（Week 7） | 模型路由 / 缓存 / 减 context / 工具次数控制 | [`multi_agent_router.py`](app/agent/multi_agent_router.py:1) |

**任务：**
1. 用 Ask 模式模拟提问（同上三件套）
2. **Week 7 三题必须能脱离笔记口述**（监控 / Harness / 成本）
3. 补充 Week 8 新题："Agent 是什么？" → **LLM + planning + tool + memory + environment 五要素**，并用自己的系统举例每个要素落在哪个文件
4. 把 Week 7 三题 + Week 8 新题精讲写进 `interview_questions.md` 的 Agent 章节

**产出：** `interview_questions.md`（Agent 专题章节）｜模式：Ask 为主

---

### Day 7（周日）：面试模拟 Day 3 + 系统设计 + 收官回顾（混合模式）

**核心任务：** 终极关卡——**"设计一个企业级 RAG 系统"全链路口述 + 收官周回顾**。

**系统设计题（Week 8 核心面试题，全链路）：**
```
文档解析 → 智能分块 → 混合检索 → Reranker → Agentic-RAG → 多轮记忆 → 监控评估 → 权限安全
```
**必须讲清每一环**：为什么这么做 / 遇到什么问题 / 你实际做了什么（对应代码）：
- 文档解析：[`app/rag/loader/`](app/rag/loader/loader_factory.py:1)（txt/md/pdf）
- 智能分块：[`splitter.py`](app/rag/splitter.py:1)
- 混合检索 + RRF：[`hybrid_retriever.py`](app/rag/hybrid_retriever.py:1)
- Reranker：[`reranker_cross_encoder.py`](app/rag/reranker_cross_encoder.py:1)
- Agentic-RAG：[`agentic_rag.py`](app/agent/agentic_rag.py:1)
- 多轮记忆：[`memory.py`](app/memory/memory.py:1)
- 监控评估：[`app/observability/eval.py`](app/observability/eval.py:1)
- 权限安全：HITL（[`research_agent_hitl.py`](app/agent/research_agent_hitl.py:1)）+ 白名单拦截

**任务：**
1. 用 Ask 模式完整模拟系统设计题，**用 mermaid 画全链路图**，逐环口述
2. 补充 Computer Use 新题精讲进 `interview_questions.md`（核心挑战：视觉理解准确率 / 动作空间设计 / 安全性）
3. 写 `week8_review.md`：本周产出清单 + **最终版全链路架构图** + 三套面试题精讲 + **8 周技术栈总表**（对照 [`计划.md`](计划.md:199)）+ 自检清单（能脱稿讲哪几题）
4. 整理 8 周所有周回顾/笔记为一份"面试前 24h 速查包"清单

**产出：** `interview_questions.md`（收尾）+ `week8_review.md`（收官回顾）｜模式：Ask + Code

---

## 📝 第 8 周面试必会问题

> 前 7 周所有问题（Week 4-7 面试题）+ 本周新增 3 题 = 完整面试题库。**重点：Week 8 是收官周，所有题目都要能脱稿。**

| 问题 | 参考答案要点 |
|------|-------------|
| **Computer Use 的核心挑战？**（新增） | ① 视觉理解准确率：GUI 截图转界面语义不精确，需视觉模型 + self-correct 循环 ② 动作空间设计：点击/输入/滚动等原子操作如何定义、如何反馈 ③ 安全性：Agent 操控真实桌面风险高，需权限边界 + HITL（呼应 Week 7 安全三原则） |
| **Agent 是什么？**（新增） | **LLM + planning + tool + memory + environment 五要素**。用自己的系统举例：LLM=app/llm.py，planning=LangGraph 工作流，tool=MCP ToolRegistry，memory=ConversationMemory，environment=VectorStore + FastAPI |
| **设计一个企业级 RAG 系统**（新增/核心） | 全链路：文档解析 → 智能分块 → 混合检索 → Reranker → Agentic-RAG → 多轮记忆 → 监控评估 → 权限安全；每环给出"为什么 + 实际代码"（见 Day 7） |
| 你怎么监控 Agent 性能？（Week 7） | LangFuse 追踪 + RAG 三指标评估 + feedback loop |
| Agent 工程中 Harness 做什么？（Week 7） | Memory / 权限沙箱 / 任务调度 / 异常重试 四件套 |
| 怎么降低 LLM 调用成本？（Week 7） | 模型路由 / 缓存 / 减 context / 工具次数控制 |

---

## 📊 本周时间分配（按每日 5h × 7 天 = 35h）

| 天 | 重点 | 预估时间 | 定位 | 模式 |
|----|------|---------|------|------|
| Day 1 | Computer Use 概念（GUI Agent 三要素） | 5h | 概念核心 | Ask |
| Day 2 | Computer Use 论文速览（OS-Copilot/UFO/CogAgent） | 5h | 概念核心 | Ask |
| Day 3 | 简历包装（3 条 STAR + 预判问题） | 5h | **求职产出** | Code |
| Day 4 | GitHub README 精修（mermaid 架构图） | 5h | **求职产出** | Code |
| Day 5 | 面试模拟 RAG 专题 | 5h | 面试核心 | Ask |
| Day 6 | 面试模拟 Agent 专题 | 5h | 面试核心 | Ask |
| Day 7 | 系统设计全链路 + 收官回顾 | 5h | **收官重点** | Ask + Code |

> 与 Week 4-7 一致：每日 5h。前 2 天纯概念（无业务代码），后 5 天以"产出可面试文件 + 口述过关"为主，不新增系统功能。

---

## 🔗 本周关键资源

1. [Anthropic Computer Use 官方文档](https://docs.anthropic.com/en/docs/build-with-claude/computer-use) — GUI Agent 原理与实操
2. [OpenAI Operator 介绍](https://openai.com/index/introducing-operator/) — 浏览器操作 Agent 产品
3. [UFO (Microsoft)](https://github.com/microsoft/UFO) — Windows 应用操作双智能体框架
4. [OS-Copilot / FRIDAY](https://github.com/OS-Copilot/OS-Copilot) — 操作系统级 Copilot 论文代码
5. [CogAgent](https://github.com/THUDM/CogAgent) — 清华 GLM 团队 GUI 视觉语言模型
6. [LangFuse 官方文档](https://langfuse.com/docs) — Week 7 复习（监控/评估）
7. [STAR 法则写作指南](https://www.indeed.com/career-advice/resumes-cover-letters/star-method) — 简历项目描述
8. [Mermaid 官方文档](https://mermaid.js.org/) — README 架构图语法
9. [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/) — Agent 专题复习
10. [FastAPI 官方文档](https://fastapi.tiangolo.com/) — 系统设计"接口层"复习

---

## ⚠️ 注意事项

- **Computer Use 是"概念了解 + 面试话术"，不是本周实现重点**：Day 1-2 只做理解与笔记，**不写 pyautogui/selenium 业务代码**（环境受限 + 收官周时间应留给求职）。若你后续有兴趣，可另行扩展
- **无外网降级**：Day 2 论文若打不开，用 Ask 模式让 AI 基于已有知识讲解三要素架构（OS-Copilot / UFO / CogAgent 均为公开论文，可离线讲解）；README 用已有截图/代码片段代替在线 Demo
- **所有运行基于 venv**：Day 3-4 改 README/requirements 后如需验证，用 `venv` 激活后跑 FastAPI（沿用 Week 4-7 环境），不新增依赖
- **Day 5-7 是"脱稿"训练，不是"再看一遍"**：先自己口述，再对照笔记补漏；**Week 7 三题（监控/Harness/成本）必须能脱离笔记讲**
- **Day 7 系统设计题是收官核心**：必须能画全链路 mermaid 图 + 每环对应到真实代码文件——这是"8 周 = 一个可讲的完整系统"的最终证明
- **面试题与代码强绑定**：所有答案都要能"指向文件"（如 [`hybrid_retriever.py`](app/rag/hybrid_retriever.py:1) 的 RRF、[`tracing.py`](app/observability/tracing.py:1) 的 @observe），避免"背概念但代码对不上"
- **本周末需完成收官三件事**：① `resume.md` ② 精修 `README.md` ③ `interview_questions.md`（Week 4-8 全题库）+ `week8_review.md`（最终版技术栈 + 架构图）
- **Week 8 是"输出周"不是"输入周"**：前 7 周是"能跑能讲"，本周是把 8 周串成**一个面试故事**——主线 = 从手写 RAG 到企业级 Agent 系统，支线 = 每个技术决策都能讲"为什么"
