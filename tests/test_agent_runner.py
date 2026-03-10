"""Tests for the agent runner."""

import pytest
from unittest.mock import patch
from app.models import Agent, AgentRun
from app.database import create_engine_and_tables, get_session
from app.agents.runner import run_agent


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine_and_tables(f"sqlite:///{tmp_path / 'test.db'}")
    factory = get_session(engine)
    session = factory()
    yield session
    session.close()


@pytest.fixture
def code_gen_agent(db_session):
    agent = Agent(id="test-cg", name="Test CG", agent_type="code_gen",
                  prompt_template="Find stocks > {threshold}", enabled=True)
    db_session.add(agent)
    db_session.commit()
    return agent


def test_agent_not_found(db_session):
    result = run_agent("nope", session=db_session)
    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_disabled_agent(db_session):
    db_session.add(Agent(id="off", name="Off", agent_type="deterministic", enabled=False))
    db_session.commit()
    result = run_agent("off", session=db_session)
    assert "disabled" in result["error"].lower()


def test_code_gen_agent(db_session, code_gen_agent):
    mock_code = 'import json\noutput = json.dumps({"found": 5})'
    with (
        patch("app.agents.runner._call_claude_for_code", return_value=mock_code),
        patch("app.agents.runner._get_data_context", return_value={}),
    ):
        result = run_agent("test-cg", variables={"threshold": 50000}, session=db_session)
    assert result["success"] is True
    assert result["output"]["found"] == 5
    runs = db_session.query(AgentRun).filter_by(agent_id="test-cg").all()
    assert len(runs) == 1
    assert runs[0].status == "success"
