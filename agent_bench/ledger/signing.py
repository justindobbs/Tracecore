"""TraceCore Ledger — bundle and registry signing utilities.

Uses Ed25519 (via the ``cryptography`` package).  The public key is committed
to the repository at ``agent_bench/ledger/pubkey.pem``; the private key is
supplied only in CI via the ``TRACECORE_LEDGER_SIGNING_KEY`` environment
variable (base64-encoded PEM).

Public API
----------
sign_bundle(bundle_dir, private_key) -> dict
    Hash + sign a bundle directory, return provenance metadata.

sign_registry(registry: dict, private_key) -> dict
    Compute SHA-256 of the canonical registry JSON and sign it; return updated
    top-level metadata fields to merge into the registry dict.

verify_bundle_signature(bundle_dir, signature, expected_sha256, public_key) -> bool
    Verify a previously signed bundle.

verify_registry_signature(registry: dict, public_key) -> bool
    Verify the top-level signature embedded in a registry dict.

load_private_key(pem_b64: str)
    Decode a base64-encoded PEM private key (as stored in the CI secret).

load_public_key_from_file(path: Path)
    Load the committed Ed25519 public key from a PEM file.

pubkey_fingerprint(public_key) -> str
    Return a short hex fingerprint (first 16 chars of SHA-256 of the raw
    public bytes) for display purposes.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


PUBKEY_PATH = Path(__file__).parent / "pubkey.pem"

_SIGNING_KEY_ENV = "TRACECORE_LEDGER_SIGNING_KEY"


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------


def load_private_key(pem_b64: str) -> Ed25519PrivateKey:
    """Decode a base64-encoded PEM private key string.

    The value stored in ``TRACECORE_LEDGER_SIGNING_KEY`` should be the
    output of::

        base64 -w0 < private_key.pem

    (On Windows: ``[Convert]::ToBase64String([IO.File]::ReadAllBytes('private_key.pem'))``)
    """
    pem_bytes = base64.b64decode(pem_b64)
    key = serialization.load_pem_private_key(pem_bytes, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError(f"Expected Ed25519PrivateKey, got {type(key).__name__}")
    return key


def load_private_key_from_env() -> Ed25519PrivateKey | None:
    """Load the signing key from the ``TRACECORE_LEDGER_SIGNING_KEY`` env var.

    Returns ``None`` if the variable is not set (non-CI contexts).
    """
    value = os.environ.get(_SIGNING_KEY_ENV)
    if not value:
        return None
    return load_private_key(value)


def load_public_key_from_file(path: Path | None = None) -> Ed25519PublicKey:
    """Load the Ed25519 public key from a PEM file (default: committed pubkey)."""
    if path is None:
        path = PUBKEY_PATH
    pem_bytes = path.read_bytes()
    key = serialization.load_pem_public_key(pem_bytes)
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError(f"Expected Ed25519PublicKey, got {type(key).__name__}")
    return key


def pubkey_fingerprint(public_key: Ed25519PublicKey) -> str:
    """Return a short hex fingerprint for a public key (first 16 hex chars of SHA-256)."""
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return hashlib.sha256(raw).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Low-level sign / verify
# ---------------------------------------------------------------------------


def sign_bytes(data: bytes, private_key: Ed25519PrivateKey) -> str:
    """Sign *data* and return a base64-encoded signature string."""
    raw_sig = private_key.sign(data)
    return base64.b64encode(raw_sig).decode()


def verify_bytes(data: bytes, signature: str, public_key: Ed25519PublicKey) -> bool:
    """Return True if *signature* is valid for *data* under *public_key*."""
    try:
        raw_sig = base64.b64decode(signature)
        public_key.verify(raw_sig, data)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Bundle helpers
# ---------------------------------------------------------------------------


def _hash_bundle_dir(bundle_dir: Path) -> tuple[str, bytes]:
    """Zip bundle files deterministically and return (hex_sha256, zip_bytes)."""
    import io

    buf = io.BytesIO()
    target_files = sorted(bundle_dir.iterdir())
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in target_files:
            if p.is_file():
                zf.write(p, arcname=p.name)
    zip_bytes = buf.getvalue()
    digest = hashlib.sha256(zip_bytes).hexdigest()
    return digest, zip_bytes


def sign_bundle(bundle_dir: Path, private_key: Ed25519PrivateKey) -> dict:
    """Hash and sign *bundle_dir*, returning provenance metadata.

    Returns a dict suitable for merging into a ledger task-row::

        {
            "bundle_sha256": "<hex>",
            "bundle_signature": "<base64>",
            "signed_at": "<ISO 8601 UTC>",
        }
    """
    digest, _zip_bytes = _hash_bundle_dir(bundle_dir)
    signature = sign_bytes(digest.encode(), private_key)
    return {
        "bundle_sha256": digest,
        "bundle_signature": signature,
        "signed_at": datetime.now(timezone.utc).isoformat(),
    }


def verify_bundle_signature(
    bundle_dir: Path,
    signature: str,
    expected_sha256: str,
    public_key: Ed25519PublicKey | None = None,
) -> bool:
    """Verify the integrity and signature of *bundle_dir*.

    Checks that the bundle hashes to *expected_sha256* and that the Ed25519
    *signature* over the hash is valid under *public_key* (defaults to the
    committed pubkey).
    """
    if public_key is None:
        public_key = load_public_key_from_file()

    actual_sha256, _zip_bytes = _hash_bundle_dir(bundle_dir)
    if actual_sha256 != expected_sha256:
        return False
    return verify_bytes(actual_sha256.encode(), signature, public_key)


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------


def _canonical_registry_bytes(registry: dict) -> bytes:
    """Produce deterministic JSON bytes for signing (excludes signature fields)."""
    clean = {k: v for k, v in registry.items() if k not in ("ledger_signature", "ledger_sha256", "signed_at", "signing_pubkey_id")}
    return json.dumps(clean, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def sign_registry(registry: dict, private_key: Ed25519PrivateKey) -> dict:
    """Compute SHA-256 + Ed25519 signature over the registry and return top-level provenance fields.

    Returns a dict to ``update()`` onto *registry*::

        {
            "ledger_sha256": "<hex>",
            "ledger_signature": "<base64>",
            "signed_at": "<ISO 8601 UTC>",
            "signing_pubkey_id": "<fingerprint>",
        }
    """
    data = _canonical_registry_bytes(registry)
    digest = hashlib.sha256(data).hexdigest()
    signature = sign_bytes(digest.encode(), private_key)
    fp = pubkey_fingerprint(private_key.public_key())
    return {
        "ledger_sha256": digest,
        "ledger_signature": signature,
        "signed_at": datetime.now(timezone.utc).isoformat(),
        "signing_pubkey_id": fp,
    }


def verify_registry_signature(
    registry: dict,
    public_key: Ed25519PublicKey | None = None,
) -> bool:
    """Return True if the top-level signature in *registry* is valid."""
    if public_key is None:
        public_key = load_public_key_from_file()

    signature = registry.get("ledger_signature")
    expected_sha256 = registry.get("ledger_sha256")
    if not signature or not expected_sha256:
        return False

    data = _canonical_registry_bytes(registry)
    actual_sha256 = hashlib.sha256(data).hexdigest()
    if actual_sha256 != expected_sha256:
        return False
    return verify_bytes(actual_sha256.encode(), signature, public_key)
