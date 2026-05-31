"""Glue: take a Run row + Workflow, compile its graph, execute, publish events."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from ..db import session_scope
from ..models import Agent, Run, Workflow
from .events import bus
from .graph import build_graph

logger = logging.getLogger(__name__)


def _publish_status(run_id: int, status: str) -> None:
    bus.publish(run_id, "status", {"status": status})


def _load_workflow_and_agents(session: Session, workflow_id: int) -> tuple[Workflow, dict[int, Agent]]:
    workflow = session.get(Workflow, workflow_id)
    if workflow is None:
        raise ValueError(f"workflow {workflow_id} not found")
    agent_ids = {
        int(n["agent_id"])
        for n in (workflow.graph or {}).get("nodes", [])
        if n.get("type") == "agent" and n.get("agent_id") is not None
    }
    agents: dict[int, Agent] = {}
    if agent_ids:
        rows = session.exec(select(Agent).where(Agent.id.in_(agent_ids))).all()
        agents = {a.id: a for a in rows if a.id is not None}
    return workflow, agents


async def execute_run(run_id: int) -> None:
    """Run the workflow associated with `run_id` asynchronously.

    Designed to be launched via `asyncio.create_task`. Updates the Run row
    status and publishes SSE events along the way.
    """
    workflow_graph: Any = None
    initial_state: dict[str, Any] = {}

    with session_scope() as session:
        run = session.get(Run, run_id)
        if run is None:
            logger.error("execute_run: run %s missing", run_id)
            return
        run.status = "running"
        run.started_at = datetime.utcnow()
        session.add(run)
        session.commit()
        _publish_status(run_id, "running")

        try:
            workflow, agents = _load_workflow_and_agents(session, run.workflow_id)
            initial_state = {
                "messages": [],
                "context": {},
                "input": run.input or "",
                "output": None,
                "label": None,
            }
            workflow_graph = build_graph(workflow.graph or {}, agents, run_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("failed to build graph for run %s", run_id)
            run.status = "failed"
            run.error = str(exc)
            run.finished_at = datetime.utcnow()
            session.add(run)
            session.commit()
            _publish_status(run_id, "failed")
            bus.publish(run_id, "done", {"ok": False, "error": str(exc)})
            return

    try:
        # LangGraph compiled graph supports `.ainvoke` which won't block the event loop
        # for long. Each agent step itself is sync (we run it in a thread via asyncio.to_thread).
        result: dict[str, Any] = await asyncio.to_thread(workflow_graph.invoke, initial_state)
    except Exception as exc:  # noqa: BLE001
        logger.exception("run %s failed during execution", run_id)
        with session_scope() as session:
            run = session.get(Run, run_id)
            if run is not None:
                run.status = "failed"
                run.error = str(exc)
                run.finished_at = datetime.utcnow()
                session.add(run)
                session.commit()
        _publish_status(run_id, "failed")
        bus.publish(run_id, "done", {"ok": False, "error": str(exc)})
        return

    output = (result or {}).get("output") or ""
    slack_channel: str | None = None
    run_trigger: str | None = None
    with session_scope() as session:
        run = session.get(Run, run_id)
        if run is not None:
            run.status = "completed"
            run.output = output
            run.finished_at = datetime.utcnow()
            session.add(run)
            session.commit()
            run_trigger = run.trigger
            workflow = session.get(Workflow, run.workflow_id)
            if workflow and workflow.slack_channel:
                slack_channel = workflow.slack_channel.strip()
    _publish_status(run_id, "completed")

    # Auto-deliver the result to the workflow's bound Slack channel. We skip
    # slack-triggered runs because the Slack handler already replies in-thread,
    # and skip the `*` wildcard which only means "match any inbound channel".
    if slack_channel and slack_channel != "*" and run_trigger != "slack" and output:
        await _notify_slack(run_id, slack_channel, output)

    bus.publish(run_id, "done", {"ok": True})


async def _notify_slack(run_id: int, channel: str, text: str) -> None:
    """Post a run's final output to Slack, logging success/failure to the run."""
    from ..channels.slack import get_slack_client
    from .agent_node import _persist_log

    client = get_slack_client()
    if client is None:
        return
    try:
        # chat_postMessage is a blocking HTTP call; keep it off the event loop.
        await asyncio.to_thread(client.chat_postMessage, channel=channel, text=text)
        with session_scope() as session:
            _persist_log(session, run_id, "slack", f"posted result to {channel}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("slack auto-post to %s failed: %s", channel, exc)
        with session_scope() as session:
            _persist_log(
                session, run_id, "slack", f"slack post failed: {exc}", level="error"
            )


_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop


def schedule_run(run_id: int) -> None:
    """Schedule `execute_run` on the FastAPI event loop (safe from sync handlers)."""
    if _main_loop is None or not _main_loop.is_running():
        asyncio.run(execute_run(run_id))
        return
    asyncio.run_coroutine_threadsafe(execute_run(run_id), _main_loop)
