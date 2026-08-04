def split_text(
    text,
    chunk_size=100,
    overlap=20
):

    chunks=[]

    start=0


    while start < len(text):

        end=min(
            start+chunk_size,
            len(text)
        )


        chunks.append(
            text[start:end]
        )


        if end == len(text):
            break


        start=end-overlap


    return chunks
if __name__=="__main__":

    text="""
    公司员工福利政策如下。
    员工入职一年后享受年假。
    普通员工一年10天年假。
    """

    chunks=split_text(
        text,
        chunk_size=20,
        overlap=5
    )


    for i,c in enumerate(chunks):

        print(
            "chunk",
            i
        )

        print(c)

        print("----------------")
def create_chunk(
    text,
    source,
    page
):

    return {
        "text":text,
        "source":source,
        "page":page
    }