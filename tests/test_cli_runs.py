"""Tests for the `agent-bench runs list` CLI command."""

from __future__ import annotations

import argparse
import json

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
