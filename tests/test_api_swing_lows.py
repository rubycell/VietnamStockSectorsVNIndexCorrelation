"""Tests for swing low and config APIs."""

import pytest
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app import database
from app.models import SwingLow, Price, Config as ConfigModel


@pytest.fixture
def client(tmp_path):
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

    # Seed price data for swing low detection
    session = factory()
    # 20 bars: first 12 at 100, then dip to 85, then recover to 110
    closes = [100] * 12 + [95, 90, 88, 92, 100, 105, 108, 110]
    lows =   [100] * 12 + [93, 88, 85, 90, 98, 103, 106, 108]
    for i in range(20):
        session.add(Price(
            ticker="FPT",
            date=date(2025, 1, 1 + i),
            open=closes[i],
            high=closes[i] * 1.01,
            low=lows[i],
            close=closes[i],
            volume=1000000,
        ))
    session.commit()
    session.close()

    yield TestClient(app)
    app.dependency_overrides.clear()


def test_detect_swing_lows(client):
    r = client.post("/api/swing-lows/detect", json={"ticker": "FPT"})
    assert r.status_code == 200
    assert len(r.json()["swing_lows"]) >= 1


def test_get_swing_lows(client):
    # First detect
    client.post("/api/swing-lows/detect", json={"ticker": "FPT"})
    # Then get
    r = client.get("/api/swing-lows/FPT")
    assert r.status_code == 200
    assert len(r.json()["swing_lows"]) >= 1


def test_config_get_set(client):
    # Set a config value
    r = client.put("/api/config/fud_threshold", json={"value": "2.5", "description": "FUD volatility threshold"})
    assert r.status_code == 200

    # Get it back
    r = client.get("/api/config/fud_threshold")
    assert r.status_code == 200
    assert r.json()["value"] == "2.5"


def test_config_list(client):
    client.put("/api/config/key1", json={"value": "val1"})
    client.put("/api/config/key2", json={"value": "val2"})
    r = client.get("/api/config")
    assert r.status_code == 200
    assert len(r.json()) >= 2
