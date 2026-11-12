"""LangGraph workflow around the deterministic planner, tool registry, and critic."""

from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from finsight.agent import Plan, _grounded_phrase, _usable
from finsight.schemas import CopilotResponse, ToolCallRecord


class AgentState(TypedDict, total=False):
    question: str
    session_id: str
    started: float
    steps: int
    plan: dict
    evidence: list
    calls: list
    calculation: Optional[str]
    value: object
    answer: str
    behavior: str
    citations: list
    confidence: str
    refusal: Optional[str]
    provider_note: str
    response: dict


def invoke_copilot(copilot, question: str, session_id: str) -> CopilotResponse:
    """Run one question through the compiled planner, executor, and critic graph."""
    if not hasattr(copilot, "_compiled_graph"):
        copilot._compiled_graph = compile_copilot_graph(copilot)
    result = copilot._compiled_graph.invoke(
        {"question": question, "session_id": session_id, "steps": 0, "calls": []},
        config={"configurable": {"thread_id": session_id}},
    )
    return CopilotResponse(**result["response"])


def compile_copilot_graph(copilot):
    graph = StateGraph(AgentState)
    graph.add_node("plan", lambda state: _plan_node(copilot, state))
    graph.add_node("refuse", lambda state: _refuse_node(copilot, state))
    graph.add_node("search", lambda state: _search_node(copilot, state))
    graph.add_node("metadata", lambda state: _metadata_node(copilot, state))
    graph.add_node("calculate", lambda state: _calculate_node(copilot, state))
    graph.add_node("critic", lambda state: _critic_node(copilot, state))
    graph.add_node("finish", lambda state: _finish_node(copilot, state))
    graph.set_entry_point("plan")
    graph.add_conditional_edges("plan", _after_plan, {"refuse": "refuse", "search": "search"})
    graph.add_edge("refuse", END)
    graph.add_edge("search", "metadata")
    graph.add_edge("metadata", "calculate")
    graph.add_edge("calculate", "critic")
    graph.add_edge("critic", "finish")
    graph.add_edge("finish", END)
    return graph.compile(checkpointer=InMemorySaver())


def _plan_node(copilot, state: AgentState) -> dict:
    session = copilot.sessions.get(state["session_id"])
    plan = copilot._plan(state["question"], session.turns)
    return {"plan": asdict(plan), "steps": 1, "started": __import__("time").perf_counter()}


def _after_plan(state: AgentState) -> str:
    if state["plan"].get("refusal_reason"):
        return "refuse"
    return "search"


def _refuse_node(copilot, state: AgentState) -> dict:
    reason = state["plan"]["refusal_reason"]
    response = copilot._response(
        state["question"],
        copilot.sessions.get(state["session_id"]),
        reason,
        "refuse",
        [],
        None,
        "low",
        reason,
        [],
        state["started"],
        "policy_refusal",
    )
    return {"response": response.model_dump()}


def _search_node(copilot, state: AgentState) -> dict:
    plan = Plan(**state["plan"])
    calls = _records(state.get("calls", []))
    evidence = _usable(copilot._search(plan, state["question"], calls))
    return {"evidence": evidence, "calls": [item.model_dump() for item in calls], "steps": state["steps"] + 1}


def _metadata_node(copilot, state: AgentState) -> dict:
    plan = Plan(**state["plan"])
    calls = _records(state.get("calls", []))
    if state["steps"] < copilot.MAX_STEPS:
        copilot._metadata(plan, calls)
    return {"calls": [item.model_dump() for item in calls], "steps": state["steps"] + 1}


def _calculate_node(copilot, state: AgentState) -> dict:
    plan = Plan(**state["plan"])
    calls = _records(state.get("calls", []))
    calculation, value = copilot._calculate(plan, state.get("evidence", []), calls)
    steps = state["steps"] + (1 if calculation else 0)
    return {"calculation": calculation, "value": value, "calls": [item.model_dump() for item in calls], "steps": steps}


def _critic_node(copilot, state: AgentState) -> dict:
    plan = Plan(**state["plan"])
    answer, behavior, citations, confidence, refusal = copilot._critic(
        plan,
        state.get("evidence", []),
        state.get("value"),
        state.get("calculation"),
    )
    note = ""
    if behavior == "answer":
        answer, note = _grounded_phrase(state["question"], answer)
    return {
        "answer": answer,
        "behavior": behavior,
        "citations": [item.model_dump() for item in citations],
        "confidence": confidence,
        "refusal": refusal,
        "provider_note": note,
        "steps": state["steps"] + 1,
    }


def _finish_node(copilot, state: AgentState) -> dict:
    session = copilot.sessions.get(state["session_id"])
    reason = "completed" if state["steps"] <= copilot.MAX_STEPS else "step_limit"
    if session.token_estimate > copilot.MAX_TOKENS:
        reason = "token_budget"
    from finsight.schemas import Citation
    response = copilot._response(
        state["question"],
        session,
        state["answer"],
        state["behavior"],
        [Citation(**item) for item in state.get("citations", [])],
        state.get("calculation"),
        state["confidence"],
        state.get("refusal"),
        _records(state.get("calls", [])),
        state["started"],
        reason,
        provider_note_text=state.get("provider_note", ""),
    )
    return {"response": response.model_dump()}


def _records(calls: list) -> list[ToolCallRecord]:
    return [ToolCallRecord(**item) if isinstance(item, dict) else item for item in calls]
