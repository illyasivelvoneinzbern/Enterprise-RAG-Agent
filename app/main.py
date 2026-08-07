from fastapi import FastAPI
from pydantic import BaseModel
from fastapi import UploadFile, File
from app.rag_agent import RAGAgent
from app.rag.build_index import build_knowledge_base
from app.memory.session_memory import SessionMemoryManager
from fastapi.responses import StreamingResponse
from app.agent.tools import SearchTool
from app.agent.registry import ToolRegistry
from app.agent.executor import ToolExecutor
from app.agent.agent_executor import AgentExecutor



# =========================
# Memory管理器
# =========================

memory_manager = SessionMemoryManager()


# =========================
# 初始化Agent
# =========================

tool_registry = ToolRegistry()


# 初始没有知识库
search_tool = SearchTool(
    None
)


tool_registry.register(
    search_tool
)



tool_executor = ToolExecutor(
    tool_registry
)



agent_executor = AgentExecutor(
    tool_executor
)



rag_agent = RAGAgent(
    None,
    agent_executor
)

# =========================
# FastAPI
# =========================

app = FastAPI()



# =========================
# 请求Schema
# =========================

class RAGRequest(BaseModel):

    session_id: str

    question: str



# =========================
# 首页
# =========================

@app.get("/")
def root():

    return {
        "message":
        "Enterprise RAG Agent Running"
    }



# =========================
# Chat接口
# =========================

@app.post("/rag/chat")
def rag_chat(
    req:RAGRequest
):


    # 根据用户session获取独立Memory

    memory = memory_manager.get_memory(
        req.session_id
    )


    # 给当前请求绑定Memory

    rag_agent.memory = memory



    answer = rag_agent.answer(
        req.question,
    )


    return {

        "answer":answer

    }

@app.post("/rag/chat/stream")
def rag_chat_stream(
    req:RAGRequest
):

    memory = memory_manager.get_memory(
        req.session_id
    )


    rag_agent.memory = memory


    return StreamingResponse(
        rag_agent.stream_answer(
            req.question
        ),
        media_type="text/plain"
    )

# =========================
# 上传知识库
# =========================

@app.post("/upload")
async def upload(
    file: UploadFile = File(...)
):


    path = f"data/{file.filename}"



    with open(
        path,
        "wb"
    ) as f:


        f.write(
            await file.read()
        )



    retriever = build_knowledge_base(
        path
    )


    rag_agent.update_retriever(
        retriever
    )


    return {

        "filename":file.filename

    }