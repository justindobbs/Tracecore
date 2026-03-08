"""Tests for the `agent-bench runs list` CLI command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

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

    def fake_run(agent, task, seed):
        captured_runs.append((agent, task, seed))
        return {"run_id": "new", "agent": agent, "task_ref": task, "seed": seed}

    def fake_persist(result):
        return None

    monkeypatch.setattr(cli, "load_run", fake_load_run)
    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli, "persist_run", fake_persist)

    # Defaults from artifact
    args = argparse.Namespace(agent=None, task=None, seed=None, replay="abc")
    exit_code = cli._cmd_run(args)
    assert exit_code == 0
    assert captured_runs[-1] == (
        fake_artifact["agent"],
        fake_artifact["task_ref"],
        fake_artifact["seed"],
    )

    # Overrides applied
    args_override = argparse.Namespace(agent="custom.py", task="t@1", seed=99, replay="abc")
    exit_code = cli._cmd_run(args_override)
    assert exit_code == 0
    assert captured_runs[-1] == ("custom.py", "t@1", 99)


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


def test_cmd_init_openai_agents_creates_scaffold_files(tmp_path, capsys):
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
    assert (tmp_path / "TRACECORE_OPENAI_AGENTS_INIT.md").exists()

    agent_text = (tmp_path / "agents" / "sample_openai_adapter.py").read_text(encoding="utf-8")
    assert "class SampleOpenaiAdapterAgent" in agent_text
    assert '"type": "set_output"' in agent_text

    task_text = (tmp_path / "tasks" / "sample_openai_task" / "task.toml").read_text(encoding="utf-8")
    assert 'id = "sample_openai_task"' in task_text
    assert 'suite = "openai_agents"' in task_text

    captured = capsys.readouterr()
    assert "Initialized" in captured.out
    assert "tracecore run --agent agents/sample_openai_adapter.py --task" in captured.out
    assert "sample_openai_task@1 --seed 0" in captured.out


def test_cmd_init_openai_agents_skips_existing_files_without_force(tmp_path, capsys):
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
    captured = capsys.readouterr()
    assert "Skipped (already exists)" in captured.out
