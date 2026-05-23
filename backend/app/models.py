from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import Column, Text
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class Guardrails(SQLModel):
    blocked_topics: list[str] = Field(default_factory=list)
    max_steps: int = 10


class GraphNode(SQLModel):
    id: str
    type: str
    agent_id: Optional[int] = None
    position: Optional[dict[str, float]] = None


class GraphEdge(SQLModel):
    id: str
    source: str
    target: str
    when: Optional[str] = None


class WorkflowGraph(SQLModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class AgentBase(SQLModel):
    name: str
    role: str
    system_prompt: str
    model: str = "gemini-2.0-flash"
    tools: list[str] = Field(default_factory=list)
    memory_window: int = 10
    temperature: float = 0.7
    max_tokens: int = 2048
    guardrails: Guardrails = Field(default_factory=Guardrails)
    schedule_cron: Optional[str] = None
    schedule_input: Optional[str] = None


class Agent(AgentBase, table=True):
    __tablename__ = "agents"

    id: Optional[int] = Field(default=None, primary_key=True)
    tools: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    guardrails: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AgentCreate(AgentBase):
    pass


class AgentUpdate(SQLModel):
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


class AgentRead(AgentBase):
    id: int
    created_at: datetime
    updated_at: datetime


class WorkflowBase(SQLModel):
    name: str
    description: str = ""
    graph: WorkflowGraph = Field(default_factory=WorkflowGraph)
    slack_channel: Optional[str] = None


class Workflow(WorkflowBase, table=True):
    __tablename__ = "workflows"

    id: Optional[int] = Field(default=None, primary_key=True)
    graph: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    graph: Optional[WorkflowGraph] = None
    slack_channel: Optional[str] = None


class WorkflowRead(WorkflowBase):
    id: int
    created_at: datetime
    updated_at: datetime


class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class RunTrigger(str, Enum):
    manual = "manual"
    slack = "slack"
    schedule = "schedule"


class Run(SQLModel, table=True):
    __tablename__ = "runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    workflow_id: int = Field(foreign_key="workflows.id")
    status: str = RunStatus.pending.value
    trigger: str = RunTrigger.manual.value
    input: str = ""
    output: Optional[str] = Field(default=None, sa_column=Column(Text))
    error: Optional[str] = Field(default=None, sa_column=Column(Text))
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    context: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class RunCreate(SQLModel):
    input: str = ""


class RunRead(SQLModel):
    id: int
    workflow_id: int
    workflow_name: Optional[str] = None
    status: str
    trigger: str
    input: str
    output: Optional[str] = None
    error: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.id")
    from_agent_id: Optional[int] = Field(default=None, foreign_key="agents.id")
    to_agent_id: Optional[int] = Field(default=None, foreign_key="agents.id")
    role: str
    content: str = Field(default="", sa_column=Column(Text))
    tokens_in: int = 0
    tokens_out: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MessageRead(SQLModel):
    id: int
    run_id: int
    from_agent_id: Optional[int] = None
    from_agent_name: Optional[str] = None
    to_agent_id: Optional[int] = None
    role: str
    content: str
    tokens_in: int
    tokens_out: int
    created_at: datetime


class LogEvent(SQLModel, table=True):
    __tablename__ = "log_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.id")
    level: str = "info"
    source: str = "runtime"
    message: str = Field(default="", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LogEventRead(SQLModel):
    id: int
    run_id: int
    level: str
    source: str
    message: str
    created_at: datetime


class RunDetail(SQLModel):
    run: RunRead
    messages: list[MessageRead]
    logs: list[LogEventRead]
