"""Tests for the `agent-bench baseline` CLI command."""

from __future__ import annotations

import argparse
import json

from agent_bench import cli


def test_cli_baseline_prints_json_and_passes_through_filters(monkeypatch, capsys):
    captured_kwargs: dict[str, tuple | None] = {}

    def fake_build_baselines(*, agent=None, task_ref=None, max_runs=None):
        captured_kwargs["values"] = (agent, task_ref, max_runs)
        return [
            {
                "agent": "agents/toy_agent.py",
                "task_ref": "filesystem_hidden_config@1",
                "success_rate": 1.0,
                "avg_steps": 12,
                "avg_tool_calls": 8,
                "runs": 3,
            }
        ]

    monkeypatch.setattr(cli, "build_baselines", fake_build_baselines)

    args = argparse.Namespace(agent="agents/toy_agent.py", task="filesystem_hidden_config@1", limit=50)
    exit_code = cli._cmd_baseline(args)

    assert exit_code == 0
    assert captured_kwargs["values"] == ("agents/toy_agent.py", "filesystem_hidden_config@1", 50)

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload[0]["agent"] == "agents/toy_agent.py"
    assert payload[0]["runs"] == 3
