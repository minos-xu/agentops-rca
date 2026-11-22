import numpy as np
import faiss

from embedder import (
    embed_text
)

from vector_store import (
    load_index,
    load_state
)

from embedding_store import (
    load_embedding_store
)

from filters import (
    match_metadata
)
index = load_index()
state = load_state()

embedding_store = (
    load_embedding_store()
)

def cosine_similarity(
    vector_a,
    vector_b
):

    return np.dot(
        vector_a,
        vector_b
    ) / (
        np.linalg.norm(vector_a)
        *
        np.linalg.norm(vector_b)
    )

def get_candidate_vector_ids(
    filters: dict | None
) -> list[int]:

    candidate_ids = []

    for vector_id, record in (
        state["records"].items()
    ):

        metadata = (
            record["metadata"]
        )

        if match_metadata(
            metadata,
            filters
        ):

            candidate_ids.append(
                int(vector_id)
            )
    # print(
    #     "候选向量数量：",
    #     len(candidate_ids)
    # )
    return candidate_ids


def retrieve_prefilter(
    question: str,
    top_k: int = 10,
    min_score: float = 0.0,
    filters: dict | None = None
) -> list[dict]:

    query_embedding = (
        embed_text(
            question
        )
    )

    candidate_ids = (
        get_candidate_vector_ids(
            filters
        )
    )

    results = []

    for vector_id in candidate_ids:

        vector = embedding_store.get(
            vector_id
        )

        if vector is None:

            print(
                f"警告：vector_id={vector_id} "
                f"缺少 embedding"
            )

            continue

        score = cosine_similarity(
            query_embedding,
            vector
        )

        if score < min_score:
            continue

        record = (
            state[
                "records"
            ][
                str(vector_id)
            ]
        )

        results.append(
            {
                "id":
                    vector_id,

                "text":
                    record["text"],

                "metadata":
                    record["metadata"],

                "score":
                    float(score)
            }
        )

    results.sort(
        key=lambda item:
            item["score"],
        reverse=True
    )

    return results[:top_k]



def retrieve(
    question: str,
    top_k: int = 10,
    min_score: float = 0,
    filters: dict | None = None
) -> list[dict]:

    query_embedding = (
        embed_text(
            question
        )
    )

    query_vector = np.asarray(
        [query_embedding],
        dtype="float32"
    )

    faiss.normalize_L2(
        query_vector
    )

    search_k = max(
        top_k * 5,
        top_k
    )

    print(
        "总向量数量：",
        index.ntotal
    )

    candidate_ids = (
        get_candidate_vector_ids(
            filters
        )
    )

    print(
        "过滤后候选数量：",
        len(candidate_ids)
    )

    scores, ids = index.search(
        query_vector,
        search_k
    )

    results = []

    for score, vector_id in zip(
        scores[0],
        ids[0]
    ):

        if vector_id == -1:
            continue

        if score < min_score:
            continue

        record = (
            state[
                "records"
            ].get(
                str(vector_id)
            )
        )

        if record is None:
            continue

        metadata = (
            record["metadata"]
        )

        if not match_metadata(
            metadata,
            filters
        ):
            continue

        results.append(
            {
                "id":
                    int(vector_id),

                "text":
                    record["text"],

                "metadata":
                    metadata,

                "score":
                    float(score)
            }
        )

        if len(results) >= top_k:
            break

    return results
