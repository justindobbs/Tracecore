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
