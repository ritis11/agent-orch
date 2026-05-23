"""Run list + detail endpoints."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..db import get_session
from ..models import Agent, LogEvent, LogEventRead, Message, MessageRead, Run, RunDetail, RunRead, Workflow

router = APIRouter(prefix="/runs", tags=["runs"])

TEMPLATE_NAMES = {"Research & Reply", "Support Triage"}


def _workflow_names(session: Session, workflow_ids: set[int]) -> dict[int, str]:
    if not workflow_ids:
        return {}
    rows = session.exec(select(Workflow).where(Workflow.id.in_(workflow_ids))).all()
    return {w.id: w.name for w in rows if w.id is not None}


def _agent_names(session: Session, agent_ids: set[int]) -> dict[int, str]:
    if not agent_ids:
        return {}
    rows = session.exec(select(Agent).where(Agent.id.in_(agent_ids))).all()
    return {a.id: a.name for a in rows if a.id is not None}


def _serialize_run(run: Run, workflow_name: str | None = None) -> RunRead:
    return RunRead(
        id=run.id,  # type: ignore[arg-type]
        workflow_id=run.workflow_id,
        workflow_name=workflow_name,
        status=run.status,
        trigger=run.trigger,
        input=run.input,
        output=run.output,
        error=run.error,
        started_at=run.started_at,
        finished_at=run.finished_at,
        total_input_tokens=run.total_input_tokens,
        total_output_tokens=run.total_output_tokens,
        total_cost_usd=run.total_cost_usd,
    )


@router.get("", response_model=list[RunRead])
def list_runs(
    workflow_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[RunRead]:
    stmt = select(Run).order_by(Run.id.desc()).limit(limit)
    if workflow_id is not None:
        stmt = select(Run).where(Run.workflow_id == workflow_id).order_by(Run.id.desc()).limit(limit)
    runs = list(session.exec(stmt))
    names = _workflow_names(session, {r.workflow_id for r in runs})
    return [_serialize_run(r, names.get(r.workflow_id)) for r in runs]


@router.get("/{run_id}", response_model=RunDetail)
def get_run_detail(run_id: int, session: Session = Depends(get_session)) -> RunDetail:
    run = session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")

    workflow = session.get(Workflow, run.workflow_id)
    workflow_name = workflow.name if workflow else None

    messages = list(
        session.exec(select(Message).where(Message.run_id == run_id).order_by(Message.id))
    )
    logs = list(
        session.exec(select(LogEvent).where(LogEvent.run_id == run_id).order_by(LogEvent.id))
    )

    agent_ids = {m.from_agent_id for m in messages if m.from_agent_id is not None}
    agent_names = _agent_names(session, agent_ids)  # type: ignore[arg-type]

    return RunDetail(
        run=_serialize_run(run, workflow_name),
        messages=[
            MessageRead(
                id=m.id,  # type: ignore[arg-type]
                run_id=m.run_id,
                from_agent_id=m.from_agent_id,
                from_agent_name=agent_names.get(m.from_agent_id) if m.from_agent_id else None,
                to_agent_id=m.to_agent_id,
                role=m.role,
                content=m.content,
                tokens_in=m.tokens_in,
                tokens_out=m.tokens_out,
                created_at=m.created_at,
            )
            for m in messages
        ],
        logs=[
            LogEventRead(
                id=l.id,  # type: ignore[arg-type]
                run_id=l.run_id,
                level=l.level,
                source=l.source,
                message=l.message,
                created_at=l.created_at,
            )
            for l in logs
        ],
    )
