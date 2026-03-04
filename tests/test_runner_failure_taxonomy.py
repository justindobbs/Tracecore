"""Regression tests for runner failure taxonomy emission.

Covers the terminal validator path (logic_failure) and verifies that every
failure branch emits the correct failure_type from the canonical taxonomy.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from agent_bench.runner.runner import run


# ---------------------------------------------------------------------------
# Shared stubs
# ---------------------------------------------------------------------------

def _make_task(validate_result: dict, *, budget: dict | None = None) -> dict:
    """Build a minimal task dict with a controlled validator."""

    def _setup(seed, env):
        pass

    actions_mod = SimpleNamespace(
        set_env=lambda env: None,
        noop=lambda: {"ok": True},
    )

    validate_mod = SimpleNamespace(validate=lambda env: validate_result)

    return {
        "id": "stub_task",
        "suite": "test",
        "version": 1,
        "description": "Stub task for taxonomy tests.",
        "default_budget": budget or {"steps": 10, "tool_calls": 10},
        "deterministic": True,
        "setup": SimpleNamespace(setup=_setup),
        "actions": actions_mod,
        "validate": validate_mod,
    }


class _NeverSucceedsAgent:
    """Agent that always emits a valid noop action."""

    def reset(self, task_spec):
        pass

    def observe(self, observation):
        pass

    def act(self):
        return {"type": "noop", "args": {}}


class _ImmediatelyTerminalAgent:
    """Agent that emits a noop on step 1 so the validator runs immediately."""

    def reset(self, task_spec):
        pass

    def observe(self, observation):
        pass

    def act(self):
        return {"type": "noop", "args": {}}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_with_stubs(task: dict, agent) -> dict:
    with (
        patch("agent_bench.runner.runner.load_task", return_value=task),
        patch("agent_bench.runner.runner.load_agent", return_value=agent),
    ):
        return run("stub_agent.py", "stub_task@1", seed=0)


# ---------------------------------------------------------------------------
# Terminal validator → logic_failure (default)
# ---------------------------------------------------------------------------

def test_terminal_validator_emits_logic_failure_type():
    task = _make_task({"terminal": True})
    result = _run_with_stubs(task, _ImmediatelyTerminalAgent())
    assert result["success"] is False
    assert result["failure_type"] == "logic_failure"
    assert result["termination_reason"] == "logic_failure"


def test_terminal_validator_uses_message_as_failure_reason():
    task = _make_task({"terminal": True, "message": "wrong_value_submitted"})
    result = _run_with_stubs(task, _ImmediatelyTerminalAgent())
    assert result["failure_reason"] == "wrong_value_submitted"


def test_terminal_validator_uses_error_field_as_failure_reason():
    task = _make_task({"terminal": True, "error": "checksum_mismatch"})
    result = _run_with_stubs(task, _ImmediatelyTerminalAgent())
    assert result["failure_reason"] == "checksum_mismatch"


def test_terminal_validator_respects_explicit_failure_type():
    task = _make_task({"terminal": True, "failure_type": "logic_failure", "message": "bad_output"})
    result = _run_with_stubs(task, _ImmediatelyTerminalAgent())
    assert result["failure_type"] == "logic_failure"


def test_terminal_validator_respects_explicit_termination_reason():
    task = _make_task({
        "terminal": True,
        "termination_reason": "logic_failure",
        "failure_type": "logic_failure",
        "message": "bad_output",
    })
    result = _run_with_stubs(task, _ImmediatelyTerminalAgent())
    assert result["termination_reason"] == "logic_failure"


def test_terminal_validator_not_triggered_when_false():
    """terminal=False should not terminate the episode early."""
    # Validator never signals terminal; budget exhaustion terminates instead.
    task = _make_task({"terminal": False, "ok": False}, budget={"steps": 2, "tool_calls": 10})
    result = _run_with_stubs(task, _NeverSucceedsAgent())
    assert result["success"] is False
    assert result["termination_reason"] == "steps_exhausted"
    assert result["failure_type"] == "budget_exhausted"


def test_terminal_validator_invalid_failure_type_falls_back_to_taxonomy():
    task = _make_task({
        "terminal": True,
        "failure_type": "totally_invalid",
        "termination_reason": "logic_failure",
    })
    result = _run_with_stubs(task, _ImmediatelyTerminalAgent())
    assert result["failure_type"] == "logic_failure"


def test_terminal_validator_snapshot_preserved_in_metadata():
    task = _make_task({
        "terminal": True,
        "message": "bad_output",
        "termination_reason": "logic_failure",
    })
    result = _run_with_stubs(task, _ImmediatelyTerminalAgent())
    validator = result.get("validator")
    assert validator == {
        "ok": False,
        "terminal": True,
        "message": "bad_output",
        "failure_reason": "bad_output",
        "failure_type": "logic_failure",
        "termination_reason": "logic_failure",
    }


# ---------------------------------------------------------------------------
# Other failure taxonomy paths (regression guard)
# ---------------------------------------------------------------------------

def test_budget_exhausted_steps_emits_correct_taxonomy():
    task = _make_task({"ok": False}, budget={"steps": 1, "tool_calls": 10})
    result = _run_with_stubs(task, _NeverSucceedsAgent())
    assert result["failure_type"] == "budget_exhausted"
    assert result["termination_reason"] == "steps_exhausted"


def test_budget_exhausted_tool_calls_emits_correct_taxonomy():
    task = _make_task({"ok": False}, budget={"steps": 10, "tool_calls": 1})
    result = _run_with_stubs(task, _NeverSucceedsAgent())
    assert result["failure_type"] == "budget_exhausted"
    assert result["termination_reason"] == "tool_calls_exhausted"


def test_invalid_action_emits_correct_taxonomy():
    class _BadActionAgent:
        def reset(self, task_spec):
            pass

        def observe(self, obs):
            pass

        def act(self):
            return {"type": "nonexistent_action", "args": {}}

    task = _make_task({"ok": False})
    result = _run_with_stubs(task, _BadActionAgent())
    assert result["failure_type"] == "invalid_action"
    assert result["termination_reason"] == "invalid_action"
    assert result["failure_reason"] == "unknown_action"


def test_invalid_action_trace_is_not_empty():
    """Regression: invalid_action must record a trace entry so the UI does not
    show 'Trace is empty for this run.'"""

    class _BadActionAgent:
        def reset(self, task_spec):
            pass

        def observe(self, obs):
            pass

        def act(self):
            return {"type": "nonexistent_action", "args": {}}

    task = _make_task({"ok": False})
    result = _run_with_stubs(task, _BadActionAgent())
    trace = result.get("action_trace", [])
    assert len(trace) >= 1, "action_trace must contain the invalid step entry"
    entry = trace[0]
    assert entry["action"]["type"] == "nonexistent_action"
    assert entry["result"]["ok"] is False
    assert "error" in entry["result"]
    assert entry["io_audit"] == []


def test_success_has_no_failure_type():
    task = _make_task({"ok": True})
    result = _run_with_stubs(task, _ImmediatelyTerminalAgent())
    assert result["success"] is True
    assert result["failure_type"] is None
    assert result["failure_reason"] is None
    assert result["termination_reason"] == "success"
    assert result.get("validator") == {"ok": True}
