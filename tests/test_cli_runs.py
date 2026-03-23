"""Tests for the `agent-bench runs list` CLI command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from agent_bench import cli


def test_cli_runs_list_filters_and_outputs_json(monkeypatch, capsys):
    captured_kwargs: dict[str, tuple | None] = {}

    def fake_list_runs(**kwargs):
        captured_kwargs["values"] = kwargs
        return [
            {
                "run_id": "abc",
                "agent": "agents/toy_agent.py",
                "task_ref": "filesystem_hidden_config@1",
                "seed": 42,
                "failure_type": "invalid_action",
            }
        ]

    monkeypatch.setattr(cli, "list_runs", fake_list_runs)

    args = argparse.Namespace(
        agent="agents/toy_agent.py",
        task="filesystem_hidden_config@1",
        limit=5,
        failure_type="invalid_action",
    )
    exit_code = cli._cmd_runs_list(args)

    assert exit_code == 0
    assert captured_kwargs["values"] == {
        "agent": "agents/toy_agent.py",
        "task_ref": "filesystem_hidden_config@1",
        "limit": 5,
        "failure_type": "invalid_action",
    }

    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["failure_type"] == "invalid_action"


def test_cli_run_replay_defaults_and_allows_overrides(monkeypatch, capsys):
    fake_artifact = {
        "agent": "agents/toy_agent.py",
        "task_ref": "filesystem_hidden_config@1",
        "seed": 7,
    }

    def fake_load_run(run_id):
        assert run_id == "abc"
        return fake_artifact

    captured_runs: list[tuple] = []

    def fake_run(agent, task, *, seed, enable_reasoning_benchmark=False):
        captured_runs.append((agent, task, seed, enable_reasoning_benchmark))
        return {"run_id": "new", "agent": agent, "task_ref": task, "seed": seed}

    def fake_persist(result):
        return None

    monkeypatch.setattr(cli, "load_run", fake_load_run)
    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli, "persist_run", fake_persist)

    # Defaults from artifact
    args = argparse.Namespace(
        agent=None,
        task=None,
        seed=None,
        replay="abc",
        replay_bundle=None,
        strict=False,
        strict_spec=False,
        record=False,
        reasoning_benchmark=False,
        timeout=None,
        from_config=None,
        _config=None,
    )
    exit_code = cli._cmd_run(args)
    assert exit_code == 0
    assert captured_runs[-1] == (
        fake_artifact["agent"],
        fake_artifact["task_ref"],
        fake_artifact["seed"],
        False,
    )

    # Overrides applied
    args_override = argparse.Namespace(
        agent="custom.py",
        task="t@1",
        seed=99,
        replay="abc",
        replay_bundle=None,
        strict=False,
        strict_spec=False,
        record=False,
        reasoning_benchmark=False,
        timeout=None,
        from_config=None,
        _config=None,
    )
    exit_code = cli._cmd_run(args_override)
    assert exit_code == 0
    assert captured_runs[-1] == ("custom.py", "t@1", 99, False)


def test_cmd_run_strict_spec_failure_returns_nonzero(monkeypatch, capsys):
    result = {
        "run_id": "abc123",
        "trace_id": "abc123",
        "agent": "agents/toy_agent.py",
        "task_ref": "filesystem_hidden_config@1",
        "task_id": "filesystem_hidden_config",
        "version": 1,
        "seed": 0,
        "success": True,
        "termination_reason": "success",
        "failure_type": None,
        "failure_reason": None,
        "steps_used": 1,
        "tool_calls_used": 1,
    }

    monkeypatch.setattr(cli, "_resolve_run_inputs", lambda args, config: ("agents/toy_agent.py", "filesystem_hidden_config@1", 0))
    monkeypatch.setattr(cli, "_run_with_timeout", lambda *args, **kwargs: result)
    monkeypatch.setattr(cli, "persist_run", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "_session_after_run", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "_print_run_summary", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "_maybe_print_star_nudge", lambda: None)

    import agent_bench.runner.spec_check as spec_check
    monkeypatch.setattr(
        spec_check,
        "check_spec_compliance",
        lambda _result: {"ok": False, "errors": ["spec: artifact_hash missing"], "mode": "strict-spec"},
    )

    args = argparse.Namespace(
        agent="agents/toy_agent.py",
        task="filesystem_hidden_config@1",
        seed=0,
        replay=None,
        replay_bundle=None,
        strict=False,
        strict_spec=True,
        record=False,
        timeout=None,
        _config=None,
    )

    rc = cli._cmd_run(args)
    assert rc == 1
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["run_id"] == "abc123"
    assert "[STRICT-SPEC FAILED]" in captured.err
    assert "spec: artifact_hash missing" in captured.err


def test_run_with_timeout_uses_direct_runner_when_timeout_is_none(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(agent, task, *, seed, enable_reasoning_benchmark=False):
        captured["call"] = (agent, task, seed, enable_reasoning_benchmark)
        return {"run_id": "direct"}

    monkeypatch.setattr(cli, "run", fake_run)

    result = cli._run_with_timeout("agents/toy_agent.py", "filesystem_hidden_config@1", 3, None)

    assert result == {"run_id": "direct"}
    assert captured["call"] == ("agents/toy_agent.py", "filesystem_hidden_config@1", 3, False)


def test_run_with_timeout_forwards_reasoning_flag_to_direct_runner(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(agent, task, *, seed, enable_reasoning_benchmark=False):
        captured["call"] = (agent, task, seed, enable_reasoning_benchmark)
        return {"run_id": "direct"}

    monkeypatch.setattr(cli, "run", fake_run)

    result = cli._run_with_timeout(
        "agents/toy_agent.py",
        "filesystem_hidden_config@1",
        3,
        None,
        enable_reasoning_benchmark=True,
    )

    assert result == {"run_id": "direct"}
    assert captured["call"] == ("agents/toy_agent.py", "filesystem_hidden_config@1", 3, True)


def test_run_with_timeout_uses_isolated_runner_when_timeout_is_set(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run_isolated(agent, task, *, seed, timeout, enable_reasoning_benchmark=False):
        captured["call"] = (agent, task, seed, timeout, enable_reasoning_benchmark)
        return {"run_id": "isolated"}

    monkeypatch.setattr(cli, "run_isolated", fake_run_isolated)

    result = cli._run_with_timeout("agents/toy_agent.py", "filesystem_hidden_config@1", 5, 12)

    assert result == {"run_id": "isolated"}
    assert captured["call"] == ("agents/toy_agent.py", "filesystem_hidden_config@1", 5, 12, False)


def test_run_with_timeout_forwards_reasoning_flag_to_isolated_runner(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run_isolated(agent, task, *, seed, timeout, enable_reasoning_benchmark=False):
        captured["call"] = (agent, task, seed, timeout, enable_reasoning_benchmark)
        return {"run_id": "isolated"}

    monkeypatch.setattr(cli, "run_isolated", fake_run_isolated)

    result = cli._run_with_timeout(
        "agents/toy_agent.py",
        "filesystem_hidden_config@1",
        5,
        12,
        enable_reasoning_benchmark=True,
    )

    assert result == {"run_id": "isolated"}
    assert captured["call"] == ("agents/toy_agent.py", "filesystem_hidden_config@1", 5, 12, True)


def test_cmd_run_forwards_reasoning_flag(monkeypatch, capsys):
    captured: dict[str, object] = {}
    result = {"run_id": "abc123", "task_ref": "filesystem_hidden_config@1", "failure_type": None}

    monkeypatch.setattr(cli, "_resolve_run_inputs", lambda args, config: ("agents/toy_agent.py", "filesystem_hidden_config@1", 0))

    def fake_run_with_timeout(agent, task, seed, timeout, *, enable_reasoning_benchmark=False):
        captured["call"] = (agent, task, seed, timeout, enable_reasoning_benchmark)
        return result

    monkeypatch.setattr(cli, "_run_with_timeout", fake_run_with_timeout)
    monkeypatch.setattr(cli, "persist_run", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "_session_after_run", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "_print_run_summary", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "_maybe_print_star_nudge", lambda: None)

    args = argparse.Namespace(
        agent="agents/toy_agent.py",
        task="filesystem_hidden_config@1",
        seed=0,
        replay=None,
        replay_bundle=None,
        strict=False,
        strict_spec=False,
        record=False,
        reasoning_benchmark=True,
        timeout=None,
        from_config=None,
        _config=None,
    )

    rc = cli._cmd_run(args)
    assert rc == 0
    assert captured["call"] == ("agents/toy_agent.py", "filesystem_hidden_config@1", 0, None, True)
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == "abc123"


def test_run_with_timeout_converts_timeout_error_to_system_exit(monkeypatch):
    def fake_run_isolated(agent, task, *, seed, timeout, enable_reasoning_benchmark=False):
        raise TimeoutError("too slow")

    monkeypatch.setattr(cli, "run_isolated", fake_run_isolated)

    try:
        cli._run_with_timeout("agents/toy_agent.py", "filesystem_hidden_config@1", 7, 9)
    except TimeoutError as exc:
        assert str(exc) == "too slow"
    else:
        raise AssertionError("expected TimeoutError")


def test_run_with_timeout_propagates_non_timeout_errors_from_isolated_runner(monkeypatch):
    def fake_run_isolated(agent, task, *, seed, timeout, enable_reasoning_benchmark=False):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "run_isolated", fake_run_isolated)

    try:
        cli._run_with_timeout("agents/toy_agent.py", "filesystem_hidden_config@1", 1, 4)
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("expected RuntimeError")


def test_cmd_init_openai_agents_creates_scaffold_files(tmp_path, capsys):
    class _Console:
        def print(self, *args, **kwargs):
            return None

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setitem(__import__("sys").modules, "rich.console", type("_M", (), {"Console": _Console}))
    args = argparse.Namespace(
        path=str(tmp_path),
        force=False,
        package_name="sample_app",
        task_id="sample_openai_task",
        task_dir=None,
        agent_name="sample_openai_adapter",
    )

    rc = cli._cmd_init_openai_agents(args)

    assert rc == 0
    assert (tmp_path / "agent-bench.toml").exists()
    assert (tmp_path / "agents" / "sample_openai_adapter.py").exists()
    assert (tmp_path / "tasks" / "sample_openai_task" / "task.toml").exists()
    assert (tmp_path / "tasks" / "sample_openai_task" / "setup.py").exists()
    assert (tmp_path / "tasks" / "sample_openai_task" / "actions.py").exists()
    assert (tmp_path / "tasks" / "sample_openai_task" / "validate.py").exists()
    assert (tmp_path / "sample_app" / "tracecore_tasks.py").exists()
    monkeypatch.undo()
    assert (tmp_path / "TRACECORE_OPENAI_AGENTS_INIT.md").exists()

    agent_text = (tmp_path / "agents" / "sample_openai_adapter.py").read_text(encoding="utf-8")
    assert "class SampleOpenaiAdapterAgent" in agent_text
    assert '"type": "set_output"' in agent_text

    task_text = (tmp_path / "tasks" / "sample_openai_task" / "task.toml").read_text(encoding="utf-8")
    assert 'id = "sample_openai_task"' in task_text
    assert 'suite = "openai_agents"' in task_text


def test_cmd_init_openai_agents_skips_existing_files_without_force(tmp_path, capsys):
    class _Console:
        def print(self, *args, **kwargs):
            return None

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setitem(__import__("sys").modules, "rich.console", type("_M", (), {"Console": _Console}))
    existing = tmp_path / "agent-bench.toml"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("original\n", encoding="utf-8")

    args = argparse.Namespace(
        path=str(tmp_path),
        force=False,
        package_name="sample_app",
        task_id="sample_openai_task",
        task_dir=None,
        agent_name="sample_openai_adapter",
    )

    rc = cli._cmd_init_openai_agents(args)

    assert rc == 0
    assert existing.read_text(encoding="utf-8") == "original\n"
    monkeypatch.undo()
