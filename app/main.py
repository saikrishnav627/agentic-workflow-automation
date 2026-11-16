"""FastAPI orchestration API for the multi-agent workflow."""
from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException
from langgraph.types import Command
from pydantic import BaseModel, Field

from .graph import build_graph

app = FastAPI(title="Agentic AI Workflow Automation", version="1.0.0")
graph = build_graph()


class WorkflowRequest(BaseModel):
    request: str = Field(..., min_length=5, max_length=2000)


class Approval(BaseModel):
    approved: bool
    reviewer: str = Field(..., min_length=1)


def _view(run_id: str) -> dict:
    snap = graph.get_state({"configurable": {"thread_id": run_id}})
    if not snap.values:
        raise HTTPException(status_code=404, detail="workflow not found")
    pending = [i.value for t in snap.tasks for i in t.interrupts]
    v = snap.values
    return {
        "run_id": run_id,
        "status": "awaiting_approval" if pending else v.get("status"),
        "pending_approval": pending[0] if pending else None,
        "plan": v.get("plan", []),
        "log": v.get("log", []),
    }


@app.post("/workflows")
def start(req: WorkflowRequest):
    run_id = uuid.uuid4().hex[:12]
    graph.invoke({"request": req.request, "log": []}, {"configurable": {"thread_id": run_id}})
    return _view(run_id)


@app.get("/workflows/{run_id}")
def get(run_id: str):
    return _view(run_id)


@app.post("/workflows/{run_id}/approve")
def approve(run_id: str, body: Approval):
    if _view(run_id)["status"] != "awaiting_approval":
        raise HTTPException(status_code=409, detail="workflow is not waiting for approval")
    graph.invoke(Command(resume=body.model_dump()), {"configurable": {"thread_id": run_id}})
    return _view(run_id)


@app.get("/health")
def health():
    return {"status": "ok"}
