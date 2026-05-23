"""Pre-built workflow templates seeded on first boot.

Run via `seed_if_empty(session)` at startup. Skipped if the workflow table
already has rows so a user's customizations are never overwritten.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlmodel import Session, select

from ..models import Agent, Workflow

logger = logging.getLogger(__name__)


def _agent(
    name: str,
    role: str,
    system_prompt: str,
    tools: list[str] | None = None,
) -> Agent:
    return Agent(
        name=name,
        role=role,
        system_prompt=system_prompt,
        tools=tools or [],
    )


def _ensure_agent(session: Session, blueprint: Agent) -> Agent:
    """Insert blueprint unless an agent with the same name already exists."""
    existing = session.exec(select(Agent).where(Agent.name == blueprint.name)).first()
    if existing:
        return existing
    session.add(blueprint)
    session.commit()
    session.refresh(blueprint)
    return blueprint


def _seed_research_and_reply(session: Session) -> Workflow:
    researcher = _ensure_agent(
        session,
        _agent(
            name="Researcher",
            role="Researcher",
            system_prompt=(
                "You are a careful researcher. Given the user's question, use the "
                "`web_search` tool (and `http_get` if you need to read a specific page) "
                "to gather 3-5 factual bullet points. Cite the source URL inline next "
                "to each bullet. Be concise and factual. Do not invent sources."
            ),
            tools=["web_search", "http_get"],
        ),
    )
    writer = _ensure_agent(
        session,
        _agent(
            name="Writer",
            role="Writer",
            system_prompt=(
                "You receive the Researcher's findings via the previous agent output. "
                "Rewrite them as a friendly 4-bullet reply for the user. Keep it under "
                "100 words. Preserve citations in parentheses. If `slack_send` is "
                "available you may use it to deliver the message; otherwise just "
                "respond with the bullets."
            ),
            tools=["slack_send"],
        ),
    )

    graph: dict[str, Any] = {
        "nodes": [
            {"id": "start", "type": "start", "position": {"x": 80, "y": 120}},
            {"id": "researcher", "type": "agent", "agent_id": researcher.id, "position": {"x": 320, "y": 120}},
            {"id": "writer", "type": "agent", "agent_id": writer.id, "position": {"x": 580, "y": 120}},
            {"id": "end", "type": "end", "position": {"x": 840, "y": 120}},
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "researcher"},
            {"id": "e2", "source": "researcher", "target": "writer"},
            {"id": "e3", "source": "writer", "target": "end"},
        ],
    }
    wf = Workflow(
        name="Research & Reply",
        description="Researcher gathers facts; Writer condenses into a friendly 4-bullet reply.",
        graph=graph,
    )
    session.add(wf)
    session.commit()
    session.refresh(wf)
    return wf


def _seed_support_triage(session: Session) -> Workflow:
    classifier = _ensure_agent(
        session,
        _agent(
            name="Classifier",
            role="Triage Classifier",
            system_prompt=(
                "You classify incoming user messages. Respond with ONLY a single JSON "
                "object on one line, no prose, no code fences: "
                '{"label": "bug" | "question" | "feedback", "reason": "short reason"}. '
                "Use 'bug' for crashes/errors, 'question' for product or how-to questions, "
                "and 'feedback' for opinions, suggestions, or praise."
            ),
        ),
    )
    bug_triager = _ensure_agent(
        session,
        _agent(
            name="Bug Triager",
            role="Bug Triage",
            system_prompt=(
                "A user reported a bug. Acknowledge it, list the repro steps you would "
                "need (max 4 bullets), and echo back a one-line 'ticket: ...' summary. "
                "Be brief and warm. Use `slack_send` if available to confirm."
            ),
            tools=["slack_send"],
        ),
    )
    product_answerer = _ensure_agent(
        session,
        _agent(
            name="ProductAnswerer",
            role="Product Answers",
            system_prompt=(
                "Answer the user's product question concisely (≤ 5 sentences). "
                "Use `web_search` for facts you are unsure about. Cite sources when used."
            ),
            tools=["web_search"],
        ),
    )
    feedback_logger = _ensure_agent(
        session,
        _agent(
            name="FeedbackLogger",
            role="Feedback Logger",
            system_prompt=(
                "Thank the user for their feedback, restate the core point in one "
                "sentence so they feel heard, and acknowledge that the team will "
                "review it."
            ),
        ),
    )

    graph: dict[str, Any] = {
        "nodes": [
            {"id": "start", "type": "start", "position": {"x": 80, "y": 200}},
            {"id": "classifier", "type": "agent", "agent_id": classifier.id, "position": {"x": 320, "y": 200}},
            {"id": "bug", "type": "agent", "agent_id": bug_triager.id, "position": {"x": 600, "y": 60}},
            {"id": "question", "type": "agent", "agent_id": product_answerer.id, "position": {"x": 600, "y": 200}},
            {"id": "feedback", "type": "agent", "agent_id": feedback_logger.id, "position": {"x": 600, "y": 340}},
            {"id": "end", "type": "end", "position": {"x": 900, "y": 200}},
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "classifier"},
            {"id": "e2", "source": "classifier", "target": "bug", "when": "label == 'bug'"},
            {"id": "e3", "source": "classifier", "target": "question", "when": "label == 'question'"},
            {"id": "e4", "source": "classifier", "target": "feedback", "when": "label == 'feedback'"},
            {"id": "e5", "source": "bug", "target": "end"},
            {"id": "e6", "source": "question", "target": "end"},
            {"id": "e7", "source": "feedback", "target": "end"},
        ],
    }
    wf = Workflow(
        name="Support Triage",
        description="Classifier routes to BugTriager, ProductAnswerer, or FeedbackLogger via conditional edges.",
        graph=graph,
    )
    session.add(wf)
    session.commit()
    session.refresh(wf)
    return wf


def seed_if_empty(session: Session) -> None:
    """Idempotent: only seeds when the workflows table is empty."""
    has_any = session.exec(select(Workflow)).first()
    if has_any:
        return
    logger.info("seeding default workflow templates")
    _seed_research_and_reply(session)
    _seed_support_triage(session)


def seed_templates() -> None:
    """No-arg helper used by tests and scripts; uses its own session."""
    from ..db import session_scope

    with session_scope() as session:
        seed_if_empty(session)
