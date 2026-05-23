"""Agent CRUD API tests."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_agents_crud_round_trip(client: TestClient, sample_agent_payload: dict) -> None:
    create = client.post("/api/agents", json=sample_agent_payload)
    assert create.status_code == 200, create.text
    created = create.json()
    agent_id = created["id"]
    assert created["name"] == sample_agent_payload["name"]
    assert created["role"] == sample_agent_payload["role"]

    listed = client.get("/api/agents")
    assert listed.status_code == 200
    ids = [a["id"] for a in listed.json()]
    assert agent_id in ids

    fetched = client.get(f"/api/agents/{agent_id}")
    assert fetched.status_code == 200
    assert fetched.json()["system_prompt"] == sample_agent_payload["system_prompt"]

    updated = client.put(
        f"/api/agents/{agent_id}",
        json={"name": "Updated Agent", "role": "updated"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Agent"
    assert updated.json()["role"] == "updated"

    deleted = client.delete(f"/api/agents/{agent_id}")
    assert deleted.status_code in (200, 204)

    missing = client.get(f"/api/agents/{agent_id}")
    assert missing.status_code == 404
