"""Lesson 53: fail-closed, simulation-only human approval and audit.

No network, subprocess, shell, Kubernetes or production effects.
This module deliberately does NOT declare any incident recovered.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SIMULATED_ACTIONS = {
    "INC-001": {
        "action": "simulate_payment_restart",
        "target": "payment (synthetic)",
        "description": "仅模拟重启 Payment 测试实例；不能证明连接池耗尽的成因已解决。",
        "risk": "真实重启可能中断请求、影响事务；本课绝不执行真实重启。",
    },
    "INC-002": {
        "action": "simulate_catalog_scale_out",
        "target": "catalog (synthetic)",
        "description": "仅模拟为 Catalog 添加一个测试副本；不能证明 CPU 饱和由索引刷新造成。",
        "risk": "真实扩容可能产生费用并影响负载均衡；本课绝不实际扩容。",
    },
}


class ApprovalError(ValueError):
    pass


def make_proposal(report: dict) -> dict:
    """Return a narrowly scoped simulated proposal, never a production grant."""
    if not isinstance(report, dict):
        return {}
    incident = report.get("incident_id")
    action = SIMULATED_ACTIONS.get(incident)
    if (not action or report.get("validation") != "passed"
            or report.get("diagnosis_status") != "prioritized_hypothesis"
            or report.get("safe_to_remediate") is not False
            or report.get("recovery_verified") is not False
            or not any(h.get("assessment") == "supported"
                       for h in report.get("hypotheses", []) if isinstance(h, dict))):
        return {}
    # Fixed sandbox policy, NOT LLM-selected production actuation.
    raw = f"lesson53|{incident}|{action['action']}"
    action_id = "SIM-" + hashlib.sha256(raw.encode()).hexdigest()[:12].upper()
    return {
        "action_id": action_id,
        "incident_id": incident,
        **action,
        "mode": "synthetic_dry_run",
        "requires_human_approval": True,
        "real_execution_allowed": False,
        "recovery_verified": False,
    }


def approval_decision(resume: Any, proposal: dict) -> str:
    """No accidental approval: exact match required, else a rejected decision."""
    if not isinstance(resume, dict) or not proposal:
        return "rejected"
    if resume.get("action_id") != proposal.get("action_id"):
        return "rejected"
    if resume.get("decision") == "approve":
        return "approved"
    return "rejected"


class SimulationAudit:
    """JSONL audit. Single-process teaching implementation, not transactional."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        result = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                result.append(json.loads(line))
        return result

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        event = {"timestamp": datetime.now(timezone.utc).isoformat(), **data}
        with self.path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(event, ensure_ascii=False) + "\n")
            fp.flush()

    def denied(self, proposal: dict, note: str = "rejected by human") -> dict:
        receipt = {
            "action_id": proposal.get("action_id", ""),
            "incident_id": proposal.get("incident_id", ""),
            "status": "rejected",
            "mode": "synthetic_dry_run",
            "note": note,
            "recovery_verified": False,
        }
        self._write(receipt)
        return receipt

    def simulate(self, proposal: dict, resume: Any) -> dict:
        """No real actuation. Idempotent per action ID in audit file."""
        if not proposal or proposal.get("mode") != "synthetic_dry_run":
            raise ApprovalError("不是受控模拟提案")
        if proposal.get("real_execution_allowed") is not False:
            raise ApprovalError("不允许生产执行权限")
        if proposal.get("recovery_verified") is not False:
            raise ApprovalError("不能声称已经恢复")
        registered = SIMULATED_ACTIONS.get(proposal.get("incident_id"))
        if registered is None or any(proposal.get(k) != v for k, v in registered.items()):
            raise ApprovalError("操作参数不属于预定义模拟白名单")
        # Check ID against deterministic canonical proposal, not the user field alone.
        expected = "SIM-" + hashlib.sha256(
            f"lesson53|{proposal['incident_id']}|{registered['action']}".encode()
        ).hexdigest()[:12].upper()
        if proposal.get("action_id") != expected:
            raise ApprovalError("提案编号不合法")
        if approval_decision(resume, proposal) != "approved":
            raise ApprovalError("缺少匹配该提案的人工批准")
        if any(x.get("action_id") == expected and x.get("status") == "simulated"
               for x in self.read()):
            return {
                "action_id": expected,
                "incident_id": proposal["incident_id"],
                "status": "already_simulated",
                "mode": "synthetic_dry_run",
                "recovery_verified": False,
            }
        receipt = {
            "action_id": expected,
            "incident_id": proposal["incident_id"],
            "action": registered["action"],
            "target": registered["target"],
            "status": "simulated",
            "mode": "synthetic_dry_run",
            "real_system_changed": False,
            "recovery_verified": False,
        }
        self._write(receipt)
        return receipt
