"""Regression tests for the SandboxedCodeAuditorAgent."""

from __future__ import annotations

from agent_bench.runner.runner import run


def test_sandboxed_code_auditor_agent_passes_task():
    result = run(
        "agents/sandboxed_code_auditor_agent.py",
        "sandboxed_code_auditor@1",
        seed=0,
    )

    assert result["task_id"] == "sandboxed_code_auditor"
    assert result["version"] == 1
    assert result["success"] is True
    assert result["tool_calls_used"] <= 10
    assert result["steps_used"] <= 10


def test_sandboxed_code_auditor_agent_passes_alternate_seed():
    result = run(
        "agents/sandboxed_code_auditor_agent.py",
        "sandboxed_code_auditor@1",
        seed=42,
    )

    assert result["success"] is True
    assert result["failure_type"] is None
