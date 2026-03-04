"""Minimal TraceCore agent stub.

This agent demonstrates the reset / observe / act interface required by the
TraceCore Deterministic Episode Runtime.  Replace the placeholder logic in
``act()`` with your own decision loop.
"""

from __future__ import annotations


class MyAgent:
    """Minimal agent implementing the TraceCore reset/observe/act contract."""

    def reset(self) -> None:
        """Called once before the episode begins. Clear any internal state."""
        self.history: list[dict] = []

    def observe(self, observation: dict) -> None:
        """Receive an observation from the environment."""
        self.history.append({"role": "env", "content": observation})

    def act(self) -> dict:
        """Return the next action to execute.

        Must return a dict with at least ``{"type": "<action_name>", "args": {...}}``.
        Return ``{"type": "submit", "args": {"answer": "<value>"}}`` to end the episode.
        """
        if len(self.history) == 0:
            return {"type": "list_directory", "args": {"path": "/"}}

        last = self.history[-1].get("content", {})

        if isinstance(last, dict) and "files" in last:
            for f in last.get("files", []):
                if "config" in str(f).lower() or "secret" in str(f).lower():
                    return {"type": "read_file", "args": {"path": str(f)}}

        if len(self.history) >= 4:
            return {"type": "submit", "args": {"answer": "unknown"}}

        return {"type": "list_directory", "args": {"path": "/tmp"}}
