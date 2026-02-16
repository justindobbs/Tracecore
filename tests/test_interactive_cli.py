"""Tests for the interactive CLI wizard."""

from __future__ import annotations

from io import StringIO
from typing import Any

from rich.console import Console

from agent_bench import interactive


class _StubConfig:
    def __init__(self, agent: str | None = None, task: str | None = None, seed: int | None = None) -> None:
        self._agent = agent
        self._task = task
        self._seed = seed

    def get_default_agent(self) -> str | None:
        return self._agent

    def get_default_task(self) -> str | None:
        return self._task

    def get_seed(self, *, agent: str | None = None) -> int | None:  # noqa: D401 - same seed for simplicity
        return self._seed


def _console(*, force_terminal: bool = True) -> Console:
    stream = StringIO()
    return Console(file=stream, record=True, no_color=True, force_terminal=force_terminal, color_system=None)


def test_run_wizard_requires_tty(monkeypatch):
    """When no TTY is available the wizard should abort gracefully."""

    console = _console(force_terminal=False)
    monkeypatch.setattr(interactive, "_is_tty", lambda: False)

    result = interactive.run_wizard(console=console, no_color=True)

    assert result is None
    assert "requires a TTY" in console.export_text()


def test_run_wizard_collects_inputs_and_confirms(monkeypatch):
    """Happy path: inputs are collected via helper prompts and confirmed."""

    console = _console()
    monkeypatch.setattr(interactive, "_is_tty", lambda: True)
    monkeypatch.setattr(interactive, "_discover_agents", lambda: ["agents/toy_agent.py"], raising=False)
    monkeypatch.setattr(interactive, "_discover_tasks", lambda: [interactive.TaskOption(ref="filesystem_hidden_config@1", suite="filesystem", description="")])
    monkeypatch.setattr(interactive, "_prompt_agent", lambda *args, **kwargs: "agents/toy_agent.py")
    monkeypatch.setattr(interactive, "_prompt_task", lambda *args, **kwargs: "filesystem_hidden_config@1")
    monkeypatch.setattr(interactive, "_prompt_seed", lambda *args, **kwargs: 42)
    monkeypatch.setattr(interactive.Confirm, "ask", lambda *args, **kwargs: True)

    result = interactive.run_wizard(config=_StubConfig(), console=console, no_color=True)

    assert result == ("agents/toy_agent.py", "filesystem_hidden_config@1", 42)
    transcript = console.export_text()
    assert "Deterministic Episode" in transcript
    assert "Launching agent-bench run" in transcript
