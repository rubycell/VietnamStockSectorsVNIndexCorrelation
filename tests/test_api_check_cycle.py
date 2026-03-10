"""Tests for the check-cycle endpoint."""

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app import database


def test_check_cycle_returns_results(tmp_path):
    engine = database.create_engine_and_tables(f"sqlite:///{tmp_path / 'test.db'}")
    factory = database.get_session(engine)

    def override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    from app.main import get_database_session
    app.dependency_overrides[get_database_session] = override
    client = TestClient(app)

    with patch("app.api.check_cycle.run_agent", return_value={"success": True, "output": {}}):
        response = client.post("/api/check-cycle")

    assert response.status_code == 200
    assert response.json()["success"] is True
    app.dependency_overrides.clear()
