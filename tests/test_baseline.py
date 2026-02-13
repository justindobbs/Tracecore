"""Tests for baseline aggregation helpers."""

from __future__ import annotations

from agent_bench.runner.baseline import summarize_runs


def test_summarize_runs_groups_by_agent_task_and_tracks_latest_trace():
    runs = [
        {
            "agent": "agents/toy_agent.py",
            "task_ref": "filesystem_hidden_config@1",
            "success": True,
            "steps_used": 10,
            "tool_calls_used": 5,
            "run_id": "run-1",
            "completed_at": "2025-01-01T00:00:00Z",
            "seed": 1,
        },
        {
            "agent": "agents/toy_agent.py",
            "task_ref": "filesystem_hidden_config@1",
            "success": False,
            "steps_used": 20,
            "tool_calls_used": 8,
            "run_id": "run-2",
            "completed_at": "2025-01-02T00:00:00Z",
            "seed": 2,
        },
        {
            "agent": "agents/rate_limit_agent.py",
            "task_ref": "rate_limited_api@1",
            "success": True,
            "metrics": {"steps_used": 6, "tool_calls_used": 6},
            "run_id": "run-3",
            "completed_at": "2025-02-01T00:00:00Z",
            "seed": 3,
        },
    ]

    rows = summarize_runs(runs)
    rows_by_key = {(
        row["agent"],
        row["task_ref"],
    ): row for row in rows}

    toy_fs = rows_by_key[("agents/toy_agent.py", "filesystem_hidden_config@1")]
    assert toy_fs["runs"] == 2
    assert toy_fs["success_rate"] == 0.5
    assert toy_fs["avg_steps"] == 15
    assert toy_fs["avg_tool_calls"] == 6.5
    assert toy_fs["last_run_id"] == "run-2"
    assert toy_fs["last_success"] is False
    assert toy_fs["last_seed"] == 2

    rate_api = rows_by_key[("agents/rate_limit_agent.py", "rate_limited_api@1")]
    assert rate_api["runs"] == 1
    assert rate_api["success_rate"] == 1.0
    assert rate_api["avg_steps"] == 6
    assert rate_api["avg_tool_calls"] == 6
    assert rate_api["last_run_id"] == "run-3"
    assert rate_api["last_success"] is True
    assert rate_api["last_seed"] == 3


def test_summarize_runs_handles_missing_metrics():
    runs = [
        {
            "agent": "agents/toy_agent.py",
            "task_ref": "filesystem_hidden_config@1",
            "success": False,
            "run_id": "run-1",
            "completed_at": "2025-03-01T00:00:00Z",
        }
    ]

    rows = summarize_runs(runs)
    assert rows[0]["avg_steps"] is None
    assert rows[0]["avg_tool_calls"] is None
