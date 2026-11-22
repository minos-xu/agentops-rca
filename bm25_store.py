import pickle
from pathlib import Path

from rank_bm25 import BM25Okapi

from chunker import tokenize
BM25_STORE_PATH = (
    "bm25_store.pkl"
)


def build_bm25_store(
    records: dict
):

    vector_ids = []
    tokenized_corpus = []

    for vector_id, record in (
        records.items()
    ):

        vector_ids.append(
            int(vector_id)
        )

        tokens = tokenize(
            record["text"]
        )

        tokenized_corpus.append(
            tokens
        )

    bm25 = BM25Okapi(
        tokenized_corpus
    )

    store = {
        "vector_ids":
            vector_ids,

        "bm25":
            bm25
    }

    return store


def save_bm25_store(
    store: dict
):

    with open(
        BM25_STORE_PATH,
        "wb"
    ) as file:

        pickle.dump(
            store,
            file
        )


def load_bm25_store():

    path = Path(
        BM25_STORE_PATH
    )

    if not path.exists():
        return None

    with open(
        path,
        "rb"
    ) as file:

        return pickle.load(
            file
        )

# if __name__ == "__main__":

#     text = (
#         "普通开发者一分钟最多调用多少次 API？"
#     )

#     print(
#         tokenize(text)
#     )