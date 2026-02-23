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

    args = argparse.Namespace(
        agent="agents/toy_agent.py",
        task="filesystem_hidden_config@1",
        limit=50,
        export=None,
        compare=None,
        format="json",
    )
    exit_code = cli._cmd_baseline(args)

    assert exit_code == 0
    assert captured_kwargs["values"] == ("agents/toy_agent.py", "filesystem_hidden_config@1", 50)

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload[0]["agent"] == "agents/toy_agent.py"
    assert payload[0]["runs"] == 3


def test_cli_baseline_exports_when_requested(monkeypatch, tmp_path, capsys):
    rows = [
        {
            "agent": "agents/toy_agent.py",
            "task_ref": "filesystem_hidden_config@1",
            "success_rate": 1.0,
            "avg_steps": 12,
            "avg_tool_calls": 8,
            "runs": 3,
        }
    ]

    def fake_build_baselines(*, agent=None, task_ref=None, max_runs=None):
        return rows

    exports: list[str] = []

    def fake_export(data, *, path=None, metadata=None):
        file_path = tmp_path / "baseline.json"
        exports.append(str(file_path))
        return file_path

    monkeypatch.setattr(cli, "build_baselines", fake_build_baselines)
    monkeypatch.setattr(cli, "export_baseline", fake_export)

    args = argparse.Namespace(agent=None, task=None, limit=10, export="latest", compare=None, format="json")
    exit_code = cli._cmd_baseline(args)

    assert exit_code == 0
    assert exports, "export should have been invoked"
    payload = json.loads(capsys.readouterr().out)
    assert payload["rows"] == rows
    assert payload["export_path"] == exports[0]


def test_cli_baseline_compare_text_output_and_exit_code(monkeypatch, capsys):
    run_a = {"agent": "a.py", "task_ref": "task@1", "success": True, "action_trace": []}
    run_b = {"agent": "a.py", "task_ref": "task@1", "success": False, "action_trace": []}

    monkeypatch.setattr(cli, "load_run_artifact", lambda ref: run_a if ref == "a" else run_b)

    args = argparse.Namespace(agent=None, task=None, limit=10, export=None, compare=("a", "b"), format="text")
    exit_code = cli._cmd_baseline(args)

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "Compare: different" in out


def test_cli_baseline_compare_json_output(monkeypatch, capsys):
    run_a = {"agent": "a.py", "task_ref": "task@1", "success": True, "action_trace": []}
    run_b = {"agent": "a.py", "task_ref": "task@1", "success": True, "action_trace": []}

    monkeypatch.setattr(cli, "load_run_artifact", lambda ref: run_a if ref == "a" else run_b)

    diff = {
        "summary": {
            "same_agent": True,
            "same_task": True,
            "same_success": True,
            "steps": {"run_a": 1, "run_b": 2},
            "tool_calls": {"run_a": 1, "run_b": 2},
        },
        "step_diffs": [{"step": 1}],
    }

    monkeypatch.setattr(cli, "diff_runs", lambda *_: diff)

    args = argparse.Namespace(agent=None, task=None, limit=10, export=None, compare=("a", "b"), format="json", show_taxonomy=False)
    exit_code = cli._cmd_baseline(args)

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload == diff


def test_cli_baseline_compare_pretty_propagates_show_taxonomy(monkeypatch):
    run_a = {"agent": "a.py", "task_ref": "task@1", "success": True, "action_trace": []}
    run_b = {"agent": "a.py", "task_ref": "task@1", "success": False, "action_trace": []}

    monkeypatch.setattr(cli, "load_run_artifact", lambda ref: run_a if ref == "a" else run_b)
    monkeypatch.setattr(cli, "diff_runs", lambda *_: {"summary": {"same_agent": True, "same_task": True}, "step_diffs": []})

    captured = {}

    def fake_pretty(diff, exit_code, show_taxonomy):
        captured["args"] = (diff, exit_code, show_taxonomy)

    monkeypatch.setattr(cli, "_print_diff_pretty", fake_pretty)

    args = argparse.Namespace(agent=None, task=None, limit=10, export=None, compare=("a", "b"), format="pretty", show_taxonomy=True)
    exit_code = cli._cmd_baseline(args)

    assert exit_code in {0, 1, 2}
    assert captured["args"][2] is True
