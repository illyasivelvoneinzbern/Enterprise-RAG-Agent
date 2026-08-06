from .base import BaseLoader



class TxtLoader(BaseLoader):


    def load(
        self,
        path
    ):


        with open(
            path,
            "r",
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