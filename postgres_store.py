"""Lesson 55: durable session registry and DB-only synthetic action audit.

Postgres is local in this teaching demo. This module has no remediation tooling.
"""
from __future__ import annotations

import json
from typing import Any

from hitl import ApprovalError, SIMULATED_ACTIONS, approval_decision, make_proposal


class SessionRepository:
    """HTTP session ID -> LangGraph thread ID; the DB is source of truth."""

    def __init__(self, conn: Any):
        self.conn = conn

    async def setup(self) -> None:
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS agentops_sessions (
                session_id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS agentops_simulation_audit (
                id BIGSERIAL PRIMARY KEY,
                action_id TEXT NOT NULL,
                incident_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('simulated', 'rejected')),
                payload JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (action_id, status)
            )
        """)

    async def load(self) -> dict[str, str]:
        async with self.conn.cursor() as cur:
            await cur.execute("SELECT session_id, thread_id FROM agentops_sessions")
            rows = await cur.fetchall()
        return {r["session_id"]: r["thread_id"] for r in rows}

    async def insert(self, session_id: str, thread_id: str) -> None:
        await self.conn.execute(
            "INSERT INTO agentops_sessions(session_id, thread_id) VALUES (%s, %s)",
            (session_id, thread_id),
        )

    async def reset(self, session_id: str, new_thread_id: str) -> None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                "UPDATE agentops_sessions SET thread_id=%s, updated_at=NOW() WHERE session_id=%s",
                (new_thread_id, session_id),
            )
            if cur.rowcount != 1:
                raise RuntimeError("Session row disappeared during reset")


class PostgresSimulationAudit:
    """Synchronous audit adapter for the existing sync LangGraph action nodes.

    UNIQUE(action_id,status) + INSERT ON CONFLICT make the *record* idempotent
    across restarts and repeat requests. There are no real remediation side effects.
    This is not a cross-system transactional executor or multi-worker design.
    """

    def __init__(self, dsn: str):
        import psycopg
        from psycopg.rows import dict_row
        self._connection = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)

    def close(self) -> None:
        self._connection.close()

    @staticmethod
    def _validate_proposal(proposal: Any) -> dict:
        if not isinstance(proposal, dict):
            raise ApprovalError("无效模拟提案")
        incident = proposal.get("incident_id")
        if incident not in SIMULATED_ACTIONS:
            raise ApprovalError("模拟动作不在白名单")
        canonical = make_proposal({
            "incident_id": incident,
            "validation": "passed",
            "diagnosis_status": "prioritized_hypothesis",
            "safe_to_remediate": False,
            "recovery_verified": False,
            "hypotheses": [{"assessment": "supported"}],
        })
        if not canonical or proposal != canonical:
            raise ApprovalError("提案与预定义白名单不符")
        return canonical

    def _write_once(self, receipt: dict) -> bool:
        from psycopg.types.json import Jsonb
        with self._connection.cursor() as cur:
            cur.execute("""
                INSERT INTO agentops_simulation_audit
                    (action_id, incident_id, status, payload)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (action_id, status) DO NOTHING
                RETURNING id
            """, (receipt["action_id"], receipt["incident_id"],
                  receipt["status"], Jsonb(receipt)))
            return cur.fetchone() is not None

    def read(self) -> list[dict]:
        with self._connection.cursor() as cur:
            cur.execute("SELECT payload FROM agentops_simulation_audit ORDER BY id DESC LIMIT 100")
            rows = cur.fetchall()
        return [r["payload"] for r in reversed(rows)]

    def denied(self, proposal: dict, note: str = "rejected by human") -> dict:
        proposal = self._validate_proposal(proposal)
        receipt = {
            "action_id": proposal["action_id"],
            "incident_id": proposal["incident_id"],
            "status": "rejected",
            "mode": "synthetic_dry_run",
            "note": note,
            "real_system_changed": False,
            "recovery_verified": False,
        }
        self._write_once(receipt)
        return receipt

    def simulate(self, proposal: dict, resume: Any) -> dict:
        proposal = self._validate_proposal(proposal)
        if approval_decision(resume, proposal) != "approved":
            raise ApprovalError("缺少正确的人工审批")
        receipt = {
            "action_id": proposal["action_id"],
            "incident_id": proposal["incident_id"],
            "action": proposal["action"],
            "target": proposal["target"],
            "status": "simulated",
            "mode": "synthetic_dry_run",
            "real_system_changed": False,
            "recovery_verified": False,
        }
        if not self._write_once(receipt):
            return {
                **receipt,
                "status": "already_simulated",
            }
        return receipt
