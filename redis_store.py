"""Lesson 57: Redis cache and atomic fixed-window rate limiter."""
from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis


_RATE_LIMIT_LUA = r"""
local current = redis.call("INCR", KEYS[1])
local ttl = redis.call("TTL", KEYS[1])

-- Set the expiry on the first request. Also repair a key that has no TTL.
if current == 1 or ttl < 0 then
    redis.call("EXPIRE", KEYS[1], tonumber(ARGV[1]))
    ttl = redis.call("TTL", KEYS[1])
end

return {current, ttl}
"""


class Lesson57RedisStore:
    """Small async Redis adapter used by the Lesson 57 API/runtime."""

    def __init__(self, redis_url: str, prefix: str = "agentops:lesson57"):
        if not redis_url or not redis_url.strip():
            raise ValueError("redis_url 不能为空")

        self.prefix = prefix.rstrip(":")
        self.client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
            health_check_interval=30,
        )

    def _key(self, suffix: str) -> str:
        return f"{self.prefix}:{suffix.lstrip(':')}"

    async def ping(self) -> bool:
        return bool(await self.client.ping())

    async def close(self) -> None:
        # aclose() is the current redis-py API; close() is retained by older versions.
        close_method = getattr(self.client, "aclose", None)
        if close_method is not None:
            await close_method()
        else:  # pragma: no cover - compatibility with older redis-py releases
            await self.client.close()

    async def get_json(self, key: str) -> Any | None:
        redis_key = self._key(f"cache:{key}")
        raw = await self.client.get(redis_key)
        if raw is None:
            return None

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # A malformed cache entry should behave like a cache miss.
            await self.client.delete(redis_key)
            return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int = 30) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds 必须大于 0")

        redis_key = self._key(f"cache:{key}")
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        await self.client.set(redis_key, payload, ex=ttl_seconds)

    async def delete_cache(self, key: str) -> None:
        await self.client.delete(self._key(f"cache:{key}"))

    async def hit_rate_limit(
        self,
        scope: str,
        identity: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """Return (allowed, current_count, retry_after_seconds)."""
        if limit <= 0:
            raise ValueError("limit 必须大于 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds 必须大于 0")
        if not scope or not identity:
            raise ValueError("scope 和 identity 不能为空")

        redis_key = self._key(f"rate:{scope}:{identity}")
        result = await self.client.eval(
            _RATE_LIMIT_LUA,
            1,
            redis_key,
            window_seconds,
        )
        current = int(result[0])
        ttl = max(1, int(result[1]))
        return current <= limit, current, ttl
