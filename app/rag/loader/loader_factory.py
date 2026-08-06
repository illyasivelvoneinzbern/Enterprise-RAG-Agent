import os


from .txt_loader import TxtLoader
from .pdf_loader import PdfLoader
from .markdown_loader import MarkdownLoader



def get_loader(path):


    suffix=os.path.splitext(path)[1]


    if suffix==".txt":

        return TxtLoader()


    elif suffix==".pdf":

        return PdfLoader()


    elif suffix in [
        ".md",
        ".markdown"
    ]:

        return MarkdownLoader()


    else:

        raise Exception(
            "unsupported file"
        )