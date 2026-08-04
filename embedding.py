from sentence_transformers import SentenceTransformer


model = SentenceTransformer(
    "BAAI/bge-small-zh-v1.5"
)


texts=[
    "苹果很好吃",
    "苹果味道不错",
    "今天北京天气很好"
]


embeddings=model.encode(texts)


for text,vector in zip(texts,embeddings):

    print(text)

    print(vector[:5])

    print("----------------")
from sklearn.metrics.pairwise import cosine_similarity


score=cosine_similarity(
    [embeddings[0]],
    [embeddings[1]]
)


print(score)
