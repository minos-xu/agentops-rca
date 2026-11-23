"""Lesson 57: PostgreSQL AgentOps runtime extended with Redis."""
from __future__ import annotations

import os

from app.agent.runtime import APIProblem
from app.agent.postgres_runtime import PostgresAgentOpsRuntime
from app.storage.redis_store import Lesson57RedisStore


class RateLimitProblem(APIProblem):
    def __init__(self, status: int, detail: str, retry_after: int):
        super().__init__(status, detail)
        self.retry_after = max(1, int(retry_after))


class RedisPostgresAgentOpsRuntime(PostgresAgentOpsRuntime):
    """Lesson 55 PostgreSQL runtime plus Redis cache and request limiting."""

    def __init__(self):
        super().__init__()
        self.redis_store: Lesson57RedisStore | None = None
        self.message_rate_limit = 10
        self.message_rate_window_seconds = 60
        self.case_cache_ttl_seconds = 30

    @staticmethod
    def _positive_int_env(name: str, default: int) -> int:
        raw = os.getenv(name, str(default)).strip()
        try:
            value = int(raw)
        except ValueError as exc:
            raise RuntimeError(f"环境变量 {name} 必须是正整数") from exc
        if value <= 0:
            raise RuntimeError(f"环境变量 {name} 必须大于 0")
        return value

    async def start(self) -> None:
        if self.graph is not None and self.redis_store is not None:
            return

        from dotenv import load_dotenv

        load_dotenv()
        redis_url = os.getenv("REDIS_URL", "").strip()
        if not redis_url:
            raise RuntimeError(
                "缺少 REDIS_URL，请在项目 .env 中配置 "
                "REDIS_URL=redis://127.0.0.1:56379/0"
            )

        self.message_rate_limit = self._positive_int_env(
            "AGENTOPS_MESSAGE_RATE_LIMIT", 10
        )
        self.message_rate_window_seconds = self._positive_int_env(
            "AGENTOPS_MESSAGE_RATE_WINDOW_SECONDS", 60
        )
        self.case_cache_ttl_seconds = self._positive_int_env(
            "AGENTOPS_CASE_CACHE_TTL_SECONDS", 30
        )

        # Start PostgreSQL, LangGraph, LLM and MCP resources first.
        await super().start()

        redis_store = Lesson57RedisStore(redis_url)
        try:
            await redis_store.ping()
            if self._stack is None:
                raise RuntimeError("PostgreSQL Runtime 未创建资源生命周期栈")

            # AsyncExitStack closes resources in reverse registration order.
            # Redis will therefore be closed before the earlier runtime resources.
            self._stack.push_async_callback(redis_store.close)
            self.redis_store = redis_store
            print(
                "[Lesson57] Redis ready; "
                f"message_limit={self.message_rate_limit}/"
                f"{self.message_rate_window_seconds}s; "
                f"case_cache_ttl={self.case_cache_ttl_seconds}s"
            )
        except BaseException:
            await redis_store.close()
            await super().close()
            raise

    async def close(self) -> None:
        try:
            await super().close()
        finally:
            self.redis_store = None

    def _require_redis(self) -> Lesson57RedisStore:
        if self.redis_store is None:
            raise APIProblem(503, "Redis 尚未就绪")
        return self.redis_store

    async def redis_health(self) -> bool:
        if self.redis_store is None:
            return False
        try:
            return await self.redis_store.ping()
        except Exception:
            return False

    async def enforce_message_rate_limit(self, session_id: str) -> dict:
        """Validate the session and atomically enforce its message quota."""
        self._ensure_ready()
        self._config(session_id)  # Unknown sessions must not consume a quota.
        store = self._require_redis()

        try:
            allowed, current, retry_after = await store.hit_rate_limit(
                scope="messages",
                identity=session_id,
                limit=self.message_rate_limit,
                window_seconds=self.message_rate_window_seconds,
            )
        except Exception as exc:
            # Fail closed: do not silently disable request protection if Redis is down.
            raise APIProblem(
                503, "Redis 限流服务暂不可用，本次消息请求已拒绝"
            ) from exc

        if not allowed:
            raise RateLimitProblem(
                429,
                f"消息请求过于频繁；每个会话每 {self.message_rate_window_seconds} 秒 "
                f"最多允许 {self.message_rate_limit} 次，请稍后重试",
                retry_after=retry_after,
            )

        return {
            "allowed": True,
            "current": current,
            "limit": self.message_rate_limit,
            "window_seconds": self.message_rate_window_seconds,
        }

    async def load_cases(self) -> list[dict]:
        """Load the source data. Kept separate to make cache behavior testable."""
        return await super().cases()

    async def cached_cases(self) -> list[dict]:
        """Cache only the static synthetic case catalogue, never RCA/session state."""
        store = self._require_redis()
        try:
            cached = await store.get_json("cases:v1")
            if isinstance(cached, list):
                return cached
        except Exception as exc:
            print(f"[Lesson57] case cache read failed; falling back to source: {type(exc).__name__}")

        cases = await self.load_cases()
        try:
            await store.set_json(
                "cases:v1", cases, ttl_seconds=self.case_cache_ttl_seconds
            )
        except Exception as exc:
            # Cache is an optimization: source reads remain available on cache failure.
            print(f"[Lesson57] case cache write failed; returning source data: {type(exc).__name__}")
        return cases
