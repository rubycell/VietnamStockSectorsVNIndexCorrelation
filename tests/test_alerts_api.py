"""Tests for alert management endpoints (mark-sent, unsent)."""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from app.main import app
from app import database
from app.models import Alert


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

    session = factory()
    session.add(Alert(
        ticker="VCB",
        rule_id="rule_4_below_swing_low",
        severity="CRITICAL",
        message="VCB below swing low",
        sent_telegram=False,
        sent_whatsapp=False,
    ))
    session.add(Alert(
        ticker="FPT",
        rule_id="rule_2_fud_opportunity",
        severity="WARNING",
        message="FUD detected for FPT",
        sent_telegram=True,
        sent_whatsapp=False,
    ))
    session.commit()
    session.close()

    yield TestClient(app)
    app.dependency_overrides.clear()


def test_mark_alert_sent_telegram(client):
    """Mark an alert as sent via Telegram."""
    response = client.post("/api/alerts/1/mark-sent", json={"channel": "telegram"})
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["channel"] == "telegram"
    assert data["marked"] is True

    alerts = client.get("/api/alerts").json()
    vcb_alert = next(a for a in alerts if a["ticker"] == "VCB")
    assert vcb_alert["sent_telegram"] is True


def test_mark_alert_sent_whatsapp(client):
    """Mark an alert as sent via WhatsApp."""
    response = client.post("/api/alerts/1/mark-sent", json={"channel": "whatsapp"})
    assert response.status_code == 200


def test_mark_alert_sent_unknown_channel(client):
    """Reject unknown channel name."""
    response = client.post("/api/alerts/1/mark-sent", json={"channel": "email"})
    assert response.status_code == 400


def test_mark_alert_not_found(client):
    """Return 404 for nonexistent alert."""
    response = client.post("/api/alerts/999/mark-sent", json={"channel": "telegram"})
    assert response.status_code == 404


def test_list_unsent_telegram(client):
    """List alerts not yet sent to Telegram."""
    response = client.get("/api/alerts/unsent?channel=telegram")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "VCB"


def test_list_unsent_whatsapp(client):
    """List alerts not yet sent to WhatsApp."""
    response = client.get("/api/alerts/unsent?channel=whatsapp")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_list_unsent_unknown_channel(client):
    """Reject unknown channel for unsent listing."""
    response = client.get("/api/alerts/unsent?channel=email")
    assert response.status_code == 400
