"""TraceCore run metrics — reproducibility, budget utilisation, and MTTR.

Computes aggregate statistics over persisted run artifacts for dashboards
and CLI reporting.

Public API
----------
compute_metrics(task_ref, agent, limit) -> dict
    Reproducibility rate, budget P50/P95, taxonomy breakdown for a given filter.

compute_all_metrics(limit) -> dict
    Same but grouped by task_ref across all stored runs.

compute_mttr(task_ref, agent, limit) -> dict
    Mean time to recovery — time between first failure and next success
    for the same agent + task_ref + seed combination.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from agent_bench.runner.runlog import iter_runs


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.rstrip("Z")).replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _artifact_and_telemetry_stats(run: dict) -> dict[str, int]:
    action_trace = run.get("action_trace") or []
    llm_trace_entries = 0
    prompt_bytes = 0
    completion_bytes = 0
    tokens_used = 0
    for entry in action_trace:
        if not isinstance(entry, dict):
            continue
        llm_trace = entry.get("llm_trace") or []
        for llm_entry in llm_trace:
            if not isinstance(llm_entry, dict):
                continue
            llm_trace_entries += 1
            request = llm_entry.get("request") or {}
            response = llm_entry.get("response") or {}
            prompt = request.get("prompt")
            completion = response.get("completion")
            if isinstance(prompt, str):
                prompt_bytes += len(prompt.encode("utf-8"))
            if isinstance(completion, str):
                completion_bytes += len(completion.encode("utf-8"))
            response_tokens = response.get("tokens_used")
            if isinstance(response_tokens, int):
                tokens_used += response_tokens

    return {
        "artifact_bytes": len(str(run).encode("utf-8")),
        "llm_trace_entries": llm_trace_entries,
        "prompt_bytes": prompt_bytes,
        "completion_bytes": completion_bytes,
        "tokens_used": tokens_used,
    }


def compute_metrics(
    *,
    task_ref: str | None = None,
    agent: str | None = None,
    limit: int = 500,
) -> dict:
    """Compute aggregate metrics for the given filter.

    Returns
    -------
    dict with keys:
        task_ref, agent, run_count, reproducibility_rate,
        budget_utilisation (steps/tool_calls P50/P95 and ceiling),
        failure_taxonomy (counts by failure_type),
        avg_wall_clock_s
    """
    runs: list[dict] = []
    for r in iter_runs(agent=agent, task_ref=task_ref):
        runs.append(r)
        if len(runs) >= limit:
            break

    if not runs:
        return {
            "task_ref": task_ref,
            "agent": agent,
            "run_count": 0,
            "reproducibility_rate": None,
            "budget_utilisation": None,
            "failure_taxonomy": {},
            "avg_wall_clock_s": None,
        }

    total = len(runs)
    passed = sum(1 for r in runs if r.get("success"))
    repro_rate = round(passed / total, 4) if total else None

    steps_list = [r["steps_used"] for r in runs if isinstance(r.get("steps_used"), int)]
    tc_list = [r["tool_calls_used"] for r in runs if isinstance(r.get("tool_calls_used"), int)]

    steps_budget = next((r.get("budgets", {}).get("steps") for r in runs if r.get("budgets")), None)
    tc_budget = next((r.get("budgets", {}).get("tool_calls") for r in runs if r.get("budgets")), None)

    budget_util: dict[str, Any] = {}
    if steps_list:
        budget_util["steps"] = {
            "p50": _pct(steps_list, 50),
            "p95": _pct(steps_list, 95),
            "ceiling": steps_budget,
            "utilisation_p50": round(_pct(steps_list, 50) / steps_budget, 4) if steps_budget else None,
        }
    if tc_list:
        budget_util["tool_calls"] = {
            "p50": _pct(tc_list, 50),
            "p95": _pct(tc_list, 95),
            "ceiling": tc_budget,
            "utilisation_p50": round(_pct(tc_list, 50) / tc_budget, 4) if tc_budget else None,
        }

    taxonomy: dict[str, int] = defaultdict(int)
    for r in runs:
        ft = r.get("failure_type") or ("success" if r.get("success") else "unknown")
        taxonomy[str(ft)] += 1

    wall_times = [r["wall_clock_elapsed_s"] for r in runs if isinstance(r.get("wall_clock_elapsed_s"), (int, float))]
    avg_wall = round(statistics.mean(wall_times), 3) if wall_times else None
    telemetry_rows = [_artifact_and_telemetry_stats(r) for r in runs]

    return {
        "task_ref": task_ref or runs[0].get("task_ref"),
        "agent": agent or runs[0].get("agent"),
        "run_count": total,
        "reproducibility_rate": repro_rate,
        "budget_utilisation": budget_util or None,
        "failure_taxonomy": dict(taxonomy),
        "avg_wall_clock_s": avg_wall,
        "artifact_bytes_avg": round(statistics.mean([r["artifact_bytes"] for r in telemetry_rows]), 2) if telemetry_rows else None,
        "artifact_bytes_max": max((r["artifact_bytes"] for r in telemetry_rows), default=None),
        "llm_trace_entries_total": sum(r["llm_trace_entries"] for r in telemetry_rows),
        "prompt_bytes_total": sum(r["prompt_bytes"] for r in telemetry_rows),
        "completion_bytes_total": sum(r["completion_bytes"] for r in telemetry_rows),
        "tokens_used_total": sum(r["tokens_used"] for r in telemetry_rows),
    }


def compute_all_metrics(*, limit: int = 500) -> list[dict]:
    """Compute metrics grouped by (task_ref, agent) across all stored runs."""
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in iter_runs():
        key = (r.get("task_ref", ""), r.get("agent", ""))
        grouped[key].append(r)

    results = []
    for (tr, ag), runs in sorted(grouped.items()):
        capped = runs[:limit]
        total = len(capped)
        passed = sum(1 for r in capped if r.get("success"))

        steps_list = [r["steps_used"] for r in capped if isinstance(r.get("steps_used"), int)]
        tc_list = [r["tool_calls_used"] for r in capped if isinstance(r.get("tool_calls_used"), int)]

        steps_budget = next((r.get("budgets", {}).get("steps") for r in capped if r.get("budgets")), None)
        tc_budget = next((r.get("budgets", {}).get("tool_calls") for r in capped if r.get("budgets")), None)

        taxonomy: dict[str, int] = defaultdict(int)
        termination_taxonomy: dict[str, int] = defaultdict(int)
        for r in capped:
            ft = r.get("failure_type") or ("success" if r.get("success") else "unknown")
            taxonomy[str(ft)] += 1
            tr_reason = r.get("termination_reason") or ("success" if r.get("success") else "unknown")
            termination_taxonomy[str(tr_reason)] += 1

        wall_times = [r["wall_clock_elapsed_s"] for r in capped if isinstance(r.get("wall_clock_elapsed_s"), (int, float))]
        telemetry_rows = [_artifact_and_telemetry_stats(r) for r in capped]

        results.append({
            "task_ref": tr,
            "agent": ag,
            "run_count": total,
            "reproducibility_rate": round(passed / total, 4) if total else None,
            "steps_p50": _pct(steps_list, 50),
            "steps_p95": _pct(steps_list, 95),
            "steps_ceiling": steps_budget,
            "tool_calls_p50": _pct(tc_list, 50),
            "tool_calls_p95": _pct(tc_list, 95),
            "tool_calls_ceiling": tc_budget,
            "failure_taxonomy": dict(taxonomy),
            "termination_taxonomy": dict(termination_taxonomy),
            "avg_wall_clock_s": round(statistics.mean(wall_times), 3) if wall_times else None,
            "artifact_bytes_avg": round(statistics.mean([r["artifact_bytes"] for r in telemetry_rows]), 2) if telemetry_rows else None,
            "artifact_bytes_max": max((r["artifact_bytes"] for r in telemetry_rows), default=None),
            "llm_trace_entries_total": sum(r["llm_trace_entries"] for r in telemetry_rows),
            "prompt_bytes_total": sum(r["prompt_bytes"] for r in telemetry_rows),
            "completion_bytes_total": sum(r["completion_bytes"] for r in telemetry_rows),
            "tokens_used_total": sum(r["tokens_used"] for r in telemetry_rows),
        })

    return results


def compute_mttr(
    *,
    task_ref: str | None = None,
    agent: str | None = None,
    limit: int = 500,
) -> dict:
    """Compute Mean Time To Recovery for a given agent+task_ref.

    MTTR is defined as the mean time (seconds) between a failure event and
    the next success for the same (agent, task_ref, seed) combination.

    Returns
    -------
    dict with keys:
        task_ref, agent, mttr_seconds, recovery_count, incident_count
    """
    runs: list[dict] = []
    for r in iter_runs(agent=agent, task_ref=task_ref):
        runs.append(r)
        if len(runs) >= limit:
            break

    grouped: dict[tuple[str, str, int], list[dict]] = defaultdict(list)
    for r in runs:
        key = (r.get("agent", ""), r.get("task_ref", ""), r.get("seed", 0))
        grouped[key].append(r)

    recovery_times: list[float] = []
    incident_count = 0

    for key, key_runs in grouped.items():
        sorted_runs = sorted(
            key_runs,
            key=lambda r: _parse_ts(r.get("started_at")) or datetime.min.replace(tzinfo=timezone.utc),
        )

        failure_ts: datetime | None = None
        for r in sorted_runs:
            ts = _parse_ts(r.get("started_at"))
            if ts is None:
                continue
            if not r.get("success"):
                if failure_ts is None:
                    failure_ts = ts
                    incident_count += 1
            else:
                if failure_ts is not None:
                    delta = (ts - failure_ts).total_seconds()
                    if delta >= 0:
                        recovery_times.append(delta)
                    failure_ts = None

    mttr = round(statistics.mean(recovery_times), 1) if recovery_times else None

    return {
        "task_ref": task_ref,
        "agent": agent,
        "mttr_seconds": mttr,
        "recovery_count": len(recovery_times),
        "incident_count": incident_count,
    }


def _pct(values: list[int | float], pct: int) -> int | float | None:
    if not values:
        return None
    sv = sorted(values)
    idx = min(int(len(sv) * pct / 100), len(sv) - 1)
    return sv[idx]
