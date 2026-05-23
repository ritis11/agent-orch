"""Dashboard aggregate stats."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, func, select

from ..db import get_session
from ..models import Agent, Run, RunStatus, Workflow

router = APIRouter(tags=["stats"])

TEMPLATE_NAMES = {"Research & Reply", "Support Triage"}


class DashboardStats(BaseModel):
    agent_count: int
    workflow_count: int
    run_count: int
    active_runs: int


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(session: Session = Depends(get_session)) -> DashboardStats:
    agent_count = session.exec(select(func.count()).select_from(Agent)).one()
    workflow_count = session.exec(select(func.count()).select_from(Workflow)).one()
    run_count = session.exec(select(func.count()).select_from(Run)).one()
    active_runs = session.exec(
        select(func.count())
        .select_from(Run)
        .where(Run.status.in_([RunStatus.pending.value, RunStatus.running.value]))
    ).one()
    return DashboardStats(
        agent_count=agent_count,
        workflow_count=workflow_count,
        run_count=run_count,
        active_runs=active_runs,
    )
