"""
lcel_rag.py — Day 4: LangChain LCEL 速通

用 LCEL（LangChain Expression Language）重写你的 RAG Pipeline。

对比对象：
  - 手写版: build_index.py + retriever.py + prompt.py + llm.py + rag_agent.py
  - LCEL 版: 本文件

核心概念（只需掌握这四个）：
  ┌─────────────────────┬────────────────────────────────────────┐
  │ RunnablePassthrough │ 透传数据，不做任何处理                      │
  │ RunnableLambda      │ 把任意 Python 函数包装为 Runnable           │
  │ | (管道符)           │ 声明式链式调用：A | B 表示"数据从 A 流向 B"  │
  │ RunnableParallel    │ 并行执行多个 Runnable，结果合并为 dict       │
  └─────────────────────┴────────────────────────────────────────┘

手写 vs LCEL 对比：

  手写流程（每一步手动调函数、手动传参）：
    query_vector = model.encode([query])
    docs = vectorstore.search(query_vector, top_k=10)
    docs = reranker.rerank(query, docs, top_k=3)
    context = build_prompt_context(docs)
    prompt = f"你是助手...\n资料:{context}\n问题:{query}"
    answer = chat(prompt)
    return answer

  LCEL 等价（声明式：定义数据如何流动，框架自动执行）：
    rag_chain = (
        {"context": retriever_runnable, "question": RunnablePassthrough()}
        | prompt_builder
        | llm_runnable
        | StrOutputParser()
    )
    answer = rag_chain.invoke(query)

关键理解：
  - | 是数据管道，不是"或"运算符
  - 每个 Runnable 只关心自己的输入输出，不管上游/下游是谁
  - 参数注入用 dict：{"context": retriever, "question": RunnablePassthrough()}
    含义："question"字段透传原始输入，"context"字段调用 retriever 获取
"""

from langchain_core.runnables import RunnablePassthrough, RunnableLambda, RunnableParallel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.llm import chat as raw_chat
from app.rag.retriever import Retriever


# ============================================
# 1. 封装 Retriever 为 Runnable
# ============================================
# 手写版: docs = retriever.retrieve(query, top_k=3)
# LCEL版: retriever_runnable.invoke(query) → [{"text": ..., "metadata": ...}, ...]

def _retrieve(query: str, retriever: Retriever, top_k: int = 3) -> list[dict]:
    """适配器：把 retriever.retrieve(query, top_k) 转为单参数函数供 RunnableLambda 使用"""
    return retriever.retrieve(query, top_k=top_k)


def create_retriever_runnable(retriever: Retriever, top_k: int = 3):
    """
    创建可链式调用的检索器 Runnable。

    手写版你需要：
      query_vector = model.encode([query])
      docs = vectorstore.search(query_vector, top_k=10)
      docs = reranker.rerank(query, docs, top_k=3)

    LCEL 版只需：
      retriever_runnable = create_retriever_runnable(my_retriever)
      docs = retriever_runnable.invoke("员工年假几天？")
    """
    return RunnableLambda(lambda q: _retrieve(q, retriever, top_k))


# ============================================
# 2. 封装 Prompt 为 Runnable（用 ChatPromptTemplate）
# ============================================
# 手写版: build_prompt.py 中手写 f-string 拼接
# LCEL版: ChatPromptTemplate.from_messages() 声明式模板

SYSTEM_TEMPLATE = """你是企业知识库助手。

你的任务是根据【知识库资料】回答用户问题。

严格要求：
1. 只能使用下面提供的资料回答。
2. 如果资料中存在答案，必须回答。
3. 不要回答不知道，除非资料完全没有相关信息。"""

HUMAN_TEMPLATE = """知识库资料:
{context}

用户问题:
{question}

请直接回答："""

rag_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_TEMPLATE),
    ("human", HUMAN_TEMPLATE),
])


# ============================================
# 3. 封装 LLM 为 Runnable
# ============================================
# 手写版: answer = chat(prompt)  ← 接收 str，返回 str
# LCEL版: RunnableLambda 包装后可以链入 | 管道

def _llm_call(messages) -> str:
    """
    适配器：ChatPromptTemplate.invoke() 返回的是 ChatPromptValue，
    需要用 .to_string() 或 .messages 提取文本。

    实际项目中可以直接用 ChatOpenAI 替代：
      from langchain_openai import ChatOpenAI
      llm = ChatOpenAI(model="deepseek-chat", ...)
    """
    # ChatPromptValue 不是列表，不能用 [-1] 索引
    # .to_string() 直接把所有消息拼接为完整 prompt 文本
    prompt_text = messages.to_string()
    return raw_chat(prompt_text)


llm_runnable = RunnableLambda(_llm_call)


# ============================================
# 4. 组装 LCEL 链
# ============================================
# 
# 数据流（从右往左读）：
#   用户输入 "员工年假几天？"
#       │
#       ▼  ┌─────────────────────────────────────────────┐
#          │ {"context": retriever, "question": Passthrough} │
#          │                                             │
#          │  "question" ← 原始输入透传                   │
#          │  "context"  ← retriever.invoke(原始输入)     │
#          └──────────────────┬──────────────────────────┘
#                             │ dict{"context": [...], "question": "..."}
#                             ▼
#          ┌─────────────────────────────────────────────┐
#          │ rag_prompt                                  │
#          │ 把 dict 填入模板 → ChatMessages             │
#          └──────────────────┬──────────────────────────┘
#                             │ [SystemMessage, HumanMessage]
#                             ▼
#          ┌─────────────────────────────────────────────┐
#          │ llm_runnable                                │
#          │ 调用 DeepSeek → str                          │
#          └──────────────────┬──────────────────────────┘
#                             │ "根据员工手册，每年有5天年假..."
#                             ▼
#          ┌─────────────────────────────────────────────┐
#          │ StrOutputParser()                           │
#          │ 确保输出是纯字符串                            │
#          └──────────────────┬──────────────────────────┘
#                             │ "根据员工手册，每年有5天年假..."
#                             ▼
#                          最终输出

def create_rag_chain(retriever: Retriever, top_k: int = 3):
    """
    创建 LCEL RAG 链。

    用法：
      chain = create_rag_chain(retriever, top_k=3)
      answer = chain.invoke("员工年假几天？")

    等价于手写版的：
      docs = retriever.retrieve(query)
      prompt = build_prompt(query, docs, history="")
      answer = chat(prompt)
    """
    retriever_runnable = create_retriever_runnable(retriever, top_k)

    # 手动构建 context 字符串（从检索结果拼成文本块）
    def _format_docs(docs: list[dict]) -> str:
        return "\n\n".join(
            f"[来源: {doc['metadata'].get('source', '未知')}]\n{doc['text']}"
            for doc in docs
        )

    # 这是 LCEL 的核心：RunnableParallel + | 管道
    chain = (
        {
            "context": retriever_runnable | RunnableLambda(_format_docs),
            "question": RunnablePassthrough(),
        }
        | rag_prompt
        | llm_runnable
        | StrOutputParser()
    )

    return chain


# ============================================
# 5. RunnableParallel 演示（了解即可）
# ============================================

def demo_runnable_parallel(retriever: Retriever):
    """
    演示 RunnableParallel 的并行能力。

    场景：同时做语义搜索 + 关键词搜索 + 元数据过滤，
         三个检索并行执行，结果合并为一个 dict。
    """
    semantic = create_retriever_runnable(retriever, top_k=3)
    keyword = RunnableLambda(lambda q: f"[关键词匹配] {q}")  # 简化为 Mock

    parallel = RunnableParallel(
        semantic_results=semantic,
        keyword_results=keyword,
    )

    return parallel  # parallel.invoke("问题") → {"semantic_results": ..., "keyword_results": ...}


# ============================================
# 6. 便捷函数
# ============================================

def lcel_rag_answer(retriever: Retriever, query: str, top_k: int = 3) -> str:
    """
    一行调用 LCEL RAG。

    对比手写版 rag_agent.py 的 answer() 方法 ——
    手写版需要：构造 messages → agent_executor.run() → 解析响应
    LCEL 版只需：链式声明 → invoke()
    """
    chain = create_rag_chain(retriever, top_k)
    return chain.invoke(query)


# ============================================
# 附：手写版 vs LCEL 版 核心代码对比
# ============================================

"""
┌──────────────────────────────────────────────────────────────────┐
│                        手写版 RAG 流程                           │
├──────────────────────────────────────────────────────────────────┤
│  # build_index.py                                               │
│  loader = get_loader(file_path)                                 │
│  documents = loader.load(file_path)                             │
│  chunks = split_documents(documents)                            │
│  vectors = model.encode([c["text"] for c in chunks])            │
│  store = VectorStore(dimension=len(vectors[0]))                 │
│  store.add(vectors, chunks)                                     │
│  retriever = Retriever(store, model, Reranker())                │
│                                                                  │
│  # rag_agent.py + prompt.py                                     │
│  self.memory.add_user_message(query)                            │
│  messages = [{"role": "system", "content": "..."}, ...]         │
│  response = self.agent_executor.run(messages)                   │
│  self.memory.add_ai_message(response)                           │
│  return {"answer": response, "sources": []}                     │
├──────────────────────────────────────────────────────────────────┤
│                         LCEL 版 RAG 流程                         │
├──────────────────────────────────────────────────────────────────┤
│  retriever = build_knowledge_base(file_path)  # 复用已有        │
│  chain = create_rag_chain(retriever)                             │
│  answer = chain.invoke(query)                                   │
│                                                                  │
│  # 链内部自动完成：                                              │
│  # query → retriever.retrieve() → format_docs()                 │
│  #       → prompt template → LLM → parse output                 │
└──────────────────────────────────────────────────────────────────┘
"""
