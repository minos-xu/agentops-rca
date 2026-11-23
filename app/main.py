"""Lesson 63 entrypoint; original routes and fail-closed limiter are reused."""
from app.api.routes import create_app
from app.agent.traced_runtime import InstrumentedAgentOpsRuntime
from fastapi.responses import JSONResponse

# Handle only transport/dependency exceptions; validation/APIProblem retain existing handlers.
# No retry around sessions, checkpoints, approvals or audit writes.
async def unavailable(request, error):
    return JSONResponse({'detail': '依赖服务暂不可用；请求未确认完成，请检查持久化状态后再处理'}, status_code=503)

from openai import APIConnectionError
import psycopg
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
def create_recovery_app(factory=InstrumentedAgentOpsRuntime):
    app = create_app(factory)
    app.title = 'AgentOps · Safe dependency failure (Lesson 63)'
    app.version = '0.63.0'
    for exception in (psycopg.OperationalError, psycopg.InterfaceError, RedisConnectionError, RedisTimeoutError, APIConnectionError, ConnectionError, TimeoutError):
        app.add_exception_handler(exception, unavailable)
    return app

app = create_recovery_app()
