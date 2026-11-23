"""Lesson 62: lightweight AgentOps observability primitives.

Standard-library only. This module records metadata, timings and token counts.
It deliberately does NOT store prompts, completions, API keys, or raw tool arguments.
"""
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
import threading
import time
from typing import Any, Iterator
from uuid import uuid4


@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    session_id: str | None
    incident_id: str | None


_ACTIVE_TRACE: ContextVar[TraceContext | None] = ContextVar(
    "lesson62_active_trace", default=None
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(value: Any) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, result)


def exception_status(error: BaseException | None) -> str:
    """Recognize LangGraph control flow without importing a version-specific class."""
    if error is None:
        return "ok"
    if any(cls.__name__ in {"GraphInterrupt", "GraphBubbleUp"}
           for cls in type(error).__mro__):
        return "interrupted"
    return "error"


class ObservabilityCollector:
    """Thread-safe, bounded in-memory event collector."""

    # Only these metadata fields are retained. Never pass prompts/tool arguments.
    SAFE_METADATA_KEYS = {
        "server",
        "operation",
        "status_code",
        "error_type",
        "retry_count",
        "model",
        "attempt",
        "transport_retry_count",
        "error_category",
    }

    def __init__(self, max_events: int = 5000) -> None:
        if max_events < 1:
            raise ValueError("max_events must be >= 1")
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._lock = threading.Lock()

    def _append(self, event: dict[str, Any]) -> None:
        try:
            with self._lock:
                self._events.append(event)
        except Exception:
            # Observability must never change application control flow.
            pass

    @staticmethod
    def _current_trace() -> TraceContext | None:
        return _ACTIVE_TRACE.get()

    @contextmanager
    def run_scope(
        self,
        *,
        session_id: str | None = None,
        incident_id: str | None = None,
        trace_id: str | None = None,
    ) -> Iterator[TraceContext]:
        """Correlate every span recorded inside one request/run."""
        context = TraceContext(
            trace_id=trace_id or uuid4().hex[:16],
            session_id=session_id,
            incident_id=incident_id,
        )
        token = _ACTIVE_TRACE.set(context)
        started = time.perf_counter()
        status = "ok"
        error_type = None
        try:
            yield context
        except BaseException as exc:
            status = exception_status(exc)
            error_type = type(exc).__name__
            raise
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            self._append({
                "timestamp": _utc_now(),
                "trace_id": context.trace_id,
                "session_id": context.session_id,
                "incident_id": context.incident_id,
                "kind": "request",
                "name": "agent_run",
                "duration_ms": duration_ms,
                "status": status,
                "metadata": {"error_type": error_type} if error_type else {},
            })
            _ACTIVE_TRACE.reset(token)

    @contextmanager
    def span(
        self,
        kind: str,
        name: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Measure a node/tool/startup span without recording sensitive payloads."""
        context = self._current_trace()
        started = time.perf_counter()
        status = "ok"
        error_type = None
        outcome: dict[str, Any] = {}
        try:
            yield outcome
        except BaseException as exc:
            status = exception_status(exc)
            error_type = type(exc).__name__
            raise
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            safe_metadata = {
                key: value
                for key, value in (metadata or {}).items()
                if key in self.SAFE_METADATA_KEYS
                and isinstance(value, (str, int, float, bool, type(None)))
            }
            if not error_type and outcome.get("status") == "error":
                status = "error"
                error_type = outcome.get("error_type", "MCPToolError")
            if error_type:
                safe_metadata["error_type"] = error_type
            self._append({
                "timestamp": _utc_now(),
                "trace_id": context.trace_id if context else "system",
                "session_id": context.session_id if context else None,
                "incident_id": context.incident_id if context else None,
                "kind": str(kind),
                "name": str(name),
                "duration_ms": duration_ms,
                "status": status,
                "metadata": safe_metadata,
            })

    def record_llm_usage(
        self,
        *,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int | None = None,
        operation: str | None = None,
    ) -> None:
        """Record usage reported by the model/provider; never estimate billing."""
        prompt = _safe_int(prompt_tokens)
        completion = _safe_int(completion_tokens)
        total = _safe_int(total_tokens) if total_tokens is not None else prompt + completion
        context = self._current_trace()
        self._append({
            "timestamp": _utc_now(),
            "trace_id": context.trace_id if context else "system",
            "session_id": context.session_id if context else None,
            "incident_id": context.incident_id if context else None,
            "kind": "llm_usage",
            "name": str(model),
            "duration_ms": None,
            "status": "ok",
            "metadata": {
                **({"operation": str(operation)} if operation is not None else {}),
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": total,
            },
        })

    def snapshot(self, trace_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            events = list(self._events)
        if trace_id is not None:
            events = [event for event in events if event["trace_id"] == trace_id]
        # Return copies so callers cannot mutate the collector's records.
        return [dict(event, metadata=dict(event["metadata"])) for event in events]

    def summary(self, trace_id: str) -> dict[str, Any]:
        events = self.snapshot(trace_id)
        requests = [e for e in events if e["kind"] == "request"]
        llm_events = [e for e in events if e["kind"] == "llm_usage"]
        llm_calls = [e for e in events if e["kind"] == "llm"]
        tool_events = [e for e in events if e["kind"] == "tool"]
        node_events = [e for e in events if e["kind"] == "node"]
        # Nested MCP attempts have their own counters; the enclosing tool span
        # preserves the existing logical-call error count.
        errors = [e for e in events if e["status"] == "error" and e["kind"] != "tool_attempt"]

        prompt_tokens = sum(e["metadata"].get("prompt_tokens", 0) for e in llm_events)
        completion_tokens = sum(e["metadata"].get("completion_tokens", 0) for e in llm_events)
        total_tokens = sum(e["metadata"].get("total_tokens", 0) for e in llm_events)

        request_duration = requests[-1]["duration_ms"] if requests else None
        return {
            "trace_id": trace_id,
            "request_duration_ms": request_duration,
            "node_count": len(node_events),
            "tool_call_count": len(tool_events),
            "tool_attempt_count": sum(e["kind"] == "tool_attempt" for e in events),
            "tool_attempt_error_count": sum(e["kind"] == "tool_attempt" and e["status"] == "error" for e in events),
            "llm_call_count": len(llm_calls),
            "llm_error_count": sum(e["status"] == "error" for e in llm_calls),
            "tool_error_count": sum(e["status"] == "error" for e in tool_events),
            "interrupted_count": sum(e["status"] == "interrupted" for e in events),
            "llm_usage_records": len(llm_events),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "error_count": len(errors),
            "events": events,
        }

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


# A convenient process-local collector. For tests, prefer a fresh instance.
observability = ObservabilityCollector()
