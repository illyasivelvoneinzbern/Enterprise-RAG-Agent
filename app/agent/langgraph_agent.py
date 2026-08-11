from typing import TypedDict, Annotated
import operator
import json

from langgraph.graph import StateGraph, END
from langchain_core.messages import ToolMessage

from app.llm import chat_with_tools, chat_stream
from app.agent.tool_schema import get_tool_schema
from app.agent.registry import ToolRegistry
from app.agent.executor import ToolExecutor
from app.agent.tools import SearchTool

# ============================================
# 1. 定义 State（替代 messages 列表）
# ============================================

class AgentState(TypedDict):
    """
    对比旧代码: def run(self, messages): 中的 messages 参数
    operator.add reducer: 每个 Node 返回的新消息自动追加，而非覆盖
    你不再需要手动 messages.append()
    """
    messages: Annotated[list, operator.add]


# ============================================
# 2. 工具初始化（复用你现有的 ToolRegistry + ToolExecutor）
# ============================================

# 初始无知识库，retriever 为 None
search_tool = SearchTool(None)

tool_registry = ToolRegistry()
tool_registry.register(search_tool)

tool_executor = ToolExecutor(tool_registry)


# ============================================
# 3. Node 1: llm_node
# ============================================

def llm_node(state: AgentState) -> dict:
    """
    对比旧代码: agent_executor.py L31-34
        response = chat_with_tools(messages, get_tool_schema())

    从 state["messages"] 读取对话历史，调用 LLM，
    返回的 response（可能带 tool_calls）自动追加到 messages
    """
    response = chat_with_tools(
        state["messages"],
        get_tool_schema()
    )
    # 返回 {"messages": [response]} → operator.add 自动追加
    return {"messages": [response]}


# ============================================
# 4. Node 2: tool_node
# ============================================

def tool_node(state: AgentState) -> dict:
    """
    对比旧代码: agent_executor.py L37-69
        if response.tool_calls:
            messages.append(assistant_msg)
            tool_call = response.tool_calls[0]
            ...
            result = executor.execute(name, arguments)
            messages.append(tool_result)

    从最后一条消息中提取 tool_call，执行工具，返回 ToolMessage
    """
    last_message = state["messages"][-1]

    # DeepSeek API 返回的是对象，用 hasattr 判断
    if hasattr(last_message, "tool_calls"):
        tool_call = last_message.tool_calls[0]
        name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        call_id = tool_call.id
    else:
        # 兼容 dict 格式（LangChain 内部消息）
        tool_call = last_message.tool_calls[0]
        name = tool_call["function"]["name"]
        arguments = json.loads(tool_call["function"]["arguments"])
        call_id = tool_call["id"]

    result = tool_executor.execute(name, arguments)

    # 返回 ToolMessage → operator.add 自动追加到 messages
    return {"messages": [
        ToolMessage(content=str(result), tool_call_id=call_id)
    ]}


# ============================================
# 5. Conditional Edge: should_continue
# ============================================

def should_continue(state: AgentState) -> str:
    """
    对比旧代码: agent_executor.py L37
        if response.tool_calls:
            ...  # 执行工具
        else:
            return response.content  # 结束

    检查最后一条消息是否有 tool_calls
    - 有 → 返回 "tool"（跳转到 tool_node）
    - 无 → 返回 END（结束）
    """
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tool"
    return END


# ============================================
# 6. 构建 Graph（替代 run() 方法）
# ============================================

graph = StateGraph(AgentState)

# 注册节点
graph.add_node("llm", llm_node)
graph.add_node("tool", tool_node)

# 声明边
graph.add_edge("__start__", "llm")      # START → LLM
graph.add_conditional_edges(            # LLM → ?
    "llm",
    should_continue,
    {"tool": "tool", END: END}
)
graph.add_edge("tool", "llm")           # tool → LLM（循环回去）

# 编译成可执行 App
langgraph_app = graph.compile()


# ============================================
# 7. 便捷调用函数（等价于旧版 agent_executor.run()）
# ============================================

def run_agent(messages: list) -> str:
    """
    对比旧代码: agent_executor.run(messages)
    功能完全等价
    """
    result = langgraph_app.invoke({"messages": messages})
    last_message = result["messages"][-1]
    return last_message.content if hasattr(last_message, "content") else str(last_message)


def update_retriever(retriever):
    """
    对比旧代码: agent_executor.update_retriever()
    """
    tool_registry.tools["knowledge_search"].retriever = retriever
