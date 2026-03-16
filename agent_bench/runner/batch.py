"""Parallel batch episode execution for TraceCore.

Runs multiple (agent, task_ref, seed) triples concurrently under a bounded
process pool, collects results, and returns an aggregate summary.

Usage::

    from agent_bench.runner.batch import run_batch, BatchJob

    jobs = [
        BatchJob(agent="agents/toy_agent.py", task_ref="filesystem_hidden_config@1", seed=42),
        BatchJob(agent="agents/toy_agent.py", task_ref="rate_limited_api@1", seed=0),
    ]
    summary = run_batch(jobs, workers=4, timeout=120, strict_spec=False)
"""

from __future__ import annotations

import concurrent.futures
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BatchJob:
    agent: str
    task_ref: str
    seed: int = 0
    timeout: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchResult:
    job: BatchJob
    result: dict | None
    error: str | None
    wall_clock_s: float
    success: bool


def _run_job(job_dict: dict) -> dict:
    """Worker entry point (runs in a subprocess via ProcessPoolExecutor)."""
    import sys
    repo_root = job_dict.get("_repo_root")
    if repo_root and repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from agent_bench.runner.isolation import run_isolated
    from agent_bench.runner.runner import run
    from agent_bench.runner.runlog import persist_run

    agent = job_dict["agent"]
    task_ref = job_dict["task_ref"]
    seed = job_dict["seed"]
    timeout = job_dict.get("timeout")

    start = time.monotonic()
    try:
        if timeout:
            result = run_isolated(agent, task_ref, seed=seed, timeout=timeout)
        else:
            result = run(agent, task_ref, seed)

    except TimeoutError as exc:
        elapsed = time.monotonic() - start
        return {
            "_ok": False,
            "_error": str(exc),
            "_wall_clock_s": elapsed,
        }
    except Exception as exc:  # noqa: BLE001
        elapsed = time.monotonic() - start
        return {
            "_ok": False,
            "_error": f"{type(exc).__name__}: {exc}",
            "_wall_clock_s": elapsed,
        }

    elapsed = time.monotonic() - start
    try:
        persist_run(result)
    except Exception:  # noqa: BLE001
        pass

    return {
        "_ok": True,
        "_wall_clock_s": elapsed,
        "result": result,
    }


def run_batch(
    jobs: list[BatchJob],
    *,
    workers: int | None = None,
    timeout: int | None = None,
    strict_spec: bool = False,
) -> dict:
    """Run *jobs* in parallel under a bounded process pool.

    Parameters
    ----------
    jobs:
        List of BatchJob descriptors.
    workers:
        Max parallel workers. Defaults to min(CPU count, len(jobs), 8).
    timeout:
        Per-job wall-clock timeout in seconds (None = no limit).
    strict_spec:
        If True, run check_spec_compliance on each result and mark non-compliant
        jobs as failures.

    Returns
    -------
    dict
        ``{"ok": bool, "results": list[BatchResult], "summary": dict}``
    """
    if not jobs:
        return {"ok": True, "results": [], "summary": {"total": 0, "passed": 0, "failed": 0}}

    n_workers = workers or min(max(1, (os.cpu_count() or 2)), len(jobs), 8)
    repo_root = str(Path(__file__).parent.parent.parent.resolve())

    job_dicts = [
        {
            "agent": j.agent,
            "task_ref": j.task_ref,
            "seed": j.seed,
            "timeout": timeout or j.timeout,
            "_repo_root": repo_root,
        }
        for j in jobs
    ]

    batch_results: list[BatchResult] = []

    with concurrent.futures.ProcessPoolExecutor(max_workers=n_workers) as pool:
        future_to_job = {
            pool.submit(_run_job, jd): (job, jd)
            for job, jd in zip(jobs, job_dicts)
        }
        for future in concurrent.futures.as_completed(future_to_job):
            job, _ = future_to_job[future]
            try:
                raw = future.result(timeout=(timeout or 300) + 10)
            except Exception as exc:  # noqa: BLE001
                raw = {"_ok": False, "_error": str(exc), "_wall_clock_s": 0.0}

            wall = float(raw.get("_wall_clock_s", 0.0))
            if raw.get("_ok"):
                result = raw["result"]
                success = bool(result.get("success"))
                error = None

                if strict_spec:
                    from agent_bench.runner.spec_check import check_spec_compliance
                    report = check_spec_compliance(result)
                    if not report["ok"]:
                        success = False
                        error = "strict-spec: " + "; ".join(report["errors"][:3])

                batch_results.append(BatchResult(
                    job=job, result=result, error=error,
                    wall_clock_s=wall, success=success,
                ))
            else:
                batch_results.append(BatchResult(
                    job=job, result=None, error=raw.get("_error", "unknown"),
                    wall_clock_s=wall, success=False,
                ))

    passed = sum(1 for r in batch_results if r.success)
    failed = len(batch_results) - passed
    wall_times = [r.wall_clock_s for r in batch_results if r.wall_clock_s > 0]

    summary = {
        "total": len(batch_results),
        "passed": passed,
        "failed": failed,
        "workers": n_workers,
        "p50_wall_clock_s": _percentile(wall_times, 50),
        "p95_wall_clock_s": _percentile(wall_times, 95),
    }

    return {
        "ok": failed == 0,
        "results": batch_results,
        "summary": summary,
    }


def _percentile(values: list[float], pct: int) -> float | None:
    if not values:
        return None
    sorted_v = sorted(values)
    idx = int(len(sorted_v) * pct / 100)
    idx = min(idx, len(sorted_v) - 1)
    return round(sorted_v[idx], 3)
