"""Tests for agent seeding."""

import pytest
from app.database import create_engine_and_tables, get_session
from app.models import Agent
from app.agents.seed import seed_agents, INITIAL_AGENTS


def test_seed_creates_agents(tmp_path):
    engine = create_engine_and_tables(f"sqlite:///{tmp_path / 'test.db'}")
    factory = get_session(engine)
    session = factory()

    seed_agents(session)

    agents = session.query(Agent).all()
    assert len(agents) == len(INITIAL_AGENTS)

    # Check specific agents exist
    ids = {a.id for a in agents}
    assert "fud-assessor" in ids
    assert "trendy-sector-detector" in ids
    assert "unusual-volume-scanner" in ids
    session.close()


def test_seed_is_idempotent(tmp_path):
    engine = create_engine_and_tables(f"sqlite:///{tmp_path / 'test.db'}")
    factory = get_session(engine)
    session = factory()

    seed_agents(session)
    seed_agents(session)  # Run again

    agents = session.query(Agent).all()
    assert len(agents) == len(INITIAL_AGENTS)  # No duplicates
    session.close()
