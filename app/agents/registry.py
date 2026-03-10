"""Agent registry — maps agent IDs to agent classes."""

from typing import Type

from app.agents.base import BaseAgent


class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, Type[BaseAgent]] = {}

    def register(self, agent_class: Type[BaseAgent]) -> None:
        self._agents[agent_class.agent_id] = agent_class

    def get(self, agent_id: str) -> BaseAgent | None:
        cls = self._agents.get(agent_id)
        return cls() if cls else None

    def list_agents(self) -> list[dict]:
        return [{"id": c.agent_id, "type": c.agent_type} for c in self._agents.values()]
