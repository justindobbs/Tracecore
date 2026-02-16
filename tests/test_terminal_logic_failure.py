"""Tests for terminal validator failures."""

from __future__ import annotations

from types import SimpleNamespace

from agent_bench.runner import runner


class _Agent:
    def reset(self, task_spec):
        self.task_spec = task_spec
        self.obs = None

    def observe(self, observation):
        self.obs = observation

    def act(self):
        return {"type": "wait", "args": {}}


class _Actions:
    @staticmethod
    def wait() -> dict:
        return {"ok": True}


class _Validate:
    def __init__(self):
        self.calls = 0

    def validate(self, _env):
        self.calls += 1
        if self.calls >= 1:
            return {
                "ok": False,
                "terminal": True,
                "message": "validator declared terminal",
                "termination_reason": "logic_failure",
                "failure_type": "logic_failure",
            }
        return {"ok": False}


def test_terminal_validator_emits_logic_failure(monkeypatch):
    validate = _Validate()

    def fake_load_task(_task_id, _version=None):
        return {
            "id": "terminal_demo",
            "version": 1,
            "description": "terminal failure demo",
            "default_budget": {"steps": 3, "tool_calls": 3},
            "actions": _Actions,
            "setup": SimpleNamespace(setup=lambda _seed, _env: None),
            "validate": validate,
        }

    monkeypatch.setattr(runner, "load_task", fake_load_task)
    monkeypatch.setattr(runner, "load_agent", lambda _path: _Agent())

    result = runner.run("agents/fake.py", "terminal_demo@1", seed=0)
    assert result["success"] is False
    assert result["termination_reason"] == "logic_failure"
    assert result["failure_type"] == "logic_failure"
    assert result["failure_reason"] == "validator declared terminal"
