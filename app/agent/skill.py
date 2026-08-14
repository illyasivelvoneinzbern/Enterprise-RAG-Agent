"""
app/agent/skill.py — Day 3: Skills 机制 + Skill 协议设计

================================================================================
一、Skill vs Tool 的核心区别（面试必背）
================================================================================

| 维度        | Tool（现有 SearchTool / ToolRegistry）   | Skill（本文件）                          |
|-------------|------------------------------------------|------------------------------------------|
| 粒度        | 原子操作（一次搜索 / 一次计算）           | 能力模块（编排多个子工具 + 内部逻辑）      |
| 组成        | 单个 run() 函数                           | name / description / can_handle / execute |
| 调用方式    | 精确查找：ToolRegistry.get("search")      | 能力发现：SkillRegistry.discover(query)   |
| 是否独立    | 单点能力                                  | 完整可复用模块（含描述 / 参数 / 副作用）   |
| 类比        | 一个 API                                  | 一个微服务                                 |

一句话：
  - Tool   = 原子操作（"怎么做一个动作"），由 LLM / Agent 直接调用；
  - Skill  = 能力模块（"我能解决哪类问题"），内部可编排多个 Tool + 业务逻辑，
             通过 can_handle() 自我发现是否适合处理当前 query。

================================================================================
二、"注册 → 发现 → 调用"模式
================================================================================

  1. 注册（register）：  把 Skill 实例按 skill.name 放入 SkillRegistry.skills
  2. 发现（discover）：  输入 query，返回所有 can_handle(query)==True 的 Skill
                          —— 这是"能力发现"（模糊/语义匹配）
  3. 调用（execute）：   Agent 选中某个 Skill 后，调用 execute(state) 执行能力

对比 ToolRegistry：
  - ToolRegistry.get(name)  = 精确查找（已知名字，直接取）
  - SkillRegistry.discover(q) = 能力发现（未知哪个能力，用 query 匹配）

Skill 让 Agent 面对新任务时"自我发现可用能力"，而不是写死调用哪个工具。

================================================================================
三、Skill 协议字段
================================================================================

  name           str  唯一标识，如 "rag_skill"
  description    str  能力描述（供 Agent / 发现机制阅读）
  input_schema   dict 入参 JSON Schema
  declares_tools list 该 Skill 内部用到的子工具名（如 ["knowledge_search"]）

  can_handle(query) -> bool   能力匹配：这个 Skill 是否适合处理该问题
  execute(state)    -> dict   执行能力并返回结果/状态（如 {"answer": "..."}）
"""

import json
import os
import sys

# 直接运行本脚本时（python app/agent/skill.py），把项目根目录补进 sys.path，
# 保证 import app.rag.* / app.llm 无论用 -m 还是直接运行都能成功。
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.agent.registry import ToolRegistry  # noqa: E402  仅用于对比演示
from app.llm import chat  # noqa: E402


# ============================================
# 1. Skill 基类协议（抽象基类）
# ============================================

class Skill:
    """
    所有 Skill 的基类 —— 定义「能力模块」的统一协议。

    子类必须提供：
      - name           唯一标识
      - description    能力描述（供 Agent / 发现机制阅读）
      - input_schema   入参 JSON Schema（dict）
      - declares_tools 内部用到的子工具名列表

    子类应实现：
      - can_handle(query) -> bool   能力匹配
      - execute(state)    -> dict   执行能力并返回结果/状态

    基类提供 __init_subclass__ 做基础校验，防止子类漏定义协议字段。
    """

    # ---- 协议字段（子类应覆盖）----
    name: str = ""
    description: str = ""
    input_schema: dict = {}
    declares_tools: list = []

    def __init_subclass__(cls, **kwargs):
        """子类创建时做基础校验：name 不能为空。"""
        super().__init_subclass__(**kwargs)
        if not cls.name:
            raise ValueError(f"Skill 子类 {cls.__name__} 必须定义非空 name")

    def __init__(self):
        # 额外的基础校验：name 唯一标识必填
        if not self.name:
            raise ValueError("Skill 必须提供唯一标识 name")

    def can_handle(self, query: str) -> bool:
        """能力匹配：判断该 Skill 是否适合处理这个 query（默认拒绝，子类覆盖）。"""
        return False

    def execute(self, state: dict) -> dict:
        """执行能力并返回结果/状态（子类覆盖）。"""
        raise NotImplementedError

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name!r} declares_tools={self.declares_tools}>"


# ============================================
# 2. RAGSkill 示例：把「检索 + 精排 + 生成」封装为能力模块
# ============================================

# 企业政策相关关键词：命中其一即视为「涉及企业知识库」的问题
_POLICY_KEYWORDS = ["年假", "病假", "薪资", "工资", "入职", "报销", "请假", "试用期"]


class RAGSkill(Skill):
    """
    基于企业知识库的检索增强生成（RAG）能力。

    把 Day 2 的 knowledge_search（MCP 工具）内部逻辑 + LLM 生成封装成一个 Skill：
      - can_handle：判断问题是否涉及企业政策（年假/病假/薪资/入职/报销等）
      - execute    ：检索企业知识库 → 组装上下文 → LLM 生成回答

    declares_tools = ["knowledge_search"]：声明内部复用了 Day 2 的 MCP 工具。
    这里为保持轻量，直接调用 hybrid_retriever（与 mcp/server.py 相同），
    而不是拉起 MCP Server 子进程；二者底层检索逻辑一致。
    """

    name = "rag_skill"
    description = "基于企业知识库的检索增强生成（检索+精排+生成），可回答年假/病假/薪资/入职/报销等员工政策问题"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "用户关于企业政策的原始问题"}
        },
        "required": ["query"],
    }
    declares_tools = ["knowledge_search"]

    KNOWLEDGE_FILE = os.path.join(PROJECT_ROOT, "data", "employee_policy.txt")

    def __init__(self):
        super().__init__()
        self._retriever = None  # 惰性加载：首次 execute 时才构建（避免无谓加载 embedding 模型）

    # ---- 能力匹配 ----
    def can_handle(self, query: str) -> bool:
        """涉及企业政策/制度/流程的问题 → 由 RAG Skill 处理。"""
        return any(k in query for k in _POLICY_KEYWORDS)

    # ---- 内部：构建检索器（惰性 + 容错）----
    def _get_retriever(self):
        """
        获取混合检索器（BM25 + FAISS + RRF 融合）。

        优先用 build_hybrid_retriever（与 mcp/server.py 一致，默认参数、不加载 CrossEncoder）；
        若 jieba / rank_bm25 等依赖缺失，则退回 build_knowledge_base 的纯向量检索。
        """
        if self._retriever is not None:
            return self._retriever

        try:
            from app.rag.hybrid_retriever import build_hybrid_retriever
            retriever = build_hybrid_retriever(self.KNOWLEDGE_FILE)
        except Exception as e:
            print(f"[RAGSkill] hybrid_retriever 不可用（{e}），退回纯向量检索 build_knowledge_base")
            from app.rag.build_index import build_knowledge_base
            retriever = build_knowledge_base(self.KNOWLEDGE_FILE)

        self._retriever = retriever
        return retriever

    # ---- 内部：检索（复用 knowledge_search 同款逻辑）----
    def _knowledge_search(self, query: str, top_k: int = 3) -> list:
        """检索企业知识库，返回命中的政策片段列表（与 mcp/server.py 的 knowledge_search 同逻辑）。"""
        return self._get_retriever().retrieve(query, top_k=top_k)

    # ---- 执行能力 ----
    def execute(self, state: dict) -> dict:
        """
        执行 RAG 能力：检索 → 组装上下文 → LLM 生成 → 返回 {"answer": ...}

        入参 state 需含 "query"；输出含 "answer"（回答原文）与 "sources"（检索片段）。
        若 LLM 无 API key / 调用失败，则返回检索结果原文拼接作为兜底，保证演示可跑通。
        """
        query = state.get("query", "").strip()
        if not query:
            return {"answer": "query 为空，无法执行 RAG Skill", "sources": []}

        # 1. 检索（Day 2 knowledge_search 逻辑）
        docs = self._knowledge_search(query, top_k=3)

        # 2. 组装上下文
        context = "\n\n".join(
            f"[{i + 1}] {d['text']}"
            for i, d in enumerate(docs)
        )
        sources = [d["text"] for d in docs]

        # 3. 用 app/llm.py 的 chat 生成回答；失败时兜底返回检索原文
        prompt = (
            f"你是企业 HR 助手。请严格依据下面的企业政策资料回答用户问题，"
            f"不要编造资料中不存在的信息。\n\n"
            f"【企业政策资料】\n{context}\n\n"
            f"【用户问题】{query}\n\n"
            f"请给出简洁、准确的回答。"
        )

        try:
            answer = chat(prompt)
            return {"answer": answer, "sources": sources}
        except Exception as e:
            # 无 API key / 网络失败 → 兜底：返回检索结果原文
            fallback = "（LLM 调用失败，以下为知识库检索到的原始资料）\n" + context
            print(f"[RAGSkill] LLM 调用失败，返回检索原文兜底：{e}")
            return {"answer": fallback, "sources": sources, "fallback": True}


# ============================================
# 3. SkillRegistry：注册 → 发现 → 精确获取
# ============================================

class SkillRegistry:
    """
    能力注册中心：按 skill.name 注册，按 query 发现可用能力。

    对比 ToolRegistry：
      - ToolRegistry.get(name)    = 精确查找（已知工具名，直接取）
      - SkillRegistry.discover(q) = 能力发现（用 query 匹配 can_handle，返回多个候选）
    """

    def __init__(self):
        self.skills: dict[str, Skill] = {}

    def register(self, skill: Skill):
        """按 skill.name 注册（重复注册会覆盖）。"""
        self.skills[skill.name] = skill

    def discover(self, query: str) -> list:
        """能力发现：返回所有 can_handle(query) 为 True 的 Skill 列表。"""
        return [s for s in self.skills.values() if s.can_handle(query)]

    def get(self, name: str):
        """精确获取：按 name 取单个 Skill（无则返回 None）。"""
        return self.skills.get(name)

    def __repr__(self):
        return f"<SkillRegistry skills={list(self.skills)}>"


# ============================================
# 4. 演示入口
# ============================================

def _demo():
    # 1. 创建 Registry 并注册 RAGSkill
    registry = SkillRegistry()
    registry.register(RAGSkill())
    print("已注册 Skills:", list(registry.skills))
    print()

    # 2. 测试几类问题：涉及企业政策 → handled；无关问题 → 不 handled
    test_queries = [
        "公司年假几天？",        # 政策类 → 应被处理
        "病假怎么请？",          # 政策类 → 应被处理
        "新员工入职需要什么材料？",  # 政策类 → 应被处理
        "今天天气怎么样？",      # 无关 → 不应被处理
        "帮我写一首诗",          # 无关 → 不应被处理
    ]

    print("=" * 60)
    print("can_handle 能力匹配测试")
    print("=" * 60)
    rag = registry.get("rag_skill")
    for q in test_queries:
        handled = rag.can_handle(q)
        # 用 ASCII 标记（Windows GBK 终端无法打印 emoji）
        print(f"  {'[YES] handled     ' if handled else '[NO]  not handled'} | {q}")

    # 3. 演示 discover 能力发现
    print()
    print("=" * 60)
    print("discover 能力发现（区别于 ToolRegistry.get 精确查找）")
    print("=" * 60)
    for q in ["公司年假几天？", "今天天气怎么样？"]:
        matched = registry.discover(q)
        print(f"  query='{q}' → 发现 Skills: {[s.name for s in matched]}")

    # 对比：ToolRegistry 是精确查找
    tr = ToolRegistry()
    print(f"  对比 ToolRegistry.get('rag_skill') = {tr.get('rag_skill')}（精确查找，未注册则 None）")

    # 4. 演示 execute 输出（会触发检索器构建，耗时取决于模型加载）
    print()
    print("=" * 60)
    print("execute 执行能力（检索 + 精排 + 生成）")
    print("=" * 60)
    result = rag.execute({"query": "公司年假几天？"})
    print(f"  answer 前 300 字：\n{result['answer'][:300]}")
    print(f"  命中片段数: {len(result.get('sources', []))}")
    if result.get("fallback"):
        print("  （本次为检索原文兜底：LLM 未配置可用 key）")

    print()
    print("完成：Skill 协议「注册 → 发现 → 调用」全链路验证通过。")


if __name__ == "__main__":
    _demo()
