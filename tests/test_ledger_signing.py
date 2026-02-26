"""Tests for agent_bench.ledger.signing and related ledger helpers."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agent_bench.ledger.signing import (
    load_public_key_from_file,
    pubkey_fingerprint,
    sign_bundle,
    sign_bytes,
    sign_registry,
    verify_bundle_signature,
    verify_bytes,
    verify_registry_signature,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def keypair():
    """Generate a fresh Ed25519 keypair for each test."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture()
def sample_bundle(tmp_path: Path) -> Path:
    """Write a minimal bundle directory with the required files."""
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "manifest.json").write_text(json.dumps({"run_id": "abc123", "success": True}))
    (bundle_dir / "tool_calls.jsonl").write_text(json.dumps({"step": 1, "action": "read_file", "result": "ok"}) + "\n")
    (bundle_dir / "validator.json").write_text(json.dumps({"success": True}))
    return bundle_dir


@pytest.fixture()
def sample_registry() -> dict:
    return {
        "version": 1,
        "entries": [
            {
                "agent": "agents/toy_agent.py",
                "suite": "core",
                "tasks": [{"task_ref": "filesystem_hidden_config@1", "success_rate": 1.0, "avg_steps": 4.0}],
            }
        ],
    }


# ---------------------------------------------------------------------------
# sign_bytes / verify_bytes
# ---------------------------------------------------------------------------


def test_sign_verify_roundtrip(keypair):
    priv, pub = keypair
    data = b"hello tracecore"
    sig = sign_bytes(data, priv)
    assert verify_bytes(data, sig, pub)


def test_verify_wrong_data_fails(keypair):
    priv, pub = keypair
    sig = sign_bytes(b"original", priv)
    assert not verify_bytes(b"tampered", sig, pub)


def test_verify_wrong_key_fails():
    priv_a = Ed25519PrivateKey.generate()
    priv_b = Ed25519PrivateKey.generate()
    sig = sign_bytes(b"data", priv_a)
    assert not verify_bytes(b"data", sig, priv_b.public_key())


def test_verify_corrupted_signature_fails(keypair):
    priv, pub = keypair
    sig = sign_bytes(b"data", priv)
    corrupted = sig[:-4] + "AAAA"
    assert not verify_bytes(b"data", corrupted, pub)


# ---------------------------------------------------------------------------
# pubkey_fingerprint
# ---------------------------------------------------------------------------


def test_fingerprint_length(keypair):
    _, pub = keypair
    fp = pubkey_fingerprint(pub)
    assert len(fp) == 16
    assert fp.isalnum()


def test_fingerprint_deterministic(keypair):
    _, pub = keypair
    assert pubkey_fingerprint(pub) == pubkey_fingerprint(pub)


def test_different_keys_different_fingerprints():
    pub_a = Ed25519PrivateKey.generate().public_key()
    pub_b = Ed25519PrivateKey.generate().public_key()
    assert pubkey_fingerprint(pub_a) != pubkey_fingerprint(pub_b)


# ---------------------------------------------------------------------------
# sign_bundle / verify_bundle_signature
# ---------------------------------------------------------------------------


def test_sign_bundle_returns_provenance(keypair, sample_bundle):
    priv, _ = keypair
    provenance = sign_bundle(sample_bundle, priv)
    assert "bundle_sha256" in provenance
    assert "bundle_signature" in provenance
    assert "signed_at" in provenance
    assert len(provenance["bundle_sha256"]) == 64  # hex SHA-256


def test_verify_bundle_roundtrip(keypair, sample_bundle):
    priv, pub = keypair
    provenance = sign_bundle(sample_bundle, priv)
    ok = verify_bundle_signature(
        sample_bundle,
        provenance["bundle_signature"],
        provenance["bundle_sha256"],
        pub,
    )
    assert ok


def test_verify_bundle_tampered_file_fails(keypair, sample_bundle):
    priv, pub = keypair
    provenance = sign_bundle(sample_bundle, priv)
    (sample_bundle / "manifest.json").write_text(json.dumps({"run_id": "tampered"}))
    ok = verify_bundle_signature(
        sample_bundle,
        provenance["bundle_signature"],
        provenance["bundle_sha256"],
        pub,
    )
    assert not ok


def test_verify_bundle_wrong_expected_hash(keypair, sample_bundle):
    priv, pub = keypair
    provenance = sign_bundle(sample_bundle, priv)
    ok = verify_bundle_signature(
        sample_bundle,
        provenance["bundle_signature"],
        "0" * 64,
        pub,
    )
    assert not ok


# ---------------------------------------------------------------------------
# sign_registry / verify_registry_signature
# ---------------------------------------------------------------------------


def test_sign_registry_adds_fields(keypair, sample_registry):
    priv, _ = keypair
    provenance = sign_registry(sample_registry, priv)
    assert "ledger_sha256" in provenance
    assert "ledger_signature" in provenance
    assert "signed_at" in provenance
    assert "signing_pubkey_id" in provenance


def test_verify_registry_roundtrip(keypair, sample_registry):
    priv, pub = keypair
    provenance = sign_registry(sample_registry, priv)
    sample_registry.update(provenance)
    assert verify_registry_signature(sample_registry, pub)


def test_verify_registry_tampered_entry_fails(keypair, sample_registry):
    priv, pub = keypair
    provenance = sign_registry(sample_registry, priv)
    sample_registry.update(provenance)
    sample_registry["entries"][0]["suite"] = "tampered"
    assert not verify_registry_signature(sample_registry, pub)


def test_verify_registry_missing_signature_fails(keypair, sample_registry):
    _, pub = keypair
    assert not verify_registry_signature(sample_registry, pub)


def test_verify_registry_wrong_key(sample_registry):
    priv_a = Ed25519PrivateKey.generate()
    priv_b = Ed25519PrivateKey.generate()
    provenance = sign_registry(sample_registry, priv_a)
    sample_registry.update(provenance)
    assert not verify_registry_signature(sample_registry, priv_b.public_key())


# ---------------------------------------------------------------------------
# Committed public key
# ---------------------------------------------------------------------------


def test_committed_pubkey_loads():
    pub = load_public_key_from_file()
    assert pub is not None
    fp = pubkey_fingerprint(pub)
    assert len(fp) == 16


def test_committed_pubkey_is_ed25519():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    pub = load_public_key_from_file()
    assert isinstance(pub, Ed25519PublicKey)
