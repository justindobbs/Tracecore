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
