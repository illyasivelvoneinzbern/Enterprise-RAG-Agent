"""
app/mcp/client.py — Day 2: 通过 MCP Client 调用 knowledge_search

演示 MCP 三层架构中的 Client 侧核心流程：
  1. initialize  —— 握手（确认协议版本与能力）
  2. list_tools  —— 工具发现（查看 Server 暴露了哪些工具）
  3. call_tool   —— 工具调用（远程调用 knowledge_search）

对比第 4 周硬编码调用：
  旧: SearchTool().run("年假几天")   → Agent 进程内直接调用
  新: ClientSession.call_tool(...)   → 协议远程调用独立进程

用法：
  python -m app.mcp.client
  或
  python app/mcp/client.py
"""

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Windows 控制台默认 GBK 编码，无法打印 emoji / 部分中文标点。
# 这里把 stdout 重配置为 UTF-8，保证终端正常显示。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def build_server_params() -> StdioServerParameters:
    """
    配置如何拉起 MCP Server 子进程。

    用 sys.executable（当前解释器）启动，确保 Client 与 Server
    使用同一个 venv python，避免系统 python 缺少 mcp 库。
    """
    return StdioServerParameters(
        command=sys.executable,
        args=["app/mcp/server.py"],
    )


async def call_knowledge_search(query: str) -> str:
    server_params = build_server_params()

    # ① 建立 stdio 双向管道：read/write 分别对应 Server 的 stdout/stdin
    async with stdio_client(server_params) as (read, write):
        # ② 创建会话，协议消息在会话内收发
        async with ClientSession(read, write) as session:
            # ③ 握手：初始化协议，协商版本与能力
            await session.initialize()

            # ④ 工具发现：列出 Server 暴露的所有工具
            tools = await session.list_tools()
            print("=" * 60)
            print("🔧 工具发现 (tools/list) —— MCP Server 暴露的工具：")
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description.strip()}")
                print(f"    输入 Schema: {tool.input_schema}")
            print("=" * 60)

            # ⑤ 工具调用：远程调用 knowledge_search
            result = await session.call_tool(
                "knowledge_search", {"query": query}
            )
            return result.content[0].text


async def main():
    query = "年假几天"
    print(f"🔍 开始端到端 MCP 调用，查询: {query}")
    text = await call_knowledge_search(query)

    print("\n📄 工具调用 (tools/call) 返回的检索结果：")
    print("-" * 60)
    print(text)
    print("-" * 60)


if __name__ == "__main__":
    asyncio.run(main())
