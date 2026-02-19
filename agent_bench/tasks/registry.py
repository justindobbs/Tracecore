"""Task registry helpers."""

from __future__ import annotations

import importlib.metadata
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for 3.10
    import tomli as tomllib  # type: ignore[assignment]

REGISTRY_PATH = Path(__file__).parent.parent.parent / "tasks" / "registry.json"


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


def _parse_task_toml(task_dir: Path) -> dict[str, object]:
    toml_path = task_dir / "task.toml"
    if not toml_path.exists():
        return {}
    data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    return data


def _normalize_task_manifest(raw: dict[str, object]) -> dict[str, object]:
    budgets = raw.get("budgets", {}) if isinstance(raw.get("budgets"), dict) else {}
    normalized = {
        "id": raw.get("id"),
        "suite": raw.get("suite"),
        "version": raw.get("version"),
        "description": raw.get("description"),
        "deterministic": raw.get("deterministic"),
        "default_budget": budgets,
        "seed_behavior": raw.get("seed_behavior"),
        "action_surface": raw.get("action_surface"),
        "validator": raw.get("validator"),
        "setup": raw.get("setup"),
    }
    return normalized


def _validate_task_manifest(raw: dict[str, object], *, source: Path) -> None:
    errors: list[str] = []

    def require_key(key: str, expected_type: type | tuple[type, ...]) -> None:
        value = raw.get(key)
        if value is None:
            errors.append(f"missing required field: {key}")
            return
        if not isinstance(value, expected_type):
            errors.append(f"field {key} must be {expected_type}")

    require_key("id", str)
    require_key("suite", str)
    require_key("version", int)
    require_key("description", str)
    require_key("deterministic", bool)
    require_key("seed_behavior", str)

    budgets = raw.get("budgets")
    if budgets is None or not isinstance(budgets, dict):
        errors.append("budgets must be a table with steps/tool_calls")
    else:
        steps = budgets.get("steps")
        tool_calls = budgets.get("tool_calls")
        if not isinstance(steps, int):
            errors.append("budgets.steps must be an int")
        if not isinstance(tool_calls, int):
            errors.append("budgets.tool_calls must be an int")

    action_surface = raw.get("action_surface")
    if action_surface is None or not isinstance(action_surface, dict):
        errors.append("action_surface must be a table with source")
    else:
        source_val = action_surface.get("source")
        if not isinstance(source_val, str):
            errors.append("action_surface.source must be a string")

    validator = raw.get("validator")
    if validator is None or not isinstance(validator, dict):
        errors.append("validator must be a table with entrypoint")
    else:
        entrypoint = validator.get("entrypoint")
        if not isinstance(entrypoint, str):
            errors.append("validator.entrypoint must be a string")

    if errors:
        joined = "; ".join(errors)
        raise ValueError(f"Invalid task manifest {source}: {joined}")


def _load_task_manifest(task_dir: Path) -> dict[str, object]:
    toml_data = _parse_task_toml(task_dir)
    if toml_data:
        _validate_task_manifest(toml_data, source=task_dir / "task.toml")
        return _normalize_task_manifest(toml_data)
    yaml_data = _parse_task_yaml(task_dir)
    return yaml_data


def _enrich_descriptor(descriptor: TaskDescriptor) -> TaskDescriptor:
    if descriptor.path and descriptor.path.exists():
        manifest = _load_task_manifest(descriptor.path)
        if manifest:
            manifest_id = manifest.get("id")
            if manifest_id and manifest_id != descriptor.id:
                raise ValueError(
                    f"Task manifest id {manifest_id} does not match registry id {descriptor.id} "
                    f"({descriptor.path})"
                )
            manifest_suite = manifest.get("suite")
            if manifest_suite and manifest_suite != descriptor.suite:
                raise ValueError(
                    f"Task manifest suite {manifest_suite} does not match registry suite {descriptor.suite} "
                    f"({descriptor.path})"
                )
            manifest_version = manifest.get("version")
            if manifest_version and int(manifest_version) != descriptor.version:
                raise ValueError(
                    f"Task manifest version {manifest_version} does not match registry version {descriptor.version} "
                    f"({descriptor.path})"
                )
            if manifest.get("description"):
                descriptor.description = str(manifest["description"])
            if manifest.get("deterministic") is not None:
                descriptor.deterministic = bool(manifest["deterministic"])
            if "default_budget" in manifest:
                descriptor.metadata["default_budget"] = manifest["default_budget"]
            if "seed_behavior" in manifest:
                descriptor.metadata["seed_behavior"] = manifest["seed_behavior"]
            if "action_surface" in manifest:
                descriptor.metadata["action_surface"] = manifest["action_surface"]
            if "validator" in manifest:
                descriptor.metadata["validator"] = manifest["validator"]
            if "setup" in manifest:
                descriptor.metadata["setup"] = manifest["setup"]
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


def validate_task_path(task_dir: Path) -> list[str]:
    errors: list[str] = []
    if not task_dir.exists():
        return [f"task path does not exist: {task_dir}"]
    toml_path = task_dir / "task.toml"
    yaml_path = task_dir / "task.yaml"
    if not toml_path.exists() and not yaml_path.exists():
        errors.append("missing manifest: task.toml or task.yaml")
    for required in ("setup.py", "actions.py", "validate.py"):
        if not (task_dir / required).exists():
            errors.append(f"missing required file: {required}")
    if errors:
        return errors
    try:
        _load_task_manifest(task_dir)
    except Exception as exc:
        errors.append(str(exc))
    return errors


def validate_registry_entries() -> list[str]:
    errors: list[str] = []
    try:
        descriptors = list_task_descriptors()
    except Exception as exc:
        return [str(exc)]
    for descriptor in descriptors:
        if descriptor.path is None:
            if descriptor.loader is None:
                errors.append(f"{descriptor.id}@{descriptor.version}: missing path or loader")
            continue
        path_errors = validate_task_path(descriptor.path)
        if path_errors:
            for err in path_errors:
                errors.append(f"{descriptor.id}@{descriptor.version}: {err}")
    return errors


def reset_registry_cache() -> None:
    global _REGISTRY
    _REGISTRY = None
