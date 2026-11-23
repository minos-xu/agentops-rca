"""Lesson 55: persistent FastAPI runtime reusing the *unchanged* Lesson 53 graph.

Single-worker, loopback-only training demo. No production monitoring or actions.
"""
from __future__ import annotations

import asyncio
import os
import secrets
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from app.core.deployment_config import PROJECT_ROOT

from app.agent.runtime import AgentOpsRuntime, APIProblem
from app.storage.postgres_store import SessionRepository, PostgresSimulationAudit


class PostgresAgentOpsRuntime(AgentOpsRuntime):
    def __init__(self):
        super().__init__()
        self.repository: SessionRepository | None = None

    async def start(self) -> None:
        if self.graph is not None:
            return
        # Install add-on without automatically upgrading the existing LangGraph/MCP.
        os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
        from mcp import Client, StdioServerParameters
        from openai import AsyncOpenAI
        from dotenv import load_dotenv
        import psycopg
        from psycopg.rows import dict_row
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from app.memory.memory_config import MEMORY_DIR, MEMORY_FILE, SERVERS, MODEL
        from app.agent.workflow import create_graph
        from app.tools.observability_mcp_client import discover_observability_tools
        from app.tools.mcp_tool_runtime import MCPToolRuntime
        from app.memory.memory_store import MemoryStore
        from app.memory.memory_retriever import SemanticMemoryRetriever

        load_dotenv()
        dsn = os.getenv("POSTGRES_DSN", "").strip()
        if not dsn or not dsn.startswith(("postgresql://", "postgres://")):
            raise RuntimeError("必须在 .env 配置 POSTGRES_DSN=postgresql://... (本地PostgreSQL)")
        key = os.getenv("DEEPSEEK_API_KEY")
        if not key:
            raise RuntimeError("缺少 DEEPSEEK_API_KEY（沿用之前课程的 .env）")

        stack = AsyncExitStack()
        try:
            saver = await stack.enter_async_context(AsyncPostgresSaver.from_conn_string(dsn))
            await saver.setup()

            session_conn = await stack.enter_async_context(
                await psycopg.AsyncConnection.connect(
                    dsn, autocommit=True, row_factory=dict_row,
                )
            )
            repository = SessionRepository(session_conn)
            await repository.setup()
            sessions = await repository.load()

            audit = await asyncio.to_thread(PostgresSimulationAudit, dsn)
            stack.callback(audit.close)
            llm = AsyncOpenAI(api_key=key, base_url="https://api.deepseek.com")
            stack.push_async_callback(llm.close)

            MEMORY_DIR.mkdir(parents=True, exist_ok=True)
            store = MemoryStore(MEMORY_FILE)
            retriever = SemanticMemoryRetriever(memory_store=store, top_k=3, min_score=0.5)
            tools = await stack.enter_async_context(MCPToolRuntime(SERVERS))
            server_path = PROJECT_ROOT / "app/tools/observability_mcp_server.py"
            if not server_path.is_file():
                raise RuntimeError("缺少 observability_mcp_server.py（第 51 课）")
            params = StdioServerParameters(command=sys.executable, args=["-m", "app.tools.observability_mcp_server"], cwd=str(PROJECT_ROOT))
            observation_client = await stack.enter_async_context(Client(params))
            await discover_observability_tools(observation_client)
            graph = create_graph(llm, tools, retriever, saver, observation_client, audit)

            # Expose state only after all resources are ready. No hidden in-memory fallback.
            self.sessions = sessions
            self.repository = repository
            self.audit = audit
            self.store = store
            self.graph = graph
            self._stack = stack
            print(f"[Lesson55] PostgreSQL ready; restored_sessions={len(sessions)}; model={MODEL}; synthetic-only")
        except BaseException:
            await stack.aclose()
            self.sessions = {}
            self.repository = None
            self.audit = None
            self.store = None
            self.graph = None
            self._stack = None
            raise

    async def close(self) -> None:
        self.graph = None
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
        self.sessions.clear()
        self.repository = None
        self.audit = None
        self.store = None

    async def create_session(self) -> dict:
        async with self._lock:
            self._ensure_ready()
            if len(self.sessions) >= 100:
                raise APIProblem(429, "教学服务器最多保留 100 个会话")
            sid = secrets.token_urlsafe(24)
            tid = secrets.token_urlsafe(24)
            # Commit to PostgreSQL *before* exposing session to HTTP.
            await self.repository.insert(sid, tid)
            self.sessions[sid] = tid
            return {"session_id": sid, "status": "created", "durable": True}

    async def reset(self, session_id: str) -> dict:
        async with self._lock:
            self._ensure_ready()
            config = self._config(session_id)
            snapshot = await self.graph.aget_state(config)
            if snapshot and "human_approval" in snapshot.next:
                raise APIProblem(409, "请先拒绝或完成审批，再重置会话")
            new_tid = secrets.token_urlsafe(24)
            await self.repository.reset(session_id, new_tid)
            self.sessions[session_id] = new_tid
            # Old checkpoints deliberately remain in PostgreSQL as history.
            return {"session_id": session_id, "status": "reset", "durable": True}
