"""Task loader."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


TASKS_ROOT = Path("tasks")


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse_task_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8").splitlines()
    data: dict[str, object] = {}
    i = 0
    while i < len(text):
        line = text[i].rstrip()
        i += 1
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("description:"):
            if line.endswith("|"):
                desc_lines = []
                while i < len(text):
                    raw = text[i]
                    if not raw.startswith("  "):
                        break
                    desc_lines.append(raw[2:])
                    i += 1
                data["description"] = "\n".join(desc_lines).strip()
                continue
        if line.startswith("default_budget:"):
            budget = {}
            while i < len(text):
                raw = text[i]
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
            if key in ("version",):
                data[key] = int(val)
            elif key in ("deterministic",):
                data[key] = val.lower() == "true"
            else:
                data[key] = val
    return data


def load_task(task_id: str, version: int | None = None) -> dict:
    task_dir = TASKS_ROOT / task_id
    if not task_dir.exists():
        raise FileNotFoundError(f"Task not found: {task_id}")

    yaml_path = task_dir / "task.yaml"
    setup_path = task_dir / "setup.py"
    actions_path = task_dir / "actions.py"
    validate_path = task_dir / "validate.py"
    for p in (yaml_path, setup_path, actions_path, validate_path):
        if not p.exists():
            raise FileNotFoundError(f"Task missing file: {p}")

    meta = _parse_task_yaml(yaml_path)
    if version is not None and int(meta.get("version", -1)) != version:
        raise ValueError(f"Task version mismatch for {task_id}")

    setup_mod = _load_module(setup_path, f"{task_id}_setup")
    actions_mod = _load_module(actions_path, f"{task_id}_actions")
    validate_mod = _load_module(validate_path, f"{task_id}_validate")

    return {
        "id": meta.get("id", task_id),
        "suite": meta.get("suite", ""),
        "version": meta.get("version", version),
        "description": meta.get("description", ""),
        "default_budget": meta.get("default_budget", {}),
        "deterministic": meta.get("deterministic", True),
        "setup": setup_mod,
        "actions": actions_mod,
        "validate": validate_mod,
    }
