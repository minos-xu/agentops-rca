from app.core.config import (
    client,
    LLM_MODEL
)


def build_context(
    results: list[dict]
) -> str:

    parts = []

    for result in results:

        metadata = (
            result["metadata"]
        )

        part = f"""
来源文件：
{metadata["source"]}

文档 ID：
{metadata["document_id"]}

Chunk：
{metadata["chunk_index"]}

内容：
{result["text"]}
"""

        parts.append(
            part.strip()
        )

    return "\n\n---\n\n".join(
        parts
    )


def build_sources(
    results: list[dict]
) -> str:

    seen = set()
    lines = []

    for result in results:

        metadata = (
            result["metadata"]
        )

        document_id = (
            metadata[
                "document_id"
            ]
        )

        if document_id in seen:
            continue

        seen.add(
            document_id
        )

        lines.append(
            f'- {metadata["source"]}'
        )

    return "\n".join(
        lines
    )

def generate_answer(
    question: str,
    results: list[dict]
) -> str:

    if not results:
        return (
            "根据现有资料无法确定。"
        )

    context = build_context(
        results
    )

    response = (
        client
        .chat
        .completions
        .create(
            model=LLM_MODEL,

            messages=[
                {
                    "role": "system",
                    "content": """
你是产品帮助中心知识助手。

只能根据提供的参考资料回答用户问题。

不得编造规则、数字、时间、条件或来源。

如果参考资料不足以回答问题，
请明确回答：
“根据现有资料无法确定。”

只回答问题本身，
不要生成来源列表。
"""
                },

                {
                    "role": "user",
                    "content": f"""
参考资料：

{context}

用户问题：

{question}
"""
                }
            ],

            stream=False
        )
    )

    return (
        response
        .choices[0]
        .message
        .content
    )