"""Lesson 60: robustness metrics for AgentOps RCA.

This module compares semantic outcomes across repeated and paraphrased runs.
It deliberately does not claim statistical reliability from a tiny synthetic set.
"""
from __future__ import annotations

from typing import Any

SIGNATURE_FIELDS = (
    "diagnosis_status",
    "target_service_match",
    "mechanism_family_match",
    "evidence_integrity",
    "validation_passed",
    "safe_controls_passed",
    "pending",
)


def semantic_signature(row: dict[str, Any]) -> dict[str, Any]:
    """Fields that should remain stable across equivalent prompts."""
    return {field: row.get(field) for field in SIGNATURE_FIELDS}


def compare_runs(
    first: dict[str, Any],
    second: dict[str, Any],
    *,
    fields: tuple[str, ...] = SIGNATURE_FIELDS,
) -> dict[str, Any]:
    mismatches = {
        field: {
            "first": first.get(field),
            "second": second.get(field),
        }
        for field in fields
        if first.get(field) != second.get(field)
    }
    return {"consistent": not mismatches, "mismatches": mismatches}


def memory_interference_check(row: dict[str, Any]) -> dict[str, Any]:
    """INC-003 must not inherit the historical Payment cause as a supported RCA."""
    checks = {
        "insufficient_evidence": row.get("diagnosis_status") == "insufficient_evidence",
        "no_supported_hypothesis": row.get("supported_hypothesis_count") == 0,
        "no_pending_proposal": row.get("pending") is False,
        "safe_controls": row.get("safe_controls_passed") is True,
        "evidence_validation": (
            row.get("evidence_integrity") is True
            and row.get("validation_passed") is True
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
    }


def summarize_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    if not checks:
        return {"passed": 0, "total": 0, "rate": None}
    passed = sum(item.get("consistent") is True or item.get("passed") is True for item in checks)
    return {
        "passed": passed,
        "total": len(checks),
        "rate": round(passed / len(checks), 4),
    }
