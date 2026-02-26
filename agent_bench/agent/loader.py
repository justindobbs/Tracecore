"""Agent loader."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from types import ModuleType


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
AGENTS_PACKAGE_ROOT = PACKAGE_ROOT / "agents"


def _resolve_agent_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.exists():
        return candidate

    packaged = PACKAGE_ROOT / path
    if packaged.exists():
        return packaged

    fallback = AGENTS_PACKAGE_ROOT / Path(path).name
    if fallback.exists():
        return fallback

    raise FileNotFoundError(f"Unable to locate agent module at {path}")


def _load_module(path: str) -> ModuleType:
    resolved_path = _resolve_agent_path(path)
    spec = importlib.util.spec_from_file_location("openclaw_agent", resolved_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Unable to load agent module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _find_agent_class(module: ModuleType):
    if hasattr(module, "Agent"):
        return getattr(module, "Agent")
    if hasattr(module, "ToyAgent"):
        return getattr(module, "ToyAgent")
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if all(hasattr(obj, name) for name in ("reset", "observe", "act")):
            return obj
    raise ValueError("No compatible agent class found")


def load_agent(path: str):
    module = _load_module(path)
    cls = _find_agent_class(module)
    return cls()
