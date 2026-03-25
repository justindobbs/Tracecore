from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent_bench import cli


def test_leaderboard_submit_json_reports_ingested_submission(monkeypatch, tmp_path, capsys):
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    monkeypatch.setattr(
        cli,
        "ingest_leaderboard_bundle",
        lambda path: {
            "ok": True,
            "submission": {"run": {"run_id": "run-123", "agent": "agents/toy_agent.py", "task_ref": "filesystem_hidden_config@1"}},
            "submission_file": str(tmp_path / "submission.json"),
            "index_file": str(tmp_path / "index.json"),
        },
    )

    args = argparse.Namespace(bundle=str(bundle_dir), format="json")
    rc = cli._cmd_leaderboard_submit(args)

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["submission"]["run"]["run_id"] == "run-123"


def test_leaderboard_submit_failure_returns_nonzero(monkeypatch, tmp_path, capsys):
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    monkeypatch.setattr(cli, "ingest_leaderboard_bundle", lambda path: (_ for _ in ()).throw(ValueError("bundle verification failed")))

    args = argparse.Namespace(bundle=str(bundle_dir), format="json")
    rc = cli._cmd_leaderboard_submit(args)

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert any("bundle verification failed" in err for err in payload["errors"])


def test_leaderboard_show_returns_submission(monkeypatch, capsys):
    monkeypatch.setattr(cli, "list_leaderboard_submissions", lambda: [{"run_id": "run-123", "success": True, "agent": "agents/toy_agent.py", "task_ref": "filesystem_hidden_config@1"}])
    monkeypatch.setattr(cli, "load_leaderboard_submission", lambda run_id: {"run": {"run_id": run_id}})

    args = argparse.Namespace(show="run-123")
    rc = cli._cmd_leaderboard(args)

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run"]["run_id"] == "run-123"


def test_leaderboard_list_text_outputs_rows(monkeypatch, capsys):
    monkeypatch.setattr(cli, "list_leaderboard_submissions", lambda: [{"run_id": "run-123", "success": True, "agent": "agents/toy_agent.py", "task_ref": "filesystem_hidden_config@1"}])

    args = argparse.Namespace(show=None)
    rc = cli._cmd_leaderboard(args)

    assert rc == 0
    out = capsys.readouterr().out
    assert "run-123" in out
    assert "filesystem_hidden_config@1" in out
