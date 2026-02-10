"""Budget helpers."""

from __future__ import annotations

import time


class Budgets:
    def __init__(self, steps: int, tool_calls: int, timeout_s: float | None = None):
        self.steps_remaining = steps
        self.tool_calls_remaining = tool_calls
        self.timeout_s = timeout_s
        self._start_time = time.monotonic()

    def consume_step(self) -> None:
        self.steps_remaining -= 1

    def consume_tool_call(self) -> None:
        self.tool_calls_remaining -= 1

    def timed_out(self) -> bool:
        if self.timeout_s is None:
            return False
        return (time.monotonic() - self._start_time) > self.timeout_s

    def exhausted(self) -> bool:
        return self.steps_remaining < 0 or self.tool_calls_remaining < 0 or self.timed_out()
