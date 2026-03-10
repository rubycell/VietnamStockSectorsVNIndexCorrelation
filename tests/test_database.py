"""Tests for database setup and model creation."""

import pytest
from sqlalchemy import inspect, text
from app.database import create_engine_and_tables, get_session


def test_create_engine_and_tables_creates_all_tables(tmp_path):
    """All expected tables exist after initialization."""
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine_and_tables(database_url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {
        "trade_fills", "trades", "holdings", "prices",
        "swing_lows", "price_levels", "alerts", "config",
        "agents", "agent_runs", "import_batches",
    }
    assert expected_tables.issubset(table_names), f"Missing: {expected_tables - table_names}"


def test_get_session_returns_usable_session(tmp_path):
    """Session can query the database."""
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine_and_tables(database_url)
    session_factory = get_session(engine)
    with session_factory() as session:
        result = session.execute(text("SELECT 1")).scalar()
        assert result == 1
