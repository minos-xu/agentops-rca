import os
from pathlib import Path

from sentence_transformers import (
    CrossEncoder
)


MODEL_PATH = (
    os.getenv(
        "RERANKER_MODEL_PATH",
        str(
            Path.home()
            / "models"
            / "bge-reranker-v2-m3"
        )
    )
)


reranker_model = CrossEncoder(
    MODEL_PATH,
    local_files_only=True
)


def rerank(
    question: str,
    candidates: list[dict],
    top_k: int = 3
) -> list[dict]:

    if not candidates:
        return []

    pairs = [
        [
            question,
            candidate["text"]
        ]
        for candidate in candidates
    ]

    scores = reranker_model.predict(
        pairs
    )

    results = []

    for candidate, score in zip(
        candidates,
        scores
    ):

        item = candidate.copy()

        item["rerank_score"] = (
            float(score)
        )

        results.append(
            item
        )

    results.sort(
        key=lambda item:
            item["rerank_score"],
        reverse=True
    )

    return results[:top_k]
