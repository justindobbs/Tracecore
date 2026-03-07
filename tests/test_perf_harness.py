from __future__ import annotations

import json
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

    summary = perf_harness.summarise_report(report)

    assert summary["episodes"] == 2
    assert summary["success_count"] == 1
    assert summary["failure_count"] == 1
    assert summary["max_wall_clock_s"] == 2.5
    assert summary["failure_reasons"] == {"TimeoutError: late": 1}


def test_write_perf_artifacts_writes_json_payloads(tmp_path: Path):
    paths = perf_harness.write_perf_artifacts(
        output_dir=tmp_path,
        stamp="20260306T000000Z",
        manifest={"episodes": 24},
        summary={"success_count": 20},
        metrics_rows=[{"task_ref": "filesystem_hidden_config@1", "run_count": 24}],
    )

    assert set(paths) == {"manifest", "summary", "metrics"}
    assert json.loads(paths["manifest"].read_text(encoding="utf-8"))["episodes"] == 24
    assert json.loads(paths["summary"].read_text(encoding="utf-8"))["success_count"] == 20
    assert json.loads(paths["metrics"].read_text(encoding="utf-8"))[0]["run_count"] == 24


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
