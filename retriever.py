from sentence_transformers import SentenceTransformer


class Retriever:


    def __init__(
        self,
        vectorstore,
        model
    ):

        self.vectorstore = vectorstore

        self.model = model



    def retrieve(
        self,
        query,
        top_k=3
    ):

        query_vector = self.model.encode(
            query
        )


        results = self.vectorstore.search(
            query_vector,
            top_k
        )


        return results