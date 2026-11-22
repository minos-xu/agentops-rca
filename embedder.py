import os

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from sentence_transformers import (
    SentenceTransformer
)

from config import (
    EMBEDDING_MODEL
)


embedding_model = (
    SentenceTransformer(
        EMBEDDING_MODEL
    )
)


def embed_text(
    text: str
):

    return embedding_model.encode(
        text
    )


def embed_texts(
    texts: list[str]
):

    return embedding_model.encode(
        texts
    )