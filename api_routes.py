"""Lesson 57 API: Lesson 54 routes with PostgreSQL + Redis runtime.

Run on loopback only. This unauthenticated teaching API must not be exposed publicly.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Callable, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from runtime import APIProblem
from redis_runtime import RateLimitProblem, RedisPostgresAgentOpsRuntime


class MessageInput(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def nonblank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("问题不能只包含空格")
        return cleaned


class ApprovalInput(BaseModel):
    decision: Literal["approve", "reject"]
    action_id: str = Field(min_length=1, max_length=70, pattern=r"^SIM-[A-Z0-9]+$")


def create_app(
    runtime_factory: Callable[[], RedisPostgresAgentOpsRuntime] = RedisPostgresAgentOpsRuntime,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(api: FastAPI):
        service = runtime_factory()
        await service.start()
        api.state.agentops = service
        try:
            yield
        finally:
            await service.close()
            api.state.agentops = None

    api = FastAPI(
        title="AgentOps V2 · PostgreSQL + Redis Synthetic RCA API",
        description=(
            "Training-only: synthetic read-only telemetry, PostgreSQL durable state, "
            "Redis cache/rate limit, and HITL dry-run. No production action."
        ),
        version="0.57.0",
        lifespan=lifespan,
    )

    @api.exception_handler(APIProblem)
    async def api_problem_handler(request: Request, exc: APIProblem):
        headers = {}
        if isinstance(exc, RateLimitProblem):
            headers["Retry-After"] = str(exc.retry_after)
        return JSONResponse(
            {"detail": exc.detail},
            status_code=exc.status,
            headers=headers,
        )

    def service(request: Request) -> RedisPostgresAgentOpsRuntime:
        svc = getattr(request.app.state, "agentops", None)
        if svc is None:
            raise HTTPException(status_code=503, detail="AgentOps 尚未启动")
        return svc

    @api.get("/health")
    async def health(request: Request):
        svc = service(request)
        redis_ok = await svc.redis_health()
        return {
            "status": "ok" if redis_ok else "degraded",
            "mode": "synthetic_dry_run",
            "real_execution_allowed": False,
            "dependencies": {"redis": "ok" if redis_ok else "unavailable"},
        }

    @api.get("/api/v1/cases")
    async def cases(request: Request):
        return {"cases": await service(request).cached_cases()}

    @api.post("/api/v1/sessions", status_code=201)
    async def new_session(request: Request):
        return await service(request).create_session()

    @api.get("/api/v1/sessions/{session_id}")
    async def session(request: Request, session_id: str):
        return await service(request).snapshot(session_id)

    @api.post("/api/v1/sessions/{session_id}/messages")
    async def send_message(request: Request, session_id: str, body: MessageInput):
        svc = service(request)
        await svc.enforce_message_rate_limit(session_id)
        return await svc.ask(session_id, body.message.strip())

    @api.get("/api/v1/sessions/{session_id}/pending")
    async def pending(request: Request, session_id: str):
        snap = await service(request).snapshot(session_id)
        return {"pending": snap["pending"], "proposal": snap["proposal"]}

    @api.post("/api/v1/sessions/{session_id}/decisions")
    async def decide(request: Request, session_id: str, body: ApprovalInput):
        return await service(request).approve(session_id, body.action_id, body.decision)

    @api.get("/api/v1/sessions/{session_id}/report")
    async def report(request: Request, session_id: str):
        return await service(request).report(session_id)

    @api.post("/api/v1/sessions/{session_id}/reset")
    async def reset(request: Request, session_id: str):
        return await service(request).reset(session_id)

    @api.get("/api/v1/audit")
    async def audit(request: Request):
        return {
            "entries": await service(request).audit_rows(),
            "mode": "synthetic_dry_run",
        }

    return api


app = create_app()
app.title = "AgentOps V2 · PostgreSQL + Redis Synthetic RCA API"
app.version = "0.57.0"
