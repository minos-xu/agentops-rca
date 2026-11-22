import re
import jieba


def tokenize(
    text: str
) -> list[str]:

    text = text.lower()

    tokens = jieba.cut(
        text
    )

    return [
        token
        for token in tokens
        if re.search(
            r"[\w\u4e00-\u9fff]",
            token
        )
    ]

def split_by_paragraph(
    text: str
) -> list[str]:

    chunks = [
        part.strip()
        for part in text.split("\n\n")
        if part.strip()
    ]

    return chunks
