class MarkdownLoader:


    def load(
        self,
        path
    ):

        with open(
            path,
            encoding="utf-8"
        ) as f:

            text=f.read()


        return [
        {
        "text":text,

        "metadata":
        {
            "source":path,
            "page":1
        }
        }
        ]