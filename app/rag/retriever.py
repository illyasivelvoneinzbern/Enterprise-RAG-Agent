from sentence_transformers import SentenceTransformer


class Retriever:


    def __init__(
        self,
        vectorstore,
        model,
        reranker=None
    ):

        self.vectorstore = vectorstore

        self.model=model

        self.reranker=reranker



    def retrieve(
        self,
        query,
        top_k=3
    ):

        query_vector = self.model.encode(
            [query]
        )


        results = self.vectorstore.search(
            query_vector,
            top_k=10
        )


        if self.reranker:

            results=self.reranker.rerank(
                query,
                results,
                top_k
            )


        return results