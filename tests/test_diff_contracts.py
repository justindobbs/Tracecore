"""Regression tests for the Trace Diff CLI output schema.

Verifies that diff_runs() always returns the expected top-level keys,
taxonomy block, budget_delta block, and that the _cmd_diff handler
produces valid JSON with --format json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from agent_bench.runner.baseline import diff_runs, load_run_artifact


# ---------------------------------------------------------------------------
# Minimal synthetic run artifacts for unit testing
# ---------------------------------------------------------------------------

def _make_run(
    *,
    run_id: str = "run_a",
    agent: str = "agents/toy_agent.py",
    task_ref: str = "filesystem_hidden_config@1",
    success: bool = True,
    steps: int = 3,
    tool_calls: int = 5,
    failure_type: str | None = None,
    termination_reason: str = "success",
    wall_clock_s: float = 1.0,
    seed: int = 0,
) -> dict:
    trace = [
        {"step": i + 1, "action": {"type": "read_file", "args": {}}, "result": {"ok": True}}
        for i in range(steps)
    ]
    return {
        "run_id": run_id,
        "agent": agent,
        "task_ref": task_ref,
        "success": success,
        "steps_used": steps,
        "tool_calls_used": tool_calls,
        "failure_type": failure_type,
        "termination_reason": termination_reason,
        "wall_clock_elapsed_s": wall_clock_s,
        "seed": seed,
        "action_trace": trace,
    }


# ---------------------------------------------------------------------------
# Schema / shape tests
# ---------------------------------------------------------------------------

def test_diff_runs_top_level_keys():
    a = _make_run(run_id="run_a")
    b = _make_run(run_id="run_b")
    result = diff_runs(a, b)
    assert "run_a" in result
    assert "run_b" in result
    assert "summary" in result
    assert "taxonomy" in result
    assert "budget_delta" in result
    assert "step_diffs" in result


def test_diff_runs_taxonomy_block_keys():
    a = _make_run(run_id="run_a", failure_type=None, termination_reason="success")
    b = _make_run(run_id="run_b", failure_type="budget_exceeded", termination_reason="budget_exceeded")
    result = diff_runs(a, b)
    tax = result["taxonomy"]
    assert "same_failure_type" in tax
    assert "same_termination_reason" in tax
    assert "run_a" in tax
    assert "run_b" in tax
    assert tax["same_failure_type"] is False
    assert tax["same_termination_reason"] is False
    assert tax["run_a"]["failure_type"] is None
    assert tax["run_b"]["failure_type"] == "budget_exceeded"


def test_diff_runs_taxonomy_identical():
    a = _make_run(run_id="run_a", failure_type=None, termination_reason="success")
    b = _make_run(run_id="run_b", failure_type=None, termination_reason="success")
    result = diff_runs(a, b)
    tax = result["taxonomy"]
    assert tax["same_failure_type"] is True
    assert tax["same_termination_reason"] is True


def test_diff_runs_budget_delta_block_keys():
    a = _make_run(run_id="run_a", steps=3, tool_calls=5, wall_clock_s=1.0)
    b = _make_run(run_id="run_b", steps=5, tool_calls=8, wall_clock_s=2.5)
    result = diff_runs(a, b)
    bd = result["budget_delta"]
    assert "steps" in bd
    assert "tool_calls" in bd
    assert "wall_clock_s" in bd
    assert bd["steps"] == 2
    assert bd["tool_calls"] == 3
    assert abs(bd["wall_clock_s"] - 1.5) < 0.01


def test_diff_runs_budget_delta_negative():
    a = _make_run(run_id="run_a", steps=5, tool_calls=8, wall_clock_s=3.0)
    b = _make_run(run_id="run_b", steps=2, tool_calls=3, wall_clock_s=1.0)
    result = diff_runs(a, b)
    bd = result["budget_delta"]
    assert bd["steps"] == -3
    assert bd["tool_calls"] == -5


def test_diff_runs_step_diffs_identical_runs():
    a = _make_run(run_id="run_a", steps=3)
    b = _make_run(run_id="run_b", steps=3)
    result = diff_runs(a, b)
    assert result["step_diffs"] == []


def test_diff_runs_step_diffs_different_length():
    a = _make_run(run_id="run_a", steps=2)
    b = _make_run(run_id="run_b", steps=4)
    result = diff_runs(a, b)
    assert len(result["step_diffs"]) > 0


def test_diff_runs_run_summary_fields():
    a = _make_run(run_id="run_a", agent="agents/toy_agent.py", task_ref="filesystem_hidden_config@1", success=True)
    b = _make_run(run_id="run_b", agent="agents/toy_agent.py", task_ref="filesystem_hidden_config@1", success=False)
    result = diff_runs(a, b)
    assert result["run_a"]["run_id"] == "run_a"
    assert result["run_b"]["run_id"] == "run_b"
    assert result["run_a"]["success"] is True
    assert result["run_b"]["success"] is False


def test_diff_runs_same_agent_same_task_flags():
    a = _make_run(run_id="run_a", agent="agents/toy_agent.py", task_ref="filesystem_hidden_config@1")
    b = _make_run(run_id="run_b", agent="agents/toy_agent.py", task_ref="filesystem_hidden_config@1")
    result = diff_runs(a, b)
    assert result["summary"]["same_agent"] is True
    assert result["summary"]["same_task"] is True


def test_diff_runs_different_agent_flags():
    a = _make_run(run_id="run_a", agent="agents/toy_agent.py")
    b = _make_run(run_id="run_b", agent="agents/other_agent.py")
    result = diff_runs(a, b)
    assert result["summary"]["same_agent"] is False


# ---------------------------------------------------------------------------
# JSON serialisability
# ---------------------------------------------------------------------------

def test_diff_runs_output_is_json_serialisable():
    a = _make_run(run_id="run_a")
    b = _make_run(run_id="run_b")
    result = diff_runs(a, b)
    serialised = json.dumps(result)
    parsed = json.loads(serialised)
    assert parsed["taxonomy"]["same_failure_type"] is True


# ---------------------------------------------------------------------------
# Performance benchmark: <10s on <=1k-step traces
# ---------------------------------------------------------------------------

def test_diff_performance_1k_steps():
    """diff_runs on two 1000-step traces must complete in under 10 seconds."""
    import time

    def _make_large_run(run_id: str, steps: int = 1000) -> dict:
        trace = [
            {
                "step": i + 1,
                "action": {"type": "read_file", "args": {"path": f"/tmp/file_{i}.txt"}},
                "result": {"ok": True, "content": f"data_{i}"},
                "io_audit": [{"type": "fs", "op": "read", "path": f"/tmp/file_{i}.txt"}],
            }
            for i in range(steps)
        ]
        return {
            "run_id": run_id,
            "agent": "agents/toy_agent.py",
            "task_ref": "filesystem_hidden_config@1",
            "success": True,
            "steps_used": steps,
            "tool_calls_used": steps,
            "failure_type": None,
            "termination_reason": "success",
            "wall_clock_elapsed_s": 5.0,
            "seed": 0,
            "action_trace": trace,
        }

    a = _make_large_run("run_a_large", steps=1000)
    b = _make_large_run("run_b_large", steps=1000)

    t0 = time.monotonic()
    result = diff_runs(a, b)
    elapsed = time.monotonic() - t0

    assert elapsed < 10.0, f"diff_runs took {elapsed:.2f}s on 1k-step trace, expected <10s"
    assert "taxonomy" in result
    assert "budget_delta" in result


# ---------------------------------------------------------------------------
# CLI handler smoke test
# ---------------------------------------------------------------------------

def test_cmd_diff_json_format(tmp_path, monkeypatch, capsys):
    """_cmd_diff with --format json must print valid JSON including taxonomy."""
    import argparse
    from agent_bench.cli import _cmd_diff

    run_a = _make_run(run_id="run_a")
    run_b = _make_run(run_id="run_b", steps=5)

    path_a = tmp_path / "run_a.json"
    path_b = tmp_path / "run_b.json"
    path_a.write_text(json.dumps(run_a))
    path_b.write_text(json.dumps(run_b))

    args = argparse.Namespace(run_a=str(path_a), run_b=str(path_b), format="json")
    exit_code = _cmd_diff(args)

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert "taxonomy" in output
    assert "budget_delta" in output
    assert "_elapsed_s" in output
    assert isinstance(exit_code, int)


def test_cmd_diff_bundle_export_to_directory(tmp_path, capsys):
    import argparse

    from agent_bench.cli import _cmd_diff

    run_a = _make_run(run_id="run_a")
    run_b = _make_run(run_id="run_b", steps=5)

    path_a = tmp_path / "run_a.json"
    path_b = tmp_path / "run_b.json"
    export_dir = tmp_path / "compare_bundle"
    path_a.write_text(json.dumps(run_a), encoding="utf-8")
    path_b.write_text(json.dumps(run_b), encoding="utf-8")

    args = argparse.Namespace(
        run_a=str(path_a),
        run_b=str(path_b),
        format="json",
        bundle=str(export_dir),
    )
    exit_code = _cmd_diff(args)

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    export_path = export_dir / "comparison-bundle.json"
    assert exit_code == 1
    assert output["bundle_export_path"] == str(export_path)
    assert len(output["bundle_export_sha256"]) == 64
    assert export_path.exists()

    bundle_payload = json.loads(export_path.read_text(encoding="utf-8"))
    assert bundle_payload["kind"] == "tracecore_comparison_bundle"
    assert bundle_payload["version"] == 1
    assert bundle_payload["run_a_ref"] == str(path_a)
    assert bundle_payload["run_b_ref"] == str(path_b)
    assert bundle_payload["diff"]["budget_delta"]["steps"] == 2
    assert bundle_payload["sha256"] == output["bundle_export_sha256"]


def test_cmd_diff_bundle_export_to_json_path(tmp_path, capsys):
    import argparse

    from agent_bench.cli import _cmd_diff

    run_a = _make_run(run_id="run_a")
    run_b = _make_run(run_id="run_b", steps=5)

    path_a = tmp_path / "run_a.json"
    path_b = tmp_path / "run_b.json"
    export_path = tmp_path / "exports" / "custom-comparison.json"
    path_a.write_text(json.dumps(run_a), encoding="utf-8")
    path_b.write_text(json.dumps(run_b), encoding="utf-8")

    args = argparse.Namespace(
        run_a=str(path_a),
        run_b=str(path_b),
        format="json",
        bundle=str(export_path),
    )
    exit_code = _cmd_diff(args)

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 1
    assert output["bundle_export_path"] == str(export_path)
    assert export_path.exists()

    bundle_payload = json.loads(export_path.read_text(encoding="utf-8"))
    assert bundle_payload["run_a"]["run_id"] == "run_a"
    assert bundle_payload["run_b"]["run_id"] == "run_b"
    assert bundle_payload["sha256"] == output["bundle_export_sha256"]
