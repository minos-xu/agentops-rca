import pickle
from pathlib import Path


EMBEDDING_STORE_PATH = (
    "embedding_store.pkl"
)


def load_embedding_store() -> dict:

    path = Path(
        EMBEDDING_STORE_PATH
    )

    if not path.exists():

        return {}

    with open(
        path,
        "rb"
    ) as file:

        return pickle.load(
            file
        )


def save_embedding_store(
    store: dict
):

    with open(
        EMBEDDING_STORE_PATH,
        "wb"
    ) as file:

        pickle.dump(
            store,
            file
        )