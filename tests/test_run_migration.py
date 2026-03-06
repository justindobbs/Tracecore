"""Tests for legacy run artifact migration."""

from __future__ import annotations

import json
from pathlib import Path

from agent_bench.runner.migration import migrate_run_artifact, migrate_run_directory


def _legacy_artifact() -> dict:
    return {
        "run_id": "legacy-run",
        "trace_id": "legacy-run",
        "agent": "agents/toy_agent.py",
        "task_ref": "filesystem_hidden_config@1",
        "task_id": "filesystem_hidden_config",
        "version": 1,
        "seed": 0,
        "success": True,
        "termination_reason": "success",
        "failure_type": None,
        "failure_reason": None,
        "steps_used": 2,
        "tool_calls_used": 2,
        "harness_version": "0.9.0",
        "started_at": "2026-03-01T00:00:00+00:00",
        "completed_at": "2026-03-01T00:00:01+00:00",
        "wall_clock_elapsed_s": 1.0,
        "sandbox": {"filesystem_roots": ["/app"], "network_hosts": []},
        "action_trace": [
            {
                "step": 1,
                "action": {"type": "noop", "args": {}},
                "result": {"ok": True},
                "io_audit": [],
            }
        ],
    }


def test_migrate_run_artifact_backfills_required_fields():
    migrated, changed = migrate_run_artifact(_legacy_artifact())
    assert changed is True
    assert migrated["spec_version"] == "tracecore-spec-v1.0"
    assert migrated["agent_ref"] == migrated["agent"]
    assert migrated["runtime_identity"]["name"] == "tracecore"
    assert migrated["budgets"]["steps"] == 2
    assert migrated["budgets"]["tool_calls"] == 2
    assert migrated["artifact_hash"].startswith("sha256:")
    assert "action_ts" in migrated["action_trace"][0]
    assert "budget_after_step" in migrated["action_trace"][0]
    assert "budget_delta" in migrated["action_trace"][0]


def test_migrate_run_directory_write_updates_files(tmp_path: Path):
    root = tmp_path / ".agent_bench" / "runs"
    root.mkdir(parents=True)
    artifact_path = root / "legacy-run.json"
    artifact_path.write_text(json.dumps(_legacy_artifact()), encoding="utf-8")

    report = migrate_run_directory(root=root, write=True)
    assert report["ok"] is True
    assert report["changed"] == 1

    migrated = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert migrated["spec_version"] == "tracecore-spec-v1.0"
    assert migrated["artifact_hash"].startswith("sha256:")
