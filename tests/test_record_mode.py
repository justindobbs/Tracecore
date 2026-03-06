"""Tests for --record mode and check_record determinism verification."""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agent_bench.runner.bundle import write_bundle
from agent_bench.runner.replay import check_record, check_strict


# ---------------------------------------------------------------------------
# check_record unit tests (no CLI, no disk)
# ---------------------------------------------------------------------------

def _make_run(success: bool, termination: str, failure_type: str | None, trace: list[dict]) -> dict:
    return {
        "success": success,
        "termination_reason": termination,
        "failure_type": failure_type,
        "action_trace": trace,
        "steps_used": len(trace),
        "tool_calls_used": len(trace),
        "sandbox": {"filesystem_roots": ["/app"], "network_hosts": ["example.com"]},
    }


def _step(n: int, action_type: str = "noop", result: dict | None = None, io_audit: list[dict] | None = None) -> dict:
    return {
        "step": n,
        "action": {"type": action_type, "args": {}},
        "result": result or {"ok": True},
        "io_audit": io_audit or [],
    }


def test_check_record_identical_runs_ok():
    trace = [_step(1), _step(2)]
    run_a = _make_run(True, "success", None, trace)
    run_b = _make_run(True, "success", None, trace)
    report = check_record(run_a, run_b)
    assert report["ok"] is True
    assert report["errors"] == []
    assert report["mode"] == "record"


def test_check_record_success_mismatch():
    run_a = _make_run(True, "success", None, [_step(1)])
    run_b = _make_run(False, "steps_exhausted", "budget_exhausted", [_step(1)])
    report = check_record(run_a, run_b)
    assert report["ok"] is False
    assert any("success mismatch" in e for e in report["errors"])


def test_check_record_termination_reason_mismatch():
    run_a = _make_run(False, "steps_exhausted", "budget_exhausted", [_step(1)])
    run_b = _make_run(False, "tool_calls_exhausted", "budget_exhausted", [_step(1)])
    report = check_record(run_a, run_b)
    assert report["ok"] is False
    assert any("termination_reason mismatch" in e for e in report["errors"])


def test_check_record_failure_type_mismatch():
    run_a = _make_run(False, "sandbox_violation", "sandbox_violation", [_step(1)])
    run_b = _make_run(False, "logic_failure", "logic_failure", [_step(1)])
    report = check_record(run_a, run_b)
    assert report["ok"] is False
    assert any("failure_type mismatch" in e for e in report["errors"])


def test_check_record_step_count_mismatch():
    run_a = _make_run(True, "success", None, [_step(1), _step(2)])
    run_b = _make_run(True, "success", None, [_step(1)])
    report = check_record(run_a, run_b)
    assert report["ok"] is False
    assert any("step count mismatch" in e for e in report["errors"])


def test_check_record_action_mismatch():
    run_a = _make_run(True, "success", None, [_step(1, "noop")])
    run_b = _make_run(True, "success", None, [_step(1, "list_dir")])
    report = check_record(run_a, run_b)
    assert report["ok"] is False
    assert any("action mismatch" in e for e in report["errors"])


def test_check_record_result_mismatch():
    run_a = _make_run(True, "success", None, [_step(1, result={"ok": True, "value": "A"})])
    run_b = _make_run(True, "success", None, [_step(1, result={"ok": True, "value": "B"})])
    report = check_record(run_a, run_b)
    assert report["ok"] is False
    assert any("result mismatch" in e for e in report["errors"])


def test_check_record_io_audit_mismatch():
    run_a = _make_run(True, "success", None, [_step(1, io_audit=[{"type": "fs", "path": "/app/a"}])])
    run_b = _make_run(True, "success", None, [_step(1, io_audit=[])])
    report = check_record(run_a, run_b)
    assert report["ok"] is False
    assert any("io_audit mismatch" in e for e in report["errors"])


def test_check_record_missing_sandbox_rejected():
    run_a = _make_run(True, "success", None, [_step(1)])
    run_b = _make_run(True, "success", None, [_step(1)])
    run_a.pop("sandbox", None)
    report = check_record(run_a, run_b)
    assert report["ok"] is False
    assert any("missing sandbox" in e for e in report["errors"])


def test_check_record_empty_traces_ok():
    run_a = _make_run(False, "steps_exhausted", "budget_exhausted", [])
    run_b = _make_run(False, "steps_exhausted", "budget_exhausted", [])
    report = check_record(run_a, run_b)
    assert report["ok"] is True


def test_check_strict_steps_used_exceeded_baseline(tmp_path):
    baseline = {
        "run_id": "baseline_run",
        "trace_id": "baseline_run",
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
        "action_trace": [_step(1)],
        "sandbox": {"filesystem_roots": ["/app"], "network_hosts": ["example.com"]},
    }
    bundle_dir = write_bundle(baseline, dest=tmp_path)

    fresh = {
        **baseline,
        "run_id": "fresh_run",
        "trace_id": "fresh_run",
        "steps_used": 2,
    }

    report = check_strict(bundle_dir, fresh)
    assert report["ok"] is False
    assert report["mode"] == "strict"
    assert any("steps_used exceeded baseline" in e for e in report["errors"])


def test_check_strict_tool_calls_used_exceeded_baseline(tmp_path):
    baseline = {
        "run_id": "baseline_run",
        "trace_id": "baseline_run",
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
        "action_trace": [_step(1)],
        "sandbox": {"filesystem_roots": ["/app"], "network_hosts": ["example.com"]},
    }
    bundle_dir = write_bundle(baseline, dest=tmp_path)

    fresh = {
        **baseline,
        "run_id": "fresh_run",
        "trace_id": "fresh_run",
        "tool_calls_used": 2,
    }

    report = check_strict(bundle_dir, fresh)
    assert report["ok"] is False
    assert report["mode"] == "strict"
    assert any("tool_calls_used exceeded baseline" in e for e in report["errors"])


# ---------------------------------------------------------------------------
# _cmd_run --record integration tests (CLI layer, mocked runner + disk)
# ---------------------------------------------------------------------------

def _make_task(success: bool) -> dict:
    def _setup(seed, env):
        pass

    actions_mod = SimpleNamespace(
        set_env=lambda env: None,
        noop=lambda: {"ok": True},
    )
    validate_mod = SimpleNamespace(validate=lambda env: {"ok": success})

    return {
        "id": "stub_task",
        "suite": "test",
        "version": 1,
        "description": "Stub task for record mode tests.",
        "default_budget": {"steps": 10, "tool_calls": 10},
        "deterministic": True,
        "sandbox": {"filesystem_roots": ["/app"], "network_hosts": []},
        "setup": SimpleNamespace(setup=_setup),
        "actions": actions_mod,
        "validate": validate_mod,
    }


class _DeterministicAgent:
    def reset(self, task_spec):
        pass

    def observe(self, obs):
        pass

    def act(self):
        return {"type": "noop", "args": {}}


class _NonDeterministicAgent:
    """Returns a different result key on each call to simulate non-determinism."""

    def __init__(self):
        self._call = 0

    def reset(self, task_spec):
        pass

    def observe(self, obs):
        pass

    def act(self):
        self._call += 1
        return {"type": "noop", "args": {"call": self._call}}


def _run_record(agent, task, tmp_path):
    """Run _cmd_run with --record using mocked runner and a temp baseline dir."""
    import argparse
    from agent_bench.cli import _cmd_run
    from agent_bench.runner import bundle as bundle_mod

    args = argparse.Namespace(
        agent="stub_agent.py",
        task="stub_task@1",
        seed=0,
        replay=None,
        replay_bundle=None,
        strict=False,
        record=True,
        timeout=None,
        _config=None,
    )

    with (
        patch("agent_bench.runner.runner.load_task", return_value=task),
        patch("agent_bench.runner.runner.load_agent", return_value=agent),
        patch("agent_bench.cli.persist_run"),
        patch.object(bundle_mod, "BASELINE_ROOT", tmp_path),
    ):
        return _cmd_run(args)


def test_record_deterministic_agent_seals_bundle(tmp_path):
    task = _make_task(success=True)
    exit_code = _run_record(_DeterministicAgent(), task, tmp_path)
    assert exit_code == 0
    bundles = list(tmp_path.iterdir())
    assert len(bundles) == 1
    bundle_dir = bundles[0]
    assert (bundle_dir / "manifest.json").exists()
    assert (bundle_dir / "tool_calls.jsonl").exists()
    assert (bundle_dir / "validator.json").exists()
    assert (bundle_dir / "integrity.sha256").exists()


def test_record_non_deterministic_agent_rejects_and_deletes_bundle(tmp_path):
    task = _make_task(success=True)
    exit_code = _run_record(_NonDeterministicAgent(), task, tmp_path)
    assert exit_code == 1
    assert list(tmp_path.iterdir()) == []


def test_record_failed_run_rejected(tmp_path):
    task = _make_task(success=False)
    exit_code = _run_record(_DeterministicAgent(), task, tmp_path)
    assert exit_code == 1
    assert list(tmp_path.iterdir()) == []
