"""
eval.py — Day 2: LangFuse Evaluation(RAG 回答质量自动评估,LLM-as-Judge + 规则兜底双通道)。

════════════════════════════════════════════════════════════════════════════
  核心:追踪只告诉你"发生了什么",评估才能告诉你"回答得好不好"。
  用 LLM-as-Judge(app.llm.chat 真实 DeepSeek)给 RAG 回答打三个分数,
  并在 LangFuse 可用时用 langfuse.score() 写回 trace,形成 feedback loop。
  本环境无外网时退化本地版:不依赖 langfuse 库,缺依赖 / LLM 失败均不崩溃。
════════════════════════════════════════════════════════════════════════════

  三个指标 ↔ RAG 三个环节(面试直接引用):
  ┌────────────────────┬────────────────────────────────────┬──────────────────┐
  │ 指标                │ 判断逻辑                           │ 对应 RAG 环节      │
  ├────────────────────┼────────────────────────────────────┼──────────────────┤
  │ Faithfulness       │ 回答里每个事实都能在 context 找到依据│ 生成环节(LLM)      │
  │  (忠实度)          │ → 1/0(无依据=编造=掉分)             │ 检索不到时硬编→掉分 │
  ├────────────────────┼────────────────────────────────────┼──────────────────┤
  │ Answer Relevance   │ 不看 context,只看"问题 vs 回答"是否  │ 对齐用户意图环节    │
  │  (回答相关性)       │ 对题 → 1/0(答非所问=掉分)           │ (query 理解/prompt)│
  ├────────────────────┼────────────────────────────────────┼──────────────────┤
  │ Context Precision  │ 正确答案是否出现在检索结果靠前位置    │ 检索环节(Retriever)│
  │  (上下文精准度)     │ → 1/0(靠后/缺失=掉分)               │ top_k/重排问题     │
  └────────────────────┴────────────────────────────────────┴──────────────────┘

  排查 RAG 回答质量问题时:先看哪个指标掉了 → 就能定位是哪个环节出问题。
   - Faithfulness 掉分        → 生成环节:LLM 硬编/检索不到硬答 → 需"诚实回答"兜底
   - Answer Relevance 掉分   → 意图对齐环节:LLM 没理解问题/答非所问 → 查 query/prompt
   - Context Precision 掉分  → 检索环节:检索结果不准/冗余 → 调 top_k / 重排

  双通道设计(与 tracing.py 双后端同一思路):
   - 通道 A「LLM-as-Judge」:app.llm.chat 真实 DeepSeek 打分(优先)。
   - 通道 B「规则兜底」    :LLM 不可用/超时/异常时,基于关键词/2-gram 包含关系
     近似打分(零成本,任何环境可跑)。demo 里两条通道分数并列打印,便于对照。

  写回 LangFuse:send_scores_to_langfuse(trace_id, scores)
   - langfuse 可 import 且 LANGFUSE_* 环境变量齐备 → langfuse.score() 逐项写回
   - 否则 → 本地 JSON 日志(app.log),与 tracing.py 降级风格一致,不崩。
════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any, Optional

from app.utils.logger import logger


# ============================================================
# 1. 提示词模板(LLM-as-Judge 三个指标的 Judge 指令)
# ============================================================

# 生成环节:回答是否忠于检索上下文(防 LLM 编造)
FAITHFULNESS_PROMPT = """你是 RAG 回答质量评估员。请判断"回答"是否忠于"上下文"。

规则:若回答中的每个事实都能在上下文中找到依据,输出 1;只要存在上下文中找不到依据的事实(即编造/硬编),输出 0。

上下文:
{context}

回答:
{answer}

只输出 0 或 1,不要输出任何其他内容。"""

# 意图对齐环节:回答是否真的回答了用户问题(不看 context)
ANSWER_RELEVANCE_PROMPT = """你是 RAG 回答质量评估员。请判断"回答"是否真的回答了"问题"。

规则:不看任何检索上下文,只比较"问题"与"回答"。若回答切题、直接回应了问题,输出 1;若答非所问、答偏题或完全无关,输出 0。

问题:
{question}

回答:
{answer}

只输出 0 或 1,不要输出任何其他内容。"""

# 检索环节:正确答案是否出现在检索结果靠前位置
CONTEXT_PRECISION_PROMPT = """你是 RAG 回答质量评估员。请判断"检索到的上下文"是否精准且不多余。

规则:根据"问题"判断——包含正确答案的上下文片段是否出现在检索结果的前列。
若正确答案出现在最靠前的位置且上下文不冗余,输出 1;若正确片段靠后、缺失或结果冗余,输出 0。

问题:
{question}

检索结果(按序排列,从最靠前到最靠后):
{chunks}

只输出 0 或 1,不要输出任何其他内容。"""


# ============================================================
# 2. 规则兜底(通道 B):零成本、任何环境可跑的近似打分
# ============================================================

def _clean_text(text: str) -> str:
    """去空白、标点,转小写,便于 n-gram 比较。"""
    return re.sub(r"[\s\W_]+", "", (text or "").lower())


def _ngrams(text: str, n: int = 2) -> set:
    """取连续 n-gram 集合(中文 2-gram 无需分词即可近似关键词)。"""
    clean = _clean_text(text)
    if not clean:
        return set()
    if len(clean) < n:
        return {clean}
    return {clean[i : i + n] for i in range(len(clean) - n + 1)}


def _overlap_ratio(a: set, b: set) -> float:
    """b 相对 a 的覆盖率(无共同项返回 0)。"""
    return len(a & b) / len(a) if a else 0.0


def _rule_faithfulness(context: str, answer: str) -> int:
    """
    规则兜底 Faithfulness:回答里的关键词(2-gram)有多少能在 context 中找到依据。
    覆盖率 >= 0.5 → 认为"忠于上下文"(1);否则(存在明显无依据内容)→ 0。
    """
    ctx_ng = _ngrams(context)
    ans_ng = _ngrams(answer)
    if not ans_ng:
        return 0
    covered = ans_ng & ctx_ng
    ratio = len(covered) / len(ans_ng)
    return 1 if ratio >= 0.5 else 0


def _rule_answer_relevance(question: str, answer: str) -> int:
    """
    规则兜底 Answer Relevance:回答是否对题。
    用 2-gram(免分词)计算「问题信息被回答覆盖的比例」:
    回答过短(疑似敷衍/未作答)或覆盖率过低 → 0。
    """
    if len(_clean_text(answer)) < 4:  # 回答太短,疑似未作答/敷衍
        return 0
    q_ng = _ngrams(question)
    a_ng = _ngrams(answer)
    if not q_ng:
        return 1  # 问题无信息可比较,宽松通过
    return 1 if _overlap_ratio(q_ng, a_ng) >= 0.2 else 0


def _rule_context_precision(question: str, context_chunks: list, correct_chunk_index: Optional[int] = None) -> int:
    """
    规则兜底 Context Precision:
      - 若提供 correct_chunk_index(正确答案所在片段位置)→ 出现在最前位(0)才给 1,否则 0。
      - 若未提供 → 用"问题关键词是否出现在首片段"近似判断检索精准度。
    """
    chunks = list(context_chunks or [])
    if not chunks:
        return 0
    if correct_chunk_index is not None:
        return 1 if correct_chunk_index == 0 else 0
    # 无标准答案位置时:问题信息与首片段的重叠近似判断(2-gram 免分词)
    q_ng = _ngrams(question)
    if not q_ng:
        return 1
    return 1 if _overlap_ratio(q_ng, _ngrams(chunks[0])) >= 0.2 else 0


# ============================================================
# 3. LLM-as-Judge 通用调用(通道 A)+ 双通道打分函数
# ============================================================

def _llm_judge(prompt: str, timeout: float = 20.0) -> Optional[int]:
    """
    调用真实 DeepSeek 让 LLM 当裁判,返回 0 或 1。
    失败(网络/超时/无 key/返回异常)返回 None,由调用方降级到规则兜底。
    """
    from app.llm import chat  # 延迟 import:仅真正打分时才触发 LLM 客户端

    start = time.time()
    result = chat(prompt)
    elapsed = time.time() - start

    text = (result or "").strip()
    # 严格解析:期望只输出 0 或 1;宽松兜底:取文本中出现的第一个数字
    if "0" in text and "1" not in text:
        return 0
    if "1" in text and "0" not in text:
        return 1
    for tok in ("1", "0"):
        if re.fullmatch(rf"\s*{tok}\s*", text):
            return int(tok)
    match = re.search(r"[01]", text)
    if match:
        return int(match.group())
    logger.warning(f"[eval] LLM judge 输出无法解析,原文={text!r},耗时={elapsed:.1f}s")
    return None


def _judge_or_fallback(
    prompt: str,
    fallback: int,
    name: str,
    use_llm: bool,
) -> int:
    """统一入口:优先 LLM-as-Judge,失败/禁用时规则兜底,并打印降级说明。"""
    if use_llm:
        try:
            start = time.time()
            verdict = _llm_judge(prompt)
            if verdict is not None:
                logger.info(f"[eval] {name}=LLM-judge 判定 {verdict} (耗时 {time.time()-start:.1f}s)")
                return verdict
        except Exception as exc:  # LLM 不可用/超时 → 降级,绝不让调用崩溃
            logger.warning(f"[eval] {name} LLM 调用失败,降级规则兜底: {exc}")
    logger.info(f"[eval] {name}=规则兜底判定 {fallback}")
    return fallback


def score_faithfulness(context: str, answer: str, use_llm: bool = True) -> int:
    """Faithfulness(忠实度):回答是否忠于 context。1=忠实,0=存在编造。"""
    prompt = FAITHFULNESS_PROMPT.format(context=context, answer=answer)
    return _judge_or_fallback(prompt, _rule_faithfulness(context, answer), "faithfulness", use_llm)


def score_answer_relevance(question: str, answer: str, use_llm: bool = True) -> int:
    """Answer Relevance(回答相关性):回答是否对题(不看 context)。1=对题,0=答非所问。"""
    prompt = ANSWER_RELEVANCE_PROMPT.format(question=question, answer=answer)
    return _judge_or_fallback(prompt, _rule_answer_relevance(question, answer), "answer_relevance", use_llm)


def score_context_precision(
    question: str,
    context_chunks: list,
    correct_chunk_index: Optional[int] = None,
    use_llm: bool = True,
) -> int:
    """Context Precision(上下文精准度):正确答案是否靠前、上下文是否精准。1=精准,0=冗余/缺失。"""
    chunks = list(context_chunks or [])
    if not chunks:
        return 0
    numbered = "\n".join(f"[{i}] {c}" for i, c in enumerate(chunks))
    prompt = CONTEXT_PRECISION_PROMPT.format(question=question, chunks=numbered)
    return _judge_or_fallback(
        prompt,
        _rule_context_precision(question, chunks, correct_chunk_index),
        "context_precision",
        use_llm,
    )


# ============================================================
# 4. 聚合评估 + LangFuse 写回(可选,缺依赖不崩)
# ============================================================

def evaluate_rag(
    question: str,
    answer: str,
    context: str,
    context_chunks: Optional[list] = None,
    correct_chunk_index: Optional[int] = None,
    use_llm: bool = True,
) -> dict:
    """
    聚合三指标打分,返回 {"faithfulness":int, "answer_relevance":int, "context_precision":int}。
      - context            :生成阶段喂给 LLM 的检索上下文(用于 Faithfulness)
      - context_chunks     :检索返回的片段列表(用于 Context Precision,默认 [context])
      - correct_chunk_index:正确答案所在片段位置(用于 Context Precision 精判)
    """
    chunks = context_chunks if context_chunks is not None else [context]
    scores = {
        "faithfulness": score_faithfulness(context, answer, use_llm),
        "answer_relevance": score_answer_relevance(question, answer, use_llm),
        "context_precision": score_context_precision(question, chunks, correct_chunk_index, use_llm),
    }
    logger.info(f"[eval] evaluate_rag scores={json.dumps(scores, ensure_ascii=False)}")
    return scores


def _langfuse_configured() -> bool:
    """判断 LangFuse 是否可用(库可 import + 环境变量齐备),与 tracing.py 一致。"""
    required = ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"]
    if not all(os.environ.get(k) for k in required):
        return False
    try:
        import langfuse  # noqa: F401
        return True
    except Exception:
        return False


def send_scores_to_langfuse(trace_id: str, scores: dict) -> str:
    """
    把三指标分数写回 LangFuse trace(feedback loop),返回实际落地的后端名。
      - LangFuse 可用 → langfuse.score() 逐项写回(trace 维度,可看板看评估趋势)
      - 否则 → 本地 JSON 日志(app.log),接口语义一致,不崩。
    """
    if _langfuse_configured():
        try:
            from langfuse import Langfuse

            lf = Langfuse()
            for name, value in scores.items():
                lf.score(
                    name=f"eval:{name}",
                    trace_id=trace_id,
                    value=int(value),
                    comment="LLM-as-Judge RAG 评估",
                )
            lf.flush()
            logger.info(f"[eval] scores written back to LangFuse trace={trace_id} scores={scores}")
            return "langfuse"
        except Exception as exc:
            logger.warning(f"[eval] LangFuse 写回失败,降级本地日志: {exc}")
    # 本地 JSON 日志后端(缺 langfuse 库 / 缺配置 / 写回失败时的兜底)
    logger.info(
        json.dumps(
            {
                "event": "eval.score",
                "trace_id": trace_id,
                "scores": {k: int(v) for k, v in scores.items()},
                "backend": "local",
                "ts": time.time(),
            },
            ensure_ascii=False,
        )
    )
    return "local"


# ============================================================
# 5. Demo:5 组样本验证三指标 + 掉分诊断
# ============================================================

def _diagnose(scores: dict) -> list[str]:
    """
    诊断:哪个指标掉分 → 对应哪个环节出问题(面试可直接引用)。
    返回一行条诊断说明(0 分对应环节 + 修复方向)。
    """
    diag: list[str] = []
    if scores["faithfulness"] == 0:
        diag.append("🚨 faithfulness=0 → 生成环节:LLM 硬编/检索不到硬答,存在无依据事实 → 需「诚实回答」兜底")
    if scores["answer_relevance"] == 0:
        diag.append("🚨 answer_relevance=0 → 意图对齐环节:答非所问/未对题 → 检查 query 理解与生成 prompt")
    if scores["context_precision"] == 0:
        diag.append("🚨 context_precision=0 → 检索环节:检索结果不准/冗余/正确片段靠后 → 调 top_k / 加重排")
    if not diag:
        diag.append("✅ 三指标全 1 → 检索→生成→对齐 三个环节均正常,回答质量合格")
    return diag


# 5 组样本:至少覆盖 ①正常政策问答 ②检索不到时 LLM 硬编 ③答非所问
# 诊断结论已内联在各样本 dict 的 diag 字段,便于面试直接引用。
_SAMPLES: list[dict[str, Any]] = [
    {
        "name": "样本1 正常政策问答(三指标应全 1)",
        "question": "普通员工每年有几天带薪年假?",
        "answer": "普通员工每年享有 10 天带薪年假。",
        "context": "普通员工每年享有10天带薪年假。",
        "context_chunks": [
            "普通员工每年享有10天带薪年假。",
        ],
        "correct_chunk_index": 0,
        "diag": "✅ 检索命中且靠前(检索✓)→ 生成忠于上下文(生成✓)→ 对题(对齐✓)",
    },
    {
        "name": "样本2 检索不到时 LLM 硬编(Faithfulness 应掉分)",
        "question": "公司为员工提供免费晚餐吗?",
        "answer": "公司每天为员工提供免费晚餐和下午茶,还有免费健身房。",
        "context": "(检索无结果)未在企业政策知识库中找到与「免费晚餐」相关的政策条款。",
        "context_chunks": [
            "(检索无结果)未找到相关政策。",
        ],
        "correct_chunk_index": None,
        "diag": "🚨 Faithfulness 掉分 = 生成环节:检索不到时 LLM 硬编事实 → 需「诚实回答:知识库中无此信息」兜底",
    },
    {
        "name": "样本3 答非所问(Answer Relevance 应掉分)",
        "question": "请病假需要提供什么证明材料?",
        "answer": "今天天气晴朗,适合外出散步。",
        "context": "病假需要提供医院相关证明。连续病假超过7天需部门负责人审批。",
        "context_chunks": [
            "病假需要提供医院相关证明。",
        ],
        "correct_chunk_index": 0,
        "diag": "🚨 Answer Relevance 掉分 = 意图对齐环节:LLM 答非所问 → 检查 query 理解 / 生成 prompt",
    },
    {
        "name": "样本4 正确片段靠后(Context Precision 应掉分)",
        "question": "员工工资每月什么时候发放?",
        "answer": "员工工资每月 15 日发放。",
        "context": "员工工资每月15日发放。",
        "context_chunks": [
            "普通员工每年享有10天带薪年假。",
            "新员工试用期通常为三个月。",
            "员工工资每月15日发放。",
        ],
        "correct_chunk_index": 2,  # 正确答案片段排在第 2 位(靠后)→ 检索精准度差
        "diag": "🚨 Context Precision 掉分 = 检索环节:正确答案片段排在最后(冗余/不精准)→ 调 top_k / 加重排",
    },
    {
        "name": "样本5 部分硬编(回答夹杂无依据内容,Faithfulness 应掉分)",
        "question": "员工工资由哪些部分组成?",
        "answer": "员工工资由基础工资、绩效奖金和福利补贴组成,并且公司提供免费晚餐和免费健身房,还有每年两次团建旅游。",
        "context": "工资由基础工资、绩效奖金和福利补贴组成。员工可以通过公司内部系统查询工资明细。",
        "context_chunks": [
            "工资由基础工资、绩效奖金和福利补贴组成。",
        ],
        "correct_chunk_index": 0,
        "diag": "🚨 Faithfulness 掉分 = 生成环节:回答后半段混入「免费晚餐/健身房/团建旅游」等无 context 依据的事实 → 需约束 LLM 只依据检索内容(诚实回答兜底)",
    },
]


def demo_eval(use_llm: bool = True) -> None:
    """
    跑 5 组样本,打印三指标分数(LLM-as-Judge 与规则兜底双通道)与掉分诊断。
    验证路径:样本2(硬编→Faithfulness 掉分)/样本3(答非所问→Answer Relevance 掉分)
             /样本4(正确片段靠后→Context Precision 掉分) 三条诊断均可真实复现。
    """
    # Windows 控制台 GBK 编码,先切 UTF-8 防中文乱码
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=" * 78)
    print("Day 2 Demo — LangFuse Evaluation(RAG 回答质量自动评估)")
    print(f"打分通道: {'LLM-as-Judge(真实 DeepSeek) + 规则兜底' if use_llm else '规则兜底(快速验证)'}")
    print("三指标对应环节: Faithfulness→生成 | Answer Relevance→对齐意图 | Context Precision→检索")
    print("=" * 78)

    summary: dict[str, int] = {}
    for i, sample in enumerate(_SAMPLES, start=1):
        print(f"\n──── {sample['name']} ────")
        print(f"  问题 : {sample['question']}")
        print(f"  回答 : {sample['answer']}")
        print(f"  上下文: {(sample['context'] or '')[:60]}...")

        # 通道 A / B 双通道打分
        llm_scores = evaluate_rag(
            sample["question"],
            sample["answer"],
            sample["context"],
            context_chunks=sample.get("context_chunks"),
            correct_chunk_index=sample.get("correct_chunk_index"),
            use_llm=use_llm,
        )
        rule_scores = {
            "faithfulness": _rule_faithfulness(sample["context"], sample["answer"]),
            "answer_relevance": _rule_answer_relevance(sample["question"], sample["answer"]),
            "context_precision": _rule_context_precision(
                sample["question"],
                sample.get("context_chunks") or [sample["context"]],
                sample.get("correct_chunk_index"),
            ),
        }

        print(f"  [LLM]  faithfulness={llm_scores['faithfulness']}  "
              f"answer_relevance={llm_scores['answer_relevance']}  "
              f"context_precision={llm_scores['context_precision']}")
        print(f"  [规则]  faithfulness={rule_scores['faithfulness']}  "
              f"answer_relevance={rule_scores['answer_relevance']}  "
              f"context_precision={rule_scores['context_precision']}  (零成本对照)")
        for line in _diagnose(llm_scores):
            print(f"  {line}")

        # 汇总:统计各指标掉分次数
        for key in ("faithfulness", "answer_relevance", "context_precision"):
            summary[key] = summary.get(key, 0) + (1 - llm_scores[key])

        # 演示把分数写回(本地后端日志),反馈 loop 闭环
        backend = send_scores_to_langfuse(trace_id=f"eval-demo-{i:02d}", scores=llm_scores)
        print(f"  分数已写回 → backend={backend} (trace_id=eval-demo-{i:02d})")

    print("\n" + "=" * 78)
    print("汇总:各指标掉分次数(越低越好)")
    for key, cnt in summary.items():
        print(f"  {key:<20} 掉分 {cnt}/5 次")
    print("-" * 78)
    print("诊断结论(面试引用):")
    print("  三指标对应 RAG 三环节: 检索(Context Precision)→ 生成(Faithfulness)→ 对齐意图(Answer Relevance)")
    print("  哪个指标掉分 → 定位哪个环节出问题,再针对性优化(feedback loop)。")
    print("  示例: 样本2(检索不到+硬编)→ Faithfulness 掉分 → 生成环节需「诚实回答」兜底")
    print("        样本3(答非所问)→ Answer Relevance 掉分 → 意图对齐环节需检查 query/prompt")
    print("        样本4(正确片段靠后)→ Context Precision 掉分 → 检索环节需调 top_k/重排")
    print("=" * 78)


if __name__ == "__main__":
    # 支持 --no-llm 参数:跳过真实 LLM 调用,纯规则兜底快速验证(离线可用)
    use_llm_flag = "--no-llm" not in sys.argv
    demo_eval(use_llm=use_llm_flag)
