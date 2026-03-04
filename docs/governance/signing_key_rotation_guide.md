# Signing Key Rotation Guide

This guide explains how to generate, rotate, and manage Ed25519 signing keys used by `tracecore bundle sign`, and how to verify existing bundles after a key rotation.

---

## Key types

TraceCore supports two signing modes:

| Mode | Key material | Verification |
|------|-------------|--------------|
| **Local Ed25519** | PEM file on disk (`signing_key.pem`) | `signature.json` in each bundle |
| **Cosign keyless** | GitHub Actions OIDC token (no long-lived key) | Sigstore transparency log + `cosign.cert` |

---

## 1. Generating a new Ed25519 key pair

```bash
# Requires: pip install cryptography
python - <<'EOF'
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PrivateFormat, PublicFormat, NoEncryption
)
key = Ed25519PrivateKey.generate()
with open("signing_key.pem", "wb") as f:
    f.write(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
with open("signing_key.pub", "wb") as f:
    f.write(key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
print("Keys written: signing_key.pem  signing_key.pub")
EOF
```

Store `signing_key.pem` securely (e.g. GitHub Actions secret, HashiCorp Vault). Never commit it to the repository.

Place the **public key** at `agent_bench/ledger/signing_key.pub` for verification tooling, and commit it.

---

## 2. Signing a bundle

```bash
# Default key location: agent_bench/ledger/signing_key.pem
tracecore bundle sign .agent_bench/baselines/<run_id>/

# Explicit key path
tracecore bundle sign .agent_bench/baselines/<run_id>/ --key /path/to/signing_key.pem
```

This writes:
- `signature.json` — hex-encoded Ed25519 signature over `integrity.sha256`
- Updates `manifest.json` with `"signed": true, "signature_algorithm": "ed25519"`
- Regenerates `integrity.sha256` to include the updated manifest

---

## 3. Verifying a bundle

```bash
tracecore bundle verify .agent_bench/baselines/<run_id>/
```

To also verify the Ed25519 signature programmatically:

```python
import json
from pathlib import Path
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

bundle_dir = Path(".agent_bench/baselines/<run_id>")
sig_doc = json.loads((bundle_dir / "signature.json").read_text())
payload = (bundle_dir / "integrity.sha256").read_bytes()
sig_bytes = bytes.fromhex(sig_doc["signature_hex"])

pub_key = load_pem_public_key(sig_doc["public_key_pem"].encode())
assert isinstance(pub_key, Ed25519PublicKey)
pub_key.verify(sig_bytes, payload)  # raises InvalidSignature if tampered
print("Signature valid")
```

---

## 4. Key rotation procedure

### Step 1: Generate a new key pair

Follow section 1 above. Name the new key with a datestamp:
```
signing_key_2026-03.pem
signing_key_2026-03.pub
```

### Step 2: Update the default key reference

Replace `agent_bench/ledger/signing_key.pem` (or update the secret in your CI) with the new private key.
Commit the new `signing_key.pub` to `agent_bench/ledger/`.

### Step 3: Re-sign new bundles

All bundles created after the rotation will automatically use the new key via `tracecore bundle sign`.

### Step 4: Archive old bundles (do not re-sign)

Existing bundles signed under the old key remain valid — their `signature.json` still contains the public key that was used to sign them. Never re-sign old bundles with a new key; that would break historical auditability.

### Step 5: Update the key inventory

Maintain a key inventory in `agent_bench/ledger/key_inventory.json`:

```json
[
  {
    "key_id": "ed25519-2025-09",
    "public_key_file": "signing_key_2025-09.pub",
    "active_from": "2025-09-01",
    "retired_at": "2026-03-01",
    "status": "retired"
  },
  {
    "key_id": "ed25519-2026-03",
    "public_key_file": "signing_key_2026-03.pub",
    "active_from": "2026-03-01",
    "retired_at": null,
    "status": "active"
  }
]
```

---

## 5. Cosign keyless rotation

Cosign keyless signing uses ephemeral OIDC-issued certificates — there is no long-lived key to rotate. Each signing event produces a unique short-lived certificate chained to the Sigstore transparency log.

To verify a Cosign-signed bundle:

```bash
cosign verify-blob \
  --certificate .agent_bench/baselines/<run_id>/cosign.cert \
  --signature   .agent_bench/baselines/<run_id>/cosign.sig \
  --certificate-identity-regexp "https://github.com/<org>/<repo>" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  .agent_bench/baselines/<run_id>/integrity.sha256
```

No key rotation is needed for keyless mode — the CI OIDC identity is the trust anchor.

---

## 6. Emergency key compromise

If a signing key is compromised:

1. **Immediately revoke** the secret in GitHub Actions / Vault.
2. Generate a new key pair (section 1).
3. Mark the compromised key as `"status": "compromised"` in `key_inventory.json` with a `"compromised_at"` timestamp.
4. All bundles signed under the compromised key should be **treated as untrusted** and re-run if reproducibility is required.
5. Open a security advisory in the repository.
