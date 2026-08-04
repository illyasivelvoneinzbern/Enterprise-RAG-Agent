from sentence_transformers import SentenceTransformer
from vectorstore import VectorStore


model=SentenceTransformer(
    "all-MiniLM-L6-v2"
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


query="我有多少年假"


query_vector=model.encode(
    query
)


results=store.search(
    query_vector,
    top_k=3
)


for r in results:

    print(r)