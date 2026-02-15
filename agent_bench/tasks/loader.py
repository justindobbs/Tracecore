"""Task loader that consults the task registry (built-in + plugins)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from agent_bench.tasks.registry import TaskDescriptor, get_task_descriptor


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_task_from_path(descriptor: TaskDescriptor) -> dict:
    if descriptor.path is None:
        raise FileNotFoundError(f"Task {descriptor.id}@{descriptor.version} missing path in descriptor")
    task_dir = descriptor.path
    toml_path = task_dir / "task.toml"
    yaml_path = task_dir / "task.yaml"
    setup_path = task_dir / "setup.py"
    actions_path = task_dir / "actions.py"
    validate_path = task_dir / "validate.py"
    if not toml_path.exists() and not yaml_path.exists():
        raise FileNotFoundError(f"Task missing manifest: {toml_path} or {yaml_path}")
    for p in (setup_path, actions_path, validate_path):
        if not p.exists():
            raise FileNotFoundError(f"Task missing file: {p}")

    meta = descriptor.metadata

    setup_mod = _load_module(setup_path, f"{descriptor.id}_setup")
    actions_mod = _load_module(actions_path, f"{descriptor.id}_actions")
    validate_mod = _load_module(validate_path, f"{descriptor.id}_validate")

    return {
        "id": descriptor.id,
        "suite": descriptor.suite,
        "version": descriptor.version,
        "description": meta.get("description", descriptor.description),
        "default_budget": meta.get("default_budget", {}),
        "deterministic": meta.get("deterministic", descriptor.deterministic),
        "setup": setup_mod,
        "actions": actions_mod,
        "validate": validate_mod,
    }


def load_task(task_id: str, version: int | None = None) -> dict:
    """Load a task using the registry (built-in manifest + entry points)."""

    descriptor = get_task_descriptor(task_id, version)
    if descriptor is None:
        raise FileNotFoundError(f"Task not found: {task_id}{'@'+str(version) if version else ''}")

    if descriptor.loader is not None:
        loaded = descriptor.loader()
        if not isinstance(loaded, dict):
            raise ValueError(f"Custom loader for {task_id}@{descriptor.version} must return dict")
        loaded.setdefault("id", descriptor.id)
        loaded.setdefault("suite", descriptor.suite)
        loaded.setdefault("version", descriptor.version)
        loaded.setdefault("description", descriptor.description)
        loaded.setdefault("deterministic", descriptor.deterministic)
        return loaded

    return _load_task_from_path(descriptor)
