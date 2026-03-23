"""Tests for baseline aggregation helpers."""

from __future__ import annotations

import json

import pytest

from agent_bench.runner import baseline
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


def test_load_run_artifact_prefers_path(tmp_path):
    payload = {"run_id": "abc", "success": True}
    path = tmp_path / "run.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = baseline.load_run_artifact(str(path))
    assert loaded == payload


def test_load_run_artifact_falls_back_to_runlog(monkeypatch):
    payload = {"run_id": "abc"}

    def fake_load_run(run_id):
        assert run_id == "abc"
        return payload

    monkeypatch.setattr(baseline, "load_run", fake_load_run)

    loaded = baseline.load_run_artifact("abc")
    assert loaded is payload


def test_diff_runs_reports_summary_and_step_differences():
    run_a = {
        "run_id": "a",
        "agent": "agents/toy_agent.py",
        "task_ref": "filesystem_hidden_config@1",
        "success": True,
        "tool_calls_used": 5,
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
        "tool_calls_used": 6,
        "action_trace": [
            {"step": 1, "action": {"type": "list_dir"}},
            {"step": 2, "action": {"type": "list_dir"}},
        ],
    }

    diff = baseline.diff_runs(run_a, run_b)
    assert diff["summary"]["same_agent"] is True
    assert diff["summary"]["same_success"] is False
    # Only step 2 should differ
    assert len(diff["step_diffs"]) == 1
    assert diff["step_diffs"][0]["step"] == 2
    assert diff["step_diffs"][0]["run_a"]["action"]["type"] == "read_file"
    assert diff["step_diffs"][0]["run_b"]["action"]["type"] == "list_dir"


def test_io_audit_diff_added_removed():
    a = [
        {"type": "fs", "op": "read", "path": "/etc/hosts"},
        {"type": "net", "op": "connect", "host": "example.com"},
    ]
    b = [
        {"type": "fs", "op": "read", "path": "/etc/hosts"},
        {"type": "net", "op": "connect", "host": "api.service"},
        {"type": "fs", "op": "write", "path": "/tmp/out"},
    ]

    delta = baseline._io_audit_diff(a, b)
    assert delta is not None
    assert delta["added"] == [
        {"type": "fs", "op": "write", "path": "/tmp/out"},
        {"type": "net", "op": "connect", "host": "api.service"},
    ]
    assert delta["removed"] == [
        {"type": "net", "op": "connect", "host": "example.com"},
    ]


def test_diff_runs_includes_io_summary_and_step_delta():
    run_a = {
        "run_id": "a",
        "agent": "agents/toy_agent.py",
        "task_ref": "filesystem_hidden_config@1",
        "success": True,
        "tool_calls_used": 2,
        "action_trace": [
            {"step": 1, "action": {"type": "list_dir"}, "io_audit": [{"type": "fs", "op": "list_dir", "path": "/app"}]},
            {"step": 2, "action": {"type": "read_file"}, "io_audit": []},
        ],
    }
    run_b = {
        "run_id": "b",
        "agent": "agents/toy_agent.py",
        "task_ref": "filesystem_hidden_config@1",
        "success": True,
        "tool_calls_used": 2,
        "action_trace": [
            {"step": 1, "action": {"type": "list_dir"}, "io_audit": [{"type": "fs", "op": "list_dir", "path": "/app"}, {"type": "net", "op": "connect", "host": "example.com"}]},
            {"step": 2, "action": {"type": "read_file"}, "io_audit": [{"type": "fs", "op": "read", "path": "/app/config"}]},
        ],
    }

    diff = baseline.diff_runs(run_a, run_b)

    assert diff["summary"]["io_audit"] == {"added": 2, "removed": 0}

    io_steps = [s for s in diff["step_diffs"] if "io_audit_delta" in s]
    assert len(io_steps) == 2
    # Step 1 picks up new net connect
    step1 = next(s for s in io_steps if s["step"] == 1)
    assert step1["io_audit_delta"]["added"] == [{"type": "net", "op": "connect", "host": "example.com"}]
    # Step 2 picks up new read
    step2 = next(s for s in io_steps if s["step"] == 2)
    assert step2["io_audit_delta"]["added"] == [{"type": "fs", "op": "read", "path": "/app/config"}]


def test_export_baseline_persists_rows_and_metadata(monkeypatch, tmp_path):
    rows = [
        {
            "agent": "agents/toy_agent.py",
            "task_ref": "filesystem_hidden_config@1",
            "success_rate": 1.0,
            "avg_steps": 12,
            "avg_tool_calls": 8,
            "runs": 3,
        }
    ]

    monkeypatch.setattr(baseline, "BASELINE_ROOT", tmp_path)

    path = baseline.export_baseline(rows, metadata={"agent_filter": "agents/toy_agent.py"})
    assert path.parent == tmp_path
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["rows"] == rows
    assert payload["metadata"] == {"agent_filter": "agents/toy_agent.py"}
    assert "generated_at" in payload


def test_diff_runs_ignores_volatile_trace_metadata_fields():
    run_a = {
        "run_id": "a",
        "agent": "agents/chain_agent.py",
        "task_ref": "rate_limited_chain@1",
        "success": True,
        "tool_calls_used": 1,
        "wall_clock_elapsed_s": 1.25,
        "action_trace": [
            {
                "step": 1,
                "action": {"type": "get_required_payload", "args": {}},
                "result": {"ok": True, "payload": "abc"},
                "action_ts": "2026-03-01T00:00:00+00:00",
                "budget_after_step": {"steps": 119, "tool_calls": 119},
                "budget_delta": {"steps": 1, "tool_calls": 1},
                "telemetry": {"action_metrics": {"latency_ms": 1.23, "error": None}},
                "io_audit": [],
            }
        ],
    }
    run_b = {
        "run_id": "b",
        "agent": "agents/chain_agent.py",
        "task_ref": "rate_limited_chain@1",
        "success": True,
        "tool_calls_used": 1,
        "wall_clock_elapsed_s": 1.67,
        "action_trace": [
            {
                "step": 1,
                "action": {"type": "get_required_payload", "args": {}},
                "result": {"ok": True, "payload": "abc"},
                "action_ts": "2026-03-01T00:00:01+00:00",
                "budget_after_step": {"steps": 118, "tool_calls": 118},
                "budget_delta": {"steps": 1, "tool_calls": 1},
                "telemetry": {"action_metrics": {"latency_ms": 3.45, "error": None}},
                "io_audit": [],
            }
        ],
    }

    diff = baseline.diff_runs(run_a, run_b)

    assert diff["step_diffs"] == []
    assert diff["summary"]["same_success"] is True
