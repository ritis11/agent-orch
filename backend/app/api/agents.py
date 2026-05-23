"""Agent CRUD."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db import get_session
from ..models import Agent
from ..runtime.tools import TOOL_REGISTRY

DEFAULT_MODEL = "gemini-2.0-flash"

router = APIRouter(prefix="/agents", tags=["agents"])


class Guardrails(BaseModel):
    blocked_topics: list[str] = Field(default_factory=list)
    max_steps: int = 6


class AgentCreate(BaseModel):
    name: str
    role: str = ""
    system_prompt: str = ""
    model: str = DEFAULT_MODEL
    tools: list[str] = Field(default_factory=list)
    memory_window: int = 10
    temperature: float = 0.7
    max_tokens: int = 1024
    guardrails: Guardrails = Field(default_factory=Guardrails)
    schedule_cron: Optional[str] = None
    schedule_input: Optional[str] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    tools: Optional[list[str]] = None
    memory_window: Optional[int] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    guardrails: Optional[Guardrails] = None
    schedule_cron: Optional[str] = None
    schedule_input: Optional[str] = None


def _validate_tools(tools: list[str]) -> None:
    bad = [t for t in tools if t not in TOOL_REGISTRY]
    if bad:
        raise HTTPException(status_code=400, detail=f"unknown tools: {bad}")


@router.get("", response_model=list[Agent])
def list_agents(session: Session = Depends(get_session)) -> list[Agent]:
    return list(session.exec(select(Agent).order_by(Agent.id)))


@router.post("", response_model=Agent)
def create_agent(payload: AgentCreate, session: Session = Depends(get_session)) -> Agent:
    _validate_tools(payload.tools)
    agent = Agent(
        name=payload.name,
        role=payload.role,
        system_prompt=payload.system_prompt,
        model=payload.model,
        tools=payload.tools,
        memory_window=payload.memory_window,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        guardrails=payload.guardrails.model_dump(),
        schedule_cron=payload.schedule_cron,
        schedule_input=payload.schedule_input,
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


@router.get("/{agent_id}", response_model=Agent)
def get_agent(agent_id: int, session: Session = Depends(get_session)) -> Agent:
    agent = session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    return agent


@router.put("/{agent_id}", response_model=Agent)
def update_agent(
    agent_id: int,
    payload: AgentUpdate,
    session: Session = Depends(get_session),
) -> Agent:
    agent = session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    data: dict[str, Any] = payload.model_dump(exclude_unset=True)
    if "tools" in data:
        _validate_tools(data["tools"] or [])
    if "guardrails" in data and data["guardrails"] is not None:
        data["guardrails"] = (
            data["guardrails"]
            if isinstance(data["guardrails"], dict)
            else data["guardrails"].model_dump()
        )
    for k, v in data.items():
        setattr(agent, k, v)
    agent.updated_at = datetime.utcnow()
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


@router.delete("/{agent_id}")
def delete_agent(agent_id: int, session: Session = Depends(get_session)) -> dict[str, bool]:
    agent = session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    session.delete(agent)
    session.commit()
    return {"ok": True}
