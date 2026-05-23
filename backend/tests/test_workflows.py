"""Workflow create + run API tests."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from tests.conftest import MockLLM, wait_for_run


def _linear_graph(agent_id: int) -> dict:
    return {
        "nodes": [
            {"id": "start", "type": "start"},
            {"id": "agent1", "type": "agent", "agent_id": agent_id},
            {"id": "end", "type": "end"},
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "agent1"},
            {"id": "e2", "source": "agent1", "target": "end"},
        ],
    }


def test_workflow_create_and_run(client: TestClient, sample_agent_payload: dict) -> None:
    agent_resp = client.post("/api/agents", json=sample_agent_payload)
    assert agent_resp.status_code == 200
    agent_id = agent_resp.json()["id"]

    graph = _linear_graph(agent_id)
    wf_resp = client.post(
        "/api/workflows",
        json={"name": "Test Flow", "description": "demo", "graph": graph},
    )
    assert wf_resp.status_code == 201, wf_resp.text
    workflow_id = wf_resp.json()["id"]

    with patch("app.runtime.agent_node.get_llm") as get_llm:
        get_llm.return_value = MockLLM(responses=["Hello from mocked LLM"])

        run_resp = client.post(
            f"/api/workflows/{workflow_id}/run",
            json={"input": "What is Yuno?"},
        )
        assert run_resp.status_code == 200, run_resp.text
        run_id = run_resp.json()["id"]

        detail = wait_for_run(client, run_id)
        assert detail["run"]["status"] == "completed"
        assert detail["messages"], "expected persisted messages"
        output = detail["run"].get("output") or ""
        contents = " ".join(m["content"] for m in detail["messages"])
        assert "mocked LLM" in output or "mocked LLM" in contents
