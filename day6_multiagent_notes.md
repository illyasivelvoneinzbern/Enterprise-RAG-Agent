# Day 6 笔记：Dify/Coze Multi-Agent 对比（Week 6）

> 目标：用 [Dify](https://dify.ai/) 和 [Coze](https://www.coze.cn/) 分别**复现** Day 4-5 手写的 Multi-Agent 工作流，
> 对照填充本模板，理解"手写 LangGraph vs 低代码平台"在 Multi-Agent 场景下的开发效率与取舍，
> 形成"手写 Multi-Agent ↔ Dify ↔ Coze"三角对比表。
>
> 前置：Day 4 手写 Router（[`multi_agent_router.py`](app/agent/multi_agent_router.py:1)）、
> Day 5 手写 Supervisor（[`supervisor_agent.py`](app/agent/supervisor_agent.py:1)）、
> Week 5 Dify 笔记（[`dify_notes.md`](dify_notes.md:1)）、Coze 笔记（[`coze_notes.md`](coze_notes.md:1)）。

---

## 1. 手写实现回顾（对照基线，已预填）

### 1.1 Day 4：Router 模式（[`multi_agent_router.py`](app/agent/multi_agent_router.py:1)）

- [`RouterState`](app/agent/multi_agent_router.py:60)：父图共享状态 `query / intent / answer / messages`
- [`intent_node`](app/agent/multi_agent_router.py:87)：**LLM 意图判断 + 规则兜底**（命中企业政策关键词 → `rag`，否则 → `research`）
- [`build_rag_subgraph`](app/agent/multi_agent_router.py:204) / [`build_research_subgraph`](app/agent/multi_agent_router.py:243)：两个**子图（SubGraph）**
- [`route_by_intent`](app/agent/multi_agent_router.py:256)：**conditional edge 一次分发** —— 只走一个子 Agent，直接到 END

> 一句话：Router = "一次分发"。意图判断后只派一个子 Agent，不收集、不综合。

### 1.2 Day 5：Supervisor 模式（[`supervisor_agent.py`](app/agent/supervisor_agent.py:1)）

- [`SupervisorState`](app/agent/supervisor_agent.py:57)：`messages` 用 `Annotated[list, operator.add]` **自动追加收集**子 Agent 结果
- [`supervisor_node`](app/agent/supervisor_agent.py:147)：**每轮 LLM 决策**派 `research / rag / finish`，失败回退规则、超限强制收尾
- [`route_after_supervisor`](app/agent/supervisor_agent.py:334)：**可迭代分发** —— 子 Agent 完成后回到 Supervisor 重新决策
- `rounds / max_rounds`：**防失控**计数，超限强制 finish
- `finish`：汇总所有子 Agent 结果（`[rag]...` / `[research]...`）**综合输出**

> 一句话：Supervisor = "可迭代分发 + 收集 + 综合"，是大厂最常用的 Multi-Agent 架构。

### 1.3 手写组件 ↔ Dify ↔ Coze 概念映射表（预填）

> 参考 [`coze_notes.md`](coze_notes.md:6) 的 4 大核心概念：**Bot / Plugin / Workflow / Knowledge**。

| 手写组件（Day 4-5 我的代码） | 对应 Dify 概念 | 对应 Coze 概念 |
|---|---|---|
| Router 父图（[`multi_agent_router.py`](app/agent/multi_agent_router.py:1) 一次分发） | 工作流"条件分支/意图分类" + 多 Agent 编排 | Workflow 条件分支 / 多 Agent 编排 |
| [`intent_node`](app/agent/multi_agent_router.py:87)（LLM 意图判断 + 规则兜底） | LLM 节点做意图分类 + IF/ELSE 条件分支 | 意图识别节点 / LLM 节点 |
| RAG 子图（[`build_rag_subgraph`](app/agent/multi_agent_router.py:204)） | 知识库检索节点 + LLM 节点 | Knowledge（知识库）+ Workflow |
| Research 子图（[`build_research_subgraph`](app/agent/multi_agent_router.py:243)） | Web 搜索工具节点 | Plugin（搜索插件） |
| Supervisor 父图（[`supervisor_agent.py`](app/agent/supervisor_agent.py:1) 可迭代分发+收集+综合） | 多 Agent 编排 / Agent 节点 | 多 Agent 编排模式 |
| [`supervisor_node`](app/agent/supervisor_agent.py:147)（每轮 LLM 决策） | Agent 节点推理模式 | 多 Agent 编排的决策器 |
| `messages` 收集（`operator.add`） | 变量聚合 / 对话记忆 | 多 Agent 上下文收集 |
| `rounds / max_rounds`（防失控） | 循环/迭代上限设置 | 多 Agent 最大轮次限制 |
| `finish` 综合输出 | 结束/汇总节点 | 多 Agent 综合回答 |

> 核心洞察：**Dify/Coze 的多 Agent 编排 ≈ 我手写的"用 LLM 做决策的 conditional edge"（Supervisor）的可视化版。**
> 平台把 `intent_node / supervisor_node / operator.add / rounds` 这些细节做成了配置项或拖拽节点。

---

## 2. 实操记录清单（用户实操时填写）

### 2.1 Dify 实操记录

- [ ] **应用类型**：创建了什么应用？
  - 聊天助手 / 工作流 / 对话流 / 多 Agent（Agent）？<!-- 待填充 -->
  - 应用名称：<!-- 待填充 -->
- [ ] **意图分流实现方式**：如何实现"企业政策 vs 外部搜索"的分流？
  - 条件分支（IF/ELSE）/ LLM 意图分类节点 / 内置 Multi-Agent 编排？<!-- 待填充 -->
  - 分流逻辑截图占位：<!-- 截图粘贴区 -->
- [ ] **知识库/工具接入**：
  - 知识库：上传了哪些文档？（建议 `data/employee_policy.txt`）<!-- 待填充 -->
  - 工具/插件：是否挂了 Web 搜索工具？<!-- 待填充 -->
- [ ] **可迭代分发**：是否实现了"Supervisor 式"多轮分发/综合？轮次上限怎么设？<!-- 待填充 -->
- [ ] **遇到问题与解决**：
  - 是否遇到 Week 5 的 **"context 为空"** 教训——工作流应用需手动引用节点输出（如 `{{#知识检索节点.result#}}`）？<!-- 待填充 -->
  - 其他问题：<!-- 待填充 -->

### 2.2 Coze 实操记录

- [ ] **Bot 类型**：创建的是什么 Bot？单 Agent / 多 Agent 编排？<!-- 待填充 -->
  - Bot 名称：<!-- 待填充 -->
- [ ] **意图分流实现方式**：如何实现"企业政策 vs 外部搜索"的分流？
  - 多 Agent 编排的"路由/意图识别" / Workflow 条件分支 / LLM 节点？<!-- 待填充 -->
  - 分流逻辑截图占位：<!-- 截图粘贴区 -->
- [ ] **知识库/工具接入**：
  - Knowledge：是否挂载 `data/employee_policy.txt`？<!-- 待填充 -->
  - Plugin：是否挂了搜索/工具插件？<!-- 待填充 -->
- [ ] **可迭代分发**：Coze 多 Agent 编排是否支持"决策器反复派发 + 收集 + 综合"？轮次上限？<!-- 待填充 -->
- [ ] **遇到问题与解决**：
  - 多 Agent 模式下知识库引用是否生效？上下文是否为空？<!-- 待填充 -->
  - 其他问题：<!-- 待填充 -->

---

## 3. 对比表：手写 vs Dify vs Coze（核心产出，实操后填写）

| 维度 | 手写（Day 4-5 LangGraph） | Dify | Coze |
|------|--------------------------|------|------|
| 开发效率（搭建时间） | <!-- 待填充：写 intent_node + 子图 + conditional edge 的耗时 --> | <!-- 待填充 --> | <!-- 待填充 --> |
| 定制深度（能否魔改） | <!-- 待填充：状态/边/防失控/兜底全部可控 --> | <!-- 待填充 --> | <!-- 待填充 --> |
| 调试便利性 | <!-- 待填充：打印 state / 单测逐节点 --> | <!-- 待填充：可视化画布 + 节点运行日志 --> | <!-- 待填充：可视化 + 调试运行 --> |
| 部署成本 | <!-- 待填充：自建服务/模型 Key --> | <!-- 待填充：云托管或私有化 Docker --> | <!-- 待填充：平台托管 --> |
| 适用场景 | <!-- 待填充：生产级/深度定制 --> | <!-- 待填充 --> | <!-- 待填充 --> |
| 面试价值 | <!-- 待填充：加分项 --> | <!-- 待填充 --> | <!-- 待填充 --> |

---

## 4. 测试清单（用户实操时对照勾选）

| # | 测试项 | 期望行为 | 手写（Day 4-5） | Dify | Coze |
|---|--------|----------|----------------|------|------|
| 1 | 意图分流正确性：企业政策问题（如"普通员工年假几天？"） | 走**知识库 Agent** | ✓ 可对照 | ☐ | ☐ |
| 2 | 意图分流正确性：外部信息问题（如"最近大模型有什么动态？"） | 走**搜索 Agent** | ✓ 可对照 | ☐ | ☐ |
| 3 | 混合问题（如"病假工资怎么算？顺便查查最近大模型动态"） | 能否**路由/分发到多个 Agent**并综合 | ✓ Supervisor 可迭代分发 | ☐ | ☐ |
| 4 | 兜底/转人工：非企业、非搜索问题（如"帮我写首诗"） | 走兜底/转人工，不硬答 | ✓ 规则兜底 | ☐ | ☐ |
| 5 | 与手写 [`supervisor_agent.py`](app/agent/supervisor_agent.py:1) 的结果对比 | 回答质量/覆盖度是否等价 | — | ☐ | ☐ |

> 手写启动方式：`uvicorn app.main:app` 或直接调用 [`multi_agent_router.route`](app/agent/multi_agent_router.py:294) /
> Supervisor 的图入口，记录相同问题的手写输出用于对比。

---

## 5. 心得与面试要点（预填面试价值提示）

### 5.1 低代码平台（Dify/Coze）的优势

- 快速搭建：意图分流、多 Agent 编排拖拽即得，不用写 `intent_node` / `conditional edge`
- 可视化调试：节点连线、运行日志、逐步查看输出
- 无需部署：平台托管，开箱即用，天然带聊天界面 + API

### 5.2 手写（LangGraph）的优势

- 深度定制：状态结构、分发逻辑、防失控、兜底、HITL 全部可控
- 生产可控：不依赖第三方平台，可自托管、私有化部署
- 面试区分度：**"我两者都做过"** —— 既能讲清楚实现原理，也能上手平台验证

### 5.3 面试话术（背熟）

> "我用手写 LangGraph 实现过 Supervisor：一个 `supervisor_node` 每轮用 LLM 决策派发
> 到 research/rag 子 Agent，用 `operator.add` 收集结果、`rounds` 防失控、最后综合输出；
> 我也在 Coze/Dify 用**多 Agent 编排**搭过等效工作流——意图识别 + 条件分发。
> **手写给我深度定制和生产可控，低代码给我快速验证和可视化调试，两者是同一个
> 模式（用 LLM 做决策的条件编排）的不同实现，我会按场景选择。**"

对应面试题：
- **"你做过 Multi-Agent 吗？"** → 三种模式（路由/编排/协作）+ 本次三角对比
- **"手写 Multi-Agent 和用平台搭有什么区别？"** → 上面 5.1 / 5.2 的取舍表
- 加分点：把 [`coze_notes.md`](coze_notes.md:42) 的"条件边 ≈ Multi-Agent 路由"与本次 Dify/Coze 双平台实操串起来讲

### 5.4 实操心得（用户填写）

- <!-- 待填充：Dify/Coze 实操中最省事/最坑的地方 -->
- <!-- 待填充：与手写 Day 4-5 对比，时间/质量/可控性的真实体感 -->
