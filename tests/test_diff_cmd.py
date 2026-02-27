"""Tests for agent-bench diff subcommand and underlying diff_runs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_bench.runner.baseline import _compare_exit_code, diff_runs


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_run(
    *,
    run_id: str = "aaa",
    agent: str = "agents/toy.py",
    task_ref: str = "task@1",
    success: bool = True,
    termination_reason: str = "success",
    failure_type: str | None = None,
    steps_used: int = 3,
    tool_calls_used: int = 3,
    seed: int = 0,
    trace: list[dict] | None = None,
) -> dict:
    return {
        "run_id": run_id,
        "agent": agent,
        "task_ref": task_ref,
        "success": success,
        "termination_reason": termination_reason,
        "failure_type": failure_type,
        "steps_used": steps_used,
        "tool_calls_used": tool_calls_used,
        "seed": seed,
        "started_at": "2026-02-20T19:00:00+00:00",
        "completed_at": "2026-02-20T19:00:01+00:00",
        "harness_version": "0.9.7",
        "action_trace": trace or [],
    }


def _make_trace_entry(step: int, action_type: str = "list_dir") -> dict:
    return {
        "step": step,
        "action_ts": "2026-02-20T19:00:00+00:00",
        "action": {"type": action_type, "args": {}},
        "result": {"ok": True},
        "io_audit": [],
        "budget_after_step": {"steps": 10 - step, "tool_calls": 10 - step},
        "budget_delta": {"steps": 1, "tool_calls": 1},
    }


# ---------------------------------------------------------------------------
# diff_runs — structure and exit codes
# ---------------------------------------------------------------------------

class TestDiffRuns:
    def test_identical_runs_no_diffs(self):
        run = _make_run(trace=[_make_trace_entry(1), _make_trace_entry(2)])
        diff = diff_runs(run, run)
        assert diff["step_diffs"] == []
        assert diff["summary"]["same_success"] is True
        assert diff["summary"]["same_agent"] is True
        assert diff["summary"]["same_task"] is True

    def test_action_change_detected(self):
        trace_a = [_make_trace_entry(1, "list_dir")]
        trace_b = [_make_trace_entry(1, "read_file")]
        run_a = _make_run(trace=trace_a)
        run_b = _make_run(trace=trace_b)
        diff = diff_runs(run_a, run_b)
        assert len(diff["step_diffs"]) == 1
        assert diff["step_diffs"][0]["step"] == 1

    def test_different_trace_lengths(self):
        run_a = _make_run(trace=[_make_trace_entry(1), _make_trace_entry(2)])
        run_b = _make_run(trace=[_make_trace_entry(1)])
        diff = diff_runs(run_a, run_b)
        assert len(diff["step_diffs"]) >= 1

    def test_different_agents_flagged(self):
        run_a = _make_run(agent="agents/a.py")
        run_b = _make_run(agent="agents/b.py")
        diff = diff_runs(run_a, run_b)
        assert diff["summary"]["same_agent"] is False

    def test_different_tasks_flagged(self):
        run_a = _make_run(task_ref="task_a@1")
        run_b = _make_run(task_ref="task_b@1")
        diff = diff_runs(run_a, run_b)
        assert diff["summary"]["same_task"] is False

    def test_success_mismatch_flagged(self):
        run_a = _make_run(success=True)
        run_b = _make_run(success=False, failure_type="logic_failure", termination_reason="logic_failure")
        diff = diff_runs(run_a, run_b)
        assert diff["summary"]["same_success"] is False

    def test_run_summary_fields(self):
        run = _make_run(failure_type="budget_exhausted", termination_reason="steps_exhausted", success=False)
        diff = diff_runs(run, run)
        assert diff["run_a"]["failure_type"] == "budget_exhausted"
        assert diff["run_a"]["termination_reason"] == "steps_exhausted"

    def test_io_audit_delta_counted(self):
        entry_a = _make_trace_entry(1)
        entry_b = dict(_make_trace_entry(1))
        entry_b["io_audit"] = [{"type": "fs", "op": "read", "path": "/app/config"}]
        run_a = _make_run(trace=[entry_a])
        run_b = _make_run(trace=[entry_b])
        diff = diff_runs(run_a, run_b)
        assert diff["summary"]["io_audit"]["added"] >= 1


class TestCompareExitCode:
    def test_identical_is_zero(self):
        run = _make_run()
        diff = diff_runs(run, run)
        assert _compare_exit_code(diff) == 0

    def test_step_diffs_is_one(self):
        run_a = _make_run(trace=[_make_trace_entry(1, "list_dir")])
        run_b = _make_run(trace=[_make_trace_entry(1, "read_file")])
        diff = diff_runs(run_a, run_b)
        assert _compare_exit_code(diff) == 1

    def test_incompatible_agents_is_two(self):
        run_a = _make_run(agent="agents/a.py")
        run_b = _make_run(agent="agents/b.py")
        diff = diff_runs(run_a, run_b)
        assert _compare_exit_code(diff) == 2

    def test_success_mismatch_is_one(self):
        run_a = _make_run(success=True)
        run_b = _make_run(success=False)
        diff = diff_runs(run_a, run_b)
        assert _compare_exit_code(diff) == 1

    def test_budget_drift_is_one(self):
        run_a = _make_run(steps_used=3, tool_calls_used=3)
        run_b = _make_run(steps_used=5, tool_calls_used=3)
        diff = diff_runs(run_a, run_b)
        assert _compare_exit_code(diff) == 1


# ---------------------------------------------------------------------------
# _cmd_diff via CLI parser — JSON output path
# ---------------------------------------------------------------------------

class TestCmdDiffJson:
    def _make_run_file(self, tmp_path: Path, name: str, **kwargs) -> Path:
        p = tmp_path / f"{name}.json"
        p.write_text(json.dumps(_make_run(**kwargs)), encoding="utf-8")
        return p

    def test_json_output_identical(self, tmp_path: Path, capsys):
        from agent_bench.cli import build_parser
        run_a = self._make_run_file(tmp_path, "a")
        run_b = self._make_run_file(tmp_path, "b")
        parser = build_parser()
        args = parser.parse_args(["diff", str(run_a), str(run_b), "--format", "json"])
        rc = args.func(args)
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert "step_diffs" in payload
        assert "summary" in payload
        assert rc == 0

    def test_json_output_different(self, tmp_path: Path, capsys):
        from agent_bench.cli import build_parser
        run_a = self._make_run_file(
            tmp_path, "a",
            trace=[_make_trace_entry(1, "list_dir")]
        )
        run_b = self._make_run_file(
            tmp_path, "b",
            trace=[_make_trace_entry(1, "read_file")]
        )
        parser = build_parser()
        args = parser.parse_args(["diff", str(run_a), str(run_b), "--format", "json"])
        rc = args.func(args)
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert len(payload["step_diffs"]) > 0
        assert rc == 1

    def test_text_output_contains_status(self, tmp_path: Path, capsys):
        from agent_bench.cli import build_parser
        run_a = self._make_run_file(tmp_path, "a")
        run_b = self._make_run_file(tmp_path, "b")
        parser = build_parser()
        args = parser.parse_args(["diff", str(run_a), str(run_b), "--format", "text"])
        args.func(args)
        captured = capsys.readouterr()
        assert "identical" in captured.out.lower() or "different" in captured.out.lower()

    def test_export_otlp_writes_files(self, tmp_path: Path, capsys):
        from agent_bench.cli import build_parser
        run_a = self._make_run_file(tmp_path, "a", run_id="a" * 32)
        run_b = self._make_run_file(tmp_path, "b", run_id="b" * 32)
        prefix = str(tmp_path / "diff_out")
        parser = build_parser()
        args = parser.parse_args([
            "diff", str(run_a), str(run_b),
            "--format", "json",
            "--export-otlp", prefix,
        ])
        args.func(args)
        assert Path(prefix).with_suffix(".run_a.otlp.json").exists()
        assert Path(prefix).with_suffix(".run_b.otlp.json").exists()

    def test_no_taxonomy_flag_accepted(self, tmp_path: Path, capsys):
        from agent_bench.cli import build_parser
        run_a = self._make_run_file(tmp_path, "a")
        run_b = self._make_run_file(tmp_path, "b")
        parser = build_parser()
        args = parser.parse_args([
            "diff", str(run_a), str(run_b),
            "--format", "json",
            "--no-taxonomy",
        ])
        rc = args.func(args)
        assert rc == 0
