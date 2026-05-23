"""Runtime graph compilation and execution tests (mocked LLM)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlmodel import Session, SQLModel, select

from app.db import engine, init_db
from app.models import Agent, Workflow
from app.runtime.runner import execute_run
from app.runtime.graph import build_graph, validate_graph
from app.seed.templates import seed_templates
from tests.conftest import MockLLM


@pytest.fixture
def seeded_db() -> None:
    SQLModel.metadata.drop_all(engine)
    init_db()
    seed_templates()


def _agents_by_id(session: Session) -> dict[int, Agent]:
    rows = session.exec(select(Agent)).all()
    return {a.id: a for a in rows if a.id is not None}


def test_seed_templates_compile(seeded_db: None) -> None:
    with Session(engine) as session:
        workflows = session.exec(select(Workflow)).all()
        agents = _agents_by_id(session)
    assert len(workflows) == 2
    for wf in workflows:
        validate_graph(wf.graph, agents)
        compiled = build_graph(wf.graph, agents, run_id=1)
        assert compiled is not None


@pytest.mark.asyncio
async def test_support_triage_routes_bug(seeded_db: None) -> None:
    with Session(engine) as session:
        triage = session.exec(
            select(Workflow).where(Workflow.name == "Support Triage")
        ).one()
        bug_agent = session.exec(select(Agent).where(Agent.name == "Bug Triager")).one()
        workflow_id = triage.id

    from app.models import Run

    with Session(engine) as session:
        run = Run(workflow_id=workflow_id, input="App crashes on login", status="pending")
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id

    with patch("app.runtime.agent_node.get_llm") as get_llm:
        get_llm.side_effect = lambda *a, **k: MockLLM(
            responses=['{"label": "bug"}', "Please share reproduction steps."]
        )
        await execute_run(run_id)  # type: ignore[arg-type]

    with Session(engine) as session:
        run = session.get(Run, run_id)
        assert run is not None
        assert run.status == "completed"
        from app.models import Message

        msgs = session.exec(select(Message).where(Message.run_id == run_id)).all()
        agent_ids = {m.from_agent_id for m in msgs}
        assert bug_agent.id in agent_ids


@pytest.mark.asyncio
async def test_research_reply_runs_both_agents_in_order(seeded_db: None) -> None:
    with Session(engine) as session:
        research_wf = session.exec(
            select(Workflow).where(Workflow.name == "Research & Reply")
        ).one()
        researcher = session.exec(select(Agent).where(Agent.name == "Researcher")).one()
        writer = session.exec(select(Agent).where(Agent.name == "Writer")).one()
        workflow_id = research_wf.id

    from app.models import Run

    with Session(engine) as session:
        run = Run(workflow_id=workflow_id, input="Summarize LangGraph", status="pending")
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id

    with patch("app.runtime.agent_node.get_llm") as get_llm:
        get_llm.side_effect = lambda *a, **k: MockLLM(
            responses=["Research notes about LangGraph.", "- LangGraph is a graph runtime\n- Used for agents"]
        )
        await execute_run(run_id)  # type: ignore[arg-type]

    with Session(engine) as session:
        run = session.get(Run, run_id)
        assert run is not None
        assert run.status == "completed"
        from app.models import Message

        msgs = list(
            session.exec(
                select(Message)
                .where(Message.run_id == run_id)
                .where(Message.role == "agent")
                .order_by(Message.id)
            )
        )
        assert len(msgs) >= 2
        assert msgs[0].from_agent_id == researcher.id
        assert msgs[1].from_agent_id == writer.id
