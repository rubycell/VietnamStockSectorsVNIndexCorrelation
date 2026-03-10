"""Integration smoke test: full API flow."""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app import database


@pytest.fixture
def client(tmp_path):
    engine = database.create_engine_and_tables(f"sqlite:///{tmp_path / 'test.db'}")
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


def test_full_stack(client):
    # Health
    assert client.get("/api/health").json()["status"] == "ok"

    # Create agent
    response = client.post("/api/agents", json={
        "id": "smoke", "name": "Smoke", "agent_type": "code_gen",
        "prompt_template": "Count prices", "enabled": True,
    })
    assert response.status_code == 201

    # Read back agent
    response = client.get("/api/agents/smoke")
    assert response.status_code == 200
    assert response.json()["name"] == "Smoke"

    # List agents
    response = client.get("/api/agents")
    assert response.status_code == 200
    assert len(response.json()) == 1

    # Execute agent with mocked runner (signal.SIGALRM unavailable in test threads)
    mock_runner_result = {"success": True, "output": {"count": 0}, "error": None}
    with patch("app.api.agents.run_agent", return_value=mock_runner_result):
        response = client.post("/api/agents/smoke/execute", json={"variables": {}})
    execute_result = response.json()
    assert execute_result["success"] is True, f"Execute failed: {execute_result.get('error')}"
    assert execute_result["output"]["count"] == 0

    # Check cycle (no holdings, so runs with empty results)
    response = client.post("/api/check-cycle")
    assert response.json()["success"] is True

    # Cleanup
    assert client.delete("/api/agents/smoke").status_code == 204

    # Verify deletion
    response = client.get("/api/agents/smoke")
    assert response.status_code == 404
