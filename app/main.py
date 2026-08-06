from fastapi import FastAPI
from pydantic import BaseModel
from fastapi import UploadFile, File
from app.rag_agent import RAGAgent
from app.rag.build_index import build_knowledge_base


app = FastAPI()


rag_agent = RAGAgent(
    None
)


app = FastAPI()



class RAGRequest(BaseModel):

    question:str



@app.get("/")
def root():

    return {
        "message":
        "Enterprise RAG Agent Running"
    }



@app.post("/rag/chat")
def rag_chat(
    req:RAGRequest
):

    answer = rag_agent.answer(
        req.question
    )


    return {
        "answer":answer
    }
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