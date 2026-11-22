"""Lesson 50: read-only, deterministic synthetic incident telemetry.

All values are invented for a teaching exercise. No production connections.
`expected_cause` is evaluation-only and MUST NEVER be included in tool responses.
"""
from __future__ import annotations

from copy import deepcopy

_CASES = {
    "INC-001": {
        "service": "order",
        "title": "订单接口 5xx 增多",
        "window": "模拟窗口 14:00–14:15",
        "metrics": {
            "order": {"error_rate_pct_before": 1.0, "error_rate_pct_now": 18.0, "p95_ms_before": 180, "p95_ms_now": 2600, "cpu_pct": 37},
            "payment": {"p95_ms_before": 130, "p95_ms_now": 2300, "db_pool_active": 20, "db_pool_max": 20, "db_pool_pending": 31},
            "database": {"cpu_pct": 42, "active_sessions": 20},
        },
        "logs": [
            {"service": "order", "time": "14:07:02", "level": "ERROR", "message": "payment request exceeded timeout 2s"},
            {"service": "payment", "time": "14:06:58", "level": "WARN", "message": "unable to acquire db connection: pool wait timeout"},
            {"service": "payment", "time": "14:07:01", "level": "ERROR", "message": "db connection acquisition timeout"},
        ],
        "traces": [
            {"trace_id": "synthetic-001", "root": "gateway", "spans": [
                {"service": "gateway", "duration_ms": 2650, "status": "ERROR"},
                {"service": "order", "duration_ms": 2550, "status": "ERROR"},
                {"service": "payment", "duration_ms": 2320, "status": "ERROR"},
                {"service": "database", "duration_ms": 2210, "status": "TIMEOUT"},
            ]}
        ],
        "topology": [{"from": "gateway", "to": "order"}, {"from": "order", "to": "payment"}, {"from": "payment", "to": "database"}],
        "expected_cause": "Payment 数据库连接池耗尽（模拟真值，仅供评测）",
    },
    "INC-002": {
        "service": "catalog",
        "title": "商品目录查询延迟上升",
        "window": "模拟窗口 10:30–10:45",
        "metrics": {
            "catalog": {"error_rate_pct_before": 0.4, "error_rate_pct_now": 2.5, "p95_ms_before": 95, "p95_ms_now": 1900, "cpu_pct": 98, "memory_pct": 67},
            "database": {"cpu_pct": 28, "p95_ms_now": 41},
        },
        "logs": [
            {"service": "catalog", "time": "10:36:15", "level": "WARN", "message": "worker queue length exceeded threshold"},
            {"service": "catalog", "time": "10:36:18", "level": "INFO", "message": "scheduled full index refresh started"},
        ],
        "traces": [
            {"trace_id": "synthetic-002", "root": "gateway", "spans": [
                {"service": "gateway", "duration_ms": 1940, "status": "OK"},
                {"service": "catalog", "duration_ms": 1870, "status": "SLOW"},
                {"service": "database", "duration_ms": 41, "status": "OK"},
            ]}
        ],
        "topology": [{"from": "gateway", "to": "catalog"}, {"from": "catalog", "to": "database"}],
        "expected_cause": "Catalog 索引刷新任务引发的 CPU 饱和（模拟真值，仅供评测）",
    },
    "INC-003": {
        "service": "checkout",
        "title": "结算服务间歇性超时（证据不足）",
        "window": "模拟窗口 17:00–17:15",
        "metrics": {
            "checkout": {"error_rate_pct_before": 0.5, "error_rate_pct_now": 5.2, "p95_ms_before": 250, "p95_ms_now": 980, "cpu_pct": 48},
            "payment": {"p95_ms_now": 500, "cpu_pct": 34},
        },
        "logs": [
            {"service": "checkout", "time": "17:08:04", "level": "WARN", "message": "intermittent downstream timeout; retry succeeded"},
            {"service": "payment", "time": "17:08:05", "level": "INFO", "message": "request latency elevated for a subset of requests"},
        ],
        "traces": [
            {"trace_id": "synthetic-003", "root": "gateway", "spans": [
                {"service": "gateway", "duration_ms": 1030, "status": "SLOW"},
                {"service": "checkout", "duration_ms": 980, "status": "SLOW"},
                {"service": "payment", "duration_ms": 500, "status": "SLOW"},
            ]}
        ],
        "topology": [{"from": "gateway", "to": "checkout"}, {"from": "checkout", "to": "payment"}],
        "expected_cause": None,  # Deliberately ambiguous.
    },
}


def list_incidents() -> list[dict]:
    return [{"id": key, "title": value["title"], "service": value["service"], "window": value["window"]}
            for key, value in _CASES.items()]


def case_exists(incident_id: str) -> bool:
    return incident_id in _CASES


def describe_incident(incident_id: str) -> dict:
    if not case_exists(incident_id):
        raise ValueError(f"未知模拟事件 {incident_id}；可用：{', '.join(_CASES)}")
    c = _CASES[incident_id]
    return {"id": incident_id, "title": c["title"], "service": c["service"], "window": c["window"], "synthetic": True}


def query_telemetry(tool: str, incident_id: str) -> dict:
    """Expose only simulated evidence (not expected root cause / answer key)."""
    if not case_exists(incident_id):
        raise ValueError(f"未知模拟事件：{incident_id}")
    mapping = {"get_service_metrics": "metrics", "search_logs": "logs", "query_traces": "traces", "get_service_topology": "topology"}
    if tool not in mapping:
        raise ValueError(f"未授权工具：{tool}")
    return deepcopy({"incident_id": incident_id, "synthetic": True, "tool": tool, "data": _CASES[incident_id][mapping[tool]]})
