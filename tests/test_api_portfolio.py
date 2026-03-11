"""Tests for portfolio API."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import database
from app.models import Holding


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

    # Seed test data
    session = factory()
    session.add(Holding(ticker="FPT", total_shares=100, avg_cost=120000, total_cost=12000000, realized_pnl=0, position_number=1))
    session.add(Holding(ticker="VCB", total_shares=200, avg_cost=90000, total_cost=18000000, realized_pnl=500000, position_number=2))
    session.commit()
    session.close()

    yield TestClient(app)
    app.dependency_overrides.clear()


def test_get_portfolio(client):
    r = client.get("/api/portfolio")
    assert r.status_code == 200
    data = r.json()
    assert len(data["holdings"]) == 2
    assert data["total_cost"] > 0


def test_get_portfolio_ticker(client):
    r = client.get("/api/portfolio/FPT")
    assert r.status_code == 200
    assert r.json()["ticker"] == "FPT"


def test_get_portfolio_ticker_not_found(client):
    assert client.get("/api/portfolio/NOPE").status_code == 404
