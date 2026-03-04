"""Smoke tests for bundle sign/verify flow.

Verifies that:
- sign_bundle() writes signature.json with expected fields
- verify_bundle() still passes after signing
- sign_bundle() fails gracefully without a signing key
- unsigned flows are not broken by the signing machinery
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_bench.runner.bundle import sign_bundle, verify_bundle, write_bundle


# ---------------------------------------------------------------------------
# Minimal synthetic run for bundle writing
# ---------------------------------------------------------------------------

def _make_result(run_id: str = "test_run_001") -> dict:
    return {
        "run_id": run_id,
        "trace_id": f"trace_{run_id}",
        "agent": "agents/toy_agent.py",
        "task_id": "filesystem_hidden_config",
        "task_ref": "filesystem_hidden_config@1",
        "version": 1,
        "seed": 0,
        "harness_version": "1.0.0",
        "started_at": "2026-03-01T00:00:00.000000+00:00",
        "completed_at": "2026-03-01T00:00:01.000000+00:00",
        "success": True,
        "termination_reason": "success",
        "failure_type": None,
        "failure_reason": None,
        "steps_used": 2,
        "tool_calls_used": 3,
        "wall_clock_elapsed_s": 1.0,
        "action_trace": [
            {"step": 1, "action": {"type": "read_file", "args": {}}, "result": {"ok": True}, "io_audit": []},
            {"step": 2, "action": {"type": "submit", "args": {}}, "result": {"ok": True}, "io_audit": []},
        ],
        "sandbox": {
            "filesystem_roots": ["/tmp"],
            "network_hosts": [],
        },
        "metrics": {},
    }


# ---------------------------------------------------------------------------
# Unsigned flow — verify_bundle must work without a signature
# ---------------------------------------------------------------------------

def test_write_and_verify_bundle_unsigned(tmp_path):
    result = _make_result()
    bundle_dir = write_bundle(result, dest=tmp_path)
    report = verify_bundle(bundle_dir)
    assert report["ok"] is True, report["errors"]
    assert not (bundle_dir / "signature.json").exists()


# ---------------------------------------------------------------------------
# sign_bundle without a key — must fail gracefully
# ---------------------------------------------------------------------------

def test_sign_bundle_no_key_returns_error(tmp_path):
    result = _make_result()
    bundle_dir = write_bundle(result, dest=tmp_path)
    report = sign_bundle(bundle_dir, key_path="/nonexistent/key.pem")
    assert report["ok"] is False
    assert report["signature_file"] is None
    assert len(report["errors"]) > 0


def test_sign_bundle_missing_integrity_file(tmp_path):
    empty_dir = tmp_path / "empty_bundle"
    empty_dir.mkdir()
    report = sign_bundle(empty_dir)
    assert report["ok"] is False
    assert any("integrity.sha256" in e for e in report["errors"])


# ---------------------------------------------------------------------------
# sign_bundle with a real key (skipped if cryptography not available)
# ---------------------------------------------------------------------------

def _generate_ed25519_key_pem() -> bytes:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PrivateFormat, NoEncryption,
    )
    key = Ed25519PrivateKey.generate()
    return key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("cryptography"),
    reason="cryptography package not installed",
)
def test_sign_bundle_with_valid_key(tmp_path):
    key_pem = _generate_ed25519_key_pem()
    key_file = tmp_path / "test_key.pem"
    key_file.write_bytes(key_pem)

    result = _make_result()
    bundle_dir = write_bundle(result, dest=tmp_path)
    report = sign_bundle(bundle_dir, key_path=str(key_file))

    assert report["ok"] is True, report["errors"]
    assert report["signature_file"] is not None

    sig_path = Path(report["signature_file"])
    assert sig_path.exists()

    sig_doc = json.loads(sig_path.read_text())
    assert sig_doc["algorithm"] == "ed25519"
    assert "signature_hex" in sig_doc
    assert "public_key_pem" in sig_doc
    assert sig_doc["signed_file"] == "integrity.sha256"


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("cryptography"),
    reason="cryptography package not installed",
)
def test_verify_bundle_still_passes_after_signing(tmp_path):
    key_pem = _generate_ed25519_key_pem()
    key_file = tmp_path / "test_key.pem"
    key_file.write_bytes(key_pem)

    result = _make_result()
    bundle_dir = write_bundle(result, dest=tmp_path)
    sign_report = sign_bundle(bundle_dir, key_path=str(key_file))
    assert sign_report["ok"] is True

    verify_report = verify_bundle(bundle_dir)
    assert verify_report["ok"] is True, verify_report["errors"]


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("cryptography"),
    reason="cryptography package not installed",
)
def test_sign_bundle_signature_hex_is_valid_hex(tmp_path):
    key_pem = _generate_ed25519_key_pem()
    key_file = tmp_path / "test_key.pem"
    key_file.write_bytes(key_pem)

    result = _make_result()
    bundle_dir = write_bundle(result, dest=tmp_path)
    report = sign_bundle(bundle_dir, key_path=str(key_file))
    assert report["ok"] is True

    sig_doc = json.loads((bundle_dir / "signature.json").read_text())
    hex_str = sig_doc["signature_hex"]
    assert all(c in "0123456789abcdef" for c in hex_str)
    assert len(hex_str) == 128
