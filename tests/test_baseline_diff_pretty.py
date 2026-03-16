"""Tests for baseline diff pretty formatting."""

from __future__ import annotations

import sys
from io import StringIO
from unittest.mock import patch

from agent_bench.cli import _print_diff_pretty
from agent_bench.runner.baseline import diff_runs


class _Console:
    def print(self, *args, **kwargs):
        for arg in args:
            print(arg)


class _Table:
    def __init__(self, *args, title=None, **kwargs):
        self.title = title or ""
        self.rows: list[tuple[object, ...]] = []

    def add_column(self, *args, **kwargs):
        return None

    def add_row(self, *args, **kwargs):
        self.rows.append(args)

    def __str__(self) -> str:
        lines = [self.title] if self.title else []
        lines.extend(" | ".join(str(item) for item in row) for row in self.rows)
        return "\n".join(lines)


class _Panel:
    def __init__(self, renderable, *args, title=None, **kwargs):
        self.renderable = renderable
        self.title = title or ""

    def __str__(self) -> str:
        if self.title:
            return f"{self.title}\n{self.renderable}"
        return str(self.renderable)


class _Text:
    def __init__(self, text="", style=None):
        self.parts: list[str] = []
        if text:
            self.parts.append(str(text))

    def append(self, text, style=None):
        self.parts.append(str(text))

    def __str__(self) -> str:
        return "".join(self.parts)


def _install_rich_stub() -> None:
    sys.modules["rich.console"] = type("_ConsoleModule", (), {"Console": _Console})
    sys.modules["rich.table"] = type("_TableModule", (), {"Table": _Table})
    sys.modules["rich.panel"] = type("_PanelModule", (), {"Panel": _Panel})
    sys.modules["rich.text"] = type("_TextModule", (), {"Text": _Text})


def test_print_diff_pretty_identical_runs():
    _install_rich_stub()
    run_a = {
        "run_id": "a",
        "agent": "agents/toy_agent.py",
        "task_ref": "filesystem_hidden_config@1",
        "success": True,
        "steps_used": 5,
        "tool_calls_used": 5,
        "seed": 0,
        "failure_type": None,
        "termination_reason": "success",
        "action_trace": [
            {"step": 1, "action": {"type": "list_dir"}},
            {"step": 2, "action": {"type": "read_file"}},
        ],
    }
    run_b = {
        "run_id": "b",
        "agent": "agents/toy_agent.py",
        "task_ref": "filesystem_hidden_config@1",
        "success": True,
        "steps_used": 5,
        "tool_calls_used": 5,
        "seed": 0,
        "failure_type": None,
        "termination_reason": "success",
        "action_trace": [
            {"step": 1, "action": {"type": "list_dir"}},
            {"step": 2, "action": {"type": "read_file"}},
        ],
    }

    diff = diff_runs(run_a, run_b)
    exit_code = 0

    output = StringIO()
    with patch("sys.stdout", output):
        _print_diff_pretty(diff, exit_code, show_taxonomy=False)

    result = output.getvalue()
    assert "IDENTICAL" in result
    assert "Run Summary" in result
    assert "Budget Usage" in result


def test_print_diff_pretty_with_divergence():
    _install_rich_stub()
    run_a = {
        "run_id": "a",
        "agent": "agents/toy_agent.py",
        "task_ref": "filesystem_hidden_config@1",
        "success": True,
        "steps_used": 5,
        "tool_calls_used": 5,
        "seed": 0,
        "failure_type": None,
        "termination_reason": "success",
        "action_trace": [
            {"step": 1, "action": {"type": "list_dir"}},
            {"step": 2, "action": {"type": "read_file"}},
        ],
    }
    run_b = {
        "run_id": "b",
        "agent": "agents/toy_agent.py",
        "task_ref": "filesystem_hidden_config@1",
        "success": False,
        "steps_used": 6,
        "tool_calls_used": 6,
        "seed": 0,
        "failure_type": "budget_exhausted",
        "termination_reason": "steps_exhausted",
        "action_trace": [
            {"step": 1, "action": {"type": "list_dir"}},
            {"step": 2, "action": {"type": "list_dir"}},
        ],
    }

    diff = diff_runs(run_a, run_b)
    exit_code = 1

    output = StringIO()
    with patch("sys.stdout", output):
        _print_diff_pretty(diff, exit_code, show_taxonomy=True)

    result = output.getvalue()
    assert "DIFFERENT" in result
    assert "Budget Usage" in result
    assert "Failure Taxonomy" in result
    assert "budget_exhausted" in result
    assert "Trace Divergence" in result
    assert "Per-Step Differences" in result
