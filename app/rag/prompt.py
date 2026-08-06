def build_prompt(
    query,
    documents
):

    context="\n".join(
    [
    f"""
    内容:
    {doc['text']}

    来源:
    {doc['metadata']['source']}
    """
    for doc in documents
    ]
    )


    prompt=f"""
你是企业知识库助手。

你的任务是根据【知识库资料】回答用户问题。

严格要求：
1. 只能使用下面提供的资料回答。
2. 如果资料中存在答案，必须回答。
3. 不要回答不知道，除非资料完全没有相关信息。

知识库资料:
{context}


用户问题:
{query}


请直接回答：
"""

    return prompt