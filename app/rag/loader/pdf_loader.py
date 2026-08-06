from pypdf import PdfReader



class PdfLoader:


    def load(
        self,
        path
    ):


        reader=PdfReader(
            path
        )


        documents=[]


        for index,page in enumerate(
            reader.pages
        ):


            text=page.extract_text()


            documents.append(
            {

                "text":text,

                "metadata":
                {

                    "source":path,

                    "page":index+1

                }

            })


        return documents