"""Tests for bundle CLI commands."""

from __future__ import annotations

import argparse
import json

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
