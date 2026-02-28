"""Golden run artifact schema assertions."""

from __future__ import annotations

from agent_bench.runner.runner import run


REQUIRED_TOP_LEVEL = {
    "run_id",
    "trace_id",
    "agent",
    "agent_ref",
    "task_ref",
    "task_id",
    "task_hash",
    "version",
    "seed",
    "success",
    "failure_type",
    "failure_reason",
    "termination_reason",
    "steps_used",
    "tool_calls_used",
    "harness_version",
    "spec_version",
    "runtime_identity",
    "budgets",
    "artifact_hash",
    "started_at",
    "completed_at",
    "sandbox",
    "action_trace",
}

TRACE_ENTRY_FIELDS = {
    "step",
    "action_ts",
    "observation",
    "action",
    "result",
    "io_audit",
    "budget_after_step",
    "budget_delta",
}

OBSERVATION_FIELDS = {"step", "task", "budget_remaining"}


def _run_reference() -> dict:
    return run("agents/toy_agent.py", "filesystem_hidden_config@1", seed=42)


def test_run_artifact_includes_required_fields():
    result = _run_reference()
    missing = REQUIRED_TOP_LEVEL.difference(result.keys())
    assert not missing, f"missing keys: {sorted(missing)}"
    assert isinstance(result["action_trace"], list) and result["action_trace"], "action_trace should be non-empty"


def test_action_trace_entries_capture_budget_and_audit_fields():
    result = _run_reference()
    entry = result["action_trace"][0]
    missing = TRACE_ENTRY_FIELDS.difference(entry.keys())
    assert not missing, f"trace entry missing keys: {sorted(missing)}"
    assert isinstance(entry["io_audit"], list)
    obs = entry["observation"]
    missing_obs = OBSERVATION_FIELDS.difference(obs.keys())
    assert not missing_obs, f"observation missing keys: {sorted(missing_obs)}"
