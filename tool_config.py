"""Shared model identifier, prompt and local STDIO server definitions."""
import os
import sys
from pathlib import Path

from mcp import StdioServerParameters
from deployment_config import load_environment, mcp_environment

load_environment()

BASE_DIR = Path(__file__).resolve().parent

MODEL = os.getenv(
    "DEEPSEEK_MODEL",
    "deepseek-chat",
)

SERVERS = {
    "rag": StdioServerParameters(
        command=sys.executable,
        args=[
            str(BASE_DIR / "mcp_stdio_launcher.py"),
            str(BASE_DIR / "rag_mcp_server.py"),
        ],
        cwd=str(BASE_DIR),
        env=mcp_environment(),
    ),

    "utility": StdioServerParameters(
        command=sys.executable,
        args=[
            str(BASE_DIR / "utility_mcp_server.py")
        ],
        cwd=str(BASE_DIR),
    ),
}


SYSTEM_PROMPT = """
你是一个能够使用多个 MCP 工具的 Agent。

工具使用规则：

1. 询问内部知识库、产品文档、账号、
   API Key、文件上传、公司内部信息时，
   优先使用 rag_query。
2. 需要计算时使用 calculator。
3. 需要查询天气时使用 get_weather。
4. 多步任务可以连续调用不同工具。
5. 不要编造工具结果。
6. 如果 RAG 不能回答，不要猜测。
7. 结合当前会话历史理解用户的指代。
"""
