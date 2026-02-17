from __future__ import annotations

from pydantic_ai import Agent as PydanticAgent, RunContext


class Agent:
    def __init__(self) -> None:
        self._x = 1

    def reset(self, task_spec):
        return None

    def act(self, observation):
        return None
