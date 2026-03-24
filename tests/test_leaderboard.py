from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_bench.leaderboard import build_submission_record, ingest_bundle


def _write_bundle(bundle_dir: Path, *, signed: bool = True, success: bool = True) -> Path:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": "run-123",
        "trace_id": "trace-123",
        "agent": "agents/toy_agent.py",
        "task_ref": "filesystem_hidden_config@1",
        "task_id": "filesystem_hidden_config",
        "version": 1,
        "seed": 0,
        "harness_version": "1.1.3",
        "started_at": "2026-03-24T00:00:00+00:00",
        "completed_at": "2026-03-24T00:00:01+00:00",
        "success": success,
        "termination_reason": "success" if success else "validator_failed",
        "failure_type": None if success else "logic_failure",
        "failure_reason": None if success else "incorrect output",
        "steps_used": 3,
        "tool_calls_used": 3,
        "trace_entry_count": 3,
        "sandbox": {"filesystem_roots": ["/app"], "network_hosts": []},
    }
    validator = {
        "success": success,
        "termination_reason": manifest["termination_reason"],
        "failure_type": manifest["failure_type"],
        "failure_reason": manifest["failure_reason"],
        "metrics": {"steps_used": 3, "tool_calls_used": 3},
    }
    signature = {
        "signed_file": "integrity.sha256",
        "algorithm": "ed25519",
        "signature_hex": "abc123",
        "public_key_pem": "-----BEGIN PUBLIC KEY-----\nZmFrZQ==\n-----END PUBLIC KEY-----\n",
    }
    (bundle_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (bundle_dir / "validator.json").write_text(json.dumps(validator), encoding="utf-8")
    (bundle_dir / "tool_calls.jsonl").write_text(json.dumps({"step": 1}) + "\n", encoding="utf-8")
    (bundle_dir / "integrity.sha256").write_text("deadbeef  manifest.json\n", encoding="utf-8")
    if signed:
        (bundle_dir / "signature.json").write_text(json.dumps(signature), encoding="utf-8")
    return bundle_dir


def test_build_submission_record_requires_signed_verified_bundle(monkeypatch, tmp_path: Path) -> None:
    bundle_dir = _write_bundle(tmp_path / "bundle", signed=False)
    monkeypatch.setattr("agent_bench.leaderboard.verify_bundle", lambda path: {"ok": True, "errors": []})

    with pytest.raises(ValueError, match="signed"):
        build_submission_record(bundle_dir)


def test_build_submission_record_rejects_failed_verify(monkeypatch, tmp_path: Path) -> None:
    bundle_dir = _write_bundle(tmp_path / "bundle")
    monkeypatch.setattr("agent_bench.leaderboard.verify_bundle", lambda path: {"ok": False, "errors": ["hash mismatch"]})

    with pytest.raises(ValueError, match="verification failed"):
        build_submission_record(bundle_dir)


def test_ingest_bundle_persists_submission_and_index(monkeypatch, tmp_path: Path) -> None:
    bundle_dir = _write_bundle(tmp_path / "bundle")
    monkeypatch.setattr("agent_bench.leaderboard.verify_bundle", lambda path: {"ok": True, "errors": []})

    dest_root = tmp_path / "deliverables" / "leaderboard"
    report = ingest_bundle(bundle_dir, dest_root=dest_root)

    assert report["ok"] is True
    submission_file = Path(report["submission_file"])
    index_file = Path(report["index_file"])
    assert submission_file.exists()
    assert index_file.exists()

    submission = json.loads(submission_file.read_text(encoding="utf-8"))
    assert submission["run"]["run_id"] == "run-123"
    assert submission["run"]["agent"] == "agents/toy_agent.py"
    assert submission["provenance"]["signature_algorithm"] == "ed25519"
    assert submission["verify_report"]["ok"] is True

    index = json.loads(index_file.read_text(encoding="utf-8"))
    assert index["version"] == 1
    assert len(index["submissions"]) == 1
    assert index["submissions"][0]["run_id"] == "run-123"


def test_ingest_bundle_replaces_existing_run_entry(monkeypatch, tmp_path: Path) -> None:
    bundle_dir = _write_bundle(tmp_path / "bundle")
    monkeypatch.setattr("agent_bench.leaderboard.verify_bundle", lambda path: {"ok": True, "errors": []})

    dest_root = tmp_path / "deliverables" / "leaderboard"
    first = ingest_bundle(bundle_dir, dest_root=dest_root)
    assert first["ok"] is True

    report = ingest_bundle(bundle_dir, dest_root=dest_root)
    assert report["ok"] is True

    index = json.loads((dest_root / "index.json").read_text(encoding="utf-8"))
    assert len(index["submissions"]) == 1
    assert index["submissions"][0]["run_id"] == "run-123"
