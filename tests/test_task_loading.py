"""Task loader coverage."""

from agent_bench.tasks.loader import load_task


def test_load_filesystem_hidden_config():
    task = load_task("filesystem_hidden_config")
    assert task["id"] == "filesystem_hidden_config"
    assert callable(task["setup"].setup)
    assert callable(task["validate"].validate)


def test_load_rate_limited_api():
    task = load_task("rate_limited_api")
    assert task["id"] == "rate_limited_api"
    assert callable(task["setup"].setup)
    assert callable(task["validate"].validate)
