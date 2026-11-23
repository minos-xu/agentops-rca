import os

from app.core.deployment_config import load_environment, PROJECT_ROOT
from openai import OpenAI




load_environment()

EMBEDDINGS_PATH = (
    str(PROJECT_ROOT / "embeddings.npy")
)

DEEPSEEK_API_KEY = os.getenv(
    "DEEPSEEK_API_KEY"
)

DEEPSEEK_BASE_URL = (
    "http://127.0.0.1:9/v1"
    if os.getenv("AGENTOPS_OFFLINE") == "1"
    else "https://api.deepseek.com/v1"
)

LLM_MODEL = (
    "deepseek-v4-flash"
)

EMBEDDING_MODEL = (
    os.getenv("EMBEDDING_MODEL_PATH", "").strip() or "BAAI/bge-small-zh-v1.5"
)


DOCUMENT_DIR = str(PROJECT_ROOT / "documents")

INDEX_PATH = str(PROJECT_ROOT / "vector.index")

METADATA_PATH = str(PROJECT_ROOT / "metadata.json")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL
)
