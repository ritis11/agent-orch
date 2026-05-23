"""In-memory pub/sub for live run events (SSE)."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Event:
    type: str
    data: dict[str, Any]
    ts: datetime = field(default_factory=datetime.utcnow)


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[int, list[asyncio.Queue[Event]]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, run_id: int) -> asyncio.Queue[Event]:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=1024)
        async with self._lock:
            self._subs.setdefault(run_id, []).append(q)
        return q

    async def unsubscribe(self, run_id: int, q: asyncio.Queue[Event]) -> None:
        async with self._lock:
            subs = self._subs.get(run_id, [])
            if q in subs:
                subs.remove(q)
            if not subs:
                self._subs.pop(run_id, None)

    def publish(self, run_id: int, event_type: str, data: dict[str, Any]) -> None:
        ev = Event(type=event_type, data=data)
        for q in list(self._subs.get(run_id, [])):
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                logger.warning("event bus queue full for run %s; dropping event", run_id)


bus = EventBus()


async def emit_log(
    run_id: int,
    message: str,
    level: str = "info",
    source: str = "runtime",
    log_id: int | None = None,
) -> None:
    from datetime import datetime

    payload: dict[str, Any] = {
        "level": level,
        "source": source,
        "message": message,
        "created_at": datetime.utcnow().isoformat(),
        "run_id": run_id,
    }
    if log_id is not None:
        payload["id"] = log_id
    bus.publish(run_id, "log", payload)


async def emit_status(run_id: int, status: str) -> None:
    bus.publish(run_id, "status", {"status": status})


async def emit_done(run_id: int, data: dict[str, Any]) -> None:
    bus.publish(run_id, "done", data)
