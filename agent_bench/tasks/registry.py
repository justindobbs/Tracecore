"""Task registry helpers."""

from __future__ import annotations

import importlib.metadata
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

REGISTRY_PATH = Path("tasks") / "registry.json"


@dataclass(slots=True)
class TaskDescriptor:
    id: str
    suite: str
    version: int
    description: str
    deterministic: bool
    path: Path | None
    loader: Callable[[], dict] | None = None
    metadata: dict | None = None


_REGISTRY: dict[tuple[str, int], TaskDescriptor] | None = None


def _load_builtin_registry() -> Iterable[TaskDescriptor]:
    if not REGISTRY_PATH.exists():
        return []
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    descriptors = []
    for entry in data.get("tasks", []):
        rel_path = entry.get("path")
        path = Path(rel_path).resolve() if rel_path else None
        descriptors.append(
            TaskDescriptor(
                id=entry["id"],
                suite=entry.get("suite", ""),
                version=int(entry.get("version", 0)),
                description=entry.get("description", ""),
                deterministic=bool(entry.get("deterministic", True)),
                path=path,
                loader=None,
                metadata=entry,
            )
        )
    return descriptors


def _load_entry_point_registry() -> Iterable[TaskDescriptor]:
    try:
        eps = importlib.metadata.entry_points(group="agent_bench.tasks")
    except Exception:  # pragma: no cover - metadata failure shouldn't crash
        return []
    descriptors: list[TaskDescriptor] = []
    for ep in eps:
        try:
            resolver = ep.load()
            provided = resolver()
            for entry in provided:
                descriptors.append(
                    TaskDescriptor(
                        id=entry["id"],
                        suite=entry.get("suite", ""),
                        version=int(entry.get("version", 0)),
                        description=entry.get("description", ""),
                        deterministic=bool(entry.get("deterministic", True)),
                        path=Path(entry["path"]).resolve() if entry.get("path") else None,
                        loader=entry.get("loader"),
                        metadata=entry,
                    )
                )
        except Exception:
            continue
    return descriptors


def _ensure_registry() -> None:
    global _REGISTRY
    if _REGISTRY is not None:
        return
    merged: dict[tuple[str, int], TaskDescriptor] = {}
    for descriptor in [*_load_builtin_registry(), *_load_entry_point_registry()]:
        merged[(descriptor.id, descriptor.version)] = descriptor
    _REGISTRY = merged


def get_task_descriptor(task_id: str, version: int | None = None) -> TaskDescriptor | None:
    _ensure_registry()
    assert _REGISTRY is not None
    if version is not None:
        return _REGISTRY.get((task_id, version))
    matches = [desc for (tid, _), desc in _REGISTRY.items() if tid == task_id]
    if not matches:
        return None
    return sorted(matches, key=lambda d: d.version, reverse=True)[0]


def list_task_descriptors() -> list[TaskDescriptor]:
    _ensure_registry()
    assert _REGISTRY is not None
    return sorted(_REGISTRY.values(), key=lambda d: (d.suite, d.id, d.version))
