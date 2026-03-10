"""Tests for rules evaluation and alerts APIs."""

import pytest
from datetime import date, datetime
from fastapi.testclient import TestClient
from app.main import app
from app import database
from app.models import Holding, SwingLow, Price, Alert


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

    # Seed: holding below swing low (should trigger rules #4 and #9)
    session = factory()
    session.add(Holding(
        ticker="FPT", total_shares=100, vwap_cost=120000,
        total_cost=12000000, current_price=100000, position_number=2
    ))
    session.add(SwingLow(
        ticker="FPT", date=date(2025, 1, 10), price=105000, confirmed=True
    ))
    session.commit()
    session.close()

    yield TestClient(app)
    app.dependency_overrides.clear()


def test_evaluate_rules(client):
    response = client.post("/api/rules/evaluate")
    assert response.status_code == 200
    data = response.json()
    assert "triggered" in data
    # FPT at 100k below swing low 105k with position #2 -> rules #4 and #9
    rule_ids = [triggered["rule_id"] for triggered in data["triggered"]]
    assert "below_swing_low_sell" in rule_ids
    assert "stoploss_all_pos2" in rule_ids


def test_rules_create_alerts(client):
    client.post("/api/rules/evaluate")
    response = client.get("/api/alerts")
    assert response.status_code == 200
    assert len(response.json()) >= 2


def test_alert_dedup(client):
    # Evaluate twice — should not create duplicate alerts
    client.post("/api/rules/evaluate")
    client.post("/api/rules/evaluate")
    response = client.get("/api/alerts")
    # Count alerts for FPT rule #4 — should be 1 per day
    rule4_alerts = [
        alert for alert in response.json()
        if alert["rule_id"] == "below_swing_low_sell"
    ]
    assert len(rule4_alerts) == 1


def test_get_alerts_empty(client):
    response = client.get("/api/alerts")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
