"""Lesson 58: fault-injection tests WITHOUT Redis, PostgreSQL, MCP or LLM.

Verify the existing Lesson57 fail-closed rate limit and fail-open case cache.
No source files are changed, no real services accessed.
"""
from __future__ import annotations

import asyncio

from runtime import APIProblem
from redis_runtime import RedisPostgresAgentOpsRuntime


class FailingRedis:
    def __init__(self):
        self.cache_calls: list[tuple[str, str]] = []

    async def hit_rate_limit(self, *args, **kwargs):
        raise ConnectionError("injected Redis outage")

    async def get_json(self, key: str):
        self.cache_calls.append(("get_json", key))
        raise ConnectionError("injected Redis cache read outage")

    async def set_json(self, key: str, *args, **kwargs):
        self.cache_calls.append(("set_json", key))
        raise ConnectionError("injected Redis cache write outage")


class OfflineRuntime(RedisPostgresAgentOpsRuntime):
    def __init__(self):
        super().__init__()
        self.graph = object()  # Only used for the base readiness check.
        self.sessions["fake-session"] = "fake-thread"
        self.redis_store = FailingRedis()  # type: ignore[assignment]
        self.source_reads = 0

    async def load_cases(self) -> list[dict]:
        self.source_reads += 1
        return [{"incident_id": "INC-OFFLINE", "synthetic": True}]


async def run_tests() -> None:
    runtime = OfflineRuntime()

    try:
        await runtime.enforce_message_rate_limit("fake-session")
    except APIProblem as exc:
        assert exc.status == 503, (exc.status, exc.detail)
        print("[PASS] Redis rate limiter unavailable => HTTP 503 fail-closed")
    else:
        raise AssertionError("Redis outage incorrectly allowed a message")

    # Unknown sessions must fail before any attempt to use Redis.
    try:
        await runtime.enforce_message_rate_limit("non-existent-session")
    except APIProblem as exc:
        assert exc.status == 404, (exc.status, exc.detail)
        print("[PASS] Unknown session remains HTTP 404")
    else:
        raise AssertionError("Unknown session was allowed")

    cases = await runtime.cached_cases()
    assert cases == [{"incident_id": "INC-OFFLINE", "synthetic": True}]
    assert runtime.source_reads == 1
    print("[PASS] Redis case cache unavailable => returns source data")

    assert runtime.redis_store.cache_calls == [
        ("get_json", "cases:v1"), ("set_json", "cases:v1")
    ]
    print("[PASS] Cache fallback path touched only the static case catalogue")
    print("ALL LESSON 58 DEGRADATION TESTS PASSED")
    print("Fault injection only: no DeepSeek/PostgreSQL/MCP/real remediation.")


if __name__ == "__main__":
    asyncio.run(run_tests())
