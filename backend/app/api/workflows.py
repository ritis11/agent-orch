"""Workflow CRUD + run trigger."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db import get_session
from ..models import Agent, Run, RunRead, RunTrigger, Workflow
from ..runtime.runner import schedule_run
from ..runtime.graph import validate_graph

router = APIRouter(prefix="/workflows", tags=["workflows"])


class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    graph: dict[str, Any] = Field(default_factory=lambda: {"nodes": [], "edges": []})
    slack_channel: Optional[str] = None


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    graph: Optional[dict[str, Any]] = None
    slack_channel: Optional[str] = None


class WorkflowRunRequest(BaseModel):
    input: str = ""


def _validate_workflow_graph(session: Session, graph: dict[str, Any] | None) -> None:
    if not graph:
        return
    agent_ids = {
        int(n["agent_id"])
        for n in graph.get("nodes", [])
        if n.get("type") == "agent" and n.get("agent_id") is not None
    }
    agents: dict[int, Agent] = {}
    if agent_ids:
        rows = session.exec(select(Agent).where(Agent.id.in_(agent_ids))).all()
        agents = {a.id: a for a in rows if a.id is not None}
    try:
        validate_graph(graph, agents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@router.get("", response_model=list[Workflow])
def list_workflows(session: Session = Depends(get_session)) -> list[Workflow]:
    return list(session.exec(select(Workflow).order_by(Workflow.id)))


@router.post("", response_model=Workflow, status_code=201)
def create_workflow(payload: WorkflowCreate, session: Session = Depends(get_session)) -> Workflow:
    _validate_workflow_graph(session, payload.graph)
    wf = Workflow(
        name=payload.name,
        description=payload.description,
        graph=payload.graph,
        slack_channel=payload.slack_channel,
    )
    session.add(wf)
    session.commit()
    session.refresh(wf)
    return wf


@router.get("/{workflow_id}", response_model=Workflow)
def get_workflow(workflow_id: int, session: Session = Depends(get_session)) -> Workflow:
    wf = session.get(Workflow, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="workflow not found")
    return wf


@router.put("/{workflow_id}", response_model=Workflow)
def update_workflow(
    workflow_id: int,
    payload: WorkflowUpdate,
    session: Session = Depends(get_session),
) -> Workflow:
    wf = session.get(Workflow, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="workflow not found")
    data = payload.model_dump(exclude_unset=True)
    if "graph" in data:
        _validate_workflow_graph(session, data["graph"])
    for k, v in data.items():
        setattr(wf, k, v)
    wf.updated_at = datetime.utcnow()
    session.add(wf)
    session.commit()
    session.refresh(wf)
    return wf


@router.delete("/{workflow_id}")
def delete_workflow(workflow_id: int, session: Session = Depends(get_session)) -> dict[str, bool]:
    wf = session.get(Workflow, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="workflow not found")
    session.delete(wf)
    session.commit()
    return {"ok": True}


@router.post("/{workflow_id}/run", response_model=RunRead)
def run_workflow(
    workflow_id: int,
    payload: WorkflowRunRequest,
    session: Session = Depends(get_session),
) -> RunRead:
    wf = session.get(Workflow, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="workflow not found")
    _validate_workflow_graph(session, wf.graph)

    run = Run(
        workflow_id=workflow_id,
        status="pending",
        trigger=RunTrigger.manual.value,
        input=payload.input or "",
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    schedule_run(run.id)  # type: ignore[arg-type]
    return _serialize_run(run, wf.name)
