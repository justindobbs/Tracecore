"""Task registry helpers."""

from __future__ import annotations

import importlib.metadata
import json
from dataclasses import dataclass, field
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
    metadata: dict = field(default_factory=dict)


_REGISTRY: dict[tuple[str, int], TaskDescriptor] | None = None


def _parse_task_yaml(task_dir: Path) -> dict[str, object]:
    yaml_path = task_dir / "task.yaml"
    if not yaml_path.exists():
        return {}
    lines = yaml_path.read_text(encoding="utf-8").splitlines()
    data: dict[str, object] = {}
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        i += 1
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("description:") and line.endswith("|"):
            desc_lines = []
            while i < len(lines):
                raw = lines[i]
                if not raw.startswith("  "):
                    break
                desc_lines.append(raw[2:])
                i += 1
            data["description"] = "\n".join(desc_lines).strip()
            continue
        if line.startswith("default_budget:"):
            budget: dict[str, int] = {}
            while i < len(lines):
                raw = lines[i]
                if not raw.startswith("  "):
                    break
                key, val = raw.strip().split(":", 1)
                budget[key.strip()] = int(val.strip())
                i += 1
            data["default_budget"] = budget
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            if key == "version":
                data[key] = int(val)
            elif key == "deterministic":
                data[key] = val.lower() == "true"
            else:
                data[key] = val
    return data


def _enrich_descriptor(descriptor: TaskDescriptor) -> TaskDescriptor:
    if descriptor.path and descriptor.path.exists():
        yaml_meta = _parse_task_yaml(descriptor.path)
        if yaml_meta:
            if yaml_meta.get("description"):
                descriptor.description = str(yaml_meta["description"])
            if yaml_meta.get("deterministic") is not None:
                descriptor.deterministic = bool(yaml_meta["deterministic"])
            if "default_budget" in yaml_meta:
                descriptor.metadata["default_budget"] = yaml_meta["default_budget"]
    descriptor.metadata.setdefault("default_budget", {})
    return descriptor


def _load_builtin_registry() -> Iterable[TaskDescriptor]:
    if not REGISTRY_PATH.exists():
        return []
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    base_dir = REGISTRY_PATH.parent
    descriptors = []
    for entry in data.get("tasks", []):
        rel_path = entry.get("path")
        path = (base_dir / rel_path).resolve() if rel_path else None
        descriptor = TaskDescriptor(
            id=entry["id"],
            suite=entry.get("suite", ""),
            version=int(entry.get("version", 0)),
            description=entry.get("description", ""),
            deterministic=bool(entry.get("deterministic", True)),
            path=path,
            loader=None,
            metadata=entry or {},
        )
        descriptors.append(_enrich_descriptor(descriptor))
    return descriptors


def _load_entry_point_registry() -> Iterable[TaskDescriptor]:
    try:
        raw_eps = importlib.metadata.entry_points()
        if hasattr(raw_eps, "select"):
            eps = raw_eps.select(group="agent_bench.tasks")
        else:  # pragma: no cover - legacy API
            eps = raw_eps.get("agent_bench.tasks", [])  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - metadata failure shouldn't crash
        return []
    descriptors: list[TaskDescriptor] = []
    for ep in eps:
        try:
            resolver = ep.load()
            provided = resolver()
            for entry in provided:
                descriptor = TaskDescriptor(
                    id=entry["id"],
                    suite=entry.get("suite", ""),
                    version=int(entry.get("version", 0)),
                    description=entry.get("description", ""),
                    deterministic=bool(entry.get("deterministic", True)),
                    path=Path(entry["path"]).resolve() if entry.get("path") else None,
                    loader=entry.get("loader"),
                    metadata=entry or {},
                )
                descriptors.append(_enrich_descriptor(descriptor))
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


def reset_registry_cache() -> None:
    global _REGISTRY
    _REGISTRY = None
