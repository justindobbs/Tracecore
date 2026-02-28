"""Agent loader."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from types import ModuleType

import agent_bench.agents as _bundled_agents_pkg

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
AGENTS_PACKAGE_ROOT = PACKAGE_ROOT / "agents"


def _resolve_agent_path(path: str) -> Path:
    """
    Resolve an agent path coming from potentially untrusted input.

    Only allow loading agents from the local agents directory or the bundled
    agent_bench.agents package, and only for simple "agents/<name>.py" values.
    """
    raw = Path(path)

    # Require a relative agents/<file>.py path with no traversal.
    if raw.is_absolute():
        raise FileNotFoundError(f"Unable to locate agent module at {path}")

    parts = raw.parts
    if len(parts) != 2 or parts[0] != "agents" or parts[1].startswith(".") or "/" in parts[1] or "\\" in parts[1]:
        raise FileNotFoundError(f"Unable to locate agent module at {path}")

    filename = parts[1]

    # First, try local agents directory.
    local_candidate = (AGENTS_PACKAGE_ROOT / filename).resolve()
    try:
        if local_candidate.is_file() and str(local_candidate).startswith(str(AGENTS_PACKAGE_ROOT.resolve())):
            return local_candidate
    except OSError:
        pass

    # Fallback to bundled agents within the installed package.
   _bundled_root = Path(_bundled_agents_pkg.__file__).parent.resolve()
    bundled_candidate = (_bundled_root / filename).resolve()
    try:
        if bundled_candidate.is_file() and str(bundled_candidate).startswith(str(_bundled_root)):
            return bundled_candidate
    except OSError:
        pass

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
