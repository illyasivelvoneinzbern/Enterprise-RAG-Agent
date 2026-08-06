from app.rag.prompt import build_prompt
from app.llm import chat


class RAGAgent:


    def __init__(
        self,
        retriever
    ):

        self.retriever = retriever



    def answer(
        self,
        query
    ):

        documents = self.retriever.retrieve(
            query,
            top_k=3
        )


        prompt = build_prompt(
            query,
            documents
        )


        response = chat(
            prompt
        )


        sources = []

        seen = set()


        for doc in documents:

            metadata = doc["metadata"]


            key = (
                metadata["source"],
                metadata.get("page")
            )


            if key not in seen:

                seen.add(key)

                sources.append(
                    metadata
                )


        return {
            "answer": response,

            "sources": sources
        }


    def update_retriever(
        self,
        retriever
    ):

        self.retriever = retriever