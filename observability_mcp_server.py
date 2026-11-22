"""AgentOps Lesson 51: read-only Observability MCP Server (SDK v2).

This STDIO server exposes ONLY deterministic, synthetic incident observations.
It never contacts production monitoring, and exposes no remediation actions.
Never print to stdout: stdout is the MCP JSON-RPC transport.
"""
from __future__ import annotations

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from incident_mock_data import query_telemetry

mcp = MCPServer("agentops-observability")


def _read(tool_name: str, incident_id: str) -> dict:
    try:
        if not isinstance(incident_id, str) or not incident_id.startswith("INC-"):
            raise ValueError("incident_id 必须形如 INC-001")
        return query_telemetry(tool_name, incident_id)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def get_service_metrics(incident_id: str) -> dict:
    """Read SYNTHETIC per-service metrics for a known incident; no live monitoring."""
    return _read("get_service_metrics", incident_id)


@mcp.tool()
def search_logs(incident_id: str) -> dict:
    """Read SYNTHETIC incident logs. This tool cannot modify logs or systems."""
    return _read("search_logs", incident_id)


@mcp.tool()
def query_traces(incident_id: str) -> dict:
    """Read SYNTHETIC trace spans for a known incident; no live tracing."""
    return _read("query_traces", incident_id)


@mcp.tool()
def get_service_topology(incident_id: str) -> dict:
    """Read SYNTHETIC service-to-service dependency edges for an incident."""
    return _read("get_service_topology", incident_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")
