import os

from deployment_config import load_environment
from openai import OpenAI




load_environment()

EMBEDDINGS_PATH = (
    "embeddings.npy"
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


DOCUMENT_DIR = "documents"

INDEX_PATH = "vector.index"

METADATA_PATH = "metadata.json"

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL
)
