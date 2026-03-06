"""Tests for the `agent-bench runs migrate` CLI command."""

from __future__ import annotations

import argparse
import json

from agent_bench import cli


def test_cli_runs_migrate_dry_run_returns_nonzero_when_changes_needed(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "_cmd_runs_migrate",
        cli._cmd_runs_migrate,
    )
    import agent_bench.runner.migration as migration
    monkeypatch.setattr(
        migration,
        "migrate_run_directory",
        lambda root, write=False: {
            "ok": True,
            "root": str(root),
            "files": [{"path": "legacy.json", "changed": True}],
            "changed": 1,
            "errors": [],
        },
    )

    args = argparse.Namespace(root=None, write=False)
    rc = cli._cmd_runs_migrate(args)
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["changed"] == 1
    assert payload["write"] is False



def test_cli_runs_migrate_write_returns_zero_when_rewritten(monkeypatch, capsys, tmp_path):
    import agent_bench.runner.migration as migration
    monkeypatch.setattr(
        migration,
        "migrate_run_directory",
        lambda root, write=False: {
            "ok": True,
            "root": str(root),
            "files": [{"path": "legacy.json", "changed": True}],
            "changed": 1,
            "errors": [],
        },
    )

    args = argparse.Namespace(root=str(tmp_path), write=True)
    rc = cli._cmd_runs_migrate(args)
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["write"] is True
    assert payload["changed"] == 1
