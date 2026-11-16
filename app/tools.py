"""Business tools the execution agent can call. They simulate internal APIs (IT, HR, procurement)."""
from __future__ import annotations

import uuid
from typing import Callable


def create_account(name: str, system: str) -> dict:
    return {"account_id": f"{system}-{uuid.uuid4().hex[:6]}", "user": name, "system": system}


def grant_access(name: str, resource: str, level: str = "read") -> dict:
    return {"user": name, "resource": resource, "level": level, "granted": True}


def order_equipment(name: str, item: str, cost: float) -> dict:
    return {"order_id": f"PO-{uuid.uuid4().hex[:6].upper()}", "item": item, "cost": cost, "for": name}


def send_email(to: str, subject: str) -> dict:
    return {"to": to, "subject": subject, "sent": True}


def schedule_meeting(name: str, topic: str) -> dict:
    return {"with": name, "topic": topic, "scheduled": True}


TOOLS: dict[str, Callable[..., dict]] = {
    "create_account": create_account,
    "grant_access": grant_access,
    "order_equipment": order_equipment,
    "send_email": send_email,
    "schedule_meeting": schedule_meeting,
}


def risk_of(tool: str, args: dict) -> str:
    """High-risk actions need a human approval checkpoint before they run."""
    if tool == "grant_access" and args.get("level") == "admin":
        return "high"
    if tool == "order_equipment" and float(args.get("cost", 0)) > 1000:
        return "high"
    return "low"
