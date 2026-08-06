class Reranker:


    def __init__(self):
        pass



    def rerank(
        self,
        query,
        documents,
        top_k=3
    ):

        scores=[]


        for doc in documents:

            text = doc["text"]


            score = self.score(
                query,
                text
            )


            scores.append(
                (
                    score,
                    doc
                )
            )


        scores.sort(
            key=lambda x:x[0],
            reverse=True
        )


        return [
            doc
            for score,doc in scores[:top_k]
        ]



    def score(
        self,
        query,
        text
    ):

        return len(
            set(query)
            &
            set(text)
        )