"""Helpers for computing baseline stats from persisted runs."""

from __future__ import annotations

from typing import Iterable

from agent_bench.runner.runlog import iter_runs


class _Bucket:
    __slots__ = (
        "count",
        "successes",
        "steps_sum",
        "steps_count",
        "tools_sum",
        "tools_count",
        "last_run_id",
        "last_completed_at",
        "last_success",
    )

    def __init__(self) -> None:
        self.count = 0
        self.successes = 0
        self.steps_sum = 0.0
        self.steps_count = 0
        self.tools_sum = 0.0
        self.tools_count = 0
        self.last_run_id: str | None = None
        self.last_completed_at: str | None = None
        self.last_success: bool | None = None


def _extract_metric(payload: dict, key: str) -> float | None:
    value = payload.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    metrics = payload.get("metrics", {})
    value = metrics.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def summarize_runs(runs: Iterable[dict]) -> list[dict]:
    """Aggregate runs into per-agent/per-task baseline rows."""

    buckets: dict[tuple[str, str], _Bucket] = {}
    for run in runs:
        agent = run.get("agent")
        task_ref = run.get("task_ref")
        if not agent or not task_ref:
            continue
        key = (agent, task_ref)
        bucket = buckets.setdefault(key, _Bucket())
        bucket.count += 1
        if run.get("success"):
            bucket.successes += 1
        steps = _extract_metric(run, "steps_used")
        if steps is not None:
            bucket.steps_sum += steps
            bucket.steps_count += 1
        tool_calls = _extract_metric(run, "tool_calls_used")
        if tool_calls is not None:
            bucket.tools_sum += tool_calls
            bucket.tools_count += 1
        completed_at = run.get("completed_at")
        if completed_at and (bucket.last_completed_at is None or completed_at > bucket.last_completed_at):
            bucket.last_completed_at = completed_at
            bucket.last_run_id = run.get("run_id")
            bucket.last_success = bool(run.get("success"))

    rows: list[dict] = []
    for (agent, task_ref), bucket in sorted(buckets.items()):
        success_rate = bucket.successes / bucket.count if bucket.count else 0.0
        avg_steps = bucket.steps_sum / bucket.steps_count if bucket.steps_count else None
        avg_tools = bucket.tools_sum / bucket.tools_count if bucket.tools_count else None
        rows.append(
            {
                "agent": agent,
                "task_ref": task_ref,
                "runs": bucket.count,
                "success_rate": success_rate,
                "avg_steps": avg_steps,
                "avg_tool_calls": avg_tools,
                "last_run_id": bucket.last_run_id,
                "last_completed_at": bucket.last_completed_at,
                "last_success": bucket.last_success,
            }
        )
    return rows


def build_baselines(*, agent: str | None = None, task_ref: str | None = None, max_runs: int | None = None) -> list[dict]:
    """Load run artifacts and compute baseline stats."""

    runs: list[dict] = []
    for idx, run in enumerate(iter_runs(agent=agent, task_ref=task_ref)):
        if max_runs is not None and idx >= max_runs:
            break
        runs.append(run)
    return summarize_runs(runs)
