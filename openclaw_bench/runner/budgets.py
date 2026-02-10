"""Budget helpers (stub)."""

class Budgets:
    def __init__(self, steps: int, tool_calls: int, timeout_s: float | None = None):
        self.steps_remaining = steps
        self.tool_calls_remaining = tool_calls
        self.timeout_s = timeout_s

    def consume_step(self) -> None:
        self.steps_remaining -= 1

    def consume_tool_call(self) -> None:
        self.tool_calls_remaining -= 1
