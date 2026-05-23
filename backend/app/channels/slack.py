"""Slack channel (Bolt Socket Mode).

Listens for app mentions and DMs, finds a workflow whose `slack_channel`
matches the event channel (id or name), runs it, and replies in the thread.

Tokens (env):
  SLACK_BOT_TOKEN
  SLACK_APP_TOKEN
  SLACK_SIGNING_SECRET (optional in socket mode but Bolt may require it)

If `SLACK_BOT_TOKEN` is missing the handler is not started — the backend boots
normally so the UI is still demoable without Slack.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Optional

from sqlmodel import Session, select

from ..db import session_scope
from ..models import Run, Workflow
from ..runtime.runner import execute_run

logger = logging.getLogger(__name__)

# Bolt async app (lazy init).
_app: Any = None
_handler: Any = None
# Sync WebClient used by the `slack_send` tool — independent of the bolt app
# so tool calls don't need an event loop.
_sync_client: Any = None
# Channel id/name lookup cache so we can resolve `#name` to `Cxxxx` once.
_channel_cache: dict[str, str] = {}


def _bot_token() -> Optional[str]:
    return os.getenv("SLACK_BOT_TOKEN")


def _app_token() -> Optional[str]:
    return os.getenv("SLACK_APP_TOKEN")


def get_slack_client() -> Any:
    """Return a sync WebClient if a bot token is configured, else None."""
    global _sync_client
    if _sync_client is not None:
        return _sync_client
    token = _bot_token()
    if not token:
        return None
    try:
        from slack_sdk import WebClient

        _sync_client = WebClient(token=token)
        return _sync_client
    except Exception as exc:  # noqa: BLE001
        logger.warning("slack WebClient init failed: %s", exc)
        return None


def is_configured() -> bool:
    return bool(_bot_token() and _app_token())


# Public alias used by main.py.
def is_slack_configured() -> bool:
    return is_configured()


def _match_workflow(session: Session, channel_id: str, channel_name: str | None) -> Workflow | None:
    """Find a workflow whose `slack_channel` matches by id or name; fall back to `*`."""
    workflows = list(session.exec(select(Workflow)))
    by_id: Workflow | None = None
    by_name: Workflow | None = None
    wildcard: Workflow | None = None
    for wf in workflows:
        sc = (wf.slack_channel or "").strip()
        if not sc:
            continue
        if sc == "*":
            wildcard = wildcard or wf
            continue
        sc_norm = sc.lstrip("#")
        if sc == channel_id:
            by_id = wf
        if channel_name and sc_norm == channel_name:
            by_name = by_name or wf
    return by_id or by_name or wildcard


def _resolve_channel_name(client: Any, channel_id: str) -> str | None:
    if channel_id in _channel_cache:
        return _channel_cache[channel_id]
    try:
        info = client.conversations_info(channel=channel_id)
        name = (info.get("channel") or {}).get("name")
        if name:
            _channel_cache[channel_id] = name
        return name
    except Exception:  # noqa: BLE001
        return None


async def _wait_for_run(run_id: int, timeout: float = 120.0) -> Run | None:
    """Poll the run row until it leaves the running state or times out."""
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        with session_scope() as session:
            run = session.get(Run, run_id)
            if run is None:
                return None
            if run.status in ("completed", "failed"):
                return run
        if asyncio.get_running_loop().time() > deadline:
            return run
        await asyncio.sleep(0.5)


def _build_app() -> Any:
    """Create the AsyncApp + register handlers. Only called when tokens are set."""
    from slack_bolt.async_app import AsyncApp

    app = AsyncApp(
        token=_bot_token(),
        signing_secret=os.getenv("SLACK_SIGNING_SECRET") or "unused-in-socket-mode",
    )

    async def _handle_event(event: dict[str, Any], say: Any, sync_client: Any) -> None:
        text: str = (event.get("text") or "").strip()
        channel_id: str = event.get("channel") or ""
        thread_ts: str = event.get("thread_ts") or event.get("ts")
        channel_name = _resolve_channel_name(sync_client, channel_id) if sync_client else None

        with session_scope() as session:
            workflow = _match_workflow(session, channel_id, channel_name)
            if workflow is None:
                logger.info("slack: no workflow matched channel %s (%s)", channel_id, channel_name)
                await say(
                    text=":information_source: No workflow is bound to this channel.",
                    thread_ts=thread_ts,
                )
                return

            run = Run(
                workflow_id=workflow.id,
                status="pending",
                trigger="slack",
                input=text,
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            run_id = run.id

        asyncio.create_task(execute_run(run_id))
        finished = await _wait_for_run(run_id)
        if finished is None:
            await say(text=":warning: run vanished", thread_ts=thread_ts)
            return
        if finished.status == "failed":
            await say(text=f":x: run failed: {finished.error or 'unknown error'}", thread_ts=thread_ts)
            return
        reply = finished.output or "(no output)"
        await say(text=reply, thread_ts=thread_ts)

    @app.event("app_mention")
    async def on_mention(event: dict[str, Any], say: Any) -> None:  # noqa: ARG001
        await _handle_event(event, say, get_slack_client())

    @app.event("message")
    async def on_message(event: dict[str, Any], say: Any) -> None:  # noqa: ARG001
        # Only respond to DMs ("im") and ignore bot/own messages.
        if event.get("bot_id") or event.get("subtype"):
            return
        if event.get("channel_type") != "im":
            return
        await _handle_event(event, say, get_slack_client())

    return app


async def start_slack_handler() -> None:
    """Start the Bolt Socket Mode handler in the background.

    Returns immediately. If tokens aren't set, logs a warning and exits without
    starting anything so the backend can still boot.
    """
    global _app, _handler

    if not is_configured():
        logger.warning(
            "Slack tokens missing (SLACK_BOT_TOKEN / SLACK_APP_TOKEN); skipping handler.",
        )
        return

    try:
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

        _app = _build_app()
        _handler = AsyncSocketModeHandler(_app, _app_token())
        # Run forever — caller wraps this in asyncio.create_task.
        await _handler.start_async()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Slack handler crashed: %s", exc)


async def stop_slack_handler() -> None:
    if _handler is not None:
        try:
            await _handler.close_async()
        except Exception:  # noqa: BLE001
            pass
