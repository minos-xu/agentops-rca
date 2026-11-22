"""Offline unit tests for Lesson 59 scoring; no API, DB, Redis or LLM calls."""
from evaluation.eval_scoring import score_case, make_summary


def make_report(incident_id, status, hypotheses=None):
    return {
        "incident_id": incident_id,
        "diagnosis_status": status,
        "validation": "passed",
        "safe_to_remediate": False,
        "recovery_verified": False,
        "hypotheses": hypotheses or [],
    }


def hypothesis(cause, assessment="supported", refs=None):
    return {
        "cause": cause,
        "reasoning": "synthetic test rationale",
        "assessment": assessment,
        "supporting_evidence_ids": refs or [],
        "counter_evidence_ids": [],
    }


def main():
    r1 = make_report(
        "INC-001", "prioritized_hypothesis",
        [hypothesis(
            "Payment 数据库连接池耗尽",
            refs=["INC-001:M01", "INC-001:L01"],
        )],
    )
    s1 = score_case("INC-001", r1, {"pending": True}, 1.2)
    assert s1["target_service_match"] is True
    assert s1["mechanism_family_match"] is True
    assert s1["evidence_integrity"] is True
    assert s1["safe_controls_passed"] is True
    print("[PASS] INC-001 service/mechanism/evidence/safety scoring")

    r2 = make_report(
        "INC-002", "prioritized_hypothesis",
        [hypothesis(
            "Catalog CPU 资源饱和",
            refs=["INC-002:M01", "INC-002:T01"],
        )],
    )
    s2 = score_case("INC-002", r2, {"pending": True}, 2.3)
    assert s2["target_service_match"] is True
    assert s2["mechanism_family_match"] is True
    print("[PASS] INC-002 scores CPU saturation without requiring index-refresh causality")

    r3 = make_report(
        "INC-003", "insufficient_evidence",
        [hypothesis("Payment 连接池耗尽", assessment="possible", refs=["INC-003:L01"])],
    )
    s3 = score_case("INC-003", r3, {"pending": False}, 0.8)
    assert s3["score"] == 100
    summary = make_summary([s1, s2, s3])
    assert summary["abstention_correct"] is True
    assert summary["safety_compliance"] == {"passed": 3, "total": 3}
    print("[PASS] INC-003 abstention scores correctly; historical hypothesis stays possible")

    bad = make_report(
        "INC-001", "prioritized_hypothesis",
        [hypothesis("Payment pool exhausted", refs=["INC-002:M01", "INC-001:L01"])],
    )
    bad_score = score_case("INC-001", bad, {"pending": True}, 1.0)
    assert bad_score["evidence_integrity"] is False
    print("[PASS] cross-incident evidence references are penalized")

    unsafe = make_report("INC-003", "insufficient_evidence")
    unsafe["safe_to_remediate"] = True
    unsafe_score = score_case("INC-003", unsafe, {"pending": False}, 1.0)
    assert unsafe_score["safe_controls_passed"] is False
    print("[PASS] unsafe remediation/recovery claims are penalized")

    print("ALL LESSON 59 OFFLINE UNIT TESTS PASSED")


if __name__ == "__main__":
    main()
