"""Tests for FastAPI template context helpers."""

from __future__ import annotations

from types import SimpleNamespace

from agent_bench.webui import app as webapp


def test_template_context_includes_recent_runs_and_baselines(monkeypatch):
    fake_tasks = [
        {"id": "filesystem_hidden_config", "version": 1, "ref": "filesystem_hidden_config@1", "suite": "fs"}
    ]
    fake_agents = ["agents/toy_agent.py"]
    fake_runs = [
        {
            "run_id": "abc",
            "agent": "agents/toy_agent.py",
            "task_ref": "filesystem_hidden_config@1",
            "seed": 42,
            "termination_reason": "success",
        }
    ]
    fake_baselines = [
        {
            "agent": "agents/toy_agent.py",
            "task_ref": "filesystem_hidden_config@1",
            "success_rate": 1.0,
            "avg_steps": 12,
            "avg_tool_calls": 6,
            "runs": 5,
        }
    ]

    monkeypatch.setattr(webapp, "get_task_options", lambda: fake_tasks)
    monkeypatch.setattr(webapp, "get_agent_options", lambda: fake_agents)
    def fake_list_runs(limit=8, agent=None, task_ref=None, failure_type=None):
        assert agent is None
        assert task_ref is None
        assert failure_type is None
        return fake_runs

    def fake_build_baselines(max_runs=400, agent=None, task_ref=None):
        assert agent is None
        assert task_ref is None
        return fake_baselines

    monkeypatch.setattr(webapp, "list_runs", fake_list_runs)
    monkeypatch.setattr(webapp, "build_baselines", fake_build_baselines)

    ctx = webapp._template_context(SimpleNamespace(), selected_task=None)

    assert ctx["tasks"] == fake_tasks
    assert ctx["agents"] == fake_agents
    assert ctx["recent_runs"] == fake_runs
    assert ctx["baselines"] == fake_baselines
    assert ctx["selected_task"] == "filesystem_hidden_config@1"
    assert ctx["selected_task_meta"]["id"] == "filesystem_hidden_config"
    assert "failure_types" in ctx
