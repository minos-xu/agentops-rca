"""Lesson 54: local-only FastAPI adapter around the tested Lesson 53 graph.

No production monitoring or remediation. InMemorySaver + process-local sessions:
not durable and NOT for concurrent multi-worker deployment.
"""
from __future__ import annotations

import asyncio
import os
import re
import secrets
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from app.core.deployment_config import PROJECT_ROOT
from typing import Any

INCIDENT_PATTERN = re.compile(r"\bINC-\d{3}\b", re.IGNORECASE)


class APIProblem(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


def summarize_state(snapshot: Any) -> dict:
    """Return JSON-safe API fields, not the entire LangGraph checkpoint."""
    values = snapshot.values if snapshot else {}
    messages = values.get("messages") or []
    answer = ""
    for msg in reversed(messages):
        if getattr(msg, "type", "") == "ai":
            answer = str(msg.content)
            break
    waiting = bool(snapshot and "human_approval" in snapshot.next)
    proposal = values.get("action_proposal") or {} if waiting else {}
    report = values.get("rca_report") or {}
    return {
        "status": "pending_approval" if waiting else "completed",
        "answer": answer,
        "incident_id": values.get("incident_id") or None,
        "diagnosis_status": report.get("diagnosis_status") if report else None,
        "validation": report.get("validation") if report else None,
        "pending": waiting,
        "proposal": proposal if waiting else None,
        "simulation_result": values.get("simulation_result") or None,
    }


class AgentOpsRuntime:
    """Single-worker teaching runtime. A global lock serializes graph + audit access."""

    def __init__(self):
        self.sessions: dict[str, str] = {}  # API session id -> Graph thread_id
        self._lock = asyncio.Lock()
        self.graph = None
        self.audit = None
        self.store = None
        self._stack = None

    async def start(self) -> None:
        if self.graph is not None:
            return
        # Import the previous lesson only at startup: cheap HTTP-only tests
        # do not require mcp/langgraph/FAISS on the test machine.
        from mcp import Client, StdioServerParameters
        from openai import AsyncOpenAI
        from langgraph.checkpoint.memory import InMemorySaver
        from dotenv import load_dotenv
        from app.memory.memory_config import MEMORY_DIR, MEMORY_FILE, SERVERS, MODEL
        from app.agent.workflow import create_graph
        from app.agent.hitl import SimulationAudit
        from app.tools.observability_mcp_client import discover_observability_tools
        from app.tools.mcp_tool_runtime import MCPToolRuntime
        from app.memory.memory_store import MemoryStore
        from app.memory.memory_retriever import SemanticMemoryRetriever

        load_dotenv()
        key = os.getenv("DEEPSEEK_API_KEY")
        if not key:
            raise RuntimeError("缺少 DEEPSEEK_API_KEY，检查项目 .env")
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(MEMORY_FILE)
        retriever = SemanticMemoryRetriever(memory_store=self.store, top_k=3, min_score=0.5)
        stack = AsyncExitStack()
        try:
            llm = AsyncOpenAI(api_key=key, base_url="https://api.deepseek.com")
            stack.push_async_callback(llm.close)
            tools = await stack.enter_async_context(MCPToolRuntime(SERVERS))
            server_path = PROJECT_ROOT / "app/tools/observability_mcp_server.py"
            if not server_path.is_file():
                raise RuntimeError("缺少 observability_mcp_server.py（第51课）")
            params = StdioServerParameters(command=sys.executable, args=["-m", "app.tools.observability_mcp_server"], cwd=str(PROJECT_ROOT))
            observation_client = await stack.enter_async_context(Client(params))
            await discover_observability_tools(observation_client)
            self.audit = SimulationAudit(MEMORY_DIR / "lesson53_simulation_audit.jsonl")
            self.graph = create_graph(llm, tools, retriever, InMemorySaver(), observation_client, self.audit)
            self._stack = stack
            print(f"[Lesson54] FastAPI runtime ready; model={MODEL}; synthetic-only")
        except BaseException:
            await stack.aclose()
            raise

    async def close(self) -> None:
        self.graph = None
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
        self.sessions.clear()

    def _config(self, session_id: str) -> dict:
        thread_id = self.sessions.get(session_id)
        if thread_id is None:
            raise APIProblem(404, "会话不存在或服务已经重启")
        return {"configurable": {"thread_id": thread_id}, "recursion_limit": 16}

    def _ensure_ready(self) -> None:
        if self.graph is None:
            raise APIProblem(503, "AgentOps 尚未就绪")

    async def create_session(self) -> dict:
        async with self._lock:
            self._ensure_ready()
            if len(self.sessions) >= 100:
                raise APIProblem(429, "演示服务的会话数量已达到上限（100）")
            session_id = secrets.token_urlsafe(24)
            self.sessions[session_id] = secrets.token_urlsafe(24)
            return {"session_id": session_id, "status": "created", "durable": False}

    async def snapshot(self, session_id: str) -> dict:
        async with self._lock:
            self._ensure_ready()
            config = self._config(session_id)
            return summarize_state(await self.graph.aget_state(config))

    async def ask(self, session_id: str, question: str) -> dict:
        from langchain_core.messages import HumanMessage
        async with self._lock:
            self._ensure_ready()
            config = self._config(session_id)
            snapshot = await self.graph.aget_state(config)
            if snapshot and "human_approval" in snapshot.next:
                raise APIProblem(409, "当前会话有待审批操作。请先批准或拒绝，再发新消息")
            match = INCIDENT_PATTERN.search(question)
            if match:
                from app.rca.incident_mock_data import case_exists
                if not case_exists(match.group(0).upper()):
                    raise APIProblem(400, "未知模拟事件 ID")
            try:
                await self.graph.ainvoke({"messages": [HumanMessage(content=question)]}, config=config)
            except ValueError as exc:
                raise APIProblem(400, str(exc)) from exc
            return summarize_state(await self.graph.aget_state(config))

    async def approve(self, session_id: str, action_id: str, decision: str) -> dict:
        from langgraph.types import Command
        async with self._lock:
            self._ensure_ready()
            config = self._config(session_id)
            snapshot = await self.graph.aget_state(config)
            if not snapshot or "human_approval" not in snapshot.next:
                raise APIProblem(409, "当前会话没有待审批操作")
            proposal = snapshot.values.get("action_proposal") or {}
            if proposal.get("action_id") != action_id:
                raise APIProblem(400, "审批编号不匹配，拒绝继续")
            if decision not in {"approve", "reject"}:
                raise APIProblem(422, "decision 只允许 approve 或 reject")
            await self.graph.ainvoke(Command(resume={"decision": decision, "action_id": action_id}), config=config)
            return summarize_state(await self.graph.aget_state(config))

    async def report(self, session_id: str) -> dict:
        async with self._lock:
            self._ensure_ready()
            snapshot = await self.graph.aget_state(self._config(session_id))
            report = (snapshot.values.get("rca_report") or {}) if snapshot else {}
            if not report:
                raise APIProblem(404, "该会话还没有结构化 RCA 报告")
            return report

    async def reset(self, session_id: str) -> dict:
        async with self._lock:
            self._ensure_ready()
            config = self._config(session_id)
            snapshot = await self.graph.aget_state(config)
            if snapshot and "human_approval" in snapshot.next:
                raise APIProblem(409, "请先拒绝或完成审批，再重置会话")
            self.sessions[session_id] = secrets.token_urlsafe(24)
            # Old checkpoints are not removed from the InMemorySaver in this lesson.
            return {"session_id": session_id, "status": "reset", "durable": False}

    async def audit_rows(self) -> list[dict]:
        async with self._lock:
            self._ensure_ready()
            return self.audit.read()[-50:]

    async def cases(self) -> list[dict]:
        from app.rca.incident_mock_data import list_incidents
        return list_incidents()
