"""Regression tests for the RunbookVerifierAgent."""

from __future__ import annotations

from agent_bench.runner.runner import run


def test_runbook_verifier_agent_passes_task():
    result = run(
        "agents/runbook_verifier_agent.py",
        "runbook_verifier@1",
        seed=0,
    )

    assert result["task_id"] == "runbook_verifier"
    assert result["version"] == 1
    assert result["success"] is True
    assert result["tool_calls_used"] <= 10
    assert result["steps_used"] <= 10


def test_autogen_rate_limit_agent_does_not_emit_rate_limit_only_action_on_runbook_task():
    result = run(
        "agents/autogen_rate_limit_agent.py",
        "runbook_verifier@1",
        seed=0,
    )

    trace = result.get("action_trace") or []
    assert trace, "expected at least one trace entry"
    first_action = (trace[0].get("action") or {}).get("type")
    assert first_action != "get_client_config"
