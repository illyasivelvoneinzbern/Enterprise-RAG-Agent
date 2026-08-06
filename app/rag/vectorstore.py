import faiss
import numpy as np


class VectorStore:


    def __init__(self, dimension):

        self.index = faiss.IndexFlatL2(
            dimension
        )

        self.documents=[]



    def add(
        self,
        vectors,
        documents
    ):

        self.index.add(
            vectors
        )


        self.documents.extend(
            documents
        )

    def search(
    self,
    query_vector,
    top_k
    ):


        distances, indexes = self.index.search(
            query_vector,
            top_k
        )


        results=[]


        for idx in indexes[0]:

            if idx == -1:
                continue

            results.append(
                self.documents[idx]
            )

        return results