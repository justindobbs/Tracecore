"""Tests for the `agent-bench tasks validate` CLI command."""

from __future__ import annotations

import argparse
import json

from agent_bench import cli


def test_cli_tasks_validate_paths_and_registry(monkeypatch, capsys):
    def fake_validate_task_path(path):
        assert path.as_posix() == "tasks/sample"
        return ["missing manifest"]

    def fake_validate_registry_entries():
        return ["registry error"]

    monkeypatch.setattr(cli, "validate_task_path", fake_validate_task_path)
    monkeypatch.setattr(cli, "validate_registry_entries", fake_validate_registry_entries)

    args = argparse.Namespace(path=["tasks/sample"], registry=True)
    exit_code = cli._cmd_tasks_validate(args)

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is False
    assert "registry error" in payload["errors"]
    assert any("missing manifest" in err for err in payload["errors"])


def test_cli_tasks_validate_defaults_to_registry(monkeypatch, capsys):
    monkeypatch.setattr(cli, "validate_registry_entries", lambda: [])

    args = argparse.Namespace(path=None, registry=False)
    exit_code = cli._cmd_tasks_validate(args)

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"valid": True, "errors": []}
