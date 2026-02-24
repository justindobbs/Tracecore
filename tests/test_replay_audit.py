"""Replay audit enforcement tests."""

from __future__ import annotations

from pathlib import Path

from agent_bench.runner.bundle import write_bundle
from agent_bench.runner.replay import check_replay


def _base_result() -> dict:
    return {
        "run_id": "run123",
        "trace_id": "run123",
        "agent": "agents/stub.py",
        "task_ref": "stub_task@1",
        "task_id": "stub_task",
        "version": 1,
        "seed": 0,
        "harness_version": "0.0.0",
        "started_at": "2026-02-22T00:00:00+00:00",
        "completed_at": "2026-02-22T00:00:01+00:00",
        "success": True,
        "termination_reason": "success",
        "failure_type": None,
        "failure_reason": None,
        "steps_used": 1,
        "tool_calls_used": 1,
        "metrics": {"steps_used": 1, "tool_calls_used": 1},
        "action_trace": [
            {
                "step": 1,
                "action_ts": "2026-02-22T00:00:00+00:00",
                "observation": {},
                "action": {"type": "noop", "args": {}},
                "result": {"ok": True},
                "io_audit": [],
                "budget_after_step": {"steps": 0, "tool_calls": 0},
                "budget_delta": {"steps": 1, "tool_calls": 1},
            }
        ],
        "sandbox": {"filesystem_roots": ["/app"], "network_hosts": ["example.com"]},
    }


def test_check_replay_io_audit_mismatch(tmp_path: Path) -> None:
    baseline = _base_result()
    bundle_dir = write_bundle(baseline, dest=tmp_path)

    fresh = _base_result()
    fresh["action_trace"][0]["io_audit"] = [{"type": "fs", "path": "/app/a"}]

    report = check_replay(bundle_dir, fresh)
    assert report["ok"] is False
    assert any("io_audit mismatch" in err for err in report["errors"])


def test_check_replay_io_audit_added_removed(tmp_path: Path) -> None:
    baseline = _base_result()
    baseline["action_trace"][0]["io_audit"] = [
        {"type": "fs", "path": "/app/a"},
    ]
    bundle_dir = write_bundle(baseline, dest=tmp_path)

    fresh = _base_result()
    fresh["action_trace"][0]["io_audit"] = [
        {"type": "fs", "path": "/app/a"},
        {"type": "net", "host": "example.com"},
    ]

    report = check_replay(bundle_dir, fresh)
    assert report["ok"] is False
    assert any("io_audit mismatch" in err for err in report["errors"])


def test_check_replay_sandbox_violation(tmp_path: Path) -> None:
    baseline = _base_result()
    baseline["action_trace"][0]["io_audit"] = [
        {"type": "fs", "path": "/root/secret"},
        {"type": "net", "host": "bad.com"},
    ]
    bundle_dir = write_bundle(baseline, dest=tmp_path)

    fresh = _base_result()
    fresh["action_trace"][0]["io_audit"] = [
        {"type": "fs", "path": "/root/secret"},
        {"type": "net", "host": "bad.com"},
    ]

    report = check_replay(bundle_dir, fresh)
    assert report["ok"] is False
    assert any("fs audit outside allowlist" in err for err in report["errors"])


def test_check_replay_sandbox_mismatch(tmp_path: Path) -> None:
    baseline = _base_result()
    bundle_dir = write_bundle(baseline, dest=tmp_path)

    fresh = _base_result()
    fresh["sandbox"] = {"filesystem_roots": ["/other"], "network_hosts": ["example.com"]}

    report = check_replay(bundle_dir, fresh)
    assert report["ok"] is False
    assert any("sandbox mismatch" in err for err in report["errors"])
