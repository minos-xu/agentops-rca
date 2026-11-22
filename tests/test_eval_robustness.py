"""Offline tests for Lesson 60 robustness metrics; no API/DB/Redis/LLM calls."""
from evaluation.eval_robustness import compare_runs, memory_interference_check


def row(**overrides):
    value = {
        "diagnosis_status": "prioritized_hypothesis",
        "target_service_match": True,
        "mechanism_family_match": True,
        "evidence_integrity": True,
        "validation_passed": True,
        "safe_controls_passed": True,
        "pending": True,
        "supported_hypothesis_count": 1,
    }
    value.update(overrides)
    return value


def main():
    a = row()
    b = row()
    assert compare_runs(a, b)["consistent"] is True
    print("[PASS] identical semantic outcomes are consistent")

    changed = row(mechanism_family_match=False)
    result = compare_runs(a, changed)
    assert result["consistent"] is False
    assert "mechanism_family_match" in result["mismatches"]
    print("[PASS] mechanism drift is detected")

    abstention = row(
        diagnosis_status="insufficient_evidence",
        target_service_match=None,
        mechanism_family_match=None,
        pending=False,
        supported_hypothesis_count=0,
    )
    result = memory_interference_check(abstention)
    assert result["passed"] is True
    print("[PASS] INC-003 abstention survives memory-interference check")

    contaminated = row(
        diagnosis_status="prioritized_hypothesis",
        pending=True,
        supported_hypothesis_count=1,
    )
    result = memory_interference_check(contaminated)
    assert result["passed"] is False
    assert result["checks"]["no_supported_hypothesis"] is False
    print("[PASS] historical-memory contamination is detected")

    unsafe = row(
        diagnosis_status="insufficient_evidence",
        target_service_match=None,
        mechanism_family_match=None,
        pending=False,
        supported_hypothesis_count=0,
        safe_controls_passed=False,
    )
    assert memory_interference_check(unsafe)["passed"] is False
    print("[PASS] unsafe recovery/remediation state is detected")

    print("ALL LESSON 60 OFFLINE UNIT TESTS PASSED")


if __name__ == "__main__":
    main()
