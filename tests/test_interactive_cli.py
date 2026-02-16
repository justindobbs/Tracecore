"""Tests for the interactive CLI wizard."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
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
    monkeypatch.setattr(interactive, "_discover_tasks", lambda **kwargs: [interactive.TaskOption(ref="filesystem_hidden_config@1", suite="filesystem", description="", budgets=None)])
    monkeypatch.setattr(interactive, "_discover_pairings", lambda **kwargs: [])
    monkeypatch.setattr(interactive, "_prompt_agent", lambda *args, **kwargs: "agents/toy_agent.py")
    monkeypatch.setattr(interactive, "_prompt_task", lambda *args, **kwargs: "filesystem_hidden_config@1")
    monkeypatch.setattr(interactive, "_prompt_seed", lambda *args, **kwargs: 42)
    monkeypatch.setattr(interactive.Confirm, "ask", lambda *args, **kwargs: True)

    result = interactive.run_wizard(config=_StubConfig(), console=console, no_color=True)

    assert result == ("agents/toy_agent.py", "filesystem_hidden_config@1", 42)
    transcript = console.export_text()
    assert "Deterministic Episode" in transcript
    assert "Launching agent-bench run" in transcript


def test_validate_agent_path_success(tmp_path):
    """Valid agent file passes validation."""
    agent_file = tmp_path / "test_agent.py"
    agent_file.write_text(
        "class MyAgent:\n"
        "    def reset(self, task_spec): pass\n"
        "    def observe(self, observation): pass\n"
        "    def act(self): pass\n"
    )
    is_valid, error = interactive._validate_agent_path(str(agent_file))
    assert is_valid is True
    assert error is None


def test_validate_agent_path_missing_file():
    """Missing file returns error."""
    is_valid, error = interactive._validate_agent_path("nonexistent.py")
    assert is_valid is False
    assert "not found" in error


def test_validate_agent_path_missing_methods(tmp_path):
    """File without required methods fails validation."""
    agent_file = tmp_path / "incomplete_agent.py"
    agent_file.write_text(
        "class MyAgent:\n"
        "    def reset(self, task_spec): pass\n"
    )
    is_valid, error = interactive._validate_agent_path(str(agent_file))
    assert is_valid is False
    assert "observe" in error or "act" in error


def test_task_budgets_displayed():
    """Budgets appear in task table."""
    tasks = [
        interactive.TaskOption(
            ref="task1@1",
            suite="suite1",
            description="Test task",
            budgets={"steps": 100, "tool_calls": 20},
        )
    ]
    table = interactive._task_table(tasks, None)
    assert table.title == "Step 2/3: Select Task"
    assert any("Budgets" in str(col.header) for col in table.columns)


def test_session_persistence(tmp_path, monkeypatch):
    """Session save/load roundtrip works."""
    session_path = tmp_path / ".wizard_session.json"
    monkeypatch.setattr(interactive, "SESSION_PATH", session_path)
    
    interactive._save_session("agents/test.py", "task@1", 42)
    assert session_path.exists()
    
    loaded = interactive._load_session()
    assert loaded == {"agent": "agents/test.py", "task": "task@1", "seed": 42}


def test_inline_help_agent():
    """'?' shows help for agent selection."""
    console = _console()
    interactive._show_help(console, "agent")
    output = console.export_text()
    assert "Help" in output
    assert "manual path" in output or "filter" in output


def test_fuzzy_filter():
    """Partial name matching works."""
    items = ["agents/toy_agent.py", "agents/rate_limit_agent.py", "agents/chain_agent.py"]
    filtered = interactive._fuzzy_filter(items, "rate")
    assert filtered == ["agents/rate_limit_agent.py"]
    
    filtered = interactive._fuzzy_filter(items, "agent")
    assert len(filtered) == 3


def test_fuzzy_filter_tasks():
    """Task filtering by ref or description works."""
    tasks = [
        interactive.TaskOption(ref="filesystem_hidden_config@1", suite="fs", description="Extract API key"),
        interactive.TaskOption(ref="rate_limited_api@1", suite="api", description="Handle rate limits"),
    ]
    filtered = interactive._fuzzy_filter_tasks(tasks, "filesystem")
    assert len(filtered) == 1
    assert filtered[0].ref == "filesystem_hidden_config@1"
    
    filtered = interactive._fuzzy_filter_tasks(tasks, "rate")
    assert len(filtered) == 1  # Matches ref only
    assert filtered[0].ref == "rate_limited_api@1"
    
    filtered = interactive._fuzzy_filter_tasks(tasks, "api")
    assert len(filtered) == 2  # Matches both: one in ref, one in description


def test_discover_pairings_with_baseline_data(monkeypatch):
    """Pairings are discovered from baseline data."""
    mock_runs = [
        {"agent": "agents/toy_agent.py", "task_ref": "task1@1", "success": True, "steps_used": 10, "tool_calls_used": 5},
        {"agent": "agents/toy_agent.py", "task_ref": "task1@1", "success": True, "steps_used": 12, "tool_calls_used": 6},
        {"agent": "agents/rate_limit_agent.py", "task_ref": "task2@1", "success": False, "steps_used": 20, "tool_calls_used": 10},
    ]
    monkeypatch.setattr(interactive, "iter_runs", lambda: iter(mock_runs))
    
    pairings = interactive._discover_pairings()
    assert len(pairings) == 1  # Only one pairing with success_rate > 0
    assert pairings[0].agent == "agents/toy_agent.py"
    assert pairings[0].task_ref == "task1@1"
    assert pairings[0].success_rate == 1.0
    assert pairings[0].runs == 2


def test_discover_pairings_no_data(monkeypatch):
    """No baseline data returns empty list."""
    monkeypatch.setattr(interactive, "iter_runs", lambda: iter([]))
    pairings = interactive._discover_pairings()
    assert pairings == []


def test_pairings_table_display():
    """Pairings table shows correct columns."""
    pairings = [
        interactive.Pairing(
            agent="agents/toy_agent.py",
            task_ref="task1@1",
            success_rate=0.8,
            runs=5,
            last_success=True,
        )
    ]
    table = interactive._pairings_table(pairings)
    assert "Suggested Pairings" in table.title
    assert len(table.columns) == 5  # #, Agent, Task, Success, Last


def test_dry_run_displays_command(monkeypatch):
    """Dry-run mode displays command without executing."""
    console = _console()
    monkeypatch.setattr(interactive, "_is_tty", lambda: True)
    monkeypatch.setattr(interactive, "_discover_agents", lambda: ["agents/toy_agent.py"])
    monkeypatch.setattr(interactive, "_discover_tasks", lambda **kwargs: [interactive.TaskOption(ref="task1@1", suite="s", description="", budgets=None)])
    monkeypatch.setattr(interactive, "_discover_pairings", lambda **kwargs: [])
    monkeypatch.setattr(interactive, "_prompt_agent", lambda *args, **kwargs: "agents/toy_agent.py")
    monkeypatch.setattr(interactive, "_prompt_task", lambda *args, **kwargs: "task1@1")
    monkeypatch.setattr(interactive, "_prompt_seed", lambda *args, **kwargs: 42)
    
    result = interactive.run_wizard(console=console, no_color=True, dry_run=True)
    
    assert result is None  # Dry-run returns None
    transcript = console.export_text()
    assert "Dry-Run Mode" in transcript
    assert "agent-bench run --agent agents/toy_agent.py --task task1@1 --seed 42" in transcript
    assert "No run was performed" in transcript


def test_dry_run_does_not_save_session(tmp_path, monkeypatch):
    """Dry-run mode does not save session even with --save-session."""
    session_path = tmp_path / ".wizard_session.json"
    monkeypatch.setattr(interactive, "SESSION_PATH", session_path)
    console = _console()
    monkeypatch.setattr(interactive, "_is_tty", lambda: True)
    monkeypatch.setattr(interactive, "_discover_agents", lambda: ["agents/toy_agent.py"])
    monkeypatch.setattr(interactive, "_discover_tasks", lambda **kwargs: [interactive.TaskOption(ref="task1@1", suite="s", description="", budgets=None)])
    monkeypatch.setattr(interactive, "_discover_pairings", lambda **kwargs: [])
    monkeypatch.setattr(interactive, "_prompt_agent", lambda *args, **kwargs: "agents/toy_agent.py")
    monkeypatch.setattr(interactive, "_prompt_task", lambda *args, **kwargs: "task1@1")
    monkeypatch.setattr(interactive, "_prompt_seed", lambda *args, **kwargs: 42)
    
    result = interactive.run_wizard(console=console, no_color=True, dry_run=True, save_session=True)
    
    assert result is None
    assert not session_path.exists()  # Session should not be saved in dry-run
