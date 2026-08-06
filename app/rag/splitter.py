def split_documents(
    documents,
    chunk_size=100,
    overlap=20
):

    chunks=[]


    for doc in documents:

        text = doc["text"]

        metadata = doc["metadata"]


        start=0


        while start < len(text):


            end=min(
                start+chunk_size,
                len(text)
            )


            chunk_text=text[start:end]


            chunks.append(
                {
                    "text":chunk_text,

                    "metadata":metadata.copy()
                }
            )


            if end == len(text):
                break


            start=end-overlap


    return chunks