"""LangGraph wiring: planner -> retriever -> (approval?) -> executor loop -> validator."""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .agents import executor, human_approval, planner, retriever, validator
from .state import WorkflowState


def route_next(state: WorkflowState) -> str:
    """Conditional routing: run the next step, pause for approval, or finish."""
    if state.get("status") == "failed":
        return "validator"
    if state["current"] >= len(state["plan"]):
        return "validator"
    step = state["plan"][state["current"]]
    if step["risk"] == "high" and "approved" not in step:
        return "human_approval"
    return "executor"


def build_graph(checkpointer=None):
    g = StateGraph(WorkflowState)
    g.add_node("planner", planner)
    g.add_node("retriever", retriever)
    g.add_node("human_approval", human_approval)
    g.add_node("executor", executor)
    g.add_node("validator", validator)

    g.add_edge(START, "planner")
    g.add_edge("planner", "retriever")
    routes = {"executor": "executor", "human_approval": "human_approval", "validator": "validator"}
    g.add_conditional_edges("retriever", route_next, routes)
    g.add_conditional_edges("executor", route_next, routes)
    g.add_edge("human_approval", "executor")
    g.add_edge("validator", END)
    # The checkpointer saves state at each step, so a run can pause for a human and resume later
    return g.compile(checkpointer=checkpointer or MemorySaver())
