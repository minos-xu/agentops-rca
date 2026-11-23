"""Lesson 53 offline checks; NO MCP, DeepSeek or GPU required."""
from __future__ import annotations

import tempfile
from pathlib import Path
from app.agent.hitl import (
    ApprovalError, SimulationAudit, make_proposal, approval_decision,
)


def valid_report(inc: str, status: str = "prioritized_hypothesis") -> dict:
    return {
        "incident_id": inc,
        "validation": "passed",
        "diagnosis_status": status,
        "hypotheses": [{"assessment": "supported"}],
        "safe_to_remediate": False,
        "recovery_verified": False,
    }


def expect_rejected(fn):
    try:
        fn()
    except ApprovalError:
        return
    raise AssertionError("unsafe operation was not rejected")


def main():
    a = make_proposal(valid_report("INC-001"))
    b = make_proposal(valid_report("INC-002"))
    assert a and b and a["action_id"] != b["action_id"]
    assert a["mode"] == "synthetic_dry_run" and not a["real_execution_allowed"]
    print("[PASS] only allowlisted dry-run proposals created")

    assert make_proposal(valid_report("INC-003", "insufficient_evidence")) == {}
    assert make_proposal(valid_report("INC-001", "insufficient_evidence")) == {}
    failed = valid_report("INC-001")
    failed["validation"] = "fallback"
    assert make_proposal(failed) == {}
    print("[PASS] insufficient evidence / fallback blocks proposals")

    assert approval_decision(None, a) == "rejected"
    assert approval_decision({"decision": "approve"}, a) == "rejected"
    assert approval_decision({"decision": "approve", "action_id": b["action_id"]}, a) == "rejected"
    assert approval_decision({"decision": "reject", "action_id": a["action_id"]}, a) == "rejected"
    assert approval_decision({"decision": "approve", "action_id": a["action_id"]}, a) == "approved"
    print("[PASS] exact action ID and explicit approval required")

    with tempfile.TemporaryDirectory() as td:
        audit = SimulationAudit(Path(td) / "audit.jsonl")
        expect_rejected(lambda: audit.simulate(a, None))
        expect_rejected(lambda: audit.simulate(a, {"decision": "approve", "action_id": b["action_id"]}))
        assert audit.read() == []
        receipt = audit.denied(a)
        assert receipt["status"] == "rejected" and len(audit.read()) == 1
        print("[PASS] rejection and mismatched approvals never execute")

        result = audit.simulate(a, {"decision": "approve", "action_id": a["action_id"]})
        assert result["status"] == "simulated"
        assert result["real_system_changed"] is False and result["recovery_verified"] is False
        assert len(audit.read()) == 2
        again = audit.simulate(a, {"decision": "approve", "action_id": a["action_id"]})
        assert again["status"] == "already_simulated" and len(audit.read()) == 2
        new_audit = SimulationAudit(Path(td) / "audit.jsonl")
        assert new_audit.simulate(a, {"decision": "approve", "action_id": a["action_id"]})["status"] == "already_simulated"
        assert len(new_audit.read()) == 2
        print("[PASS] approval simulates once; repeated and restarted audit remains idempotent")

        tampered = {**a, "target": "production"}
        expect_rejected(lambda: audit.simulate(tampered, {"decision": "approve", "action_id": a["action_id"]}))
        tampered = {**a, "real_execution_allowed": True}
        expect_rejected(lambda: audit.simulate(tampered, {"decision": "approve", "action_id": a["action_id"]}))
        tampered = {**a, "action_id": "SIM-FORGED"}
        expect_rejected(lambda: audit.simulate(tampered, {"decision": "approve", "action_id": "SIM-FORGED"}))
        print("[PASS] tampered production targets and forged proposals rejected")

    print("ALL LESSON 53 HITL CORE TESTS PASSED")

if __name__ == "__main__":
    main()
