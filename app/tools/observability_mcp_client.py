"""Strict client-side helper for the SDK v2 Observability MCP Server.

The planner chooses names, but Python controls tool permissions and validates
MCP tool responses. In particular, tool errors never count as observations.
"""
from __future__ import annotations

import json
from mcp.types import TextContent
from app.agent.recovery import bounded_call, MCP_TIMEOUT_SECONDS
from app.telemetry.observability import observability

REQUIRED_TOOLS = ("get_service_metrics", "search_logs", "query_traces")
OPTIONAL_TOOLS = ("get_service_topology",)
ALLOWED_TOOLS = frozenset(REQUIRED_TOOLS + OPTIONAL_TOOLS)


async def discover_observability_tools(client) -> set[str]:
    names: set[str] = set()
    cursor = None
    while True:
        page = await client.list_tools(cursor=cursor)
        for tool in page.tools:
            if tool.name in names:
                raise RuntimeError(f"Observability MCP 重复工具名：{tool.name}")
            names.add(tool.name)
        cursor = getattr(page, "next_cursor", None)
        if not cursor:
            break
    if names != ALLOWED_TOOLS:
        raise RuntimeError(
            f"Observability MCP 工具集合异常；expected={sorted(ALLOWED_TOOLS)}, actual={sorted(names)}"
        )
    for tool in sorted(names):
        print(f"[MCP Observability] discovered {tool}")
    return names


def _extract_json_result(result) -> dict:
    if getattr(result, "is_error", False):
        raise RuntimeError("MCP Tool Error")

    data = getattr(result, "structured_content", None)
    if isinstance(data, dict):
        # MCP v2 returns dictionaries as first-class structured results.
        if {"incident_id", "synthetic", "tool", "data"}.issubset(data):
            return data
        # Some return type formats wrap values in a `result` field.
        if isinstance(data.get("result"), dict):
            return data["result"]
        if isinstance(data.get("result"), str):
            try:
                decoded = json.loads(data["result"])
                if isinstance(decoded, dict):
                    return decoded
            except json.JSONDecodeError:
                pass
    for part in result.content:
        if isinstance(part, TextContent):
            try:
                decoded = json.loads(part.text)
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, dict):
                return decoded
    raise RuntimeError("MCP 返回内容无法解析为结构化遥测 JSON")


async def query_observability_tool(client, tool_name: str, incident_id: str) -> dict:
    if tool_name not in ALLOWED_TOOLS:
        raise ValueError(f"未授权的只读遥测工具：{tool_name}")
    if not isinstance(incident_id, str) or not incident_id.startswith("INC-"):
        raise ValueError("无效的 incident_id")
    async def invoke():
        result = await client.call_tool(tool_name, {"incident_id": incident_id})
        data = _extract_json_result(result)
        if (data.get("incident_id") != incident_id
                or data.get("tool") != tool_name
                or data.get("synthetic") is not True
                or not isinstance(data.get("data"), (dict, list))):
            raise RuntimeError(f"遥测内容验证失败：{tool_name} / {incident_id}")
        if "expected_cause" in json.dumps(data, ensure_ascii=False):
            raise RuntimeError("遥测工具错误暴露了评测真值 expected_cause")
        return data
    with observability.span("tool", tool_name, metadata={"server": "observability"}):
        return await bounded_call(
            invoke, kind="tool_attempt", name=tool_name, metadata={"server": "observability"},
            safe_read=True, timeout=MCP_TIMEOUT_SECONDS,
        )
