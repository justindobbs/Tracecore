"""Agent loader."""

from __future__ import annotations

import inspect
import importlib.util
from types import ModuleType


def _load_module(path: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location("openclaw_agent", path)
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
