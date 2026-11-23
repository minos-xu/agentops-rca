"""Lesson 52: offline RCA validation tests; NO LLM, MCP or GPU required."""
from __future__ import annotations

from copy import deepcopy

from app.rca.incident_mock_data import query_telemetry
from app.rca.rca_core import (
    TOOLS, make_evidence_catalog, validate_rca,
    RCAValidationError, insufficient_report, render_report, has_observed_mechanism_signal,
)


def catalog_for(inc: str) -> dict:
    return make_evidence_catalog([query_telemetry(tool, inc) for tool in TOOLS], inc)


def lookup(cat: dict, needle: str) -> str:
    ids = [e["id"] for e in cat["items"] if needle in e["statement"]]
    assert ids, f"missing evidence containing {needle}"
    return ids[0]


def valid_result(cat: dict, hypothesis: bool = True) -> dict:
    inc = cat["incident_id"]
    support = [lookup(cat, "db_pool_active"), lookup(cat, "pool wait timeout")] if inc == "INC-001" else []
    return {
        "incident_id": inc,
        "diagnosis_status": "prioritized_hypothesis" if hypothesis else "insufficient_evidence",
        "summary": "合成遥测仅支持初步排查结论。",
        "hypotheses": [{
            "cause": "Payment 连接池资源饱和（待核验发生机制）",
            "assessment": "supported", "supporting_evidence_ids": support,
            "counter_evidence_ids": [], "unknowns": ["为何出现连接池饱和"],
            "reasoning": "指标和错误日志均提示连接池无法取得空闲连接。",
        }] if hypothesis else [],
        "next_read_only_steps": ["只读检查连接池等待时长和数据库慢 SQL"],
        "safe_to_remediate": False, "recovery_verified": False,
    }


def rejects(fn, label):
    try:
        fn()
    except RCAValidationError:
        print(f"[PASS] {label}")
        return
    raise AssertionError(f"Unexpected acceptance: {label}")


def main():
    for inc in ("INC-001", "INC-002", "INC-003"):
        cat = catalog_for(inc)
        assert len(cat["items"]) > 0 and all(x["synthetic"] is True for x in cat["items"])
        assert all(x["id"].startswith(inc + ":") for x in cat["items"])
        assert all(s["ok"] for s in cat["tool_status"].values())
        assert "expected_cause" not in repr(cat)
        print(f"[PASS] {inc} evidence catalog: {len(cat['items'])} traceable facts")

    cat1 = catalog_for("INC-001")
    cat2 = catalog_for("INC-002")
    cat3 = catalog_for("INC-003")
    good = valid_result(cat1)
    report = validate_rca(good, cat1)
    assert report["diagnosis_status"] == "prioritized_hypothesis" and report["validation"] == "passed"
    rendered = render_report(report, cat1)
    assert "MCP" not in rendered or "模拟" in rendered
    assert good["hypotheses"][0]["supporting_evidence_ids"][0] in rendered
    print("[PASS] valid prioritized hypothesis with metrics + logs")

    conservative = validate_rca(valid_result(cat3, False), cat3)
    assert conservative["diagnosis_status"] == "insufficient_evidence"
    print("[PASS] ambiguous INC-003 remains insufficient_evidence")

    # Two sources may support a *symptom* without identifying its root mechanism.
    misleading = valid_result(cat3, False)
    misleading["diagnosis_status"] = "prioritized_hypothesis"
    misleading["hypotheses"] = [{
        "cause": "payment 下游变慢引发 checkout 间歇性超时",
        "assessment": "supported",
        "supporting_evidence_ids": [lookup(cat3, "payment.p95_ms_now"),
                                    lookup(cat3, "intermittent downstream timeout")],
        "counter_evidence_ids": [],
        "unknowns": ["缺少具体故障机制证据"],
        "reasoning": "延迟和超时只能证明异常传播，不能确认根因机制",
    }]
    rejects(lambda: validate_rca(misleading, cat3), "symptoms alone cannot prioritize a root mechanism")
    assert has_observed_mechanism_signal(cat1)
    assert has_observed_mechanism_signal(cat2)
    assert not has_observed_mechanism_signal(cat3)
    print("[PASS] mechanism quality gate on three synthetic cases")

    bad = deepcopy(good)
    bad["hypotheses"][0]["supporting_evidence_ids"].append("INC-001:Z99")
    rejects(lambda: validate_rca(bad, cat1), "fabricated evidence ID rejected")

    bad = deepcopy(good)
    bad["hypotheses"][0]["supporting_evidence_ids"].append(lookup(cat2, "cpu_pct"))
    rejects(lambda: validate_rca(bad, cat1), "cross-incident evidence ID rejected")

    bad = deepcopy(good)
    bad["incident_id"] = "INC-002"
    rejects(lambda: validate_rca(bad, cat1), "wrong incident ID rejected")

    bad = deepcopy(good)
    bad["safe_to_remediate"] = True
    rejects(lambda: validate_rca(bad, cat1), "unapproved remediation rejected")

    bad = deepcopy(good)
    bad["recovery_verified"] = True
    rejects(lambda: validate_rca(bad, cat1), "fabricated recovery rejected")

    bad = deepcopy(good)
    bad["next_read_only_steps"] = ["立即重启服务"]
    rejects(lambda: validate_rca(bad, cat1), "write operation in next steps rejected")

    bad = deepcopy(good)
    bad["hypotheses"][0]["supporting_evidence_ids"] = [lookup(cat1, "db_pool_active")]
    rejects(lambda: validate_rca(bad, cat1), "one-source overclaim rejected")

    broken = [query_telemetry(tool, "INC-001") for tool in TOOLS if tool != "search_logs"]
    partial = make_evidence_catalog(broken, "INC-001")
    assert not partial["tool_status"]["search_logs"]["ok"]
    bad = deepcopy(good)
    rejects(lambda: validate_rca(bad, partial), "missing tool source cannot support prioritized report")

    mixed = [query_telemetry(tool, "INC-001") for tool in TOOLS]
    mixed[0]["incident_id"] = "INC-002"
    partial2 = make_evidence_catalog(mixed, "INC-001")
    assert not partial2["tool_status"]["get_service_metrics"]["ok"]
    print("[PASS] cross-incident MCP payload discarded, becomes explicit gap")

    fallback = insufficient_report(partial, "MCP failed")
    assert fallback["diagnosis_status"] == "insufficient_evidence"
    assert fallback["safe_to_remediate"] is False
    assert fallback["recovery_verified"] is False
    print("[PASS] safe fallback with no fabricated RCA or remediation")
    print("ALL LESSON 52 RCA TESTS PASSED")


if __name__ == "__main__":
    main()
