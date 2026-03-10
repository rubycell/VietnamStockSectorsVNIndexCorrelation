"""Tests for prices API."""

import pytest
from datetime import date
from unittest.mock import patch, MagicMock
import pandas as pd
from fastapi.testclient import TestClient
from app.main import app
from app import database
from app.models import Price


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

    # Seed price data
    session = factory()
    session.add(Price(ticker="FPT", date=date(2025, 1, 15), open=119000, high=121000, low=118000, close=120000, volume=1000000))
    session.add(Price(ticker="FPT", date=date(2025, 1, 16), open=120000, high=123000, low=119500, close=122000, volume=1200000))
    session.commit()
    session.close()

    yield TestClient(app)
    app.dependency_overrides.clear()


def test_get_prices(client):
    r = client.get("/api/prices/FPT")
    assert r.status_code == 200
    assert len(r.json()["prices"]) == 2


def test_get_prices_not_found(client):
    r = client.get("/api/prices/NOPE")
    assert r.status_code == 200
    assert len(r.json()["prices"]) == 0


def test_fetch_prices_mocked(client):
    """Test the fetch endpoint with mocked vnstock."""
    mock_df = pd.DataFrame({
        "time": [pd.Timestamp("2025-01-17")],
        "open": [122000], "high": [125000], "low": [121000], "close": [124000], "volume": [1500000],
    })

    with patch("app.api.prices._fetch_from_vnstock", return_value=mock_df):
        r = client.post("/api/prices/fetch", json={"tickers": ["FPT"]})

    assert r.status_code == 200
    assert r.json()["fetched"]["FPT"] >= 1
