from sentence_transformers import SentenceTransformer


model = SentenceTransformer(
    "BAAI/bge-small-zh-v1.5"
)


def embed_texts(texts):

    vectors = model.encode(
        texts
    )

    return vectors