from sentence_transformers import SentenceTransformer

from vectorstore import VectorStore

from retriever import Retriever

from prompt import build_prompt

from llm import chat

model=SentenceTransformer(
    "BAAI/bge-small-zh-v1.5"
)



documents=[

"员工入职一年后享受10天年假",

"工资每个月15号发放",

"公司下午六点下班"

]



vectors=model.encode(
    documents
)



store=VectorStore(
    dimension=512
)


store.add(
    vectors,
    documents
)



retriever=Retriever(
    store,
    model
)



query="我有多少年假"


docs=retriever.retrieve(
    query
)



prompt=build_prompt(
    query,
    docs
)

docs=retriever.retrieve(
    query
)


prompt=build_prompt(
    query,
    docs
)

answer=chat(
    prompt
)


print(answer)