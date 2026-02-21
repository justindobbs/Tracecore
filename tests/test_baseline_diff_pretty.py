"""Tests for baseline diff pretty formatting."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from agent_bench.cli import _print_diff_pretty
from agent_bench.runner.baseline import diff_runs


def test_print_diff_pretty_identical_runs():
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
