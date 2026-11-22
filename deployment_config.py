"""Deployment paths and explicit MCP environment; no Agent business logic."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent


def environment_file() -> Path:
    path = Path(os.getenv("AGENTOPS_ENV_FILE", str(PROJECT_ROOT / ".env"))).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_environment() -> None:
    """Respect injected environment values and never rewrite an environment file."""
    load_dotenv(dotenv_path=environment_file(), override=False)


def data_directory() -> Path:
    load_environment()
    path = Path(os.getenv("AGENTOPS_DATA_DIR", str(PROJECT_ROOT / "data"))).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


# MCP intentionally inherits a small default environment. Forward only the
# settings required by the local RAG model and its DeepSeek client.
MCP_ENV_KEYS = (
    "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "EMBEDDING_MODEL_PATH", "AGENTOPS_OFFLINE",
    "RERANKER_MODEL_PATH", "HF_HOME", "HF_HUB_CACHE", "TRANSFORMERS_CACHE",
    "SENTENCE_TRANSFORMERS_HOME", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE",
    "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS", "TOKENIZERS_PARALLELISM", "PYTHONUNBUFFERED",
)


def mcp_environment() -> dict[str, str]:
    load_environment()
    values = {key: os.environ[key] for key in MCP_ENV_KEYS if key in os.environ}
    values["AGENTOPS_ENV_FILE"] = str(environment_file())
    return values
