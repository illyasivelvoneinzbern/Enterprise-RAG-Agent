class SearchTool:


    name = "knowledge_search"


    description = """
    查询企业知识库。
    当用户询问企业政策、
    制度、流程时使用。
    """


    def __init__(self, retriever):

        self.retriever = retriever


    def run(self, query):

        return self.retriever.retrieve(
            query,
            top_k=3
        )