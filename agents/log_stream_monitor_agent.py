"""Reference agent for the log_stream_monitor task."""

from __future__ import annotations


class LogStreamMonitorAgent:
    def __init__(self) -> None:
        self.reset({})

    def reset(self, task_spec):
        self.task_spec = task_spec or {}
        self.obs = None
        self.cursor: int = 0
        self.done: bool = False

    def observe(self, observation):
        self.obs = observation

    def _extract_stream_code(self, entries: list[str]) -> str | None:
        for entry in entries:
            if "CRITICAL" in entry and "STREAM_CODE=" in entry:
                for part in entry.split():
                    if part.startswith("STREAM_CODE="):
                        return part.split("=", 1)[1]
        return None

    def act(self):
        if self.done:
            return {"type": "wait", "args": {}}

        last_action = self.obs.get("last_action") if self.obs else None
        last_result = self.obs.get("last_action_result") if self.obs else None
        action_type = last_action.get("type") if isinstance(last_action, dict) else None

        if action_type == "poll_stream" and last_result and last_result.get("ok"):
            entries = last_result.get("entries", [])
            stream_code = self._extract_stream_code(entries)
            if stream_code is not None:
                self.done = True
                return {"type": "set_output", "args": {"key": "STREAM_CODE", "value": stream_code}}
            if last_result.get("exhausted"):
                self.done = True
                return {"type": "wait", "args": {}}
            self.cursor = last_result.get("next_cursor", self.cursor + 1)

        if action_type == "set_output":
            self.done = True
            return {"type": "wait", "args": {}}

        return {"type": "poll_stream", "args": {"cursor": self.cursor}}
