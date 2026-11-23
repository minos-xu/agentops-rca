"""Lesson 52: deterministic evidence registry and fail-closed RCA report checking.

This module has NO LLM or MCP dependency. Inputs are untrusted synthetic telemetry
already obtained via Observability MCP, and a candidate JSON object from an LLM.
Evidence ID validation proves provenance only, NOT causal truth/entailment.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

TOOLS = ("get_service_metrics", "search_logs", "query_traces", "get_service_topology")
PREFIXES = {"get_service_metrics": "M", "search_logs": "L", "query_traces": "T", "get_service_topology": "P"}
VALID_STATUS = {"prioritized_hypothesis", "insufficient_evidence"}
VALID_ASSESSMENT = {"supported", "possible", "weak"}


class RCAValidationError(ValueError):
    """An untrusted model report did not pass structural/safety checks."""


def _str(x: Any, limit: int = 240) -> str:
    return str(x).replace("\n", " ").strip()[:limit]


def _require_str(x: Any, field: str, limit: int = 300) -> str:
    if not isinstance(x, str) or not x.strip() or len(x) > limit:
        raise RCAValidationError(f"{field} 需要非空文本，长度 <= {limit}")
    return x.strip()


def _require_strings(x: Any, field: str, count: int = 8, limit: int = 220) -> list[str]:
    if not isinstance(x, list) or len(x) > count:
        raise RCAValidationError(f"{field} 必须是长度 <= {count} 的数组")
    return [_require_str(v, field, limit) for v in x]


def make_evidence_catalog(observations: list[dict], incident_id: str) -> dict:
    """Create traceable, SOURCE-BOUND facts from current incident ONLY.

    An invalid or failed tool result produces a gap, never evidence. No expected
    answer/label is ever included. We intentionally do not infer causes here.
    """
    if not isinstance(incident_id, str) or not incident_id.startswith("INC-"):
        raise ValueError("incident_id 无效")
    if not isinstance(observations, list):
        raise ValueError("observations 必须是数组")

    found: dict[str, dict] = {}
    errors: dict[str, str] = {}
    for row in observations:
        if not isinstance(row, dict):
            continue
        tool = row.get("tool")
        if tool not in TOOLS:
            continue
        if tool in found or tool in errors:
            # Duplicate observations could contradict. Fail closed for that tool.
            found.pop(tool, None)
            errors[tool] = "duplicate tool result"
            continue
        if row.get("incident_id") != incident_id or row.get("synthetic") is not True:
            errors[tool] = "incident_id/synthetic mismatch"
            continue
        if row.get("error") is not None:
            errors[tool] = _str(row.get("error"), 160)
            continue
        if not isinstance(row.get("data"), (dict, list)):
            errors[tool] = "missing or malformed data"
            continue
        found[tool] = row

    items = []
    status = {}

    def add(tool: str, statement: str) -> None:
        prefix = PREFIXES[tool]
        existing = sum(item["source"] == tool for item in items)
        if existing >= 120:
            raise ValueError("遥测结果过大，请先在工具层限制返回条数")
        items.append({
            "id": f"{incident_id}:{prefix}{existing + 1:02d}", "source": tool,
            "statement": _str(statement, 440), "synthetic": True,
        })

    for tool in TOOLS:
        if tool not in found:
            status[tool] = {"ok": False, "reason": errors.get(tool, "not collected")}
            continue
        start = len(items)
        data = found[tool]["data"]
        try:
            if tool == "get_service_metrics":
                if not isinstance(data, dict):
                    raise ValueError("metrics must be object")
                for service, fields in data.items():
                    if not isinstance(fields, dict):
                        raise ValueError("metrics service values must be object")
                    for name, value in fields.items():
                        if not isinstance(value, (int, float, bool, str)) or isinstance(value, str) and len(value) > 200:
                            raise ValueError("metric value invalid")
                        add(tool, f"{_str(service, 70)}.{_str(name, 80)}={json.dumps(value, ensure_ascii=False)}")
            elif tool == "search_logs":
                if not isinstance(data, list):
                    raise ValueError("logs must be array")
                for log in data:
                    if not isinstance(log, dict):
                        raise ValueError("log entry malformed")
                    add(tool, f"time={_str(log.get('time'))} service={_str(log.get('service'))} level={_str(log.get('level'))} message={_str(log.get('message'), 250)}")
            elif tool == "query_traces":
                if not isinstance(data, list):
                    raise ValueError("traces must be array")
                for trace in data:
                    if not isinstance(trace, dict) or not isinstance(trace.get("spans"), list):
                        raise ValueError("trace malformed")
                    for span in trace["spans"]:
                        if not isinstance(span, dict):
                            raise ValueError("span malformed")
                        add(tool, f"trace={_str(trace.get('trace_id'))} service={_str(span.get('service'))} duration_ms={_str(span.get('duration_ms'))} status={_str(span.get('status'))}")
            else:
                if not isinstance(data, list):
                    raise ValueError("topology must be array")
                for edge in data:
                    if not isinstance(edge, dict):
                        raise ValueError("topology edge malformed")
                    add(tool, f"dependency {_str(edge.get('from'))} -> {_str(edge.get('to'))}")
        except (ValueError, TypeError) as exc:
            del items[start:]
            status[tool] = {"ok": False, "reason": f"invalid observation: {exc}"}
            continue
        if len(items) == start:
            status[tool] = {"ok": False, "reason": "empty result"}
        else:
            status[tool] = {"ok": True, "count": len(items) - start}

    return {"incident_id": incident_id, "synthetic": True, "items": items, "tool_status": status}


def has_observed_mechanism_signal(catalog: dict) -> bool:
    """Teaching-only conservative mechanism gate. NOT causal verification.

    Requires corroborating resource-pressure metrics and service-specific logs,
    so latency propagation alone is insufficient to prioritize an RCA mechanism.
    No evaluation labels and no incident-specific IDs are consulted.
    """
    metrics = defaultdict(dict)
    logs = defaultdict(list)
    for item in catalog.get("items", []):
        statement = item.get("statement", "")
        if item.get("source") == "get_service_metrics":
            match = re.fullmatch(
                r"([a-zA-Z0-9_-]+)\.([a-zA-Z0-9_]+)=(-?(?:\d+\.?\d*|\.\d+))",
                statement,
            )
            if match:
                metrics[match.group(1)][match.group(2)] = float(match.group(3))
        elif item.get("source") == "search_logs":
            match = re.search(r"\bservice=([a-zA-Z0-9_-]+)\b.*?\bmessage=(.*)$", statement)
            if match:
                logs[match.group(1)].append(match.group(2).lower())

    for service, fields in metrics.items():
        service_logs = logs.get(service, [])
        active = fields.get("db_pool_active")
        maximum = fields.get("db_pool_max")
        pending = fields.get("db_pool_pending")
        if (active is not None and maximum is not None and pending is not None
                and maximum > 0 and active >= maximum and pending > 0
                and any("pool wait timeout" in m or "connection acquisition timeout" in m
                        for m in service_logs)):
            return True
        if (fields.get("cpu_pct", 0) >= 95 and any(
                "worker queue length exceeded threshold" in m for m in service_logs)):
            return True
    return False


def validate_rca(raw: dict, catalog: dict) -> dict:
    """Validate exact source IDs and fail closed on unsafe or malformed output.

    This is a provenance/structural guard, not a semantic entailment verifier.
    """
    if not isinstance(raw, dict):
        raise RCAValidationError("输出不是 JSON 对象")
    incident_id = catalog["incident_id"]
    if raw.get("incident_id") != incident_id:
        raise RCAValidationError("事故编号与采集对象不一致")
    if raw.get("safe_to_remediate") is not False or raw.get("recovery_verified") is not False:
        raise RCAValidationError("本阶段禁止执行修复、声称恢复或打开修复许可")
    status = raw.get("diagnosis_status")
    if status not in VALID_STATUS:
        raise RCAValidationError("诊断状态不合法")
    summary = _require_str(raw.get("summary"), "summary", 650)
    hypotheses = raw.get("hypotheses")
    if not isinstance(hypotheses, list) or len(hypotheses) > 4:
        raise RCAValidationError("hypotheses 必须是最多四项的数组")
    if status == "prioritized_hypothesis" and not hypotheses:
        raise RCAValidationError("已优先排序但没有任何候选")
    items = {item["id"]: item for item in catalog["items"]}
    validated = []
    has_supported = False

    def check_refs(refs: Any, field: str) -> list[str]:
        if not isinstance(refs, list) or len(refs) > 12 or not all(isinstance(ref, str) for ref in refs):
            raise RCAValidationError(f"{field} 必须是证据编号数组")
        if len(refs) != len(set(refs)):
            raise RCAValidationError(f"{field} 存在重复引用")
        missing = set(refs) - set(items)
        if missing:
            raise RCAValidationError(f"{field} 编造或跨事件证据编号：{sorted(missing)}")
        return refs

    for n, item in enumerate(hypotheses):
        if not isinstance(item, dict):
            raise RCAValidationError(f"候选 {n} 不是 JSON 对象")
        cause = _require_str(item.get("cause"), f"hypotheses[{n}].cause", 180)
        assessment = item.get("assessment")
        if assessment not in VALID_ASSESSMENT:
            raise RCAValidationError("候选状态无效")
        support = check_refs(item.get("supporting_evidence_ids"), "supporting_evidence_ids")
        counter = check_refs(item.get("counter_evidence_ids"), "counter_evidence_ids")
        if set(support) & set(counter):
            raise RCAValidationError("同一证据不能同时被标为支持和反对")
        if assessment == "supported":
            sources = {items[ref]["source"] for ref in support}
            if len(sources) < 2:
                raise RCAValidationError("较强候选必须有至少两类独立遥测来源支持")
            has_supported = True
        if assessment == "supported" and status == "insufficient_evidence":
            raise RCAValidationError("总体证据不足时不能称某候选得到较强支持")
        validated.append({
            "cause": cause, "assessment": assessment,
            "supporting_evidence_ids": support, "counter_evidence_ids": counter,
            "unknowns": _require_strings(item.get("unknowns"), "unknowns", count=6),
            "reasoning": _require_str(item.get("reasoning"), "reasoning", 500),
        })
    if status == "prioritized_hypothesis" and not has_supported:
        raise RCAValidationError("优先候选状态要求至少一个两类证据支持的候选")
    if status == "prioritized_hypothesis" and not has_observed_mechanism_signal(catalog):
        raise RCAValidationError(
            "当前仅有异常现象或传播线索，缺少资源压力与同服务日志的交叉验证；"
            "本课模拟案例只能报告 insufficient_evidence。"
        )
    if status == "prioritized_hypothesis":
        critical = ("get_service_metrics", "search_logs", "query_traces")
        if any(not catalog["tool_status"][tool]["ok"] for tool in critical):
            raise RCAValidationError("三种必需证据源有缺失，必须降级为证据不足")

    steps = _require_strings(raw.get("next_read_only_steps"), "next_read_only_steps", count=8, limit=300)
    dangerous = ("执行重启", "立即重启", "重启服务", "执行回滚", "立即回滚", "执行扩容", "修改配置", "删除服务", "restart ", "rollback ", "delete ", "kill ")
    if any(any(word in step.lower() for word in dangerous) for step in steps):
        raise RCAValidationError("下一步建议中含写入或高风险执行操作，本课仅允许只读调查")

    return {
        "incident_id": incident_id,
        "diagnosis_status": status,
        "summary": summary,
        "hypotheses": validated,
        "next_read_only_steps": steps,
        "safe_to_remediate": False,
        "recovery_verified": False,
        "validation": "passed",
    }


def insufficient_report(catalog: dict, reason: str) -> dict:
    """Conservative deterministic fallback; never infer a root cause."""
    missing = [name for name, entry in catalog["tool_status"].items() if not entry["ok"]]
    return {
        "incident_id": catalog["incident_id"],
        "diagnosis_status": "insufficient_evidence",
        "summary": "诊断报告校验未通过，或证据不完整；无法提供可信的确定性归因。",
        "hypotheses": [],
        "next_read_only_steps": ["检查本次 MCP 工具结果和证据编号。", "补充独立遥测证据后重新分析。"],
        "safe_to_remediate": False,
        "recovery_verified": False,
        "validation": "fallback",
        "validation_reason": _str(reason, 220),
        "missing_sources": missing,
    }


def render_report(report: dict, catalog: dict) -> str:
    facts = {item["id"]: item for item in catalog["items"]}
    status_name = {
        "prioritized_hypothesis": "有证据支持的优先候选（仍未确认因果根因）",
        "insufficient_evidence": "证据不足，不能确定根因",
    }[report["diagnosis_status"]]
    lines = [
        f"# {report['incident_id']} 结构化 RCA 报告（模拟演练）",
        "", "**数据边界**：全部为模拟遥测，非生产监控；无执行修复能力。",
        f"**诊断状态**：{status_name}",
        f"**证据校验**：{report['validation']}", "",
        "## 证据采集状态",
    ]
    for name, entry in catalog["tool_status"].items():
        lines.append(f"- {name}: {'成功' if entry['ok'] else '缺失/失败（' + entry.get('reason','') + '）'}")
    lines.extend(["", "## 分析摘要（模型提出的解释，待验证）", report["summary"]])
    if report["hypotheses"]:
        lines.extend(["", "## 候选假设及可追溯证据"])
        for i, hypothesis in enumerate(report["hypotheses"], 1):
            lines.append(f"### {i}. {hypothesis['cause']}（{hypothesis['assessment']}）")
            lines.append(hypothesis["reasoning"])
            for key, title in (("supporting_evidence_ids", "支持"), ("counter_evidence_ids", "反对/限制")):
                refs = hypothesis[key]
                if refs:
                    lines.append(f"**{title}证据：**")
                    for ref in refs:
                        e = facts[ref]
                        lines.append(f"- `{ref}` [{e['source']}] {e['statement']}")
            if hypothesis["unknowns"]:
                lines.append("**待补证据：**" + "；".join(hypothesis["unknowns"]))
    lines.extend(["", "## 后续只读调查建议"])
    for i, action in enumerate(report["next_read_only_steps"], 1):
        lines.append(f"{i}. {action}")
    lines.append("\n**执行控制**：safe_to_remediate=false；recovery_verified=false；本课不允许修复或宣称已恢复。")
    if report["validation"] == "fallback":
        lines.append(f"\n**校验降级原因**：{report.get('validation_reason', 'unknown')}")
    lines.append("\n**校验边界**：引用编号已与本次 MCP 观测匹配，但引用匹配不等于科学因果证明。")
    return "\n".join(lines)
