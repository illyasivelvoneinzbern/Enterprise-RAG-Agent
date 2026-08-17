"""
tracing.py — Day 1: 接入 LangFuse 的可观测追踪模块(双后端,无外网优雅降级)。

════════════════════════════════════════════════════════════════════════════
 设计目标:对已有业务代码(app/llm.py / app/rag/*)零侵入,只在外层包一层追踪。
 观测点(对应 langfuse_notes.md「三层观测点」):
   - LLM token 消耗 : traced_chat / traced_chat_with_tools 记录 input/output/usage
   - 检索耗时       : traced_retrieve 记录 input / 命中数量 / 耗时
   - (工具调用耗时   : 后续 Day 4 reliability 或 MCP 层再接,本模块聚焦 chat+retrieve)
════════════════════════════════════════════════════════════════════════════

 可切换后端(核心卖点):
   - 后端 A「LangFuse」:优先使用 langfuse.decorators.observe 装饰器。
     仅需在 .env 配置 LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST
     (LangFuse SDK 启动时自动读取,与 app/config/settings.py 同一套 .env 机制),
     本模块无需任何改动即自动切到真实后端,数据上云/自托管看板。
   - 后端 B「本地 JSON 日志」:当 langfuse 库不可用(import 失败 / 未安装)或
     LANGFUSE_* 环境变量未配置时自动回退。接口与后端 A 完全一致(都是 observe 包装),
     只是输出载体从「看板」变成「结构化 JSON 日志」(走 app/utils/logger.py)。
     概念与流程与 LangFuse 完全一致——"追踪"的工程思路在任何环境都保留。

 切换规则(透明):
   BACKEND = "langfuse" 当且仅当 langfuse 可 import 且 LANGFUSE_* 三项齐备;
   否则 BACKEND = "local"。

 接入真实 LangFuse 只需三步:
   1. pip install langfuse
   2. .env 加 LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST
   3. 重跑 demo_tracing() —— 自动切到 LangFuse,数据进看板
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable, Optional

from app.utils.logger import logger


# ============================================================
# 1. 后端探测:LangFuse 是否可用且已配置
# ============================================================

def _langfuse_configured() -> bool:
    """判断是否具备切换真实 LangFuse 后端的条件(库可 import + 环境变量齐备)。"""
    required = ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"]
    if not all(os.environ.get(k) for k in required):
        return False
    try:
        import langfuse  # noqa: F401
        return True
    except Exception:
        return False


_LANGFUSE_AVAILABLE = _langfuse_configured()

if _LANGFUSE_AVAILABLE:
    # 后端 A:真实 LangFuse
    from langfuse.decorators import observe as _langfuse_observe

    BACKEND = "langfuse"
else:
    # 后端 B:本地 JSON 日志(缺库 / 缺配置时自动降级)
    _langfuse_observe = None  # type: ignore[assignment]
    BACKEND = "local"


# ============================================================
# 2. 本地 JSON 日志后端:一个与 @observe() 接口一致的装饰器
# ============================================================

def _safe_json(value: Any) -> Any:
    """把对象转成可 JSON 序列化的结构,失败时降级为 str。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_json(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _safe_json(v) for k, v in value.items()}
    # openai 的 Message / Usage / Choice 等 pydantic 对象,优先用 model_dump,失败用 __dict__/str
    for attr in ("model_dump", "dict"):
        method = getattr(value, attr, None)
        if callable(method):
            try:
                return _safe_json(method())
            except Exception:
                pass
    return str(value)


def _extract_usage_metrics(result: Any) -> Optional[dict]:
    """
    从追踪函数返回值中提取 token 消耗(仅当返回结构带 usage 时)。

      - traced_chat 返回 str → 无 usage,返回 None(标注 usage_unavailable)。
      - traced_chat_with_tools 返回 {"message":..., "usage":...} → 提取三项 token。
      - traced_retrieve 返回 list → 无 usage,返回 None。
    """
    if isinstance(result, dict) and result.get("usage"):
        usage = _safe_json(result["usage"])
        return {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }
    return None


def _local_observe() -> Callable:
    """
    本地 JSON 日志装饰器工厂(后端 B)。

    用法与 LangFuse @observe() 完全一致:@observe() 包住函数即可,
    函数名自动作为 span 名。记录 函数名/输入/输出/耗时/异常,
    若返回值带 usage 则自动追加 token 记录。输出走 app/utils/logger.py(app.log)。
    """

    def decorator(func: Callable) -> Callable:
        span_name = func.__name__

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.info(
                json.dumps(
                    {
                        "event": "span.start",
                        "name": span_name,
                        "input": _safe_json({"args": args, "kwargs": kwargs}),
                        "ts": time.time(),
                    },
                    ensure_ascii=False,
                )
            )

            start = time.time()
            try:
                result = func(*args, **kwargs)
                record: dict[str, Any] = {
                    "event": "span.end",
                    "name": span_name,
                    "elapsed_ms": round((time.time() - start) * 1000, 2),
                    "output": _safe_json(result),
                    "ts": time.time(),
                }
                usage = _extract_usage_metrics(result)
                if usage is not None:
                    record["usage"] = usage
                logger.info(json.dumps(record, ensure_ascii=False))
                return result
            except Exception as exc:  # 追踪模块不能掩盖业务异常
                logger.error(
                    json.dumps(
                        {
                            "event": "span.error",
                            "name": span_name,
                            "elapsed_ms": round((time.time() - start) * 1000, 2),
                            "error": f"{type(exc).__name__}: {exc}",
                            "ts": time.time(),
                        },
                        ensure_ascii=False,
                    )
                )
                raise

        return wrapper

    return decorator


# ============================================================
# 3. 对外暴露的观察者(统一入口,后端透明切换)
# ============================================================

if _LANGFUSE_AVAILABLE:
    observe = _langfuse_observe          # 后端 A:LangFuse 原生装饰器
else:
    observe = _local_observe             # 后端 B:本地 JSON 日志装饰器工厂


# ============================================================
# 4. 追踪包装函数(对 app.llm / app.rag 零侵入)
# ============================================================

@observe()
def traced_chat(prompt: str) -> str:
    """包装 app.llm.chat:记录输入 prompt / 输出回答 / 耗时。

    ⚠️ app.llm.chat 返回字符串,openai 的 usage 在 response 上而非 message 上,
    原函数未透传 response → 这里拿不到 token。为遵守"不改 llm.py"约束,
    输出里 usage 标记为 None;要精确 token 数请用 traced_chat_with_tools。
    """
    from app.llm import chat

    return chat(prompt)


@observe()
def traced_chat_with_tools(messages: list, tools: list) -> dict:
    """包装 app.llm.chat_with_tools:记录输入 messages/tools / 输出 / 耗时 / token。

    关键:原 chat_with_tools 只返回 response.choices[0].message(usage 丢失),
    无法做 token 追踪。为拿到 usage,这里用与 chat_with_tools 完全相同的
    OpenAI 客户端配置与参数重建一次调用(行为一致,未改 llm.py 一行),
    返回 {"message": 原语义的首条 message, "usage": response.usage},
    调用方语义不变,同时 token 数进入追踪记录。
    """
    from openai import OpenAI

    from app.config.settings import settings

    client = OpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.BASE_URL)
    response = client.chat.completions.create(
        model=settings.MODEL_NAME,
        messages=messages,
        tools=tools,
    )
    return {
        "message": _safe_json(response.choices[0].message),
        "usage": _safe_json(response.usage),
    }


@observe()
def traced_retrieve(query: str, top_k: int = 3) -> list:
    """包装混合检索 retrieve:记录输入 query / 命中数量 / 耗时 / 命中片段。

    优先用 app.rag.hybrid_retriever(顶层 import jieba,未安装会 import 失败 →
    捕获后降级到 app.rag.retriever.Retriever,再不行用桩数据,保证任何环境可演示)。
    """
    try:
        from app.rag.hybrid_retriever import build_hybrid_retriever

        retriever = build_hybrid_retriever("data/employee_policy.txt")
    except Exception as hybrid_exc:
        logger.warning(f"[tracing] hybrid_retriever 不可用,降级: {hybrid_exc}")
        try:
            from app.rag.embedding import model
            from app.rag.loader.loader_factory import get_loader
            from app.rag.retriever import Retriever
            from app.rag.splitter import split_documents
            from app.rag.vectorstore import VectorStore

            loader = get_loader("data/employee_policy.txt")
            docs = loader.load("data/employee_policy.txt")
            chunks = split_documents(docs)
            vectors = model.encode([c["text"] for c in chunks])
            store = VectorStore(dimension=len(vectors[0]))
            store.add(vectors, chunks)
            retriever = Retriever(store, model)
        except Exception as retr_exc:
            logger.warning(f"[tracing] Retriever 构建失败,用桩数据演示: {retr_exc}")
            return _stub_docs(query, top_k)

    return retriever.retrieve(query, top_k=top_k)


def _stub_docs(query: str, top_k: int = 3) -> list:
    """桩数据:任何环境都能演示追踪输出(标注 STUB 防止误当真实结果)。"""
    return [
        {
            "text": f"[STUB] 演示片段 1 —— 关于「{query}」的占位命中内容(无真实检索环境)",
            "metadata": {"source": "stub", "note": "demo-only"},
            "rrf_score": 0.0,
        }
    ][:top_k]


# ============================================================
# 5. Demo:跑真实查询演示追踪链路
# ============================================================

def demo_tracing(queries: Optional[list[str]] = None) -> None:
    """跑 1-2 个真实查询,演示 chat/retrieve 的追踪输出,并打印追踪链路说明。"""
    import sys

    # Windows 控制台 GBK 编码,先切 UTF-8 防中文乱码
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    queries = queries or ["年假几天", "病假工资怎么算"]

    print("=" * 70)
    print("Day 1 Demo — 可观测追踪(LangFuse + 本地 JSON 日志双后端)")
    print(f"当前后端: {BACKEND}")
    if BACKEND == "local":
        print("说明: langfuse 未安装/未配置 → 已优雅降级为本地 JSON 日志(输出见 app.log)。")
        print("      接入真实 LangFuse: pip install langfuse + .env 配 LANGFUSE_* 三变量即可,代码零改动。")
    else:
        print("说明: LangFuse 已接入,追踪数据将上报看板。")
    print("=" * 70)

    print("\n[1] 检索追踪(观测点:检索耗时 + 命中数量)")
    for q in queries:
        hits = traced_retrieve(q, top_k=3)
        print(f"    query={q!r} -> 命中 {len(hits)} 条,首条片段: {hits[0]['text'][:40]}...")

    print("\n[2] LLM 追踪(观测点:输入/输出/耗时)")
    for q in queries:
        answer = traced_chat(q)
        print(f"    query={q!r} -> 回答 {len(answer)} 字(注:chat 返回 str 拿不到 usage,见日志)")

    print("\n[3] LLM-with-tools 追踪(观测点:token 数,来自 response.usage)")
    try:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "knowledge_search",
                    "description": "检索企业政策知识库",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                    },
                },
            }
        ]
        result = traced_chat_with_tools(
            [{"role": "user", "content": "年假几天?"}],
            tools,
        )
        usage = result.get("usage") or {}
        print(f"    tools 追踪成功 -> usage: {usage}")
    except Exception as exc:
        print(f"    tools 追踪失败(可接受,不影响演示): {exc}")

    print("\n" + "=" * 70)
    print("追踪链路示意图: 用户请求 -> [traced_chat] LLM(token/耗时)")
    print("                           -> [traced_retrieve] 检索(耗时/命中数)")
    print("                           -> [traced_chat_with_tools] LLM+工具(token/耗时)")
    print(f"输出载体: {BACKEND} 后端  →  app.log 中的 span.start / span.end JSON 记录")
    print("=" * 70)


if __name__ == "__main__":
    demo_tracing()
