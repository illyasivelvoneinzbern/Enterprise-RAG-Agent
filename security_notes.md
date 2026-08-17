# Day 5 笔记：Agent 安全三原则（权限沙箱概念）

> 目标：理解"Agent 越强越危险"的本质，掌握 Agent 安全三原则——**① 工具权限最小化 ② 用户审批门（HITL）③ 沙箱隔离（Docker）**，
> 并与本项目已有代码做一一对应：
> - ① 工具白名单 + 按意图只暴露对应工具（Day 4 Router 按意图分流是雏形）
> - ② [`research_agent_hitl.py`](app/agent/research_agent_hitl.py:1) 的 `interrupt_before=["search"]` 审批门
> - ③ [`dockerfile`](dockerfile:1) 的容器隔离

---

## 一、为什么需要 Agent 安全？

**核心认知：Agent 越强，越危险。** 传统软件只能执行程序员写死的逻辑；Agent 能自主决定"调用哪个工具、传什么参数、做几次、怎么组合"。能力越大，一旦被滥用或误触发，破坏半径也越大。

**Agent 失控的三种典型风险：**

| 风险 | 表现 | 举例 |
|------|------|------|
| **越权调用** | 调用超出任务范围的工具 | 用户只问"年假几天"，Agent 却顺手调用了 `send_email` 群发邮件 |
| **数据泄露** | 把内部/敏感数据外发 | Agent 把企业薪资数据拼进 web 搜索结果/发给外部 API |
| **恶意/误操作** | 执行破坏性动作 | Agent 调 `delete_data` 删了索引库，或执行了 prompt 注入来的恶意指令 |

**关键点**：危险不只是"恶意攻击"，更多是**无意误触发**——LLM 是概率模型，偶发一次"想多了"就可能执行破坏动作。所以安全设计要假设"**Agent 一定会犯错**"，用边界兜住。

---

## 二、Agent 安全三原则

| 原则 | 含义 | 项目已有落地 | 面试话术 |
|------|------|-------------|---------|
| **① 工具权限最小化** | Agent 只能调用"完成当前任务所需的最小工具集"，未授权的工具一律拒绝 | 工具白名单 + 按意图只暴露对应工具；Day 4 Router 按意图分流是天然雏形 | "我不给 Agent 全部工具，只按意图暴露该子任务需要的少数几个，白名单外直接拦截" |
| **② 用户审批门（HITL）** | 高风险操作必须先暂停、人工确认后才执行 | ✅ [`research_agent_hitl.py`](app/agent/research_agent_hitl.py:198) 的 `interrupt_before=["search"]` | "用 LangGraph 的 interrupt 在关键节点前暂停，人工确认/修改后再 resume，等于给危险动作加了道人工闸门" |
| **③ 沙箱隔离** | 不可信/高风险的代码在隔离环境（Docker）运行，无法破坏宿主机 | 项目已有 [`dockerfile`](dockerfile:1)，深化理解资源/进程/网络隔离 | "把 Agent 及其工具跑进 Docker 容器，即使工具出问题也只坏在容器里，影响不了宿主机和其他服务" |

> ⚠️ 三个原则不是"三选一"，而是**层层递进的三道防线**：白名单挡"不该调"→ 审批门挡"高风险"→ 沙箱兜住"已经失控"。

---

## 三、原则①：工具权限最小化

**含义：** 不给 Agent"万能工具箱"，只给"够用的一套"。白名单之外的工具，调用即被拒绝。

**思想来源：** 最小权限原则（Principle of Least Privilege）——每个模块只拥有完成其任务所必需的最小权限。

**本项目已有落地：**

1. **工具白名单拦截**（概念代码，Week 7 Plan Day 5）：

```python
# ① 工具权限最小化：白名单注册，未注册工具一律拒绝
ALLOWED_TOOLS = {"knowledge_search", "safe_web_search"}   # 白名单

def call_tool_safe(name: str, args: dict):
    if name not in ALLOWED_TOOLS:
        raise PermissionError(f"工具 {name} 不在白名单，已拦截")
    return execute(name, args)
```

2. **按意图只暴露对应工具**（Day 4 Router 是天然雏形）：[`multi_agent_router.py`](app/agent/multi_agent_router.py:87) 的 `intent_node` 把问题分成 `rag` / `research` 两类，分别分发到对应子 Agent——**RAG 子图只碰知识库检索工具，Research 子图只碰搜索工具**，任何一路都不会拿到另一路的工具，这就是"按意图最小化"的雏形。

**面试话术：**
> "我的 Agent 不持有一把万能钥匙。工具注册进白名单才能被调用，而且 Router 按意图分流，RAG 场景只暴露检索工具、Research 场景只暴露搜索工具——每个子 Agent 拿到的都是完成任务的最小工具集，白名单外直接抛 PermissionError 拦截。"

---

## 四、原则②：用户审批门（HITL）

**含义：** Human-in-the-Loop——高风险操作先"暂停"，等真人确认/修改后才执行。把"Agent 自主"变成"Agent 建议 + 人拍板"。

**核心机制：** 图执行引擎的**外挂中断**。LangGraph 的 HITL 就是"图暂停 + 外部输入 + 图恢复"三步。

**本项目已有落地（真实代码）：** [`research_agent_hitl.py`](app/agent/research_agent_hitl.py:198)

```python
research_app_hitl = research_graph.compile(
    checkpointer=memory_saver,
    interrupt_before=["search"]  # ← 关键！在 search 节点前暂停
)
```

执行流程（[`research_interactive()`](app/agent/research_agent_hitl.py:208) 三步走）：

1. `invoke()` → Planner 拆解完子问题后，图在 `search` 前**自动暂停**
2. 用户查看/修改子问题，用 `update_state()` 注入修改
3. `invoke(None)` → 从暂停点恢复执行

```
暂停(interrupt) → 人工决策 → 状态修改(update_state) → 恢复(invoke)
```

**概念版审批门**（Plan Day 5）：

```python
# ② 用户审批门（HITL）：高风险工具先挂起，等人工确认
PENDING_APPROVAL = {"execute_code", "send_email", "delete_data"}

def call_tool_hitl(name: str, args: dict, approve=None):
    if name in PENDING_APPROVAL:
        if approve is None or not approve():       # 无人确认 → 拒绝
            return "已拦截：该操作需要用户确认"
    return execute(name, args)
```

**面试话术：**
> "Human-in-the-Loop 我用 LangGraph 的 interrupt 实现：三步——`interrupt_before` 指定暂停节点、`invoke` 触发暂停、`update_state` 注入人工反馈后再 `invoke(None)` 恢复。本质是图执行引擎的外挂中断机制，配合 Checkpoint 还能回滚重放。"

---

## 五、原则③：沙箱隔离（Docker）

**含义：** 不可信/高风险的代码放进隔离环境运行，即便工具出问题（bug、被注入、被恶意利用），也只能破坏隔离环境内部，**影响不到宿主机**。

**为什么 Docker 能隔离？三大隔离维度：**

| 隔离维度 | 机制 | 效果 | 类比 |
|---------|------|------|------|
| **资源隔离** | cgroups 限制 CPU/内存/磁盘配额 | 容器吃爆资源也不会拖垮宿主机/其他服务 | 给每个租户独立的"预算上限" |
| **进程隔离** | namespace 隔离 PID/进程树 | 容器里的进程看不到、杀不掉宿主机进程 | 每个租户独立的"进程房间" |
| **网络隔离** | 独立网络命名空间 + 端口映射 | 容器默认访问不到宿主网络，只能经显式暴露的端口 | 每个租户独立的"网络门禁" |

**本项目已有落地：** [`dockerfile`](dockerfile:1)

```dockerfile
FROM python:3.11          # 干净的镜像基座（最小运行环境）
WORKDIR /app
COPY requirements.txt .    # 只拷贝依赖清单
RUN pip install -r requirements.txt
COPY . .                   # 应用代码整体进容器
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**解读：**
- `COPY . .` 把应用装进容器 → 应用跑在**隔离的进程空间**里，与宿主机进程隔离
- 对外只暴露 `8000` 端口 → **网络隔离**，宿主机其他端口/网络不可见
- 容器内 `pip install` 依赖独立安装 → 依赖与宿主机互不污染

**面试话术：**
> "沙箱我用 Docker 做三层隔离：cgroups 限制资源配额、namespace 隔离进程、独立网络命名空间隔离网络。容器里出任何问题，只影响容器本身，宿主机和旁路服务不受牵连——这层兜底让 Agent 的不可信代码翻不了天。"

---

## 六、工具风险分级

**核心思想：** 不是所有工具都一样危险，按"破坏半径"分级，给不同级别配不同放行策略。

| 分级 | 例子 | 放行策略 |
|------|------|---------|
| **🟢 只读工具** | 知识检索、网页搜索、数据库查询（SELECT）、文件读取 | **直接放行**（低风险，不改变系统状态） |
| **🟡 写操作** | 发消息、改数据、写文件、上传 | **需人工审批**（HITL 拦截，确认后执行） |
| **🔴 高危操作** | 执行代码、外发数据、删除文件、改权限 | **双重确认或直接禁止**（极高破坏半径，默认拒绝） |

**分级落地逻辑：**

```python
RISK_LEVEL = {
    "knowledge_search": "read",      # 只读 → 直接放行
    "safe_web_search":  "read",
    "send_message":     "write",     # 写 → 需审批
    "update_data":      "write",
    "execute_code":     "danger",    # 高危 → 默认禁止
    "delete_data":      "danger",
    "export_data":      "danger",
}

def call_tool_guarded(name, args, approve=None):
    level = RISK_LEVEL.get(name, "danger")      # 未登记 → 按最高风险处理（默认拒绝）
    if level == "read":
        return execute(name, args)              # 只读直接放行
    if level == "write":
        return execute(name, args) if approve() else "已拦截：该操作需要用户确认"
    raise PermissionError(f"高危操作 {name} 已禁止")   # danger 直接禁止
```

> 注意默认安全原则：**未登记的工具按最高风险处理**（fail-closed），宁可误拦，不可漏放。

---

## 七、Agent 安全边界架构图（三道防线）

```
                        用户（Human）
                            │  审批确认（②审批门）
                            ▼
   ┌─────────────────────────────────────────────────────┐
   │                    Agent（LLM + 工具调用）             │
   │                 "想调什么工具" 由 LLM 决定            │
   └────────────────────────┬────────────────────────────┘
                            │ 工具调用请求
                            ▼
   ═══════════════ ① 权限层（白名单 + 风险分级）═══════════
   │  工具在不在白名单？风险是 read/write/danger 哪级？   │
   │  ✗ 不在白名单 / danger → 直接拦截（PermissionError） │
   │  ✓ 只读 → 放行            ✓ 写 → 转 ② 审批门          │
   ═════════════════════┬─────────────────────────────────
                        │
                        ▼
   ═══════════════ ② 审批门（HITL）══════════════════════
   │  写/高危操作 → interrupt 暂停 → 等用户 approve()     │
   │  用户拒绝 → 拦截并返回"需要确认"；用户同意 → 放行      │
   ═════════════════════┬─────────────────────────────────
                        │
                        ▼
   ═══════════════ ③ 沙箱（Docker 隔离）═════════════════
   │  真正执行工具的进程跑在容器里：                      │
   │  资源隔离（cgroups）+ 进程隔离（namespace）          │
   │  + 网络隔离（独立网络命名空间）                      │
   │  即使工具失控，也只坏在容器内，影响不到宿主机          │
   ═════════════════════┬─────────────────────────────────
                        ▼
                    工具（检索 / 搜索 / 写数据 / 执行...）
```

**三道防线一句话：**

| 防线 | 挡什么 | 对应原则 |
|------|--------|---------|
| **① 白名单 + 风险分级** | 挡"不该调用的工具" | 工具权限最小化 |
| **② 审批门（HITL）** | 挡"高风险动作未经确认" | 用户审批门 |
| **③ Docker 沙箱** | 兜住"已经失控的执行" | 沙箱隔离 |

> 类比：白名单是"门禁卡权限"、审批门是"贵重物品人工放行"、沙箱是"即使小偷进了房间也只能在这个房间里折腾，拆不了大楼"。

---

## 八、面试要点：一句话背书

**Q：Agent 安全怎么做的？**

> "Agent 越强越危险，所以安全上我上了三道防线：
> **① 工具权限最小化**——白名单 + Router 按意图分流，每个子 Agent 只拿任务所需的最小工具集，白名单外直接拦截；
> **② 用户审批门（HITL）**——用 LangGraph 的 `interrupt_before` 在关键节点前暂停，高风险操作人工确认后才执行；
> **③ 沙箱隔离**——Agent 和工具跑进 Docker 容器，资源/进程/网络三层隔离，失控也翻不了天。
> 对应地，我给工具做了风险分级：只读直接放行、写操作要审批、高危默认禁止（fail-closed）。"

**一句话浓缩：** 白名单（最小化）→ 审批门（HITL）→ 沙箱（Docker），三道防线层层兜底。

---

## 九、自检清单（能讲清"Agent 安全怎么做的？"）

- [ ] 能讲清为什么"Agent 越强越危险"（越权调用 / 数据泄露 / 恶意误操作）
- [ ] 能说出安全三原则，并各举一个项目里的落地代码位置
  - ① 最小化：白名单 + [`multi_agent_router.py`](app/agent/multi_agent_router.py:87) 按意图分流
  - ② HITL：[`research_agent_hitl.py`](app/agent/research_agent_hitl.py:198) 的 `interrupt_before=["search"]`
  - ③ 沙箱：[`dockerfile`](dockerfile:1) 的资源/进程/网络隔离
- [ ] 能说出 HITL 的三步（暂停 → 人工决策 → 恢复），并理解 `interrupt_before` / `update_state` / `invoke(None)` 的作用
- [ ] 能手画"Agent 安全边界"图：Agent → 权限层（白名单）→ 审批门 → 沙箱 → 工具
- [ ] 能给工具做风险分级（只读放行 / 写审批 / 高危禁止），并解释"默认拒绝（fail-closed）"
- [ ] 能讲清 Docker 三大隔离（资源 cgroups / 进程 namespace / 网络隔离）
- [ ] 能背出"Agent 安全怎么做的"一句话背书（见第八节）

> 下一步（Day 6）：把 Week 4-7 所有模块整合进 [`app/main.py`](app/main.py:1)（FastAPI），统一加装可靠性 + 可观测 + 权限沙箱，形成对外可服务的完整系统。
