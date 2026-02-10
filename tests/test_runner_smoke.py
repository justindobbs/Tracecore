"""Runner smoke test."""

from openclaw_bench.runner.runner import run


def test_runner_smoke():
    result = run("agents/toy_agent.py", "filesystem_hidden_config@1", seed=42)
    assert result["task_id"] == "filesystem_hidden_config"
    assert result["version"] == 1
    assert result["success"] is True
