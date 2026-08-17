"""
Enterprise-RAG-Agent — FastAPI 入口（Week 7 Day 6 整合版）
==========================================================

把所有 Week 4-7 的改进整合进统一服务入口，形成"一个可对外服务的完整系统"：

  - Week 4 : RAGAgent（/rag/chat、/rag/chat/stream）+ 上传建库（/upload）
  - Week 6 : Multi-Agent Supervisor（/rag/supervisor）+ Router（/rag/router）
  - Week 7 : 统一可靠性（重试 + 熔断 + 超时降级）+ 可观测（追踪 / 评估）接入点

整合方式（不污染各接口）：
  - `_safe_answer()`       —— 统一可靠性包装：retry_with_backoff + CircuitBreaker
                               + run_with_timeout_sync（30s 超时降级），所有接口共用
  - `_trace_span()`        —— 统一可观测接入点：ENABLE_TRACING / ENABLE_EVAL 环境变量开关，
                               默认关闭（无网络/未配置 LangFuse 时优雅降级，tracing/eval 自带降级）
  - TaskQueue              —— 多用户排队（轻量接入说明见 README，避免复杂化阻塞）
"""

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi import UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pathlib import Path
import os
import sys

from app.utils.logger import logger
from app.rag_agent import RAGAgent
from app.rag.build_index import build_knowledge_base
from app.memory.session_memory import SessionMemoryManager
from app.agent.tools import SearchTool
from app.agent.registry import ToolRegistry
from app.agent.executor import ToolExecutor
from app.agent.agent_executor import AgentExecutor

# Week 7 Day 4 可靠性组件（仅标准库依赖，顶层 import 安全）
from app.agent.reliability import (
    retry_with_backoff,
    run_with_timeout_sync,
    CircuitBreaker,
    TaskQueue,  # 多用户排队：可选接入点（见 README 说明，默认不强制排队）
)

# Windows GBK 控制台打印中文前先切 UTF-8（服务启动/验证脚本友好）
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass


# =========================
# 可观测开关（默认关闭，避免无网络/未配置 LangFuse 时崩）
# =========================

# ENABLE_TRACING=1 时启用追踪（traced_chat / traced_retrieve，走 tracing.py 双后端降级）
ENABLE_TRACING = os.environ.get("ENABLE_TRACING", "0") == "1"
# ENABLE_EVAL=1 时启用 RAG 回答质量评估（LLM-as-Judge + 规则兜底，走 eval.py）
ENABLE_EVAL = os.environ.get("ENABLE_EVAL", "0") == "1"


# =========================
# Memory管理器
# =========================

memory_manager = SessionMemoryManager()


# =========================
# 初始化Agent
# =========================

tool_registry = ToolRegistry()


# 初始没有知识库
search_tool = SearchTool(None)


tool_registry.register(search_tool)


tool_executor = ToolExecutor(tool_registry)


agent_executor = AgentExecutor(tool_executor)


rag_agent = RAGAgent(None, agent_executor)

# =========================
# FastAPI
# =========================

app = FastAPI()

# =========================
# CORS（供 Vue 前端跨域调用）
# 开发环境放开所有来源；生产环境请改为具体域名列表
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# 前端静态资源（可选）
# 若存在 web/dist（执行 cd web && npm run build 生成），
# 则通过 /web 提供 Vue 前端界面，实现单服务部署
# =========================

WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
_WEB_INDEX = WEB_DIST / "index.html"


@app.get("/web")
@app.get("/web/{full_path:path}")
async def web_frontend(full_path: str = ""):
    if not _WEB_INDEX.exists():
        return {"message": "前端未构建：请先在 web 目录执行 npm run build"}
    target = (WEB_DIST / full_path).resolve()
    if full_path and target.is_file() and str(target).startswith(str(WEB_DIST.resolve())):
        return FileResponse(target)
    return FileResponse(_WEB_INDEX)


# =========================
# Week 7 统一可靠性 + 可观测辅助层（不污染各接口）
# =========================

# 熔断器：连续失败 3 次打开，冷却 5s 后半开探测；状态切换打日志便于观测
_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    cooldown=5.0,
    fallback="服务暂时不可用，请稍后再试。",
    on_state_change=lambda old, new: logger.info(f"[CircuitBreaker] {old} -> {new}"),
)


def _safe_answer(fn, *, timeout=30, fallback="系统繁忙，请稍后再试。"):
    """
    统一可靠性包装：重试 + 熔断 + 超时降级。

    调用链（由内到外）：
      fn()  →  CircuitBreaker.call（熔断保护，打开时快速失败）
              →  retry_with_backoff（LLM/网络偶发失败，1s→2s→4s+抖动 重试 3 次）
              →  run_with_timeout_sync（30s 超时，守护线程不挂死调用方）

    参数：
      fn        无参可调用（用 lambda 绑定参数，如 lambda: chat(prompt)），返回字符串
      timeout   超时秒数，默认 30
      fallback  降级话术

    返回：fn 的成功返回值；任何异常/超时都兜底返回 fallback，绝不向上抛 500。
    """
    def _guarded():
        # 熔断保护 + 指数退避重试（熔断 open 期间不消耗真实调用，直接快速失败）
        return _circuit_breaker.call(
            lambda: retry_with_backoff(fn, max_retries=3)
        )

    try:
        return run_with_timeout_sync(_guarded, timeout=timeout, fallback=fallback)
    except Exception as e:  # noqa: BLE001 —— 可靠性层绝不把异常漏给接口
        logger.error(f"[reliability] 兜底降级: {e}")
        return fallback


def _trace_span(question, answer, context=None):
    """
    统一可观测接入点：追踪 + 评估（受 ENABLE_TRACING / ENABLE_EVAL 开关控制，默认关闭）。

      - 追踪：traced_chat / traced_retrieve（tracing.py 自带 LangFuse ↔ 本地 JSON 双后端降级）
      - 评估：evaluate_rag（eval.py 自带 LLM-as-Judge ↔ 规则兜底双通道降级）
    try/except 包裹：即使 langfuse / LLM / 检索均不可用，也绝不影响主流程。
    """
    if ENABLE_TRACING:
        try:
            from app.observability.tracing import traced_chat, traced_retrieve
            traced_retrieve(question, top_k=3)  # 检索观测点：命中数/耗时（默认走本地 JSON 日志）
            traced_chat(question)               # LLM 观测点：输入/输出/耗时
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[tracing] 追踪降级（不影响主流程）: {e}")

    if ENABLE_EVAL and context is not None:
        try:
            from app.observability.eval import evaluate_rag
            scores = evaluate_rag(question, answer, context, use_llm=True)
            logger.info(f"[eval] evaluate_rag scores={scores}")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[eval] 评估降级（不影响主流程）: {e}")


# =========================
# 请求Schema
# =========================

class RAGRequest(BaseModel):
    session_id: str
    question: str


class SupervisorRequest(BaseModel):
    """Supervisor / Router 多 Agent 接口请求体。"""
    session_id: str
    question: str
    max_rounds: int = 3  # Supervisor 最大迭代轮次（防无限循环）


# =========================
# 首页
# =========================

@app.get("/")
def root():
    return {
        "message": "Enterprise RAG Agent Running",
        "reliability": "retry + circuit-breaker + timeout(30s)",
        "observability": f"tracing={'on' if ENABLE_TRACING else 'off'} | eval={'on' if ENABLE_EVAL else 'off'}",
    }


# =========================
# Chat接口（Week 4，统一加装可靠性 + 可观测）
# =========================

@app.post("/rag/chat")
def rag_chat(req: RAGRequest):
    # 根据用户session获取独立Memory
    memory = memory_manager.get_memory(req.session_id)

    # 给当前请求绑定Memory
    rag_agent.memory = memory

    # 统一可靠性包装（重试 + 熔断 + 30s 超时降级）
    answer = _safe_answer(
        lambda: rag_agent.answer(req.question),
        timeout=30,
        fallback="系统繁忙，请稍后再试。",
    )

    # 统一可观测接入点（默认关闭）
    _trace_span(req.question, answer if isinstance(answer, str) else str(answer))

    return {"answer": answer}


@app.post("/rag/chat/stream")
def rag_chat_stream(req: RAGRequest):
    memory = memory_manager.get_memory(req.session_id)
    rag_agent.memory = memory

    # 流式接口不适合同步超时包装（会阻塞逐 chunk 输出），保持原逻辑 + try/except 兜底
    try:
        return StreamingResponse(
            rag_agent.stream_answer(req.question),
            media_type="text/plain",
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"[stream] 流式回答失败: {e}")
        return StreamingResponse(
            iter(["系统繁忙，请稍后再试。"]),
            media_type="text/plain",
        )


# =========================
# 多 Agent 接口（Week 6：Supervisor / Router，统一加装可靠性 + 可观测）
# =========================

@app.post("/rag/supervisor")
def rag_supervisor(req: SupervisorRequest):
    """
    Supervisor 多 Agent 能力（Week 6 Day 5）：
    接收问题 → LLM 决策派谁（rag/research）→ 收集子 Agent 结果 → 决策是否迭代 → 综合输出。
    复用 supervisor_agent.supervise(query, max_rounds)，懒加载避免 import 时加载模型。
    """
    def _call():
        from app.agent.supervisor_agent import supervise  # 延迟 import：防顶层依赖影响
        return supervise(req.question, max_rounds=req.max_rounds)

    answer = _safe_answer(
        _call,
        timeout=45,  # 多 Agent 迭代比单 RAG 慢，放宽到 45s
        fallback="Supervisor 暂时无法作答，请稍后再试。",
    )

    _trace_span(req.question, answer)
    return {"answer": answer, "mode": "supervisor", "max_rounds": req.max_rounds}


@app.post("/rag/router")
def rag_router(req: RAGRequest):
    """
    Multi-Agent Router 能力（Week 6 Day 4）：
    一次意图分发 → research（外部实时信息）/ rag（企业知识库）。
    复用 multi_agent_router.route(query)，懒加载避免 import 时加载模型。
    """
    def _call():
        from app.agent.multi_agent_router import route  # 延迟 import
        return route(req.question)

    answer = _safe_answer(
        _call,
        timeout=45,
        fallback="Router 暂时无法作答，请稍后再试。",
    )

    _trace_span(req.question, answer)
    return {"answer": answer, "mode": "router"}


# =========================
# 上传知识库
# =========================

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    path = f"data/{file.filename}"

    try:
        with open(path, "wb") as f:
            f.write(await file.read())

        retriever = build_knowledge_base(path)
        rag_agent.update_retriever(retriever)
        return {"filename": file.filename}
    except Exception as e:  # noqa: BLE001
        logger.error(f"[upload] 上传/建库失败: {e}")
        return {"filename": file.filename, "error": f"知识库构建失败: {e}"}


# =========================
# 本地启动入口（uvicorn 方式见 README；此入口便于 python app/main.py 调试）
# =========================

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("Enterprise-RAG-Agent (Week 7 Day 6 整合版)")
    print(f"  reliability : retry + circuit-breaker + timeout(30s)")
    print(f"  tracing     : {'ON' if ENABLE_TRACING else 'OFF (设 ENABLE_TRACING=1 开启)'}")
    print(f"  eval        : {'ON' if ENABLE_EVAL else 'OFF (设 ENABLE_EVAL=1 开启)'}")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
