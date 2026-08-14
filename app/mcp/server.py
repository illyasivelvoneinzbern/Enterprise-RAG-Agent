"""
app/mcp/server.py — Day 2: 把 knowledge_search 封装为独立 MCP Server

背景：
  第 4 周的 SearchTool 是硬编码在 Agent 进程内的工具（app/agent/tools.py），
  Day 2 用 MCP（Model Context Protocol）把它升级为「独立进程运行的标准化工具服务」。

核心概念：
  - MCP Server = 工具提供方，作为独立进程运行（默认 stdio 传输）
  - @server.tool() 装饰器把 Python 函数自动注册为 MCP 工具
  - 客户端通过协议 tools/list 发现工具、tools/call 调用工具
  - 工具与 Agent 彻底解耦：Agent 侧零改动即可新增/替换工具

关于 mcp 版本：
  项目 venv 中安装的是 mcp 2.0.0（2026 新版，已移除 FastMCP）。
  FastMCP → MCPServer，用法几乎一致：server.tool() 装饰器 + server.run()。
  若后续升级到旧版（1.x）可改回 from mcp.server.fastmcp import FastMCP。

用法（stdio 启动，供 client.py 拉起子进程）：
  venv\\Scripts\\python.exe -m app.mcp.server
  或
  venv\\Scripts\\python.exe app/mcp/server.py
"""

import json
import os
import sys

from mcp.server.mcpserver import MCPServer

# 直接运行本脚本时（python app/mcp/server.py），Python 只把脚本所在目录
# app/mcp 加入 sys.path，导致 app 包不可见。这里把项目根目录补进 sys.path，
# 保证 import app.rag.* 无论用 -m 还是直接运行都能成功。
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.rag.hybrid_retriever import build_hybrid_retriever

# 企业知识库文件路径（相对项目根目录）
KNOWLEDGE_FILE = "data/employee_policy.txt"


def _build_retriever():
    """
    构建底层检索器。

    使用 build_hybrid_retriever（BM25 + FAISS + RRF 融合，见
    app/rag/hybrid_retriever.py）。
    use_cross_encoder 保持默认 False → 用旧字符重合 Reranker，
    避免加载 bge-reranker-v2-m3 大模型拖慢测试。
    """
    return build_hybrid_retriever(KNOWLEDGE_FILE)


# 全局构建一次，进程生命周期内复用（不重复加载 embedding 模型）
retriever = _build_retriever()

# 创建 MCP Server 实例，服务名 "knowledge"（工具提供方身份标识）
server = MCPServer("knowledge")


@server.tool()
def knowledge_search(query: str) -> str:
    """
    查询企业知识库，返回与问题相关的政策片段。

    可查询年假、病假、薪资、入职、试用期等员工政策，
    例如："年假几天"、"工资什么时候发"、"入职需要什么材料"。

    参数:
        query: 用户的问题或查询关键词（如 "年假几天"）

    返回:
        JSON 字符串（ensure_ascii=False），包含命中的政策片段列表，
        每段含 text（原文）、metadata（元信息）、rrf_score（融合得分）。
    """
    docs = retriever.retrieve(query, top_k=3)
    return json.dumps(docs, ensure_ascii=False)


if __name__ == "__main__":
    # stdio 方式启动（默认传输），等待 MCP Client 通过标准输入/输出通信
    server.run(transport="stdio")
