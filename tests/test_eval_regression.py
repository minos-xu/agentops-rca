"""Offline tests for Lesson 61 regression gates; no LLM/DB/Redis/MCP calls."""
from __future__ import annotations

from evaluation.eval_regression import evaluate_regression, aggregate_regression


def make_row(incident_id: str) -> dict:
    common = {
        "incident_id": incident_id,
        "score": 100,
        "evidence_integrity": True,
        "validation_passed": True,
        "safe_controls_passed": True,
        "report": {"hypotheses": []},
        "latency_seconds": 1.0,
    }
    if incident_id == "INC-001":
        return {
            **common,
            "diagnosis_status": "prioritized_hypothesis",
            "expected_status": "prioritized_hypothesis",
            "pending": True,
            "expected_pending": True,
            "target_service_match": True,
            "mechanism_family_match": True,
            "report": {"hypotheses": [{"assessment": "supported"}]},
        }
    if incident_id == "INC-002":
        return {
            **common,
            "diagnosis_status": "prioritized_hypothesis",
            "expected_status": "prioritized_hypothesis",
            "pending": True,
            "expected_pending": True,
            "target_service_match": True,
            "mechanism_family_match": True,
            "report": {"hypotheses": [{"assessment": "supported"}]},
        }
    return {
        **common,
        "diagnosis_status": "insufficient_evidence",
        "expected_status": "insufficient_evidence",
        "pending": False,
        "expected_pending": False,
        "target_service_match": None,
        "mechanism_family_match": None,
        "report": {"hypotheses": [{"assessment": "possible"}]},
    }


def check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[PASS] {label}")


def main() -> None:
    rows = [make_row(case_id) for case_id in ("INC-001", "INC-002", "INC-003")]
    results = [evaluate_regression(row) for row in rows]
    check(all(row["passed"] for row in results), "accepted baseline contract passes all three cases")

    bad = make_row("INC-001")
    bad["diagnosis_status"] = "insufficient_evidence"
    result = evaluate_regression(bad)
    check("diagnosis_status" in result["failed_checks"], "diagnosis status regression is detected")

    bad = make_row("INC-002")
    bad["mechanism_family_match"] = False
    result = evaluate_regression(bad)
    check("mechanism_family" in result["failed_checks"], "mechanism-family regression is detected")

    bad = make_row("INC-001")
    bad["evidence_integrity"] = False
    result = evaluate_regression(bad)
    check("evidence_integrity" in result["failed_checks"], "evidence-integrity regression is detected")

    bad = make_row("INC-002")
    bad["safe_controls_passed"] = False
    result = evaluate_regression(bad)
    check("safety_controls" in result["failed_checks"], "unsafe control state is detected")

    bad = make_row("INC-001")
    bad["pending"] = False
    result = evaluate_regression(bad)
    check("hitl_state" in result["failed_checks"], "unexpected HITL state is detected")

    bad = make_row("INC-003")
    bad["pending"] = True
    bad["report"] = {"hypotheses": [{"assessment": "supported"}]}
    result = evaluate_regression(bad)
    check("correct_abstention" in result["failed_checks"], "INC-003 false diagnosis / proposal is detected")

    bad = make_row("INC-001")
    bad["score"] = 90
    result = evaluate_regression(bad)
    check("score_floor" in result["failed_checks"], "score drop below regression floor is detected")

    aggregate = aggregate_regression(results)
    check(
        aggregate["regression_passed"] and aggregate["passed_cases"] == 3,
        "aggregate regression report passes",
    )

    print("ALL LESSON 61 OFFLINE REGRESSION TESTS PASSED")


if __name__ == "__main__":
    main()
