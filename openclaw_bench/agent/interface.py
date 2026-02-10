"""Agent interface contract (stub)."""

class Agent:
    def reset(self, task_spec: dict) -> None:  # pragma: no cover - interface only
        raise NotImplementedError

    def observe(self, observation: dict) -> None:  # pragma: no cover - interface only
        raise NotImplementedError

    def act(self) -> dict:  # pragma: no cover - interface only
        raise NotImplementedError
