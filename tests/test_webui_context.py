"""Tests for FastAPI template context helpers."""

from __future__ import annotations

from pathlib import Path
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
    assert "pairings" in ctx
    assert all("name" in p and "last_run_id" in p for p in ctx["pairings"])


def test_build_plugin_registry_handles_large_mixed_task_set(tmp_path, monkeypatch):
    tasks = [
        {
            "id": f"plugin_task_{idx}",
            "version": 1,
            "ref": f"plugin_task_{idx}@1",
            "suite": "plugins",
            "description": f"Plugin task {idx}",
        }
        for idx in range(12)
    ]

    calls: list[tuple[str, int | None]] = []

    def fake_load_task(task_id: str, version: int | None = None):
        calls.append((task_id, version))
        if task_id.endswith(("3", "8")):
            raise RuntimeError(f"failed to load {task_id}")

        task_dir = tmp_path / task_id
        task_dir.mkdir(exist_ok=True)
        actions_path = task_dir / "actions.py"
        validate_path = task_dir / "validate.py"
        actions_path.write_text(
            "def action_schema():\n    return {'wait': []}\n\n"
            "def wait():\n    return {'ok': True}\n",
            encoding="utf-8",
        )
        validate_path.write_text(
            "def validate(env):\n    return {'ok': True}\n",
            encoding="utf-8",
        )
        actions_mod = webapp._build_plugin_registry.__globals__["__builtins__"]
        from agent_bench.tasks.loader import _load_module
        loaded_actions = _load_module(actions_path, f"{task_id}_actions")
        loaded_validate = _load_module(validate_path, f"{task_id}_validate")
        return {"actions": loaded_actions, "validate": loaded_validate}

    monkeypatch.setattr(webapp, "TASKS_ROOT", Path("__missing_tasks_root__"))
    monkeypatch.setattr(__import__("agent_bench.tasks.loader", fromlist=["load_task"]), "load_task", fake_load_task)

    registry = webapp._build_plugin_registry(tasks)

    assert len(registry) == len(tasks)
    assert [entry["ref"] for entry in registry] == [task["ref"] for task in tasks]

    failures = {entry["id"]: entry for entry in registry if entry["lint_ok"] is False}
    assert failures["plugin_task_3"]["lint_errors"] == ["failed to load plugin_task_3"]
    assert failures["plugin_task_8"]["lint_errors"] == ["failed to load plugin_task_8"]

    successful = [entry for entry in registry if entry["id"] not in {"plugin_task_3", "plugin_task_8"}]
    assert successful
    assert all(entry["source"] == "bundled" for entry in successful)
    assert all(entry["actions"] == ["action_schema", "wait"] for entry in successful)
    assert all(entry["lint_ok"] is True for entry in successful)
    assert calls == [(task["id"], task["version"]) for task in tasks]


def test_build_plugin_registry_marks_missing_validate_and_actions_as_lint_failures(tmp_path, monkeypatch):
    tasks = [
        {
            "id": "missing_validate",
            "version": 1,
            "ref": "missing_validate@1",
            "suite": "plugins",
            "description": "missing validate",
        },
        {
            "id": "missing_actions",
            "version": 1,
            "ref": "missing_actions@1",
            "suite": "plugins",
            "description": "missing actions",
        },
    ]

    actions_path = tmp_path / "missing_validate_actions.py"
    actions_path.write_text(
        "def action_schema():\n    return {'wait': []}\n\n"
        "def wait():\n    return {'ok': True}\n",
        encoding="utf-8",
    )
    from agent_bench.tasks.loader import _load_module
    actions_mod = _load_module(actions_path, "missing_validate_actions")

    calls: list[tuple[str, int | None]] = []

    def fake_load_task(task_id: str, version: int | None = None):
        calls.append((task_id, version))
        if task_id == "missing_validate" and version == 1:
            return {"actions": actions_mod, "validate": object()}
        return {"actions": None, "validate": None}

    monkeypatch.setattr(webapp, "TASKS_ROOT", Path("__missing_tasks_root__"))
    monkeypatch.setattr(__import__("agent_bench.tasks.loader", fromlist=["load_task"]), "load_task", fake_load_task)

    registry = webapp._build_plugin_registry(tasks)

    by_id = {entry["id"]: entry for entry in registry}
    assert by_id["missing_validate"]["lint_ok"] is False
    assert by_id["missing_validate"]["lint_errors"] == ["missing validate.validate()"]

    assert by_id["missing_actions"]["lint_ok"] is False
    assert by_id["missing_actions"]["lint_errors"] == ["missing actions module", "missing validate.validate()", "action_schema() not defined (warning)"]
    assert calls == [("missing_validate", 1), ("missing_actions", 1)]
