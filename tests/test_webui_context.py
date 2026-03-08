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


def test_template_context_summarizes_compare_diff(monkeypatch):
    fake_tasks = [
        {"id": "filesystem_hidden_config", "version": 1, "ref": "filesystem_hidden_config@1", "suite": "fs"}
    ]
    fake_agents = ["agents/toy_agent.py"]
    compare_diff = {
        "summary": {
            "same_agent": True,
            "same_task": True,
            "same_success": False,
            "steps": {"run_a": 2, "run_b": 3},
            "tool_calls": {"run_a": 1, "run_b": 4},
            "io_audit": {"added": 1, "removed": 0},
        },
        "taxonomy": {
            "same_failure_type": False,
            "same_termination_reason": False,
            "run_a": {"failure_type": None, "termination_reason": "success"},
            "run_b": {"failure_type": "logic_failure", "termination_reason": "validator_rejected"},
        },
        "budget_delta": {"steps": 1, "tool_calls": 3, "wall_clock_s": 2.5},
        "step_diffs": [
            {
                "step": 2,
                "run_a": {"action": {"type": "read_file"}, "result": {"ok": True}},
                "run_b": {"action": {"type": "set_output"}, "result": {"ok": False}},
                "io_audit_delta": {"added": [{"type": "fs", "path": "/tmp/out.txt"}], "removed": []},
            }
        ],
    }

    monkeypatch.setattr(webapp, "get_task_options", lambda: fake_tasks)
    monkeypatch.setattr(webapp, "get_agent_options", lambda: fake_agents)
    monkeypatch.setattr(webapp, "list_runs", lambda **kwargs: [])
    monkeypatch.setattr(webapp, "build_baselines", lambda **kwargs: [])
    monkeypatch.setattr(webapp, "list_pairings", lambda: [])
    monkeypatch.setattr(webapp, "load_latest_baseline", lambda: None)
    monkeypatch.setattr(webapp, "_build_plugin_registry", lambda tasks: [])

    ctx = webapp._template_context(SimpleNamespace(), selected_task=None, compare_diff=compare_diff)

    assert ctx["compare_delta"] == {
        "steps_a": 2,
        "steps_b": 3,
        "tools_a": 1,
        "tools_b": 4,
        "steps_delta": 1,
        "tools_delta": 3,
    }
    assert ctx["compare_changed_step_count"] == 1
    assert ctx["compare_io_step_count"] == 1
    assert ctx["compare_step_summary"] == [
        {
            "step": 2,
            "action_a": "read_file",
            "action_b": "set_output",
            "action_changed": True,
            "result_changed": True,
            "has_io_drift": True,
        }
    ]
    assert ctx["compare_taxonomy_summary"] == [
        {
            "label": "Failure type",
            "same": False,
            "run_a": "none",
            "run_b": "logic_failure",
        },
        {
            "label": "Termination reason",
            "same": False,
            "run_a": "success",
            "run_b": "validator_rejected",
        },
    ]
    assert ctx["compare_budget_badges"] == [
        {"label": "Steps", "value": 1, "kind": "pill-warn"},
        {"label": "Tool calls", "value": 3, "kind": "pill-warn"},
        {"label": "Wall", "value": 2.5, "suffix": "s", "kind": "pill-warn"},
    ]


def test_template_context_groups_local_and_bundled_assets(monkeypatch, tmp_path):
    fake_tasks = [
        {"id": "local_task", "version": 1, "ref": "local_task@1", "suite": "local", "description": "local task"},
        {"id": "bundled_task", "version": 1, "ref": "bundled_task@1", "suite": "bundled", "description": "bundled task"},
    ]
    fake_agents = ["agents/local_agent.py", "agent_bench/agents/reference_agent.py"]
    fake_plugin_registry = [
        {"id": "local_task", "ref": "local_task@1", "source": "local", "suite": "local", "version": 1},
        {"id": "bundled_task", "ref": "bundled_task@1", "source": "bundled", "suite": "bundled", "version": 1},
    ]

    local_tasks_root = tmp_path / "tasks"
    local_agents_root = tmp_path / "agents"
    (local_tasks_root / "local_task").mkdir(parents=True)
    local_agents_root.mkdir(parents=True)

    monkeypatch.setattr(webapp, "TASKS_ROOT", local_tasks_root)
    monkeypatch.setattr(webapp, "AGENTS_ROOT", local_agents_root)
    monkeypatch.setattr(webapp, "get_task_options", lambda: fake_tasks)
    monkeypatch.setattr(webapp, "get_agent_options", lambda: fake_agents)
    monkeypatch.setattr(webapp, "list_runs", lambda **kwargs: [])
    monkeypatch.setattr(webapp, "build_baselines", lambda **kwargs: [])
    monkeypatch.setattr(webapp, "list_pairings", lambda: [])
    monkeypatch.setattr(webapp, "load_latest_baseline", lambda: None)
    monkeypatch.setattr(webapp, "_build_plugin_registry", lambda tasks: fake_plugin_registry)

    ctx = webapp._template_context(SimpleNamespace(), selected_task=None)

    assert ctx["grouped_tasks"]["local"] == [fake_tasks[0]]
    assert ctx["grouped_tasks"]["bundled"] == [fake_tasks[1]]
    assert ctx["grouped_plugins"]["local"] == [fake_plugin_registry[0]]
    assert ctx["grouped_plugins"]["bundled"] == [fake_plugin_registry[1]]
    assert ctx["grouped_agents"]["local"] == ["agents/local_agent.py"]
    assert ctx["grouped_agents"]["bundled"] == ["agent_bench/agents/reference_agent.py"]


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
