"""Shared state passed between agents in the graph."""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class WorkflowState(TypedDict, total=False):
    request: str
    plan: list[dict]          # [{tool, args, risk, status, approved?, result?}]
    current: int              # index of the next step to run
    context: dict             # policies found by the retrieval agent
    status: str               # planned | completed | completed_with_rejections | failed
    log: Annotated[list[str], operator.add]  # each agent appends what it did
