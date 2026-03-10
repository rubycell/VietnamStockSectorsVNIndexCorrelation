"""Base class for all agents."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentResult:
    success: bool
    output: dict[str, Any] | None = None
    error: str | None = None
    generated_code: str | None = None


class BaseAgent(ABC):
    agent_id: str = ""
    agent_type: str = "deterministic"

    @abstractmethod
    def run(self, context: dict) -> AgentResult:
        ...
