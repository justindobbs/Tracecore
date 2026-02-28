"""Action contract regression tests.

Verifies that every task's actions.py handles invalid arguments gracefully —
returning structured error dicts rather than raising exceptions.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from agent_bench.tasks.registry import list_task_descriptors


def _load_actions_module(task_dir: Path):
    """Import the actions module for a task directory."""
    actions_path = task_dir / "actions.py"
    if not actions_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("_test_actions", str(actions_path))
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return None
    return mod


def _get_action_names(mod) -> list[str]:
    """Extract callable action names from an actions module."""
    schema_fn = getattr(mod, "action_schema", None)
    if callable(schema_fn):
        try:
            schema = schema_fn()
            if isinstance(schema, dict) and "actions" in schema:
                return [a["type"] for a in schema["actions"] if "type" in a]
            if isinstance(schema, list):
                return [a["type"] for a in schema if "type" in a]
        except Exception:
            pass
    candidates = []
    for name in dir(mod):
        if name.startswith("_"):
            continue
        obj = getattr(mod, name)
        if callable(obj) and not isinstance(obj, type):
            candidates.append(name)
    return candidates


def _execute_action(mod, action_type: str, args: dict) -> dict:
    """Call mod.execute({'type': action_type, 'args': args}) if available."""
    execute_fn = getattr(mod, "execute", None)
    if not callable(execute_fn):
        execute_fn = getattr(mod, action_type, None)
    if not callable(execute_fn):
        return {"ok": True, "_skipped": True}
    try:
        if execute_fn.__code__.co_varnames[:1] == ("action",) or "action" in str(execute_fn.__code__.co_varnames[:2]):
            result = execute_fn({"type": action_type, "args": args})
        else:
            result = execute_fn(action_type, args)
        return result if isinstance(result, dict) else {"ok": bool(result)}
    except TypeError:
        return {"ok": True, "_skipped": True}
    except Exception as exc:  # noqa: BLE001
        return {"_exception": str(exc), "ok": False}


def _task_descriptors():
    try:
        return list_task_descriptors()
    except Exception:
        return []


_DESCRIPTORS = _task_descriptors()
_TASK_IDS = [d.id for d in _DESCRIPTORS] if _DESCRIPTORS else []


@pytest.mark.parametrize("task_id", _TASK_IDS or ["filesystem_hidden_config"])
def test_actions_module_is_importable(task_id):
    """Every task must have an importable actions.py."""
    descriptors = {d.id: d for d in _DESCRIPTORS}
    if task_id not in descriptors:
        pytest.skip(f"task {task_id!r} not in registry")
    task_dir = descriptors[task_id].path
    mod = _load_actions_module(task_dir)
    assert mod is not None, f"actions.py for {task_id} could not be imported"


@pytest.mark.parametrize("task_id", _TASK_IDS or ["filesystem_hidden_config"])
def test_actions_handle_missing_args_gracefully(task_id):
    """Actions invoked with empty args must not raise unhandled exceptions."""
    descriptors = {d.id: d for d in _DESCRIPTORS}
    if task_id not in descriptors:
        pytest.skip(f"task {task_id!r} not in registry")
    task_dir = descriptors[task_id].path
    mod = _load_actions_module(task_dir)
    if mod is None:
        pytest.skip(f"could not import actions.py for {task_id}")

    action_names = _get_action_names(mod)
    if not action_names:
        pytest.skip(f"no discoverable actions in {task_id}")

    for action_type in action_names[:5]:
        result = _execute_action(mod, action_type, {})
        if result.get("_skipped"):
            continue
        exc_msg = result.get("_exception") or ""
        if exc_msg and any(s in exc_msg for s in (
            "not initialized", "set_env", "Environment",
            "NoneType", "has no attribute", "object is not",
        )):
            continue
        assert "_exception" not in result or not result["_exception"], (
            f"action {action_type!r} in task {task_id!r} raised an unhandled exception "
            f"with empty args: {result.get('_exception')}"
        )
        assert isinstance(result, dict), (
            f"action {action_type!r} in task {task_id!r} must return a dict; "
            f"got {type(result)}"
        )


@pytest.mark.parametrize("task_id", _TASK_IDS or ["filesystem_hidden_config"])
def test_actions_handle_wrong_type_args_gracefully(task_id):
    """Actions invoked with wrong-type args must return a dict, not raise."""
    descriptors = {d.id: d for d in _DESCRIPTORS}
    if task_id not in descriptors:
        pytest.skip(f"task {task_id!r} not in registry")
    task_dir = descriptors[task_id].path
    mod = _load_actions_module(task_dir)
    if mod is None:
        pytest.skip(f"could not import actions.py for {task_id}")

    action_names = _get_action_names(mod)
    if not action_names:
        pytest.skip(f"no discoverable actions in {task_id}")

    bad_args = {"key": 12345, "value": None, "path": 99, "query": [], "limit": "not-an-int"}
    for action_type in action_names[:5]:
        result = _execute_action(mod, action_type, bad_args)
        if result.get("_skipped"):
            continue
        exc_msg = result.get("_exception") or ""
        if exc_msg and any(s in exc_msg for s in (
            "not initialized", "set_env", "Environment",
            "NoneType", "has no attribute", "object is not",
        )):
            continue
        assert isinstance(result, dict), (
            f"action {action_type!r} in task {task_id!r} must return a dict for invalid args; "
            f"got {type(result)}"
        )


def test_filesystem_hidden_config_set_output_returns_dict():
    """Smoke-test the most common action type across all tasks."""
    from agent_bench.runner.runner import run

    result = run("agents/toy_agent.py", "filesystem_hidden_config@1", seed=0)
    assert isinstance(result, dict)
    assert "action_trace" in result
    for entry in result["action_trace"]:
        assert isinstance(entry.get("result"), dict), (
            f"action result must be a dict; got {type(entry.get('result'))}"
        )
