"""Tests for the `agent-bench verify` command."""

from __future__ import annotations

import argparse
import json

from agent_bench import cli


def test_verify_defaults_to_latest_run(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_latest_run_id", lambda prefer_success=True: "abc")
    monkeypatch.setattr(cli, "_load_run_from_ref", lambda ref: {"run_id": ref})
    monkeypatch.setattr(cli, "verify_bundle", lambda *_: {"ok": True, "errors": []})
    monkeypatch.setattr(cli, "_load_cli_session", lambda: None)

    args = argparse.Namespace(
        latest=False,
        run=None,
        bundle=None,
        strict=False,
        strict_spec=False,
        prefer_success=True,
        json=True,
    )
    rc = cli._cmd_verify(args)
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["run"] == "abc"


def test_verify_fails_when_no_latest(monkeypatch):
    monkeypatch.setattr(cli, "_latest_run_id", lambda prefer_success=True: None)
    monkeypatch.setattr(cli, "_load_cli_session", lambda: None)

    args = argparse.Namespace(
        latest=True,
        run=None,
        bundle=None,
        strict=False,
        strict_spec=False,
        prefer_success=True,
        json=True,
    )
    rc = cli._cmd_verify(args)
    assert rc == 1


def test_verify_with_bundle_and_run_enforces_replay(monkeypatch, tmp_path, capsys):
    bundle_dir = tmp_path / "b"
    bundle_dir.mkdir()

    monkeypatch.setattr(cli, "_load_run_from_ref", lambda ref: {"run_id": ref})
    monkeypatch.setattr(cli, "verify_bundle", lambda *_: {"ok": True, "errors": []})
    monkeypatch.setattr(cli, "_load_cli_session", lambda: None)

    calls = {"checker": None}

    def fake_check(bundle, run_artifact):
        calls["checker"] = "check_replay"
        assert bundle == bundle_dir
        assert run_artifact["run_id"] == "abc"
        return {"ok": True, "errors": [], "mode": "replay"}

    monkeypatch.setattr(cli, "check_replay", fake_check)

    args = argparse.Namespace(
        latest=False,
        run="abc",
        bundle=str(bundle_dir),
        strict=False,
        strict_spec=False,
        prefer_success=True,
        json=False,
    )

    rc = cli._cmd_verify(args)
    assert rc == 0
    assert calls["checker"] == "check_replay"
    assert "OK  verify" in capsys.readouterr().err
