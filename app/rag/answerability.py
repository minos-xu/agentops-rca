import json

from app.rag.retriever import (
    retrieve_prefilter,
)

from app.rag.reranker import (
    rerank
)

from app.core.config import (
    client
)



from app.rag.eval_dataset import (
    EVAL_DATASET,
    NO_ANSWER_DATASET
)
def judge_answerability(
    question: str,
    context: str
) -> dict:

    prompt = f"""
你是一个知识库问答系统的资料判断器。

你的任务不是回答问题，
而是判断给定资料是否包含足够的信息回答用户问题。

要求：

1. 只能根据 Context 判断。
2. 不允许使用你自己的知识补充。
3. 如果 Context 只是主题相关，但没有真正提供答案，也必须判断为 false。
4. 如果 Context 明确包含回答问题所需的信息，判断为 true。
5. 只返回 JSON。

Question:
{question}

Context:
{context}

返回格式：

{{
    "answerable": true,
    "reason": "简短原因"
}}
"""

    response = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    content = (
        response
        .choices[0]
        .message
        .content
    )

    return json.loads(
        content
    )



def check_results_answerability(
    question: str,
    results: list[dict]
) -> dict:

    if not results:

        return {
            "answerable": False,
            "reason": "没有检索到候选资料"
        }

    context = build_context(
        results
    )

    return judge_answerability(
        question,
        context
    )

def build_context(
    results: list[dict]
) -> str:

    parts = []

    for index, result in enumerate(
        results,
        start=1
    ):

        parts.append(
            (
                f"[资料 {index}]\n"
                f'{result["text"]}'
            )
        )

    return "\n\n".join(
        parts
    )

def evaluate_answerability():

    answerable_correct = 0
    no_answer_correct = 0

    print(
        "\n===== Answerability Evaluation ====="
    )

    for item in EVAL_DATASET:

        question = (
            item["question"]
        )

        candidates = retrieve_prefilter(
            question,
            top_k=10,
            min_score=0,
            filters=None
        )

        results = rerank(
            question,
            candidates,
            top_k=3
        )

        judge_result = (
            check_results_answerability(
                question,
                results
            )
        )

        predicted = (
            judge_result[
                "answerable"
            ]
        )

        if predicted:
            answerable_correct += 1

        print(
            question,
            "→",
            predicted,
            judge_result["reason"]
        )

    for item in NO_ANSWER_DATASET:

        question = (
            item["question"]
        )

        candidates = retrieve_prefilter(
            question,
            top_k=10,
            min_score=0,
            filters=None
        )

        results = rerank(
            question,
            candidates,
            top_k=3
        )

        judge_result = (
            check_results_answerability(
                question,
                results
            )
        )

        predicted = (
            judge_result[
                "answerable"
            ]
        )

        if not predicted:
            no_answer_correct += 1

        print(
            question,
            "→",
            predicted,
            judge_result["reason"]
        )

    answerable_rate = (
        answerable_correct
        / len(EVAL_DATASET)
    )

    no_answer_rate = (
        no_answer_correct
        / len(NO_ANSWER_DATASET)
    )

    print(
        "\nAnswerable Accuracy:",
        f"{answerable_rate:.2%}"
    )

    print(
        "No-Answer Accuracy:",
        f"{no_answer_rate:.2%}"
    )

if __name__=="__main__":

    evaluate_answerability()