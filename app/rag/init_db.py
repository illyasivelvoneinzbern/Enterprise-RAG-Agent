from .splitter import split_text
from .embedding import model
from .vectorstore import VectorStore
from .retriever import Retriever



text="""

公司员工福利政策如下。

员工入职一年后享受年假。

普通员工一年10天年假。

"""


documents = split_text(
    text,
    source="employee_policy.txt",
    page=1,
    chunk_size=50,
    overlap=10
)



texts=[
    doc["text"]
    for doc in documents
]


vectors=model.encode(
    texts
)



store=VectorStore(
    dimension=len(vectors[0])
)



store.add(
    vectors,
    documents
)



retriever=Retriever(
    store,
    model
)
print(documents)