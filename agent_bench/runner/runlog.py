"""Run artifact logging helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

RUN_LOG_ROOT = Path(".agent_bench") / "runs"


def _ensure_root() -> None:
    RUN_LOG_ROOT.mkdir(parents=True, exist_ok=True)


def persist_run(result: dict) -> Path:
    """Persist a run result to disk and return the artifact path."""

    run_id = result.get("run_id")
    if not run_id:
        raise ValueError("run result missing run_id; cannot persist")

    _ensure_root()
    path = RUN_LOG_ROOT / f"{run_id}.json"
    with path.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    return path


def load_run(run_id: str) -> dict:
    """Load a specific run artifact by ID."""

    path = RUN_LOG_ROOT / f"{run_id}.json"
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def iter_runs(*, agent: str | None = None, task_ref: str | None = None) -> Iterator[dict]:
    """Iterate over persisted runs newest-first with optional filters."""

    if not RUN_LOG_ROOT.exists():
        return iter(())

    files = sorted(
        RUN_LOG_ROOT.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    def _iterator():
        for path in files:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if agent and data.get("agent") != agent:
                continue
            if task_ref and data.get("task_ref") != task_ref:
                continue
            yield data

    return _iterator()


def list_runs(*, agent: str | None = None, task_ref: str | None = None, limit: int = 20) -> list[dict]:
    runs: list[dict] = []
    for run in iter_runs(agent=agent, task_ref=task_ref):
        runs.append(run)
        if len(runs) >= limit:
            break
    return runs
