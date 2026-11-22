"""LangGraph interrupt/resume integration test. Requires only langgraph, no LLM/MCP."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, Command
from hitl import make_proposal, approval_decision, SimulationAudit


class State(TypedDict, total=False):
    report: dict
    proposal: dict
    decision: str
    receipt: dict


def build(audit: SimulationAudit):
    def prepare(state: State) -> dict:
        return {"proposal": make_proposal(state["report"])}

    def gate(state: State) -> dict:
        p = state["proposal"]
        raw = interrupt({"proposal": p})
        return {"decision": approval_decision(raw, p)}

    def execute(state: State) -> dict:
        p = state["proposal"]
        return {"receipt": audit.simulate(p, {"decision": "approve", "action_id": p["action_id"]})}

    def reject(state: State) -> dict:
        return {"receipt": audit.denied(state["proposal"])}

    builder = StateGraph(State)
    for name, fn in [("prepare", prepare), ("gate", gate), ("execute", execute), ("reject", reject)]:
        builder.add_node(name, fn)
    builder.add_edge(START, "prepare")
    builder.add_conditional_edges("prepare", lambda s: "gate" if s["proposal"] else "done", {"gate": "gate", "done": END})
    builder.add_conditional_edges("gate", lambda s: s["decision"], {"approved": "execute", "rejected": "reject"})
    builder.add_edge("execute", END)
    builder.add_edge("reject", END)
    return builder.compile(checkpointer=InMemorySaver())


def report(inc: str, status: str = "prioritized_hypothesis") -> dict:
    return {"incident_id": inc, "validation": "passed", "diagnosis_status": status,
            "safe_to_remediate": False, "recovery_verified": False,
            "hypotheses": [{"assessment": "supported"}]}


def run():
    with tempfile.TemporaryDirectory() as td:
        audit = SimulationAudit(Path(td) / "audit.jsonl")
        graph = build(audit)

        cfg = {"configurable": {"thread_id": str(uuid4())}}
        graph.invoke({"report": report("INC-001")}, cfg)
        snap = graph.get_state(cfg)
        assert "gate" in snap.next and snap.values["proposal"]["action_id"]
        assert audit.read() == [], "interrupt must occur before any effect"
        print("[PASS] LangGraph interrupt paused before simulation")
        action_id = snap.values["proposal"]["action_id"]
        result = graph.invoke(Command(resume={"decision": "approve", "action_id": action_id}), cfg)
        assert result["receipt"]["status"] == "simulated" and len(audit.read()) == 1
        assert graph.get_state(cfg).next == ()
        print("[PASS] same thread_id resume approved once")

        cfg2 = {"configurable": {"thread_id": str(uuid4())}}
        graph.invoke({"report": report("INC-002")}, cfg2)
        aid2 = graph.get_state(cfg2).values["proposal"]["action_id"]
        result = graph.invoke(Command(resume={"decision": "reject", "action_id": aid2}), cfg2)
        assert result["receipt"]["status"] == "rejected"
        assert len([e for e in audit.read() if e["status"] == "simulated"]) == 1
        print("[PASS] rejected approval never simulates")

        cfg3 = {"configurable": {"thread_id": str(uuid4())}}
        graph.invoke({"report": report("INC-002")}, cfg3)
        result = graph.invoke(Command(resume={"decision": "approve", "action_id": action_id}), cfg3)
        assert result["receipt"]["status"] == "rejected"
        print("[PASS] cross-thread action ID cannot approve another proposal")

        cfg4 = {"configurable": {"thread_id": str(uuid4())}}
        result = graph.invoke({"report": report("INC-003", "insufficient_evidence")}, cfg4)
        assert not result["proposal"] and graph.get_state(cfg4).next == ()
        print("[PASS] insufficient evidence skips approval and simulation")

    print("ALL LESSON 53 GRAPH TESTS PASSED")

if __name__ == "__main__":
    run()
