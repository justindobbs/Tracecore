"""Stub deterministic task helpers for AutoGen adapter tests."""

from __future__ import annotations

from types import SimpleNamespace


def make_task(*, task_id: str = "stub_task", version: int = 1) -> dict:
    """Return a minimal deterministic task dict suitable for runner tests."""

    def _setup(seed, env):
        pass

    def noop():
        return {"ok": True, "message": "ok"}

    def wait(steps: int | None = None):
        return {"ok": True, "message": f"waited:{steps or 0}"}

    def set_output(key: str, value: str):
        return {"ok": True, "message": f"set:{key}"}

    actions_mod = SimpleNamespace(
        set_env=lambda env: None,
        noop=noop,
        wait=wait,
        set_output=set_output,
    )
    validate_mod = SimpleNamespace(validate=lambda env: {"ok": True, "terminal": True})

    return {
        "id": task_id,
        "suite": "test",
        "version": version,
        "description": "Stub task for adapter integration test.",
        "default_budget": {"steps": 3, "tool_calls": 3},
        "deterministic": True,
        "setup": SimpleNamespace(setup=_setup),
        "actions": actions_mod,
        "validate": validate_mod,
    }
