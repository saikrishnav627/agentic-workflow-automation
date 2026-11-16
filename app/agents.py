"""The four specialized agents: planner, retriever, executor and validator."""
from __future__ import annotations

import os
import re

from .state import WorkflowState
from .tools import TOOLS, risk_of

# Small policy knowledge base the retrieval agent searches before anything is executed
POLICIES = {
    "create_account": "Accounts are created in Okta and Slack on day one. Usernames follow first.last.",
    "grant_access": "Admin access to production requires manager approval and expires after 30 days.",
    "order_equipment": "Standard laptop budget is $1,500. Orders above $1,000 need approval.",
    "send_email": "Welcome emails go out from people-ops@company.com.",
    "schedule_meeting": "New hires get a 30-minute onboarding call with their manager in week one.",
}


# ---------- Planner agent ----------
def _rule_based_plan(request: str) -> list[dict]:
    """Deterministic planner used when no LLM key is configured."""
    text = request.lower()
    name_match = re.search(r"\bfor ([A-Z][a-z]+(?: [A-Z][a-z]+)?)", request)
    name = name_match.group(1) if name_match else "employee"
    steps: list[dict] = []
    if "onboard" in text or "account" in text:
        steps += [{"tool": "create_account", "args": {"name": name, "system": "okta"}},
                  {"tool": "create_account", "args": {"name": name, "system": "slack"}}]
    if "admin" in text:
        resource = "production" if "prod" in text else "staging"
        steps.append({"tool": "grant_access", "args": {"name": name, "resource": resource, "level": "admin"}})
    elif "access" in text:
        steps.append({"tool": "grant_access", "args": {"name": name, "resource": "github", "level": "read"}})
    if "laptop" in text or "equipment" in text:
        cost = 2400.0 if "macbook pro" in text else 900.0
        steps.append({"tool": "order_equipment", "args": {"name": name, "item": "laptop", "cost": cost}})
    if "onboard" in text or "welcome" in text:
        steps.append({"tool": "send_email", "args": {"to": name, "subject": "Welcome to the team"}})
        steps.append({"tool": "schedule_meeting", "args": {"name": name, "topic": "Onboarding"}})
    return steps


def _llm_plan(request: str) -> list[dict]:
    from langchain_openai import ChatOpenAI
    from pydantic import BaseModel

    class Step(BaseModel):
        tool: str
        args: dict

    class Plan(BaseModel):
        steps: list[Step]

    llm = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o-mini"), temperature=0).with_structured_output(Plan)
    plan = llm.invoke(
        f"Break this request into tool calls. Available tools and argument names: "
        f"create_account(name, system), grant_access(name, resource, level), "
        f"order_equipment(name, item, cost), send_email(to, subject), schedule_meeting(name, topic).\n"
        f"Request: {request}"
    )
    return [s.model_dump() for s in plan.steps if s.tool in TOOLS]


def planner(state: WorkflowState) -> dict:
    steps = _llm_plan(state["request"]) if os.getenv("OPENAI_API_KEY") else _rule_based_plan(state["request"])
    for s in steps:
        s["risk"] = risk_of(s["tool"], s["args"])
        s["status"] = "pending"
    log = f"planner: {len(steps)} steps, {sum(s['risk'] == 'high' for s in steps)} need approval"
    return {"plan": steps, "current": 0, "log": [log], "status": "planned" if steps else "failed"}


# ---------- Retrieval agent ----------
def retriever(state: WorkflowState) -> dict:
    tools_used = sorted({s["tool"] for s in state["plan"]})
    context = {t: POLICIES[t] for t in tools_used if t in POLICIES}
    return {"context": context, "log": [f"retriever: loaded {len(context)} policies"]}


# ---------- Execution agent ----------
def executor(state: WorkflowState) -> dict:
    plan = [dict(s) for s in state["plan"]]
    step = plan[state["current"]]
    if step["risk"] == "high" and not step.get("approved"):
        step["status"] = "rejected"
        msg = f"executor: skipped {step['tool']} (not approved)"
    else:
        try:
            step["result"] = TOOLS[step["tool"]](**step["args"])
            step["status"] = "done"
            msg = f"executor: ran {step['tool']}"
        except Exception as e:  # tool failure is recorded, the validator decides what happens
            step["status"], step["error"] = "failed", str(e)
            msg = f"executor: {step['tool']} failed: {e}"
    plan[state["current"]] = step
    return {"plan": plan, "current": state["current"] + 1, "log": [msg]}


# ---------- Human approval checkpoint ----------
def human_approval(state: WorkflowState) -> dict:
    from langgraph.types import interrupt

    plan = [dict(s) for s in state["plan"]]
    step = plan[state["current"]]
    decision = interrupt({
        "step_index": state["current"],
        "tool": step["tool"],
        "args": step["args"],
        "policy": state["context"].get(step["tool"], ""),
        "question": "Approve this high-risk action?",
    })
    step["approved"] = bool(decision.get("approved"))
    step["reviewer"] = decision.get("reviewer", "unknown")
    plan[state["current"]] = step
    verdict = "approved" if step["approved"] else "rejected"
    return {"plan": plan, "log": [f"human: {step['reviewer']} {verdict} {step['tool']}"]}


# ---------- Validation agent ----------
def validator(state: WorkflowState) -> dict:
    plan = state["plan"]
    failed = [s for s in plan if s["status"] == "failed"]
    rejected = [s for s in plan if s["status"] == "rejected"]
    if failed:
        status = "failed"
    elif rejected:
        status = "completed_with_rejections"
    else:
        status = "completed"
    done = sum(s["status"] == "done" for s in plan)
    return {"status": status, "log": [f"validator: {done}/{len(plan)} steps done, status={status}"]}
