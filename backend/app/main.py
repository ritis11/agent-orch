"""FastAPI entrypoint.

Wires up CORS, mounts the API routers under `/api`, runs DB init + seeding on
startup, and launches Slack + scheduler in the background. The app must boot
even without GEMINI_API_KEY or Slack tokens (degraded mode).
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import agents as agents_router
from .api import runs as runs_router
from .api import stats as stats_router
from .api import stream as stream_router
from .api import tools as tools_router
from .api import workflows as workflows_router
from .channels.slack import (
    is_slack_configured,
    start_slack_handler,
    stop_slack_handler,
)
from .db import init_db, session_scope
from .runtime.runner import set_main_loop
from .scheduler import shutdown_scheduler, start_scheduler
from .seed.templates import seed_if_empty

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with session_scope() as session:
        seed_if_empty(session)

    # Make the running event loop available to sync routes that want to schedule
    # async coroutines (see runtime/runner.schedule_run).
    set_main_loop(asyncio.get_running_loop())

    start_scheduler()

    slack_task: asyncio.Task | None = None
    if is_slack_configured():
        slack_task = asyncio.create_task(start_slack_handler())
    else:
        logger.warning("Slack not configured; skipping handler startup.")

    try:
        yield
    finally:
        shutdown_scheduler()
        if slack_task is not None:
            await stop_slack_handler()
            slack_task.cancel()
            try:
                await slack_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass


app = FastAPI(title="Yuno Agent Orchestration", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents_router.router, prefix="/api")
app.include_router(workflows_router.router, prefix="/api")
app.include_router(runs_router.router, prefix="/api")
app.include_router(stream_router.router, prefix="/api")
app.include_router(tools_router.router, prefix="/api")
app.include_router(stats_router.router, prefix="/api")


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}
