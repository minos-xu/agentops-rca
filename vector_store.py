import json
from pathlib import Path

import faiss
import numpy as np

from config import (
    INDEX_PATH,
    METADATA_PATH
)


def create_index(
    dimension: int
):

    base_index = (
        faiss.IndexFlatIP(
            dimension
        )
    )

    return faiss.IndexIDMap2(
        base_index
    )


def save_index(
    index,
    state: dict
):

    faiss.write_index(
        index,
        INDEX_PATH
    )

    with open(
        METADATA_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            state,
            file,
            ensure_ascii=False,
            indent=2
        )


def load_state():

    if not Path(
        METADATA_PATH
    ).exists():

        return {
            "next_vector_id": 0,
            "documents": {},
            "records": {}
        }

    with open(
        METADATA_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(
            file
        )


def load_index():

    if not Path(
        INDEX_PATH
    ).exists():

        return None

    return faiss.read_index(
        INDEX_PATH
    )


def add_vectors(
    index,
    embeddings,
    vector_ids
):

    vectors = np.asarray(
        embeddings,
        dtype="float32"
    )

    ids = np.asarray(
        vector_ids,
        dtype="int64"
    )

    faiss.normalize_L2(
        vectors
    )

    index.add_with_ids(
        vectors,
        ids
    )


def remove_vectors(
    index,
    vector_ids
):

    if not vector_ids:
        return

    ids = np.asarray(
        vector_ids,
        dtype="int64"
    )

    index.remove_ids(
        ids
    )
