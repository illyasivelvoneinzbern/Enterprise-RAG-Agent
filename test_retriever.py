from app.rag.build_index import build_knowledge_base


# 1. 构建知识库
retriever = build_knowledge_base(
    "data/employee_policy.txt"
)


# 2. 测试问题

query = "员工什么时候可以享受年假？"


# 3. 检索

results = retriever.retrieve(
    query,
    top_k=3
)


# 4. 打印结果

print("="*50)

print("问题:")
print(query)


print("\n检索结果:")


for i,doc in enumerate(results):

    print("\n-----")

    print(
        "排名:",
        i+1
    )

    print(
        "内容:",
        doc["text"]
    )


    print(
        "来源:",
        doc["metadata"]
    )