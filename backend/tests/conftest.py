"""Shared pytest fixtures."""
from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

# Configure test database before importing app modules that create the engine.
_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ.setdefault("GEMINI_API_KEY", "test-key")

from app.db import engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db() -> Generator[None, None, None]:
    SQLModel.metadata.drop_all(engine)
    init_db()
    yield


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with patch("app.main.start_slack_handler", return_value=None), patch(
        "app.main.start_scheduler", return_value=None
    ), patch("app.main.stop_slack_handler", return_value=None):
        with TestClient(app) as test_client:
            yield test_client


@pytest.fixture
def sample_agent_payload() -> dict[str, Any]:
    return {
        "name": "Test Agent",
        "role": "tester",
        "system_prompt": "You are a test agent.",
        "model": "gemini-2.0-flash",
        "tools": [],
        "memory_window": 5,
        "temperature": 0.2,
        "max_tokens": 256,
        "guardrails": {"blocked_topics": [], "max_steps": 3},
        "schedule_cron": None,
        "schedule_input": None,
    }


class MockLLM:
    """Deterministic LLM stub for tests."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses or ["ok"])
        self._calls = 0

    def bind_tools(self, tools: Any) -> "MockLLM":
        return self

    def invoke(self, messages: Any) -> AIMessage:
        content = self._responses[min(self._calls, len(self._responses) - 1)]
        self._calls += 1
        return AIMessage(
            content=content,
            usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        )


@pytest.fixture
def mock_llm() -> Generator[Any, None, None]:
    with patch("app.runtime.agent_node.get_llm") as get_llm:
        get_llm.side_effect = lambda *a, **k: MockLLM()
        yield get_llm


def wait_for_run(client: TestClient, run_id: int, timeout: float = 10.0) -> dict[str, Any]:
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/runs/{run_id}")
        assert resp.status_code == 200
        body = resp.json()
        status = body["run"]["status"]
        if status in ("completed", "failed"):
            return body
        time.sleep(0.05)
    raise TimeoutError(f"run {run_id} did not finish in {timeout}s")
