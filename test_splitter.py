from app.rag.splitter import split_documents


documents=[

{
"text":
"员工入职一年后享受年假。" * 20,

"metadata":
{
"source":"test.txt",
"page":1
}

}

]


chunks=split_documents(
    documents,
    chunk_size=50,
    overlap=10
)


for c in chunks:

    print("----------------")

    print(c["text"])

    print(c["metadata"])