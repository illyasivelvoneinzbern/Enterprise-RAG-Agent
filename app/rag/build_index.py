from .loader.loader_factory import get_loader
from .splitter import split_documents
from .embedding import model
from .vectorstore import VectorStore
from .retriever import Retriever
from .reranker import Reranker


def build_knowledge_base(
    file_path
):


    # 1.读取文件

    loader=get_loader(
        file_path
    )


    documents=loader.load(
        file_path
    )


    # 2.chunk

    chunks = split_documents(
        documents
    )


    # 3.embedding

    vectors=model.encode(
        [
            c["text"]
            for c in chunks
        ]
    )


    # 4.vector store

    store=VectorStore(
        dimension=len(vectors[0])
    )


    store.add(
        vectors,
        chunks
    )


    # 5.retriever
    reranker=Reranker()


    retriever=Retriever(
        store,
        model,
        reranker
    )


    return retriever