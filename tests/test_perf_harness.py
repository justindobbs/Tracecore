from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from scripts import perf_harness


def test_build_jobs_repeats_scenario_and_offsets_seed():
    jobs = perf_harness.build_jobs(episodes=6, scenario=[
        {"agent": "agents/a.py", "task_ref": "task_a@1", "seed": 1},
        {"agent": "agents/b.py", "task_ref": "task_b@1", "seed": 10},
    ])

    assert len(jobs) == 6
    assert jobs[0].agent == "agents/a.py"
    assert jobs[1].agent == "agents/b.py"
    assert jobs[2].task_ref == "task_a@1"
    assert jobs[0].seed == 1
    assert jobs[1].seed == 11
    assert jobs[5].seed == 15
    assert jobs[5].metadata == {"episode_index": 5}


def test_build_jobs_rejects_non_positive_episode_count():
    try:
        perf_harness.build_jobs(episodes=0)
    except ValueError as exc:
        assert "episodes must be > 0" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-positive episode count")


def test_summarise_report_aggregates_failures_and_wall_clock():
    jobs = perf_harness.build_jobs(episodes=2, scenario=[
        {"agent": "agents/a.py", "task_ref": "task_a@1", "seed": 1},
    ])
    results = [
        perf_harness.BatchResult(job=jobs[0], result={"success": True}, error=None, wall_clock_s=1.2, success=True),
        perf_harness.BatchResult(job=jobs[1], result=None, error="TimeoutError: late", wall_clock_s=2.5, success=False),
    ]
    report = {"summary": {"total": 2, "passed": 1, "failed": 1}, "results": results}

    original = perf_harness._collect_run_artifact_stats
    perf_harness._collect_run_artifact_stats = lambda run_log_root=None: {
        "root": ".agent_bench/runs",
        "file_count": 2,
        "total_bytes": 400,
        "avg_bytes": 200.0,
    }
    original_samples = perf_harness._collect_system_samples
    perf_harness._collect_system_samples = lambda: {
        "available": False,
        "provider": "psutil",
        "cpu_percent": None,
        "process_rss_bytes": None,
        "system_memory_total_bytes": None,
        "system_memory_available_bytes": None,
    }
    try:
        summary = perf_harness.summarise_report(report)
    finally:
        perf_harness._collect_run_artifact_stats = original
        perf_harness._collect_system_samples = original_samples

    assert summary["episodes"] == 2
    assert summary["success_count"] == 1
    assert summary["failure_count"] == 1
    assert summary["max_wall_clock_s"] == 2.5
    assert summary["failure_reasons"] == {"TimeoutError: late": 1}
    assert summary["run_artifacts"]["file_count"] == 2
    assert summary["run_artifacts"]["total_bytes"] == 400
    assert summary["system_samples"]["available"] is False


def test_collect_run_artifact_stats_reports_sizes(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "a.json").write_text("{}", encoding="utf-8")
    (runs_dir / "b.json").write_text('{"x": 1}', encoding="utf-8")

    stats = perf_harness._collect_run_artifact_stats(runs_dir)

    assert stats["root"] == str(runs_dir)
    assert stats["file_count"] == 2
    assert stats["total_bytes"] == sum(path.stat().st_size for path in runs_dir.glob("*.json"))
    assert stats["avg_bytes"] is not None


def test_collect_run_artifact_stats_handles_missing_root(tmp_path: Path):
    stats = perf_harness._collect_run_artifact_stats(tmp_path / "missing-runs")

    assert stats == {
        "root": str(tmp_path / "missing-runs"),
        "file_count": 0,
        "total_bytes": 0,
        "avg_bytes": None,
    }


def test_collect_system_samples_handles_missing_psutil(monkeypatch):
    original_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "psutil":
            raise ModuleNotFoundError("No module named 'psutil'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    stats = perf_harness._collect_system_samples()

    assert stats == {
        "available": False,
        "provider": "psutil",
        "cpu_percent": None,
        "process_rss_bytes": None,
        "system_memory_total_bytes": None,
        "system_memory_available_bytes": None,
    }


def test_collect_system_samples_uses_psutil_when_available(monkeypatch):
    class _MemoryInfo:
        rss = 123456

    class _Process:
        def __init__(self, pid):
            self.pid = pid

        def memory_info(self):
            return _MemoryInfo()

    fake_psutil = types.SimpleNamespace(
        Process=lambda pid: _Process(pid),
        virtual_memory=lambda: types.SimpleNamespace(total=999999, available=555555),
        cpu_percent=lambda interval=None: 12.5,
    )
    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)

    stats = perf_harness._collect_system_samples()

    assert stats == {
        "available": True,
        "provider": "psutil",
        "cpu_percent": 12.5,
        "process_rss_bytes": 123456,
        "system_memory_total_bytes": 999999,
        "system_memory_available_bytes": 555555,
    }


def test_build_episode_series_returns_chart_ready_rows():
    jobs = perf_harness.build_jobs(episodes=2, scenario=[
        {"agent": "agents/a.py", "task_ref": "task_a@1", "seed": 10},
    ])
    report = {
        "results": [
            perf_harness.BatchResult(job=jobs[0], result={"success": True}, error=None, wall_clock_s=1.2345, success=True),
            perf_harness.BatchResult(job=jobs[1], result=None, error="TimeoutError", wall_clock_s=2.0, success=False),
        ]
    }

    rows = perf_harness.build_episode_series(report)

    assert rows == [
        {
            "episode": 1,
            "episode_index": 0,
            "agent": "agents/a.py",
            "task_ref": "task_a@1",
            "seed": 10,
            "success": True,
            "wall_clock_s": 1.234,
            "error": None,
        },
        {
            "episode": 2,
            "episode_index": 1,
            "agent": "agents/a.py",
            "task_ref": "task_a@1",
            "seed": 11,
            "success": False,
            "wall_clock_s": 2.0,
            "error": "TimeoutError",
        },
    ]


def test_write_perf_artifacts_writes_json_payloads(tmp_path: Path):
    paths = perf_harness.write_perf_artifacts(
        output_dir=tmp_path,
        stamp="20260306T000000Z",
        manifest={"episodes": 24},
        summary={"success_count": 20},
        metrics_rows=[{"task_ref": "filesystem_hidden_config@1", "run_count": 24}],
        series_rows=[{"episode": 1, "wall_clock_s": 0.5}],
    )

    assert set(paths) == {"manifest", "summary", "metrics", "series"}
    assert json.loads(paths["manifest"].read_text(encoding="utf-8"))["episodes"] == 24
    assert json.loads(paths["summary"].read_text(encoding="utf-8"))["success_count"] == 20
    assert json.loads(paths["metrics"].read_text(encoding="utf-8"))[0]["run_count"] == 24
    assert json.loads(paths["series"].read_text(encoding="utf-8"))[0]["episode"] == 1


def test_run_perf_harness_uses_batch_and_metrics(monkeypatch, tmp_path: Path):
    captured = {}

    def fake_run_batch(jobs, *, workers, timeout, strict_spec):
        captured["episodes"] = len(jobs)
        captured["workers"] = workers
        captured["timeout"] = timeout
        captured["strict_spec"] = strict_spec
        return {
            "ok": True,
            "summary": {"total": len(jobs), "passed": len(jobs), "failed": 0},
            "results": [
                perf_harness.BatchResult(job=job, result={"success": True}, error=None, wall_clock_s=0.5, success=True)
                for job in jobs
            ],
        }

    monkeypatch.setattr(perf_harness, "run_batch", fake_run_batch)
    monkeypatch.setattr(
        perf_harness,
        "compute_all_metrics",
        lambda limit: [{"task_ref": "filesystem_hidden_config@1", "agent": "agents/toy_agent.py", "run_count": limit}],
    )
    monkeypatch.setattr(perf_harness, "_timestamp_slug", lambda now=None: "20260306T010203Z")
    monkeypatch.setattr(
        perf_harness,
        "_collect_system_samples",
        lambda: {
            "available": True,
            "provider": "psutil",
            "cpu_percent": 9.5,
            "process_rss_bytes": 1000,
            "system_memory_total_bytes": 2000,
            "system_memory_available_bytes": 1500,
        },
    )

    payload = perf_harness.run_perf_harness(
        episodes=8,
        workers=3,
        timeout=99,
        strict_spec=True,
        output_dir=tmp_path,
    )

    assert payload["ok"] is True
    assert payload["stamp"] == "20260306T010203Z"
    assert captured == {"episodes": 8, "workers": 3, "timeout": 99, "strict_spec": True}
    assert Path(payload["artifacts"]["summary"]).exists()
    assert json.loads(Path(payload["artifacts"]["metrics"]).read_text(encoding="utf-8"))[0]["run_count"] == 8
    manifest = json.loads(Path(payload["artifacts"]["manifest"]).read_text(encoding="utf-8"))
    assert manifest["system_samples"]["available"] is True
    assert manifest["artifact_set"] == ["manifest", "summary", "metrics", "series"]
    assert json.loads(Path(payload["artifacts"]["series"]).read_text(encoding="utf-8"))[0]["episode"] == 1
