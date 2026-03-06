"""Bundle audit verification tests."""

from __future__ import annotations

from pathlib import Path

from agent_bench.runner.bundle import verify_bundle, write_bundle


def _base_result() -> dict:
    return {
        "run_id": "run123",
        "trace_id": "run123",
        "agent": "agents/stub.py",
        "task_ref": "stub_task@1",
        "task_id": "stub_task",
        "version": 1,
        "seed": 0,
        "harness_version": "0.0.0",
        "started_at": "2026-02-22T00:00:00+00:00",
        "completed_at": "2026-02-22T00:00:01+00:00",
        "success": True,
        "termination_reason": "success",
        "failure_type": None,
        "failure_reason": None,
        "steps_used": 1,
        "tool_calls_used": 1,
        "metrics": {"steps_used": 1, "tool_calls_used": 1},
        "action_trace": [
            {
                "step": 1,
                "action_ts": "2026-02-22T00:00:00+00:00",
                "observation": {},
                "action": {"type": "noop", "args": {}},
                "result": {"ok": True},
                "io_audit": [],
                "budget_after_step": {"steps": 0, "tool_calls": 0},
                "budget_delta": {"steps": 1, "tool_calls": 1},
            }
        ],
        "sandbox": {"filesystem_roots": ["/app"], "network_hosts": ["example.com"]},
    }


def test_verify_bundle_ok(tmp_path: Path) -> None:
    result = _base_result()
    bundle_dir = write_bundle(result, dest=tmp_path)
    report = verify_bundle(bundle_dir)
    assert report["ok"] is True


def test_verify_bundle_missing_sandbox_fails(tmp_path: Path) -> None:
    result = _base_result()
    result.pop("sandbox", None)
    bundle_dir = write_bundle(result, dest=tmp_path)
    report = verify_bundle(bundle_dir)
    assert report["ok"] is False
    assert any("sandbox" in err for err in report["errors"])


def test_verify_bundle_disallowed_io_fails(tmp_path: Path) -> None:
    result = _base_result()
    result["action_trace"][0]["io_audit"] = [{"type": "fs", "path": "/etc/passwd"}]
    bundle_dir = write_bundle(result, dest=tmp_path)
    report = verify_bundle(bundle_dir)
    assert report["ok"] is False
    assert any("outside allowlist" in err for err in report["errors"])


def test_verify_bundle_tampered_integrity_hash_fails(tmp_path: Path) -> None:
    result = _base_result()
    bundle_dir = write_bundle(result, dest=tmp_path)
    integrity_path = bundle_dir / "integrity.sha256"
    original = integrity_path.read_text(encoding="utf-8")
    tampered = original.replace("a", "b", 1) if "a" in original else ("0" + original[1:])
    integrity_path.write_text(tampered, encoding="utf-8")

    report = verify_bundle(bundle_dir)
    assert report["ok"] is False
    assert any("hash mismatch" in err for err in report["errors"])


def test_verify_bundle_malformed_integrity_line_fails(tmp_path: Path) -> None:
    result = _base_result()
    bundle_dir = write_bundle(result, dest=tmp_path)
    (bundle_dir / "integrity.sha256").write_text("not-a-valid-integrity-line\n", encoding="utf-8")

    report = verify_bundle(bundle_dir)
    assert report["ok"] is False
    assert any("malformed integrity line" in err for err in report["errors"])
