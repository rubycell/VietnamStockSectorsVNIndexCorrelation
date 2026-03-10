"""Tests for FastAPI application."""

from fastapi.testclient import TestClient
from app.main import app


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_served():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
