"""Offline tests for Lesson 62 observability primitives."""
from __future__ import annotations

import asyncio
import time

from observability import ObservabilityCollector


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[PASS] {message}")


def test_trace_correlation_and_request_duration() -> None:
    obs = ObservabilityCollector()
    with obs.run_scope(session_id="session-a", incident_id="INC-001") as trace:
        with obs.span("node", "incident_planner"):
            time.sleep(0.002)
        with obs.span("tool", "get_service_metrics", metadata={"server": "observability"}):
            time.sleep(0.001)
        obs.record_llm_usage(
            model="deepseek-chat",
            prompt_tokens=100,
            completion_tokens=40,
            total_tokens=140,
        )

    events = obs.snapshot(trace.trace_id)
    check(len(events) == 4, "request, node, tool and LLM usage share one trace")
    check(all(e["session_id"] == "session-a" for e in events), "session correlation is preserved")
    summary = obs.summary(trace.trace_id)
    check(summary["request_duration_ms"] > 0, "request duration is measured")
    check(summary["node_count"] == 1 and summary["tool_call_count"] == 1, "node and tool spans are counted")
    check(summary["prompt_tokens"] == 100 and summary["completion_tokens"] == 40, "LLM token usage is aggregated")


def test_error_capture_and_safe_metadata() -> None:
    obs = ObservabilityCollector()
    with obs.run_scope(session_id="session-b", incident_id="INC-002") as trace:
        try:
            with obs.span(
                "tool",
                "search_logs",
                metadata={
                    "server": "observability",
                    "api_key": "DO_NOT_STORE",
                    "arguments": "sensitive payload",
                },
            ):
                raise TimeoutError("synthetic timeout")
        except TimeoutError:
            pass

    event = [e for e in obs.snapshot(trace.trace_id) if e["kind"] == "tool"][0]
    check(event["status"] == "error", "tool exception is recorded as an error")
    check(event["metadata"].get("error_type") == "TimeoutError", "exception type is retained")
    check("api_key" not in event["metadata"] and "arguments" not in event["metadata"], "unsafe metadata is discarded")


def test_concurrent_trace_isolation() -> None:
    obs = ObservabilityCollector()

    async def worker(session_id: str, incident_id: str) -> str:
        with obs.run_scope(session_id=session_id, incident_id=incident_id) as trace:
            with obs.span("node", "parallel_node"):
                await asyncio.sleep(0.003)
            return trace.trace_id

    async def run() -> tuple[str, str]:
        return await asyncio.gather(
            worker("session-x", "INC-001"),
            worker("session-y", "INC-002"),
        )

    first, second = asyncio.run(run())
    first_events = obs.snapshot(first)
    second_events = obs.snapshot(second)
    check(first != second, "concurrent requests receive distinct trace IDs")
    check({e["session_id"] for e in first_events} == {"session-x"}, "first trace does not mix sessions")
    check({e["session_id"] for e in second_events} == {"session-y"}, "second trace does not mix sessions")


def test_system_startup_and_bounded_storage() -> None:
    obs = ObservabilityCollector(max_events=3)
    with obs.span("startup", "fastapi_lifespan"):
        time.sleep(0.001)
    check(obs.snapshot("system")[0]["kind"] == "startup", "startup span is recorded outside a request")

    with obs.run_scope(session_id="s", incident_id="INC-003") as trace:
        for index in range(5):
            with obs.span("node", f"node-{index}"):
                pass
    check(len(obs.snapshot()) == 3, "event storage is bounded to configured capacity")
    check(len(obs.snapshot(trace.trace_id)) <= 3, "snapshot respects bounded storage")


def test_interrupt_and_error_classification():
    from langgraph.errors import GraphInterrupt, GraphBubbleUp
    from trace_callback import TraceCallback
    from observability import exception_status
    from uuid import uuid4
    obs = ObservabilityCollector()
    for error, expected in [(GraphInterrupt(()), "interrupted"),
                            (GraphBubbleUp(), "interrupted"), (ValueError("SECRET"), "error")]:
        try:
            with obs.run_scope(session_id="gate") as ctx:
                with obs.span("node", "gate"):
                    raise error
        except BaseException as caught:
            assert caught is error
        events = obs.snapshot(ctx.trace_id)
        assert all(e["status"] == expected for e in events)
        assert all(e["metadata"]["error_type"] == type(error).__name__ for e in events)
        summary = obs.summary(ctx.trace_id)
        assert summary["error_count"] == (2 if expected == "error" else 0)
        assert summary["interrupted_count"] == (2 if expected == "interrupted" else 0)
        with obs.run_scope(session_id="callback") as callback_ctx:
            callback = TraceCallback(obs)
            rid = uuid4()
            callback._begin(rid, "node", "human_approval")
            callback._finish(rid, error)
            callback._finish(rid, error)  # Duplicate completion must not duplicate events.
        recorded = obs.snapshot(callback_ctx.trace_id)
        assert len(recorded) == 2 and recorded[0]["status"] == expected
        assert obs._current_trace() is None
    class Derived(GraphInterrupt):
        pass
    assert exception_status(Derived(())) == "interrupted"
    check("SECRET" not in str(obs.snapshot()), "interrupt MRO classification preserves propagation and excludes error messages")


def test_llm_calls_usage_and_failures():
    from types import SimpleNamespace as NS
    from unittest.mock import AsyncMock, patch
    from workflow import tracked_chat_completion
    from observability import observability as obs
    obs.clear()
    async def run():
        create = AsyncMock(return_value=NS(usage=NS(prompt_tokens=12, completion_tokens=8, total_tokens=20)))
        client = NS(chat=NS(completions=NS(create=create)))
        with obs.run_scope(session_id="llm") as ctx:
            for operation in ("planner", "structured_rca", "assistant_response"):
                await tracked_chat_completion(client, operation, model="deepseek-chat", messages=[{"content": "SECRET_PROMPT"}], retry_count=1)
            create.side_effect = ValueError("SECRET_ERROR")
            try:
                await tracked_chat_completion(client, "planner", model="deepseek-chat")
            except ValueError:
                pass
            else:
                raise AssertionError("API exception swallowed")
            create.side_effect = None
            create.return_value = NS(usage=None)
            await tracked_chat_completion(client, "assistant_response", model="deepseek-chat")
            # Broken token recording must not change the successful API result.
            create.return_value = NS(usage=NS(prompt_tokens=1, completion_tokens=1, total_tokens=2))
            with patch.object(obs, "record_llm_usage", side_effect=RuntimeError("sink down")):
                await tracked_chat_completion(client, "assistant_response", model="deepseek-chat")
        summary = obs.summary(ctx.trace_id)
        assert summary["llm_call_count"] == 6 and summary["llm_error_count"] == 1
        assert summary["llm_usage_records"] == 3
        assert (summary["prompt_tokens"], summary["completion_tokens"], summary["total_tokens"]) == (36, 24, 60)
        calls = [e for e in summary["events"] if e["kind"] == "llm"]
        assert all(e["duration_ms"] >= 0 and e["metadata"]["model"] == "deepseek-chat" for e in calls)
        assert calls[1]["metadata"]["retry_count"] == 1
        assert "SECRET" not in str(summary)
    asyncio.run(run())
    check(True, "LLM calls, real provider usage fields, retry metadata and API failures are recorded safely")


def test_mcp_actual_calls():
    from types import SimpleNamespace as NS
    from unittest.mock import AsyncMock
    from contextlib import redirect_stdout
    from io import StringIO
    from mcp_tool_runtime import MCPToolRuntime
    from observability_mcp_client import query_observability_tool
    from observability import observability as obs
    obs.clear()
    async def run():
        runtime = MCPToolRuntime({})
        client = NS(call_tool=AsyncMock(return_value=NS(structured_content={"value": "SECRET_RESULT"}, is_error=False)))
        runtime.tool_clients["demo"] = client
        runtime.tool_servers["demo"] = "unit-server"
        output = StringIO()
        with obs.run_scope(session_id="mcp") as ctx, redirect_stdout(output):
            text = await runtime.execute("demo", {"query": "SECRET_ARGUMENT"})
            assert "SECRET_RESULT" in text
            client.call_tool.side_effect = TimeoutError("SECRET_EXCEPTION")
            assert "TimeoutError" in await runtime.execute("demo", {})
            client.call_tool.side_effect = None
            client.call_tool.return_value.is_error = True
            assert (await runtime.execute("demo", {})).startswith("MCP Tool 执行失败")
            data = {"incident_id": "INC-001", "tool": "search_logs", "synthetic": True, "data": []}
            client.call_tool.return_value = NS(structured_content=data, is_error=False)
            assert await query_observability_tool(client, "search_logs", "INC-001") == data
            client.call_tool.side_effect = TimeoutError("SECRET_EXCEPTION")
            try:
                await query_observability_tool(client, "search_logs", "INC-001")
            except TimeoutError:
                pass
        summary = obs.summary(ctx.trace_id)
        assert summary["tool_call_count"] == 5 and summary["tool_error_count"] == 3
        assert summary["error_count"] == 3
        assert "SECRET" not in str(summary) and "SECRET" not in output.getvalue()
        assert {e["metadata"].get("server") for e in summary["events"] if e["kind"] == "tool"} == {"unit-server", "observability"}
    asyncio.run(run())
    check(True, "both MCP paths record successes, exceptions and protocol errors without logging payloads")


def test_concurrent_callbacks_and_tools():
    from observability import observability as obs
    from trace_callback import TraceCallback
    from uuid import uuid4
    obs.clear()
    callback = TraceCallback(obs)
    async def worker(sid):
        with obs.run_scope(session_id=sid) as ctx:
            rid = uuid4()
            await callback.on_chain_start({}, {}, run_id=rid, name="planner")
            with obs.span("llm", "planner"), obs.span("tool", "search_logs"):
                await asyncio.sleep(0.001)
                obs.record_llm_usage(model="deepseek-chat", operation="planner", prompt_tokens=2, completion_tokens=1)
            await callback.on_chain_end({}, run_id=rid)
        return ctx.trace_id
    async def run():
        return await asyncio.gather(*(worker(f"session-{i}") for i in range(8)))
    traces = asyncio.run(run())
    for i, tid in enumerate(traces):
        events = obs.snapshot(tid)
        assert len(events) == 5 and {e["session_id"] for e in events} == {f"session-{i}"}
        assert obs.summary(tid)["llm_call_count"] == 1
    assert not callback.started and obs._current_trace() is None
    check(True, "concurrent callback, LLM and MCP events retain their own session context")


def test_observability_storage_failure_is_nonfatal():
    class BrokenStorage:
        def append(self, event):
            raise OSError("storage unavailable")
    obs = ObservabilityCollector()
    obs._events = BrokenStorage()
    with obs.run_scope(session_id="sink-failure"):
        with obs.span("llm", "planner"):
            value = "original result"
        obs.record_llm_usage(model="deepseek-chat", prompt_tokens=1, completion_tokens=2)
    assert value == "original result" and obs._current_trace() is None
    original = ValueError("original failure")
    try:
        with obs.run_scope(session_id="sink-failure"):
            with obs.span("tool", "search_logs"):
                raise original
    except ValueError as exc:
        assert exc is original
    else:
        raise AssertionError("Original exception swallowed")
    assert obs._current_trace() is None
    check(True, "storage failures preserve results, original exceptions and ContextVar cleanup")


if __name__ == "__main__":
    test_trace_correlation_and_request_duration()
    test_error_capture_and_safe_metadata()
    test_concurrent_trace_isolation()
    test_system_startup_and_bounded_storage()
    test_interrupt_and_error_classification()
    test_llm_calls_usage_and_failures()
    test_mcp_actual_calls()
    test_concurrent_callbacks_and_tools()
    test_observability_storage_failure_is_nonfatal()
    print("ALL LESSON 62 OBSERVABILITY TESTS PASSED")
