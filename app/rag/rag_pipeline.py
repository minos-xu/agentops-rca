from app.rag.retriever import (
    retrieve_prefilter
)

from app.rag.reranker import (
    rerank
)

from app.rag.answerability import (
    check_results_answerability
)

from app.rag.generator import (
    generate_answer,
    build_sources
)


CANDIDATE_K = 10
FINAL_K = 3


def run_rag(
    question: str
) -> dict:

    # =========================
    # 1. Retrieve
    # =========================

    candidates = retrieve_prefilter(
        question,
        top_k=CANDIDATE_K,
        min_score=0,
        filters=None
    )

    if not candidates:

        return {
            "answer":
                "根据现有资料无法确定。",

            "sources":
                [],

            "answerable":
                False,

            "reason":
                "没有检索到候选资料"
        }

    # =========================
    # 2. Rerank
    # =========================

    results = rerank(
        question,
        candidates,
        top_k=FINAL_K
    )

    # =========================
    # 3. Answerability
    # =========================

    judge_result = (
        check_results_answerability(
            question,
            results
        )
    )

    if not judge_result[
        "answerable"
    ]:

        return {
            "answer":
                "根据现有资料无法确定。",

            "sources":
                [],

            "answerable":
                False,

            "reason":
                judge_result[
                    "reason"
                ]
        }

    # =========================
    # 4. Generate
    # =========================

    answer = generate_answer(
        question,
        results
    )

    sources = build_sources(
        results
    )

    return {
        "answer":
            answer,

        "sources":
            sources,

        "answerable":
            True,

        "reason":
            judge_result["reason"],

        "debug": {
            "candidate_count":
                len(candidates),

            "reranked_count":
                len(results),

            "top_rerank_score":
                (
                    results[0][
                        "rerank_score"
                    ]
                    if results
                    else None
                )
        }
    }