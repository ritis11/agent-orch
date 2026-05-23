"""Gemini LLM factory + cost table.

Uses `langchain-google-genai`. The API key is read from `GEMINI_API_KEY`
(falls back to `GOOGLE_API_KEY` which the underlying SDK also recognises).

If no key is configured we still return a chat model — the call will fail at
invocation time with a clear error, which lets the backend boot for demoing
the UI without credentials.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


SUPPORTED_MODELS: list[str] = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

AVAILABLE_MODELS = SUPPORTED_MODELS

# USD per 1M tokens. Approximate public pricing; tweak as Google updates.
COST_TABLE: dict[str, dict[str, float]] = {
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro":   {"input": 1.25, "output": 5.00},
}


def _resolve_api_key() -> str | None:
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def get_gemini_api_key() -> str | None:
    key = _resolve_api_key()
    return key.strip() if key else None


def get_llm(model: str, temperature: float = 0.7, max_tokens: int = 1024) -> Any:
    """Return a configured ChatGoogleGenerativeAI instance.

    Imports lazily so the backend can boot even if the package or key is
    missing — only the path that actually invokes an LLM will hit the issue.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    api_key = _resolve_api_key()
    if not api_key:
        logger.warning("GEMINI_API_KEY not set; LLM calls will fail until configured.")

    return ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        max_output_tokens=max_tokens,
        google_api_key=api_key,
    )


def estimate_cost(model: str, in_tokens: int, out_tokens: int) -> float:
    rates = COST_TABLE.get(model) or COST_TABLE["gemini-2.0-flash"]
    return (in_tokens / 1_000_000) * rates["input"] + (out_tokens / 1_000_000) * rates["output"]
