# Day 6 笔记：Coze 扣子实战（Multi-Agent 客服工作流）

> 目标：用 [Coze](https://www.coze.cn/) 搭建一个 Multi-Agent 客服工作流，
> 理解"平台 Multi-Agent ≈ 你手写的 LangGraph 条件编排"，形成概念映射表。

## 1. Coze 4 大核心概念映射表（核心产出）

| Coze 概念 | 说明 | 类比我的代码 |
|---|---|---|
| **Bot** | 一个完整 AI 应用（面向用户入口） | [`main.py`](app/main.py:1) FastAPI 应用 |
| **Plugin** | 可复用的能力插件（搜索/天气/数据库） | [`SearchTool`](app/agent/tools.py:1) |
| **Workflow** | 可视化编排的多步流程 | [`langgraph_agent.py`](app/agent/langgraph_agent.py:1) / [`research_agent.py`](app/agent/research_agent.py:1) |
| **Knowledge** | 知识库（文档向量化） | [`vector_store/`](app/rag/vector_store/base.py:1) |

**核心洞察**：Coze 的 Workflow 就是我手写的 `planner → search → writer`（[`research_agent.py`](app/agent/research_agent.py:1)）的可视化版。

## 2. Multi-Agent 客服工作流架构（今天要搭的）

```
用户问题
   │
   ▼
┌─────────────────┐   是 HR 问题    ┌──────────────────┐
│   意图识别 Agent  │ ───────────→  │   知识库 Agent    │ → 回答
│  (判断问题归属)   │                │ (Knowledge+RAG)  │
└────────┬────────┘                └──────────────────┘
         │ 非 HR 问题
         ▼
┌─────────────────┐
│   转人工 Agent    │ → 转人工 / 兜底话术
└─────────────────┘
```

## 3. Multi-Agent 三种主流模式（面试核心）

| 模式 | 说明 | 类比 |
|---|---|---|
| **路由模式**（今天用） | 意图识别 Agent 判断 → 派给专门 Agent | 客服分流 |
| **编排模式** | 一个 Supervisor 调度多个 Worker 协作 | [`research_agent.py`](app/agent/research_agent.py:1) 的 planner→search→writer |
| **协作模式** | 多个 Agent 平等讨论/接力 | 多专家会诊 |

> **面试话术**：Coze 的 Multi-Agent 路由模式 ≈ 我用 LangGraph 写的条件边
> （conditional edge）——`意图识别 → 知识库 or 转人工`。

## 4. 操作步骤（已完成打 ✓）

- [ ] **创建 Bot**：coze.cn → 创建 Bot → 选模型（如豆包）
- [ ] **创建 Knowledge**：上传 `data/employee_policy.txt` → 自动向量化
- [ ] **挂载 Knowledge**：Bot 设置里勾选"引用知识库" → 单 Agent 版先跑通
- [ ] **升级 Multi-Agent**：多 Agent 编排里加 意图识别 Agent / 知识库 Agent / 转人工 Agent
- [ ] **测试**：HR 问题走知识库，非 HR 问题走转人工

## 5. 测试清单（手写 RAG vs Coze 单 Agent vs Coze Multi-Agent）

| 测试问题 | 标准答案 | Coze 单 Agent | Coze Multi-Agent（走哪个 Agent） |
|---|---|---|---|
| 普通员工年假几天？ | 10 天 | | 知识库 Agent |
| 工资什么时候发？ | 每月 15 日 | | 知识库 Agent |
| 连续病假超过几天需审批？ | 7 天 | | 知识库 Agent |
| 帮我写一首诗（非 HR） | 转人工/兜底话术 | | 转人工 Agent |
| 今天天气如何？（非 HR） | 转人工/兜底话术 | | 转人工 Agent |

## 6. 差异心得（实操后填写）

### 6.1 Coze 的 Multi-Agent 帮我省了什么

- （如：不用手写条件边，可视化连线即可）
- （如：Agent 分工、意图识别由平台编排）

### 6.2 手写 LangGraph 的优势

- （如：条件边逻辑可精确控制，如 `should_retry` 循环）
- （如：状态管理、人机交互（HITL）可深度定制）
- （如：不依赖平台，可部署到生产环境）

### 6.3 与 Dify 的对比（Day 7 三角表素材）

- （如：Dify 偏 RAG/知识库问答，Coze 偏 Bot/插件/多 Agent）
- （如：Coze 插件生态丰富，Dify 更强调私有化部署）

## 7. 面试话术（背熟）

> "我在 Coze 里用 Multi-Agent 路由模式搭过客服工作流——意图识别 Agent 判断
> 问题归属，派给知识库 Agent 或转人工 Agent。**这个思想和我在 LangGraph 里写的
> 条件边（conditional edge）是同一个模式的不同实现**：手写给我精确控制，
> 平台给我快速验证。"

对应面试题：**"你做过 Multi-Agent 吗？"**
- 三种模式：路由 / 编排 / 协作
- 路由模式 = 意图识别 + 条件分发（今天 Coze 实操）
- 手写等价物 = LangGraph conditional edge（[`research_agent.py`](app/agent/research_agent.py:1) 已实现）
