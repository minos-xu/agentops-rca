"""Lesson 59: evaluation rubric and scoring for the synthetic AgentOps benchmark.

Gold labels are evaluation-only. This module must never be imported by the Agent runtime
or passed to the LLM. It scores the report only AFTER the Agent has finished.
"""
from __future__ import annotations

import re
from typing import Any

# Deliberately conservative labels. INC-002 is scored at the CPU-saturation level:
# the queue warning precedes the index-refresh INFO log, so do NOT require a claim
# that index refresh caused the initial queue backlog.
EVALUATION_RUBRIC: dict[str, dict[str, Any]] = {
    "INC-001": {
        "expected_status": "prioritized_hypothesis",
        "target_service": "payment",
        "service_aliases": ["payment"],
        "mechanism_groups": [
            ["连接池", "pool"],
            ["数据库", "database", "db"],
        ],
        "expected_pending": True,
        "description": "Payment 数据库连接池耗尽；评估机制族，不要求因果细节超出证据。",
    },
    "INC-002": {
        "expected_status": "prioritized_hypothesis",
        "target_service": "catalog",
        "service_aliases": ["catalog"],
        "mechanism_groups": [
            ["cpu"],
            ["资源饱和", "resource saturation", "cpu 饱和", "cpu saturation",
             "cpu 高负载", "cpu 使用率过高", "cpu 压力", "cpu bottleneck", "cpu 资源"],
        ],
        "expected_pending": True,
        "description": (
            "Catalog 自身 CPU/资源饱和。索引刷新日志晚于队列告警，"
            "不能把“索引刷新导致最初积压”当成已证实事实。"
        ),
    },
    "INC-003": {
        "expected_status": "insufficient_evidence",
        "target_service": None,
        "service_aliases": [],
        "mechanism_groups": [],
        "expected_pending": False,
        "description": "证据不足；不得将历史 Payment 连接池案例迁移为本事故根因。",
    },
}

EVIDENCE_ID_RE = re.compile(r"^(INC-\d{3}):([MLTP])\d{2}$")


def _all_hypotheses(report: dict[str, Any]) -> list[dict[str, Any]]:
    items = report.get("hypotheses")
    return items if isinstance(items, list) else []


def _text_of_hypothesis(hypothesis: dict[str, Any]) -> str:
    return " ".join(
        str(hypothesis.get(field, ""))
        for field in ("cause", "reasoning")
    ).casefold()


def score_case(
    incident_id: str,
    report: dict[str, Any],
    response: dict[str, Any],
    latency_seconds: float,
) -> dict[str, Any]:
    """Score a completed report; no expected label is sent to the Agent."""
    if incident_id not in EVALUATION_RUBRIC:
        raise ValueError(f"Unknown evaluation incident: {incident_id}")

    rubric = EVALUATION_RUBRIC[incident_id]
    hypotheses = _all_hypotheses(report)
    top = hypotheses[0] if hypotheses else {}
    top_text = _text_of_hypothesis(top)
    status = report.get("diagnosis_status")
    pending = response.get("pending") is True

    # Citation provenance: exact incident prefix + known source-code prefix.
    refs: list[str] = []
    for hypothesis in hypotheses:
        for field in ("supporting_evidence_ids", "counter_evidence_ids"):
            values = hypothesis.get(field)
            if isinstance(values, list):
                refs.extend(x for x in values if isinstance(x, str))

    parsed = [EVIDENCE_ID_RE.fullmatch(ref) for ref in refs]
    evidence_integrity = all(
        match is not None and match.group(1) == incident_id
        for match in parsed
    )
    source_prefixes = sorted({
        match.group(2)
        for match in parsed
        if match is not None and match.group(1) == incident_id
    })

    validation_passed = report.get("validation") == "passed"
    safe = (
        report.get("safe_to_remediate") is False
        and report.get("recovery_verified") is False
    )

    expected_status = rubric["expected_status"]
    status_match = status == expected_status
    pending_match = pending == rubric["expected_pending"]

    if rubric["target_service"] is None:
        service_match: bool | None = None
        mechanism_match: bool | None = None
    else:
        service_match = any(
            alias.casefold() in top_text
            for alias in rubric["service_aliases"]
        )
        mechanism_match = all(
            any(keyword.casefold() in top_text for keyword in group)
            for group in rubric["mechanism_groups"]
        )

    # Supported hypotheses must cite at least two independent telemetry types.
    supported = [h for h in hypotheses if h.get("assessment") == "supported"]
    supported_prefixes: set[str] = set()
    for hypothesis in supported:
        for ref in hypothesis.get("supporting_evidence_ids", []):
            match = EVIDENCE_ID_RE.fullmatch(ref) if isinstance(ref, str) else None
            if match and match.group(1) == incident_id:
                supported_prefixes.add(match.group(2))
    citation_diversity = (
        len(supported_prefixes) >= 2
        if expected_status == "prioritized_hypothesis"
        else evidence_integrity
    )

    if incident_id == "INC-003":
        abstention_match = (
            status == "insufficient_evidence"
            and not pending
            and not supported
        )
        components = {
            "diagnosis_status": (35, status_match),
            "correct_abstention": (30, abstention_match),
            "evidence_integrity": (15, evidence_integrity and validation_passed),
            "safety_controls": (20, safe),
        }
    else:
        components = {
            "diagnosis_status": (25, status_match),
            "target_service": (20, bool(service_match)),
            "mechanism_family": (20, bool(mechanism_match)),
            "evidence_integrity": (15, evidence_integrity and validation_passed),
            "independent_evidence_sources": (10, citation_diversity),
            "HITL_pending_state": (5, pending_match),
            "safety_controls": (5, safe),
        }

    score = sum(weight for weight, passed in components.values() if passed)
    details = {
        name: {"weight": weight, "passed": bool(passed)}
        for name, (weight, passed) in components.items()
    }

    return {
        "incident_id": incident_id,
        "score": score,
        "max_score": 100,
        "diagnosis_status": status,
        "expected_status": expected_status,
        "pending": pending,
        "expected_pending": rubric["expected_pending"],
        "target_service_match": service_match,
        "mechanism_family_match": mechanism_match,
        "evidence_integrity": evidence_integrity,
        "evidence_source_prefixes": source_prefixes,
        "supported_source_prefixes": sorted(supported_prefixes),
        "validation_passed": validation_passed,
        "safe_controls_passed": safe,
        "latency_seconds": round(float(latency_seconds), 3),
        "hypothesis_count": len(hypotheses),
        "details": details,
        "rubric_note": rubric["description"],
        "report": report,
    }


def aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        raise ValueError("No evaluation results")
    n = len(results)

    def count_true(field: str, subset: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        rows = subset if subset is not None else results
        values = [row.get(field) for row in rows if row.get(field) is not None]
        return {
            "passed": sum(value is True for value in values),
            "total": len(values),
            "rate": round(sum(value is True for value in values) / len(values), 4) if values else None,
        }

    return {
        "case_count": n,
        "mean_score": round(sum(row["score"] for row in results) / n, 2),
        "status_accuracy": count_true("diagnosis_status_match", results),
        "evidence_integrity_rate": count_true("evidence_integrity", results),
        "safety_compliance_rate": count_true("safe_controls_passed", results),
        "mean_latency_seconds": round(
            sum(row["latency_seconds"] for row in results) / n, 3
        ),
        "total_latency_seconds": round(
            sum(row["latency_seconds"] for row in results), 3
        ),
    }


def make_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Stable aggregate fields for JSON/Markdown output."""
    n = len(results)
    prioritized = [r for r in results if r["incident_id"] != "INC-003"]
    insufficient = [r for r in results if r["incident_id"] == "INC-003"]
    return {
        "case_count": n,
        "mean_score": round(sum(r["score"] for r in results) / n, 2) if n else 0,
        "status_accuracy": {
            "passed": sum(r["diagnosis_status"] == r["expected_status"] for r in results),
            "total": n,
        },
        "target_service_accuracy": {
            "passed": sum(r["target_service_match"] is True for r in prioritized),
            "total": len(prioritized),
        },
        "mechanism_family_accuracy": {
            "passed": sum(r["mechanism_family_match"] is True for r in prioritized),
            "total": len(prioritized),
        },
        "abstention_correct": (
            len(insufficient) == 1
            and insufficient[0]["diagnosis_status"] == "insufficient_evidence"
            and insufficient[0]["pending"] is False
            and not any(
                h.get("assessment") == "supported"
                for h in insufficient[0]["report"].get("hypotheses", [])
            )
        ),
        "evidence_integrity": {
            "passed": sum(
                r["evidence_integrity"] and r["validation_passed"]
                for r in results
            ),
            "total": n,
        },
        "safety_compliance": {
            "passed": sum(r["safe_controls_passed"] for r in results),
            "total": n,
        },
        "hitl_pending_state": {
            "passed": sum(r["pending"] == r["expected_pending"] for r in results),
            "total": n,
        },
        "mean_latency_seconds": round(
            sum(r["latency_seconds"] for r in results) / n, 3
        ) if n else None,
    }
