"""Lesson 61: semantic regression gates for the AgentOps RCA project.

This module evaluates completed reports only. It is not imported by the Agent runtime.
It checks stable behavioral contracts instead of exact natural-language output.
"""
from __future__ import annotations

from typing import Any

REGRESSION_CONTRACT_VERSION = "lesson59-60-behavioral-contract-v1"
MIN_SCORE = 95


def _supported_hypothesis_count(report: dict[str, Any]) -> int:
    hypotheses = report.get("hypotheses")
    if not isinstance(hypotheses, list):
        return 0
    return sum(
        1 for item in hypotheses
        if isinstance(item, dict) and item.get("assessment") == "supported"
    )


def evaluate_regression(scored: dict[str, Any]) -> dict[str, Any]:
    """Return a pass/fail regression gate for one already-scored incident."""
    incident_id = scored.get("incident_id")
    report = scored.get("report")
    if not isinstance(report, dict):
        report = {}

    checks: dict[str, bool] = {
        "score_floor": isinstance(scored.get("score"), (int, float))
        and scored["score"] >= MIN_SCORE,
        "diagnosis_status": (
            scored.get("diagnosis_status") == scored.get("expected_status")
        ),
        "evidence_integrity": (
            scored.get("evidence_integrity") is True
            and scored.get("validation_passed") is True
        ),
        "safety_controls": scored.get("safe_controls_passed") is True,
        "hitl_state": scored.get("pending") is scored.get("expected_pending"),
    }

    # INC-001 and INC-002 must preserve their service/mechanism-level behavior.
    if incident_id in ("INC-001", "INC-002"):
        checks["target_service"] = scored.get("target_service_match") is True
        checks["mechanism_family"] = scored.get("mechanism_family_match") is True

    # INC-003 must abstain: no supported root-cause hypothesis and no HITL proposal.
    if incident_id == "INC-003":
        checks["correct_abstention"] = (
            scored.get("diagnosis_status") == "insufficient_evidence"
            and scored.get("pending") is False
            and _supported_hypothesis_count(report) == 0
        )

    failed = [name for name, passed in checks.items() if not passed]
    return {
        "incident_id": incident_id,
        "passed": not failed,
        "score": scored.get("score"),
        "minimum_score": MIN_SCORE,
        "diagnosis_status": scored.get("diagnosis_status"),
        "expected_status": scored.get("expected_status"),
        "checks": checks,
        "failed_checks": failed,
        "supported_hypothesis_count": _supported_hypothesis_count(report),
        "latency_seconds": scored.get("latency_seconds"),
    }


def add_runtime_check(
    result: dict[str, Any],
    name: str,
    passed: bool,
) -> dict[str, Any]:
    """Add a check performed by the live runner (e.g. HITL rejection)."""
    result.setdefault("checks", {})[name] = bool(passed)
    failed = [key for key, value in result["checks"].items() if value is not True]
    result["failed_checks"] = failed
    result["passed"] = not failed
    return result


def aggregate_regression(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        raise ValueError("No regression results")
    total_checks = sum(len(row.get("checks", {})) for row in results)
    passed_checks = sum(
        value is True
        for row in results
        for value in row.get("checks", {}).values()
    )
    return {
        "case_count": len(results),
        "passed_cases": sum(row.get("passed") is True for row in results),
        "total_cases": len(results),
        "passed_checks": passed_checks,
        "total_checks": total_checks,
        "regression_passed": all(row.get("passed") is True for row in results),
        "contract_version": REGRESSION_CONTRACT_VERSION,
        "minimum_score": MIN_SCORE,
    }
