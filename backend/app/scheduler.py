"""APScheduler integration for agents with `schedule_cron`.

Choice: for each agent with `schedule_cron`, we look for the first workflow
whose graph references that agent and trigger that workflow with
`schedule_input` (or the agent's role as a default input). This keeps things
predictable for users — the cron drives a real graph rather than a phantom
one-agent run. If no workflow references the agent, the job logs a warning and
does nothing.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import select

from .db import session_scope
from .models import Agent, Run, Workflow
from .runtime.runner import execute_run

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _find_workflow_for_agent(agent_id: int) -> Workflow | None:
    with session_scope() as session:
        workflows = list(session.exec(select(Workflow)))
        for wf in workflows:
            for node in (wf.graph or {}).get("nodes", []):
                if node.get("type") == "agent" and node.get("agent_id") == agent_id:
                    return wf
    return None


async def _trigger_agent_schedule(agent_id: int) -> None:
    wf = _find_workflow_for_agent(agent_id)
    if wf is None:
        logger.warning("scheduler: no workflow references agent %s; skipping run", agent_id)
        return
    with session_scope() as session:
        agent = session.get(Agent, agent_id)
        if agent is None:
            return
        run = Run(
            workflow_id=wf.id,
            status="pending",
            trigger="schedule",
            input=(agent.schedule_input or agent.role or ""),
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id
    await execute_run(run_id)


def _register_agent_jobs(scheduler: AsyncIOScheduler) -> None:
    with session_scope() as session:
        agents = list(session.exec(select(Agent).where(Agent.schedule_cron.is_not(None))))
    for agent in agents:
        if not agent.schedule_cron:
            continue
        try:
            trigger = CronTrigger.from_crontab(agent.schedule_cron)
        except Exception as exc:  # noqa: BLE001
            logger.warning("invalid cron '%s' for agent %s: %s", agent.schedule_cron, agent.id, exc)
            continue
        scheduler.add_job(
            _trigger_agent_schedule,
            trigger=trigger,
            args=[agent.id],
            id=f"agent-{agent.id}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info("scheduled agent %s with cron '%s'", agent.id, agent.schedule_cron)


def start_scheduler() -> AsyncIOScheduler:
    """Start the APScheduler and register one job per scheduled agent."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = AsyncIOScheduler()
    try:
        _register_agent_jobs(_scheduler)
        _scheduler.start()
    except Exception as exc:  # noqa: BLE001
        logger.warning("scheduler failed to start: %s", exc)
    return _scheduler


def stop_scheduler() -> None:
    shutdown_scheduler()


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            pass
        _scheduler = None
