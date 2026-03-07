"""Performance harness for TraceCore Phase 6 scalability checks.

Builds a repeated batch workload using existing runner and metrics surfaces,
executes it with the parallel batch runner, and writes chart-ready JSON
artifacts into ``deliverables/perf/``.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_bench.runner.batch import BatchJob, BatchResult, run_batch
from agent_bench.runner.metrics import compute_all_metrics
from agent_bench.runner.runlog import RUN_LOG_ROOT

DEFAULT_SCENARIO = [
    {"agent": "agents/toy_agent.py", "task_ref": "filesystem_hidden_config@1", "seed": 42},
    {"agent": "agents/rate_limit_agent.py", "task_ref": "rate_limited_api@1", "seed": 11},
    {"agent": "agents/chain_agent.py", "task_ref": "rate_limited_chain@1", "seed": 7},
    {"agent": "agents/ops_triage_agent.py", "task_ref": "log_alert_triage@1", "seed": 21},
]


def _timestamp_slug(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    return current.strftime("%Y%m%dT%H%M%SZ")


def build_jobs(*, episodes: int, scenario: list[dict[str, Any]] | None = None) -> list[BatchJob]:
    scenario_rows = scenario or DEFAULT_SCENARIO
    if episodes <= 0:
        raise ValueError("episodes must be > 0")
    jobs: list[BatchJob] = []
    for idx in range(episodes):
        base = scenario_rows[idx % len(scenario_rows)]
        jobs.append(
            BatchJob(
                agent=str(base["agent"]),
                task_ref=str(base["task_ref"]),
                seed=int(base.get("seed", 0)) + idx,
                metadata={"episode_index": idx},
            )
        )
    return jobs


def summarise_report(report: dict[str, Any]) -> dict[str, Any]:
    results = report.get("results", [])
    wall_times = [float(r.wall_clock_s) for r in results if getattr(r, "wall_clock_s", 0) is not None]
    success_count = sum(1 for r in results if getattr(r, "success", False))
    failure_reasons = Counter()
    for result in results:
        error = getattr(result, "error", None)
        if error:
            failure_reasons[str(error)] += 1
        elif not getattr(result, "success", False):
            failure_reasons["unsuccessful_run"] += 1

    run_artifacts = _collect_run_artifact_stats()
    system_samples = _collect_system_samples()

    return {
        "summary": report.get("summary", {}),
        "episodes": len(results),
        "success_count": success_count,
        "failure_count": len(results) - success_count,
        "max_wall_clock_s": round(max(wall_times), 3) if wall_times else None,
        "failure_reasons": dict(failure_reasons),
        "run_artifacts": run_artifacts,
        "system_samples": system_samples,
    }


def _collect_run_artifact_stats(run_log_root: Path | None = None) -> dict[str, Any]:
    root = run_log_root or RUN_LOG_ROOT
    if not root.exists():
        return {
            "root": str(root),
            "file_count": 0,
            "total_bytes": 0,
            "avg_bytes": None,
        }

    files = list(root.glob("*.json"))
    total_bytes = sum(path.stat().st_size for path in files)
    return {
        "root": str(root),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "avg_bytes": round(total_bytes / len(files), 2) if files else None,
    }


def _collect_system_samples() -> dict[str, Any]:
    try:
        import psutil
    except ModuleNotFoundError:
        return {
            "available": False,
            "provider": "psutil",
            "cpu_percent": None,
            "process_rss_bytes": None,
            "system_memory_total_bytes": None,
            "system_memory_available_bytes": None,
        }

    process = psutil.Process(os.getpid())
    memory = psutil.virtual_memory()
    return {
        "available": True,
        "provider": "psutil",
        "cpu_percent": psutil.cpu_percent(interval=None),
        "process_rss_bytes": int(process.memory_info().rss),
        "system_memory_total_bytes": int(memory.total),
        "system_memory_available_bytes": int(memory.available),
    }


def write_perf_artifacts(
    *,
    output_dir: Path,
    stamp: str,
    manifest: dict[str, Any],
    summary: dict[str, Any],
    metrics_rows: list[dict[str, Any]],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / f"perf-manifest-{stamp}.json"
    summary_path = output_dir / f"perf-summary-{stamp}.json"
    metrics_path = output_dir / f"perf-metrics-{stamp}.json"

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    metrics_path.write_text(json.dumps(metrics_rows, indent=2), encoding="utf-8")

    return {
        "manifest": manifest_path,
        "summary": summary_path,
        "metrics": metrics_path,
    }


def run_perf_harness(
    *,
    episodes: int,
    workers: int,
    timeout: int,
    strict_spec: bool,
    output_dir: Path,
) -> dict[str, Any]:
    jobs = build_jobs(episodes=episodes)
    report = run_batch(jobs, workers=workers, timeout=timeout, strict_spec=strict_spec)
    stamp = _timestamp_slug()
    metrics_rows = compute_all_metrics(limit=max(episodes, 1))
    summary = summarise_report(report)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "episodes": episodes,
        "workers": workers,
        "timeout": timeout,
        "strict_spec": strict_spec,
        "scenario": DEFAULT_SCENARIO,
        "system_samples": summary.get("system_samples", {}),
    }
    artifact_paths = write_perf_artifacts(
        output_dir=output_dir,
        stamp=stamp,
        manifest=manifest,
        summary=summary,
        metrics_rows=metrics_rows,
    )
    return {
        "ok": report.get("ok", False),
        "stamp": stamp,
        "artifacts": {name: str(path) for name, path in artifact_paths.items()},
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a configurable TraceCore performance harness.")
    parser.add_argument("--episodes", type=int, default=24, help="Number of batch episodes to run (default: 24)")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers for run_batch (default: 4)")
    parser.add_argument("--timeout", type=int, default=180, help="Per-job timeout in seconds (default: 180)")
    parser.add_argument(
        "--output-dir",
        default="deliverables/perf",
        help="Directory for perf artifacts (default: deliverables/perf)",
    )
    parser.add_argument("--strict-spec", action="store_true", help="Enable strict-spec validation during batch runs")
    args = parser.parse_args()

    payload = run_perf_harness(
        episodes=args.episodes,
        workers=args.workers,
        timeout=args.timeout,
        strict_spec=args.strict_spec,
        output_dir=Path(args.output_dir),
    )
    print(json.dumps(payload, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
