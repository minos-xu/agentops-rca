from pathlib import Path
from app.core.deployment_config import PROJECT_ROOT

CATEGORY_MAP = {
    "account_manual.txt":
        "account",

    "api_manual.txt":
        "api",

    "refund_policy.txt":
        "refund",

    "security_guide.txt":
        "security",

    "upload_manual.txt":
        "upload"
}

def load_document(
    file_path: Path
) -> str:

    return file_path.read_text(
        encoding="utf-8"
    )


def load_documents(
    directory: str
) -> list[dict]:

    documents = []

    directory_path = Path(
        directory
    )

    for file_path in sorted(
        directory_path.glob("*.txt")
    ):

        text = load_document(
            file_path
        )

        documents.append(
            {
                "document_id":
                    file_path.name,

                "source":
                    str(file_path.relative_to(PROJECT_ROOT))
                    if directory_path == PROJECT_ROOT / "documents"
                    else str(file_path),

                "category":
                    CATEGORY_MAP.get(
                        file_path.name,
                        "other"
                    ),

                "text":
                    text
            }
        )

    return documents