"""TraceCore Ledger — static registry of known agents and their baseline metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

_REGISTRY_PATH = Path(__file__).parent / "registry.json"


def _load_registry() -> list[dict]:
    with _REGISTRY_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh).get("entries", [])


def list_entries() -> list[dict]:
    """Return all ledger entries sorted by agent name."""
    return sorted(_load_registry(), key=lambda e: e.get("agent", ""))


def get_entry(agent: str) -> dict | None:
    """Return the ledger entry for *agent*, or None if not found.

    Matching is done against the ``agent`` field; both exact path and
    basename (without extension) are accepted.
    """
    needle = agent.strip()
    needle_stem = Path(needle).stem
    for entry in _load_registry():
        candidate = entry.get("agent", "")
        if candidate == needle or Path(candidate).stem == needle_stem:
            return entry
    return None


def iter_entries(
    *,
    suite: str | None = None,
    task_ref: str | None = None,
) -> Iterator[dict]:
    """Iterate over ledger entries with optional filters."""
    for entry in list_entries():
        if suite and entry.get("suite") != suite:
            continue
        if task_ref:
            tasks = entry.get("tasks", [])
            if not any(t.get("task_ref") == task_ref for t in tasks):
                continue
        yield entry
