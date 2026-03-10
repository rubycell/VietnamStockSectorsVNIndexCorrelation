"""Tests for agent base class and registry."""

from app.agents.base import BaseAgent, AgentResult
from app.agents.registry import AgentRegistry


class FakeAgent(BaseAgent):
    agent_id = "fake-agent"
    agent_type = "deterministic"

    def run(self, context: dict) -> AgentResult:
        return AgentResult(success=True, output={"message": f"processed {context.get('ticker', '?')}"})


def test_base_agent_run_returns_result():
    result = FakeAgent().run({"ticker": "FPT"})
    assert result.success is True
    assert result.output["message"] == "processed FPT"


def test_agent_result_error_case():
    result = AgentResult(success=False, error="broke")
    assert result.success is False
    assert result.output is None


def test_registry_register_and_get():
    registry = AgentRegistry()
    registry.register(FakeAgent)
    assert isinstance(registry.get("fake-agent"), FakeAgent)


def test_registry_get_unknown_returns_none():
    assert AgentRegistry().get("nope") is None


def test_registry_list_agents():
    registry = AgentRegistry()
    registry.register(FakeAgent)
    agents = registry.list_agents()
    assert agents == [{"id": "fake-agent", "type": "deterministic"}]
