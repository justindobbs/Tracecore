"""Shared helpers for integration generators."""

from __future__ import annotations

from agent_bench.runner.runner import _action_schema, _parse_task_ref
from agent_bench.tasks.loader import load_task


def load_task_metadata(task_ref: str) -> dict:
    """Load a task and return metadata useful to generators."""

    task_id, version = _parse_task_ref(task_ref)
    task = load_task(task_id, version)
    description = (
        task.get("description")
        or getattr(task.get("task"), "__doc__", None)
        or ""
    )
    default_budget = task.get("default_budget") or {}
    return {
        "task_id": task_id,
        "version": version,
        "description": description or "",
        "action_schema": _action_schema(task["actions"]),
        "default_budget": default_budget,
    }
