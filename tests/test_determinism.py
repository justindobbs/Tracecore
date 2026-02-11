"""Determinism regression tests."""

from __future__ import annotations

import json

import pytest

from agent_bench.runner.runner import run
from agent_bench.tasks.loader import load_task

DETERMINISTIC_CASES = (
    {
        "task_id": "filesystem_hidden_config",
        "agent": "agents/toy_agent.py",
        "seed": 42,
    },
    {
        "task_id": "rate_limited_api",
        "agent": "agents/rate_limit_agent.py",
        "seed": 11,
    },
)

REPEATS = 5


def _strip_metadata(payload: dict) -> dict:
    """Remove metadata fields that are expected to change across executions."""

    scrubbed = dict(payload)
    for key in ("run_id", "trace_id", "started_at", "completed_at"):
        scrubbed.pop(key, None)
    return scrubbed


def _task_ref(task_id: str) -> str:
    task = load_task(task_id)
    assert task.get("deterministic", True), f"Task {task_id} must be marked deterministic."
    version = task["version"]
    return f"{task_id}@{version}"


@pytest.mark.parametrize("case", DETERMINISTIC_CASES, ids=lambda c: c["task_id"])
def test_runs_are_identical_with_fixed_seed(case):
    task_ref = _task_ref(case["task_id"])
    baseline = run(case["agent"], task_ref, seed=case["seed"])
    baseline_norm = _strip_metadata(baseline)
    baseline_json = json.dumps(baseline_norm, sort_keys=True)

    for _ in range(REPEATS - 1):
        next_result = run(case["agent"], task_ref, seed=case["seed"])
        next_norm = _strip_metadata(next_result)
        assert next_norm == baseline_norm, "Result dictionaries diverged despite fixed seed."
        assert json.dumps(next_norm, sort_keys=True) == baseline_json, "JSON order mismatch."
