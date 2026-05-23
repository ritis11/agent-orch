"""Server-Sent Events for live run progress.

The endpoint first replays any persisted backlog (so late subscribers see
history), then forwards live events from the in-process bus. A `done` event
closes the stream.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select
from sse_starlette.sse import EventSourceResponse

from ..db import get_session
from ..models import LogEvent, Message, Run
from ..runtime.events import bus

router = APIRouter(prefix="/runs", tags=["runs"])

logger = logging.getLogger(__name__)


def _msg_to_dict(m: Message) -> dict[str, Any]:
    return {
        "id": m.id,
        "run_id": m.run_id,
        "from_agent_id": m.from_agent_id,
        "to_agent_id": m.to_agent_id,
        "role": m.role,
        "content": m.content,
        "tokens_in": m.tokens_in,
        "tokens_out": m.tokens_out,
        "created_at": m.created_at.isoformat(),
    }


def _log_to_dict(l: LogEvent) -> dict[str, Any]:
    return {
        "id": l.id,
        "run_id": l.run_id,
        "level": l.level,
        "source": l.source,
        "message": l.message,
        "created_at": l.created_at.isoformat(),
    }


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> EventSourceResponse:
    run = session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")

    # Capture backlog snapshot before subscribing so we don't miss events
    # produced between snapshot and subscribe (the live stream may replay
    # a couple of already-seen events; the UI dedupes by id).
    backlog_logs = list(
        session.exec(select(LogEvent).where(LogEvent.run_id == run_id).order_by(LogEvent.id))
    )
    backlog_msgs = list(
        session.exec(select(Message).where(Message.run_id == run_id).order_by(Message.id))
    )
    terminal_status = run.status if run.status in ("completed", "failed") else None

    q = await bus.subscribe(run_id)

    async def gen() -> AsyncIterator[dict[str, Any]]:
        try:
            for l in backlog_logs:
                yield {"event": "log", "data": json.dumps(_log_to_dict(l))}
            for m in backlog_msgs:
                yield {"event": "message", "data": json.dumps(_msg_to_dict(m))}
            yield {"event": "status", "data": json.dumps({"status": run.status})}

            if terminal_status:
                # Run is already finished; close immediately.
                yield {"event": "done", "data": json.dumps({"ok": terminal_status == "completed"})}
                return

            while True:
                if await request.is_disconnected():
                    return
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # Keep-alive comment so proxies don't close the connection.
                    yield {"event": "ping", "data": "{}"}
                    continue
                yield {"event": ev.type, "data": json.dumps(ev.data)}
                if ev.type == "done":
                    return
        finally:
            await bus.unsubscribe(run_id, q)

    return EventSourceResponse(gen())
