"""Offline Lesson55 safety checks, no Postgres/LLM/MCP needed."""
from __future__ import annotations

import asyncio
from types import MethodType

from hitl import ApprovalError, make_proposal
from postgres_store import SessionRepository, PostgresSimulationAudit


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rowcount = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    async def execute(self, sql, args=None):
        if sql.startswith("SELECT session_id"):
            self._rows = [{"session_id": k, "thread_id": v} for k, v in self.connection.sessions.items()]
        elif sql.startswith("UPDATE agentops_sessions"):
            thread, sid = args
            self.rowcount = int(sid in self.connection.sessions)
            if self.rowcount:
                self.connection.sessions[sid] = thread

    async def fetchall(self):
        return self._rows


class FakeConnection:
    def __init__(self):
        self.sessions = {}
        self.created = 0

    async def execute(self, sql, args=None):
        if sql.strip().startswith("CREATE TABLE"):
            self.created += 1
        elif sql.startswith("INSERT INTO agentops_sessions"):
            sid, thread = args
            assert sid not in self.sessions
            self.sessions[sid] = thread

    def cursor(self):
        return FakeCursor(self)


async def test_sessions():
    conn = FakeConnection()
    repo = SessionRepository(conn)
    await repo.setup()
    assert conn.created == 2
    await repo.insert("secret-session", "thread-1")
    assert (await repo.load()) == {"secret-session": "thread-1"}
    await repo.reset("secret-session", "thread-2")
    assert (await SessionRepository(conn).load()) == {"secret-session": "thread-2"}
    try:
        await repo.reset("nonexistent-session", "thread-3")
    except RuntimeError:
        pass
    else:
        raise AssertionError("reset must fail for nonexistent session")
    print("[PASS] durable session repository insert/load/reset contract")


def test_audit():
    report = {
        "incident_id": "INC-001", "validation": "passed",
        "diagnosis_status": "prioritized_hypothesis",
        "safe_to_remediate": False, "recovery_verified": False,
        "hypotheses": [{"assessment": "supported"}],
    }
    proposal = make_proposal(report)
    assert proposal
    audit = PostgresSimulationAudit.__new__(PostgresSimulationAudit)
    entries = {}

    def write(self, receipt):
        key = receipt["action_id"], receipt["status"]
        if key in entries:
            return False
        entries[key] = receipt
        return True

    audit._write_once = MethodType(write, audit)
    assert audit.denied(proposal)["status"] == "rejected"
    assert audit.denied(proposal)["status"] == "rejected"
    assert len(entries) == 1
    for bad in [
        {**proposal, "target": "production-db"},
        {**proposal, "real_execution_allowed": True},
        {**proposal, "action_id": "SIM-FAKE"},
        {**proposal, "recovery_verified": True},
    ]:
        try:
            audit.simulate(bad, {"decision": "approve", "action_id": bad["action_id"]})
        except ApprovalError:
            pass
        else:
            raise AssertionError("tampered proposal was accepted")
    try:
        audit.simulate(proposal, {"decision": "approve", "action_id": "SIM-WRONG"})
    except ApprovalError:
        pass
    else:
        raise AssertionError("approval ID mismatch was accepted")
    okay = {"decision": "approve", "action_id": proposal["action_id"]}
    receipt = audit.simulate(proposal, okay)
    assert receipt["status"] == "simulated" and receipt["real_system_changed"] is False
    assert audit.simulate(proposal, okay)["status"] == "already_simulated"
    assert len(entries) == 2
    print("[PASS] DB audit: allowlist, human approval, tamper checks and idempotency")


if __name__ == "__main__":
    asyncio.run(test_sessions())
    test_audit()
    print("ALL LESSON 55 OFFLINE TESTS PASSED")
