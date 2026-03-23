"""Helpers for computing baseline stats from persisted runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from agent_bench.runner.runlog import iter_runs, load_run, _validate_run_id

BASELINE_ROOT = Path(".agent_bench") / "baselines"


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
        "last_seed",
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
        self.last_seed: int | None = None


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
            bucket.last_seed = run.get("seed")

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
                "last_seed": bucket.last_seed,
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


def _ensure_baseline_root() -> None:
    BASELINE_ROOT.mkdir(parents=True, exist_ok=True)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def export_baseline(rows: list[dict], *, path: str | Path | None = None, metadata: dict | None = None) -> Path:
    """Persist the given baseline rows to disk."""

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
    }
    if metadata:
        payload["metadata"] = metadata

    _ensure_baseline_root()
    if path is None:
        path = BASELINE_ROOT / f"baseline-{_timestamp()}.json"
    else:
        path = Path(path)
        if not path.is_absolute():
            path = BASELINE_ROOT / path
        if path.suffix != ".json":
            path = path.with_suffix(".json")

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return path


def load_latest_baseline() -> dict | None:
    """Load the most recent exported baseline payload, if any."""

    if not BASELINE_ROOT.exists():
        return None
    candidates = sorted(BASELINE_ROOT.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:  # pragma: no cover - corrupted file shouldn't crash UI
            continue
        data["_path"] = str(path)
        data["_filename"] = path.name
        return data
    return None


def load_run_artifact(ref: str) -> dict:
    """Load a run artifact either by explicit path or run_id."""

    candidate = Path(ref)
    if candidate.exists():
        resolved = candidate.resolve()
        if resolved.is_dir():
            raise FileNotFoundError(f"Artifact not found: {ref}")
        with resolved.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    if candidate.is_absolute() or ref.startswith("."):
        raise FileNotFoundError(f"Artifact not found: {ref}")

    _validate_run_id(ref)
    return load_run(ref)


_TRACE_VOLATILE_KEYS = frozenset({"action_ts", "budget_after_step", "budget_delta", "io_audit", "telemetry"})


def _normalize_trace_entry(entry: dict | None) -> dict | None:
    """Strip volatile/additive fields that don't affect semantic correctness."""

    if entry is None:
        return None
    normalized: dict[str, object] = {}
    for key, value in entry.items():
        if key in _TRACE_VOLATILE_KEYS:
            continue
        if value is None:
            continue
        normalized[key] = value
    return normalized


def _normalize_io_audit(io_entries: list | None) -> list[dict]:
    """Canonicalize io_audit entries for deterministic diffing.

    - Ensure list of dicts
    - Drop empty/unknown keys beyond type/op/path/host
    - Sort for stable comparison
    """

    if not io_entries:
        return []
    normalized: list[dict] = []
    for raw in io_entries:
        if not isinstance(raw, dict):
            continue
        audit_type = raw.get("type")
        op = raw.get("op")
        path = raw.get("path")
        host = raw.get("host")
        entry: dict[str, object] = {}
        if isinstance(audit_type, str):
            entry["type"] = audit_type
        if isinstance(op, str):
            entry["op"] = op
        if isinstance(path, str):
            entry["path"] = path
        if isinstance(host, str):
            entry["host"] = host
        if entry:
            normalized.append(entry)
    normalized.sort(key=lambda e: (e.get("type", ""), e.get("op", ""), e.get("path", ""), e.get("host", "")))
    return normalized


def _io_audit_key(entry: dict) -> tuple[str, str, str, str]:
    return (
        entry.get("type") or "",
        entry.get("op") or "",
        entry.get("path") or "",
        entry.get("host") or "",
    )


def _key_to_io_entry(key: tuple[str, str, str, str]) -> dict:
    type_, op, path, host = key
    entry: dict[str, str] = {}
    if type_:
        entry["type"] = type_
    if op:
        entry["op"] = op
    if path:
        entry["path"] = path
    if host:
        entry["host"] = host
    return entry


def _io_audit_diff(a: list | None, b: list | None) -> dict[str, list[dict]] | None:
    """Compute added/removed io_audit entries between two steps."""

    norm_a = _normalize_io_audit(a)
    norm_b = _normalize_io_audit(b)
    set_a = {_io_audit_key(item) for item in norm_a}
    set_b = {_io_audit_key(item) for item in norm_b}

    added = [_key_to_io_entry(key) for key in sorted(set_b - set_a)]
    removed = [_key_to_io_entry(key) for key in sorted(set_a - set_b)]

    if not added and not removed:
        return None
    return {"added": added, "removed": removed}


def diff_runs(run_a: dict, run_b: dict) -> dict:
    """Produce a structured diff between two run artifacts."""

    trace_a = run_a.get("action_trace") or []
    trace_b = run_b.get("action_trace") or []
    summary = {
        "same_agent": run_a.get("agent") == run_b.get("agent"),
        "same_task": run_a.get("task_ref") == run_b.get("task_ref"),
        "same_success": bool(run_a.get("success")) == bool(run_b.get("success")),
        "steps": {"run_a": len(trace_a), "run_b": len(trace_b)},
        "tool_calls": {
            "run_a": run_a.get("tool_calls_used"),
            "run_b": run_b.get("tool_calls_used"),
        },
        "io_audit": {"added": 0, "removed": 0},
    }

    step_diffs: list[dict] = []
    max_len = max(len(trace_a), len(trace_b))
    for idx in range(max_len):
        raw_a = trace_a[idx] if idx < len(trace_a) else None
        raw_b = trace_b[idx] if idx < len(trace_b) else None
        entry_a = _normalize_trace_entry(raw_a)
        entry_b = _normalize_trace_entry(raw_b)

        io_delta = _io_audit_diff((raw_a or {}).get("io_audit") if raw_a else None, (raw_b or {}).get("io_audit") if raw_b else None)
        if io_delta:
            summary["io_audit"]["added"] += len(io_delta["added"])
            summary["io_audit"]["removed"] += len(io_delta["removed"])

        if entry_a != entry_b or io_delta:
            diff_entry = {
                "step": idx + 1,
                "run_a": entry_a,
                "run_b": entry_b,
            }
            if io_delta:
                diff_entry["io_audit_delta"] = io_delta
            step_diffs.append(diff_entry)

    taxonomy = {
        "same_failure_type": run_a.get("failure_type") == run_b.get("failure_type"),
        "same_termination_reason": run_a.get("termination_reason") == run_b.get("termination_reason"),
        "run_a": {
            "failure_type": run_a.get("failure_type"),
            "termination_reason": run_a.get("termination_reason"),
        },
        "run_b": {
            "failure_type": run_b.get("failure_type"),
            "termination_reason": run_b.get("termination_reason"),
        },
    }
    budget_delta = {
        "steps": (len(trace_b) - len(trace_a)),
        "tool_calls": (
            (run_b.get("tool_calls_used") or 0) - (run_a.get("tool_calls_used") or 0)
        ),
        "wall_clock_s": round(
            (run_b.get("wall_clock_elapsed_s") or 0.0)
            - (run_a.get("wall_clock_elapsed_s") or 0.0),
            3,
        ),
    }

    return {
        "run_a": _run_summary(run_a),
        "run_b": _run_summary(run_b),
        "summary": summary,
        "taxonomy": taxonomy,
        "budget_delta": budget_delta,
        "step_diffs": step_diffs,
    }


def _run_summary(run: dict) -> dict:
    return {
        "run_id": run.get("run_id"),
        "agent": run.get("agent"),
        "task_ref": run.get("task_ref"),
        "success": bool(run.get("success")),
        "failure_type": run.get("failure_type"),
        "termination_reason": run.get("termination_reason"),
        "steps_used": run.get("steps_used"),
        "tool_calls_used": run.get("tool_calls_used"),
        "seed": run.get("seed"),
    }
