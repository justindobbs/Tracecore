"""Tests for bundle CLI commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent_bench import cli


def test_bundle_seal_fails_when_latest_success_run_missing(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_latest_run_id", lambda prefer_success=True: "missing-success-run")

    def _missing(ref):
        raise FileNotFoundError(f"run artifact not found: {ref}")

    monkeypatch.setattr(cli, "_load_run_from_ref", _missing)

    args = argparse.Namespace(
        run=None,
        latest=True,
        sign=False,
        key=None,
        format="json",
    )

    rc = cli._cmd_bundle_seal(args)
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert any("run artifact not found: missing-success-run" in err for err in payload["errors"])


def test_bundle_seal_reports_verify_failure_after_write(monkeypatch, tmp_path, capsys):
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()

    monkeypatch.setattr(cli, "_load_run_from_ref", lambda ref: {"run_id": ref})
    monkeypatch.setattr(cli, "write_bundle", lambda run_artifact: bundle_dir)
    monkeypatch.setattr(cli, "verify_bundle", lambda path: {"ok": False, "errors": [f"hash mismatch in {path}"]})
    monkeypatch.setattr(cli, "_session_after_bundle", lambda **_kwargs: None)

    args = argparse.Namespace(
        run="abc",
        latest=False,
        sign=False,
        key=None,
        format="json",
    )

    rc = cli._cmd_bundle_seal(args)
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["bundle_dir"] == str(bundle_dir)
    assert payload["verify"]["ok"] is False
    assert payload["ok"] is False


def test_bundle_seal_reports_sign_failure(monkeypatch, tmp_path, capsys):
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()

    monkeypatch.setattr(cli, "_load_run_from_ref", lambda ref: {"run_id": ref})
    monkeypatch.setattr(cli, "write_bundle", lambda run_artifact: bundle_dir)
    monkeypatch.setattr(cli, "verify_bundle", lambda path: {"ok": True, "errors": []})
    monkeypatch.setattr(cli, "_session_after_bundle", lambda **_kwargs: None)

    import agent_bench.runner.bundle as bundle_mod
    monkeypatch.setattr(
        bundle_mod,
        "sign_bundle",
        lambda bundle_dir, key_path=None: {"ok": False, "signature_file": None, "errors": ["Signing key not found"]},
    )

    args = argparse.Namespace(
        run="abc",
        latest=False,
        sign=True,
        key="missing-key.pem",
        format="json",
    )

    rc = cli._cmd_bundle_seal(args)
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["verify"]["ok"] is True
    assert payload["sign"]["ok"] is False
    assert payload["ok"] is False
    assert any("Signing key not found" in err for err in payload["sign"]["errors"])
