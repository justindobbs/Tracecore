"""Tests for the multi-agent orchestration harness."""

from __future__ import annotations

import pytest

from agent_bench.agents.multi_agent_orchestrator import (
    MultiAgentOrchestrator,
    OrchestrationPlan,
    RoleContract,
    RosterEntry,
)
from agent_bench.runner import runner


class _StaticAgent:
    def __init__(self, action):
        self._action = action

    def reset(self, _task_spec):
        pass

    def observe(self, _observation):
        pass

    def act(self):
        return self._action


def test_orchestrator_enforces_role_contract():
    contract = RoleContract(
        name="Recon",
        description="Reads metadata",
        responsibilities=["Inspect README"],
        allowed_actions={"read_file"},
    )
    plan = OrchestrationPlan(
        roster=[RosterEntry(contract=contract, agent_factory=lambda: _StaticAgent({"type": "set_output"}))],
        initial_role="Recon",
    )
    orchestrator = MultiAgentOrchestrator(plan)
    orchestrator.reset({})
    orchestrator.observe(None)

    with pytest.raises(ValueError, match="disallowed action"):
        orchestrator.act()


def test_multi_role_agent_solves_security_triage():
    result = runner.run(
        "agent_bench/agents/multi_role_ops_agent.py",
        "security_incident_triage@1",
        seed=0,
    )
    assert result["success"] is True
    roles = [
        (entry.get("action") or {}).get("meta", {}).get("role")
        for entry in result.get("action_trace", [])
    ]
    assert "Recon" in roles
    assert "Executor" in roles
