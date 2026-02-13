"""Integration test to ensure the chain agent solves the chain task."""

from agent_bench.runner.runner import run


def test_chain_agent_succeeds_on_chain_task():
    result = run("agents/chain_agent.py", "rate_limited_chain@1", seed=7)
    assert result["success"] is True
    assert result["termination_reason"] == "success"
    assert result["failure_reason"] is None
    assert result["failure_type"] is None
