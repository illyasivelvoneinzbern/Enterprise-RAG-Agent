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
        embeddings,
        documents
    ):

        vectors=np.array(
            embeddings
        ).astype(
            "float32"
        )


        self.index.add(
            vectors
        )


        self.documents.extend(
            documents
        )



    def search(
        self,
        query_embedding,
        top_k=3
    ):

        query=np.array(
            [query_embedding]
        ).astype(
            "float32"
        )


        distances, indexes = self.index.search(
            query,
            top_k
        )


        results=[]


        for distance,idx in zip(
            distances[0],
            indexes[0]
        ):

            results.append(
                {
                    "text":self.documents[idx],
                    "score":float(distance)
                }
            )


        return results