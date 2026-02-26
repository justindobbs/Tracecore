"""TraceCore Ledger — static registry of known agents and their baseline metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

_REGISTRY_PATH = Path(__file__).parent / "registry.json"


def _load_registry() -> dict:
    with _REGISTRY_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _registry_entries() -> list[dict]:
    return _load_registry().get("entries", [])


def list_entries() -> list[dict]:
    """Return all ledger entries sorted by agent name."""
    return sorted(_registry_entries(), key=lambda e: e.get("agent", ""))


def get_entry(agent: str) -> dict | None:
    """Return the ledger entry for *agent*, or None if not found.

    Matching is done against the ``agent`` field; both exact path and
    basename (without extension) are accepted.
    """
    needle = agent.strip()
    needle_stem = Path(needle).stem
    for entry in _registry_entries():
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


def get_registry_metadata() -> dict:
    """Return top-level registry metadata (version, provenance fields) without entries."""
    registry = _load_registry()
    return {k: v for k, v in registry.items() if k != "entries"}


def stamp_registry(signing_key_b64: str | None = None) -> None:
    """Sign the ledger registry and write provenance fields back to registry.json.

    If *signing_key_b64* is None, reads from the ``TRACECORE_LEDGER_SIGNING_KEY``
    environment variable.  Raises ``RuntimeError`` if no key is available.
    """
    import os

    from agent_bench.ledger.signing import (
        load_private_key,
        sign_registry,
    )

    key_b64 = signing_key_b64 or os.environ.get("TRACECORE_LEDGER_SIGNING_KEY")
    if not key_b64:
        raise RuntimeError(
            "No signing key available. Set TRACECORE_LEDGER_SIGNING_KEY or pass signing_key_b64."
        )

    private_key = load_private_key(key_b64)
    registry = _load_registry()
    provenance = sign_registry(registry, private_key)
    registry.update(provenance)

    with _REGISTRY_PATH.open("w", encoding="utf-8") as fh:
        json.dump(registry, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
