"""LangChain tool implementations available to agents."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

HTTP_BODY_LIMIT = 4000
TAVILY_SEARCH_URL = "https://api.tavily.com/search"


def _tavily_api_key() -> str | None:
    return os.getenv("TAVILY_API_KEY") or None


@tool
def web_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search the web via Tavily and return compact results.

    Args:
        query: Natural-language search query.
        max_results: Maximum number of results to return (1-10).
    """
    api_key = _tavily_api_key()
    if not api_key:
        return [{"title": "error", "href": "", "body": "TAVILY_API_KEY not configured"}]

    max_results = max(1, min(int(max_results or 5), 10))
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                TAVILY_SEARCH_URL,
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                },
            )
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:  # noqa: BLE001 - tools should never raise to the agent
        logger.warning("web_search failed: %s", exc)
        return [{"title": "error", "href": "", "body": f"search failed: {exc}"}]

    results: list[dict[str, str]] = []
    for r in payload.get("results") or []:
        results.append({
            "title": r.get("title", ""),
            "href": r.get("url", ""),
            "body": r.get("content", ""),
        })
    return results or [{"title": "error", "href": "", "body": "no results returned"}]


@tool
def http_get(url: str) -> str:
    """Fetch a URL with HTTP GET and return the response body (truncated)."""
    try:
        with httpx.Client(follow_redirects=True, timeout=10.0) as client:
            resp = client.get(url, headers={"User-Agent": "yuno-agent/1.0"})
            text = resp.text or ""
            if len(text) > HTTP_BODY_LIMIT:
                text = text[:HTTP_BODY_LIMIT] + f"\n...[truncated at {HTTP_BODY_LIMIT} chars]"
            return f"HTTP {resp.status_code}\n{text}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("http_get failed for %s: %s", url, exc)
        return f"error: {exc}"


@tool
def slack_send(channel: str, text: str) -> str:
    """Post a message to a Slack channel using the configured bot token.

    Args:
        channel: Channel id (Cxxx) or name like `#agent-demo`.
        text: Message text to send.
    """
    # Imported lazily to avoid hard dependency during boot if Slack is not configured.
    from ..channels import slack as slack_channel

    client = slack_channel.get_slack_client()
    if client is None:
        return "slack not configured"
    try:
        resp = client.chat_postMessage(channel=channel, text=text)
        return f"ok ts={resp.get('ts')}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("slack_send failed: %s", exc)
        return f"error: {exc}"


@tool
def calculator(expression: str) -> str:
    """Safely evaluate a numeric expression (no Python builtins).

    Uses `asteval` which restricts operators to math + comparisons.
    """
    try:
        from asteval import Interpreter

        interp = Interpreter(minimal=True, use_numpy=False)
        result = interp(expression)
        if interp.error:
            return f"error: {interp.error[0].get_error()[1]}"
        return str(result)
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


# Registry — keeps the GET /api/tools endpoint and per-agent tool selection in sync.
TOOL_REGISTRY: dict[str, Any] = {
    "web_search": web_search,
    "http_get": http_get,
    "slack_send": slack_send,
    "calculator": calculator,
}

TOOL_DESCRIPTIONS: list[dict[str, str]] = [
    {"name": "web_search", "description": "Search the web (Tavily) and return top result snippets."},
    {"name": "http_get", "description": "Fetch a URL and return the response body (truncated to ~4k chars)."},
    {"name": "slack_send", "description": "Post a message to a Slack channel or DM."},
    {"name": "calculator", "description": "Safely evaluate a numeric expression."},
]


def get_tools_for_agent(agent: Any, context: dict[str, Any] | None = None) -> list[Any]:
    """Return LangChain tool objects matching the agent's `tools` list."""
    names: list[str] = list(getattr(agent, "tools", []) or [])
    return [TOOL_REGISTRY[n] for n in names if n in TOOL_REGISTRY]


def get_tool_definitions() -> list[dict[str, str]]:
    return list(TOOL_DESCRIPTIONS)
