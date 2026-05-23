"""Single-agent execution step used as a LangGraph node.

`run_agent` is the core unit: load the agent's tools + memory, call Gemini in
a bounded ReAct loop (tool calls until either no more tool calls or
`guardrails.max_steps` is hit), persist messages/log events, update Run token
totals, and return a partial state update for the graph.

Classification convention (used by Support Triage):
If the final assistant message looks like JSON with a "label" field
(e.g. {"label": "bug", "reason": "..."}), we copy that label into
`state["label"]` so conditional edges (`when: label == 'bug'`) can route off it.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from ..db import session_scope
from ..models import Agent, Message, Run
from .events import bus
from .llm import estimate_cost, get_llm
from .tools import TOOL_REGISTRY, get_tools_for_agent

logger = logging.getLogger(__name__)


def _load_memory(session, agent_id: int, run_id: int, limit: int) -> list[Any]:
    """Load the agent's last `limit` messages from prior runs as memory.

    We pull from messages where this agent was the producer, excluding the
    current run (those will be appended below). Keeps memory simple — no
    summarization, just a sliding window.
    """
    from sqlmodel import select

    if limit <= 0:
        return []
    stmt = (
        select(Message)
        .where(Message.from_agent_id == agent_id)
        .where(Message.run_id != run_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    rows = list(session.exec(stmt))
    rows.reverse()
    return [AIMessage(content=m.content) for m in rows if m.content]


def _maybe_extract_label(text: str) -> str | None:
    """Extract routing label from JSON or plain-word classifier output."""
    if not text:
        return None
    stripped = text.strip().lower()
    for label in ("bug", "question", "feedback"):
        if stripped == label or stripped.startswith(label + " ") or stripped.startswith(label + "\n"):
            return label
    m = re.search(r"\{[\s\S]*?\}", text)
    if m:
        try:
            obj = json.loads(m.group(0))
            label = obj.get("label") if isinstance(obj, dict) else None
            if isinstance(label, str):
                return label.strip().lower()
        except json.JSONDecodeError:
            pass
    match = re.search(r"\b(bug|question|feedback)\b", stripped)
    return match.group(1) if match else None


def _usage_from_message(msg: Any) -> tuple[int, int]:
    """Extract (input_tokens, output_tokens) from a LangChain AIMessage if available."""
    usage = getattr(msg, "usage_metadata", None) or {}
    if isinstance(usage, dict):
        return int(usage.get("input_tokens", 0) or 0), int(usage.get("output_tokens", 0) or 0)
    return 0, 0


def _persist_message(
    session,
    run_id: int,
    from_agent_id: int | None,
    role: str,
    content: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
) -> Message:
    row = Message(
        run_id=run_id,
        from_agent_id=from_agent_id,
        role=role,
        content=content,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _persist_log(session, run_id: int, source: str, message: str, level: str = "info") -> None:
    from .events import bus  # local import to avoid cycle issues at import time
    from ..models import LogEvent

    row = LogEvent(run_id=run_id, level=level, source=source, message=message)
    session.add(row)
    session.commit()
    session.refresh(row)
    bus.publish(
        run_id,
        "log",
        {
            "id": row.id,
            "run_id": row.run_id,
            "level": row.level,
            "source": row.source,
            "message": row.message,
            "created_at": row.created_at.isoformat(),
        },
    )


def _publish_message(run_id: int, msg: Message) -> None:
    bus.publish(
        run_id,
        "message",
        {
            "id": msg.id,
            "run_id": msg.run_id,
            "from_agent_id": msg.from_agent_id,
            "to_agent_id": msg.to_agent_id,
            "role": msg.role,
            "content": msg.content,
            "tokens_in": msg.tokens_in,
            "tokens_out": msg.tokens_out,
            "created_at": msg.created_at.isoformat(),
        },
    )


def _content_text(content: Any) -> str:
    """LangChain content may be str or list[dict]; collapse to a string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for chunk in content:
            if isinstance(chunk, dict):
                parts.append(str(chunk.get("text") or chunk.get("content") or ""))
            else:
                parts.append(str(chunk))
        return "".join(parts)
    return str(content) if content is not None else ""


def run_agent(agent: Agent, state: dict[str, Any], run_id: int) -> dict[str, Any]:
    """Run a single agent step. Returns the partial state update for LangGraph."""
    node_source = f"agent:{agent.id}:{agent.name}"
    guardrails = agent.guardrails or {}
    max_steps = int(guardrails.get("max_steps", 6) or 6)

    tools = get_tools_for_agent(agent)
    llm = get_llm(agent.model, agent.temperature, agent.max_tokens)
    if tools:
        try:
            llm = llm.bind_tools(tools)
        except Exception as exc:  # noqa: BLE001
            logger.warning("bind_tools failed for agent %s: %s", agent.name, exc)

    with session_scope() as session:
        _persist_log(session, run_id, node_source, f"agent '{agent.name}' starting")

        memory = _load_memory(session, agent.id or 0, run_id, agent.memory_window)
        system = SystemMessage(content=agent.system_prompt or f"You are {agent.name}.")
        user_input = state.get("input") or ""
        prior_output = state.get("output")
        # Feed previous node output as additional context for downstream agents.
        if prior_output and prior_output != user_input:
            user_input = (
                f"User request:\n{state.get('input', '')}\n\n"
                f"Previous agent output:\n{prior_output}"
            )
        messages: list[Any] = [system, *memory, HumanMessage(content=user_input)]

        total_in = total_out = 0
        final_text = ""

        for step in range(max_steps):
            try:
                ai_msg = llm.invoke(messages)
            except Exception as exc:  # noqa: BLE001
                _persist_log(session, run_id, node_source, f"LLM error: {exc}", level="error")
                final_text = f"[agent error] {exc}"
                break

            in_tok, out_tok = _usage_from_message(ai_msg)
            total_in += in_tok
            total_out += out_tok
            messages.append(ai_msg)

            tool_calls = getattr(ai_msg, "tool_calls", None) or []
            if not tool_calls:
                final_text = _content_text(ai_msg.content)
                break

            for call in tool_calls:
                name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
                args = call.get("args") if isinstance(call, dict) else getattr(call, "args", {}) or {}
                call_id = call.get("id") if isinstance(call, dict) else getattr(call, "id", None)
                tool_fn = TOOL_REGISTRY.get(name or "")
                if tool_fn is None:
                    result = f"error: tool '{name}' not available"
                else:
                    try:
                        result = tool_fn.invoke(args)
                    except Exception as exc:  # noqa: BLE001
                        result = f"error: {exc}"
                result_str = result if isinstance(result, str) else json.dumps(result, default=str)
                _persist_log(session, run_id, node_source, f"tool {name}({args}) -> {result_str[:200]}")
                tool_row = _persist_message(
                    session,
                    run_id,
                    from_agent_id=agent.id,
                    role="tool",
                    content=f"{name}: {result_str}",
                )
                _publish_message(run_id, tool_row)
                messages.append(
                    ToolMessage(content=result_str, tool_call_id=call_id or name or "tool")
                )
        else:
            _persist_log(
                session, run_id, node_source,
                f"reached max_steps={max_steps}; stopping tool loop",
                level="warn",
            )
            # Use the last AI content if any.
            for m in reversed(messages):
                if isinstance(m, AIMessage):
                    final_text = _content_text(m.content)
                    break

        msg_row = _persist_message(
            session, run_id, agent.id, "agent", final_text, total_in, total_out
        )
        _publish_message(run_id, msg_row)

        run = session.get(Run, run_id)
        if run is not None:
            run.total_input_tokens += total_in
            run.total_output_tokens += total_out
            run.total_cost_usd += estimate_cost(agent.model, total_in, total_out)
            session.add(run)
            session.commit()

        _persist_log(
            session, run_id, node_source,
            f"agent '{agent.name}' done (in={total_in}, out={total_out})",
        )

    update: dict[str, Any] = {
        "messages": (state.get("messages") or []) + [{"role": "agent", "agent": agent.name, "content": final_text}],
        "output": final_text,
        "last_agent": agent.name,
    }
    label = _maybe_extract_label(final_text)
    if label:
        update["label"] = label
    return update
