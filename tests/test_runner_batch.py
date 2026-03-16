from __future__ import annotations

from agent_bench.runner import batch


def test_run_job_uses_direct_runner_when_timeout_not_set(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(agent, task_ref, seed):
        captured["run"] = (agent, task_ref, seed)
        return {"run_id": "direct", "success": True}

    monkeypatch.setattr("agent_bench.runner.runner.run", fake_run)
    monkeypatch.setattr("agent_bench.runner.runlog.persist_run", lambda result: captured.setdefault("persist", result))

    raw = batch._run_job({
        "agent": "agents/toy_agent.py",
        "task_ref": "filesystem_hidden_config@1",
        "seed": 2,
        "timeout": None,
        "_repo_root": "C:/repo",
    })

    assert raw["_ok"] is True
    assert raw["result"]["run_id"] == "direct"
    assert captured["run"] == ("agents/toy_agent.py", "filesystem_hidden_config@1", 2)
    assert captured["persist"] == {"run_id": "direct", "success": True}


def test_run_job_uses_isolated_runner_when_timeout_is_set(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run_isolated(agent, task_ref, *, seed, timeout):
        captured["isolated"] = (agent, task_ref, seed, timeout)
        return {"run_id": "isolated", "success": True}

    monkeypatch.setattr("agent_bench.runner.isolation.run_isolated", fake_run_isolated)
    monkeypatch.setattr("agent_bench.runner.runlog.persist_run", lambda result: captured.setdefault("persist", result))

    raw = batch._run_job({
        "agent": "agents/toy_agent.py",
        "task_ref": "filesystem_hidden_config@1",
        "seed": 4,
        "timeout": 15,
        "_repo_root": "C:/repo",
    })

    assert raw["_ok"] is True
    assert raw["result"]["run_id"] == "isolated"
    assert captured["isolated"] == ("agents/toy_agent.py", "filesystem_hidden_config@1", 4, 15)
    assert captured["persist"] == {"run_id": "isolated", "success": True}


def test_run_job_returns_timeout_error_payload(monkeypatch):
    def fake_run_isolated(agent, task_ref, *, seed, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr("agent_bench.runner.isolation.run_isolated", fake_run_isolated)

    raw = batch._run_job({
        "agent": "agents/toy_agent.py",
        "task_ref": "filesystem_hidden_config@1",
        "seed": 1,
        "timeout": 6,
        "_repo_root": "C:/repo",
    })

    assert raw["_ok"] is False
    assert raw["_error"] == "timed out"
    assert raw["_wall_clock_s"] >= 0


def test_run_job_returns_exception_payload(monkeypatch):
    def fake_run(agent, task_ref, seed):
        raise RuntimeError("boom")

    monkeypatch.setattr("agent_bench.runner.runner.run", fake_run)

    raw = batch._run_job({
        "agent": "agents/toy_agent.py",
        "task_ref": "filesystem_hidden_config@1",
        "seed": 1,
        "timeout": None,
        "_repo_root": "C:/repo",
    })

    assert raw["_ok"] is False
    assert raw["_error"] == "RuntimeError: boom"
    assert raw["_wall_clock_s"] >= 0
