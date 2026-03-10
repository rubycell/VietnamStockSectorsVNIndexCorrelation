"""Tests for agent management API."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import database


@pytest.fixture
def client(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = database.create_engine_and_tables(db_url)
    factory = database.get_session(engine)

    def override():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    from app.main import get_database_session
    app.dependency_overrides[get_database_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


SAMPLE = {
    "id": "test-agent",
    "name": "Test",
    "agent_type": "code_gen",
    "prompt_template": "Analyze {ticker}",
    "enabled": True,
}


def test_create_agent(client):
    response = client.post("/api/agents", json=SAMPLE)
    assert response.status_code == 201
    assert response.json()["id"] == "test-agent"


def test_list_agents(client):
    client.post("/api/agents", json=SAMPLE)
    assert len(client.get("/api/agents").json()) == 1


def test_get_agent(client):
    client.post("/api/agents", json=SAMPLE)
    assert client.get("/api/agents/test-agent").status_code == 200


def test_get_not_found(client):
    assert client.get("/api/agents/nope").status_code == 404


def test_update_agent(client):
    client.post("/api/agents", json=SAMPLE)
    response = client.put(
        "/api/agents/test-agent",
        json={"name": "Updated", "enabled": False},
    )
    assert response.json()["name"] == "Updated"
    assert response.json()["enabled"] is False


def test_delete_agent(client):
    client.post("/api/agents", json=SAMPLE)
    assert client.delete("/api/agents/test-agent").status_code == 204
    assert client.get("/api/agents/test-agent").status_code == 404


def test_duplicate_fails(client):
    client.post("/api/agents", json=SAMPLE)
    assert client.post("/api/agents", json=SAMPLE).status_code == 409
