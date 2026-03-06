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


def test_bundle_status_empty_text_reports_no_bundles(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    args = argparse.Namespace(format="text", limit=10)
    rc = cli._cmd_bundle_status(args)

    assert rc == 0
    assert "No bundles found under .agent_bench/baselines" in capsys.readouterr().err


def test_bundle_status_json_reports_mixed_bundle_states(monkeypatch, tmp_path, capsys):
    baselines = tmp_path / ".agent_bench" / "baselines"
    ok_bundle = baselines / "ok-bundle"
    bad_bundle = baselines / "bad-bundle"
    ok_bundle.mkdir(parents=True)
    bad_bundle.mkdir(parents=True)
    (ok_bundle / "signature.json").write_text("{}", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        cli,
        "verify_bundle",
        lambda path: {"ok": path.name == "ok-bundle", "errors": [] if path.name == "ok-bundle" else ["hash mismatch"]},
    )

    args = argparse.Namespace(format="json", limit=10)
    rc = cli._cmd_bundle_status(args)

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    bundles = {Path(entry["bundle_dir"]).name: entry for entry in payload["bundles"]}
    assert bundles["ok-bundle"]["ok"] is True
    assert bundles["ok-bundle"]["signed"] is True
    assert bundles["bad-bundle"]["ok"] is False
    assert bundles["bad-bundle"]["signed"] is False


def test_bundle_status_json_respects_limit_and_recency(monkeypatch, tmp_path, capsys):
    baselines = tmp_path / ".agent_bench" / "baselines"
    oldest = baselines / "oldest"
    middle = baselines / "middle"
    newest = baselines / "newest"
    oldest.mkdir(parents=True)
    middle.mkdir(parents=True)
    newest.mkdir(parents=True)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "verify_bundle", lambda path: {"ok": True, "errors": []})

    class _FakeDir:
        def __init__(self, path: Path, mtime: float):
            self._path = path
            self.name = path.name

            class _Stat:
                def __init__(self, value: float):
                    self.st_mtime = value

            self._stat = _Stat(mtime)

        def is_dir(self):
            return True

        def stat(self):
            return self._stat

        def __truediv__(self, other: str):
            return self._path / other

        def __fspath__(self):
            return str(self._path)

        def __str__(self):
            return str(self._path)

    fake_dirs = [
        _FakeDir(oldest, 100.0),
        _FakeDir(middle, 200.0),
        _FakeDir(newest, 300.0),
    ]
    baselines_resolved = str(baselines.resolve())
    monkeypatch.setattr(Path, "iterdir", lambda self: fake_dirs if str(self.resolve()) == baselines_resolved else [])

    args = argparse.Namespace(format="json", limit=2)
    rc = cli._cmd_bundle_status(args)

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    names = [Path(entry["bundle_dir"]).name for entry in payload["bundles"]]
    assert names == ["newest", "middle"]
