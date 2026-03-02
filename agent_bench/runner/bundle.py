"""Baseline bundle writer.

A *baseline bundle* is a directory that captures a single certified run in a
format suitable for replay verification, ledger submission, and CI diffing.

Bundle layout::

    <bundle_dir>/
        manifest.json        # run metadata + ledger-linkable fields
        tool_calls.jsonl     # one JSON line per trace entry (action + result)
        validator.json       # final validation snapshot
        integrity.sha256     # SHA-256 hashes of the three files above

Usage::

    from agent_bench.runner.bundle import write_bundle
    bundle_path = write_bundle(result, dest=Path(".agent_bench/baselines"))
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


BASELINE_ROOT = Path(".agent_bench") / "baselines"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_manifest(bundle_dir: Path, result: dict) -> Path:
    manifest = {
        "run_id": result.get("run_id"),
        "trace_id": result.get("trace_id"),
        "agent": result.get("agent"),
        "task_ref": result.get("task_ref"),
        "task_id": result.get("task_id"),
        "version": result.get("version"),
        "seed": result.get("seed"),
        "harness_version": result.get("harness_version"),
        "started_at": result.get("started_at"),
        "completed_at": result.get("completed_at"),
        "success": result.get("success"),
        "termination_reason": result.get("termination_reason"),
        "failure_type": result.get("failure_type"),
        "failure_reason": result.get("failure_reason"),
        "steps_used": result.get("steps_used"),
        "tool_calls_used": result.get("tool_calls_used"),
        "trace_entry_count": len(result.get("action_trace", [])),
        "sandbox": result.get("sandbox"),
    }
    path = bundle_dir / "manifest.json"
    with path.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    return path


def _write_tool_calls(bundle_dir: Path, result: dict) -> Path:
    path = bundle_dir / "tool_calls.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for entry in result.get("action_trace", []):
            row = {
                "step": entry.get("step"),
                "action_ts": entry.get("action_ts"),
                "action": entry.get("action"),
                "result": entry.get("result"),
                "io_audit": entry.get("io_audit", []),
                "budget_after_step": entry.get("budget_after_step"),
                "budget_delta": entry.get("budget_delta"),
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def _write_validator(bundle_dir: Path, result: dict) -> Path:
    validator_snapshot = {
        "success": result.get("success"),
        "termination_reason": result.get("termination_reason"),
        "failure_type": result.get("failure_type"),
        "failure_reason": result.get("failure_reason"),
        "metrics": result.get("metrics", {}),
    }
    path = bundle_dir / "validator.json"
    with path.open("w", encoding="utf-8") as fh:
        json.dump(validator_snapshot, fh, ensure_ascii=False, indent=2)
    return path


def _write_integrity(bundle_dir: Path, paths: list[Path]) -> Path:
    integrity_path = bundle_dir / "integrity.sha256"
    with integrity_path.open("w", encoding="utf-8") as fh:
        for p in paths:
            digest = _sha256_file(p)
            fh.write(f"{digest}  {p.name}\n")
    return integrity_path


def write_bundle(result: dict, *, dest: Path | None = None) -> Path:
    """Write a baseline bundle for *result* and return the bundle directory.

    Parameters
    ----------
    result:
        The run result dict returned by :func:`agent_bench.runner.runner.run`.
    dest:
        Parent directory under which the bundle subdirectory is created.
        Defaults to :data:`BASELINE_ROOT`.

    Returns
    -------
    Path
        The bundle directory (``<dest>/<run_id>/``).
    """
    if dest is None:
        dest = BASELINE_ROOT

    run_id = result.get("run_id")
    if not run_id:
        raise ValueError("run result missing run_id; cannot write bundle")

    bundle_dir = dest / run_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = _write_manifest(bundle_dir, result)
    tool_calls_path = _write_tool_calls(bundle_dir, result)
    validator_path = _write_validator(bundle_dir, result)
    _write_integrity(bundle_dir, [manifest_path, tool_calls_path, validator_path])

    return bundle_dir


def sign_bundle(bundle_dir: Path, *, key_path: str | None = None) -> dict:
    """Sign a bundle directory using Ed25519.

    Writes ``signature.json`` into the bundle dir containing the hex-encoded
    signature over the existing ``integrity.sha256`` file.  Requires the
    ``cryptography`` package.

    Parameters
    ----------
    bundle_dir:
        Path to an existing bundle directory (must contain ``integrity.sha256``).
    key_path:
        Path to an Ed25519 private key PEM file.  Defaults to
        ``agent_bench/ledger/signing_key.pem`` relative to the package root.

    Returns
    -------
    dict
        ``{"ok": bool, "signature_file": str | None, "errors": list[str]}``
    """
    errors: list[str] = []
    integrity_path = bundle_dir / "integrity.sha256"
    if not integrity_path.exists():
        return {"ok": False, "signature_file": None, "errors": ["integrity.sha256 not found — run write_bundle first"]}

    if key_path is None:
        default_key = Path(__file__).parent.parent / "ledger" / "signing_key.pem"
        if default_key.exists():
            key_path = str(default_key)

    if not key_path or not Path(key_path).exists():
        return {
            "ok": False,
            "signature_file": None,
            "errors": [
                f"Signing key not found: {key_path!r}. "
                "Provide --key <path> or place an Ed25519 private key at agent_bench/ledger/signing_key.pem"
            ],
        }

    try:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError:
        return {"ok": False, "signature_file": None, "errors": ["cryptography package required: pip install cryptography"]}

    try:
        key_bytes = Path(key_path).read_bytes()
        private_key = load_pem_private_key(key_bytes, password=None)
        if not isinstance(private_key, Ed25519PrivateKey):
            return {"ok": False, "signature_file": None, "errors": ["Key must be an Ed25519 private key"]}
    except Exception as exc:
        return {"ok": False, "signature_file": None, "errors": [f"Failed to load signing key: {exc}"]}

    try:
        payload = integrity_path.read_bytes()
        signature_bytes = private_key.sign(payload)
        public_key = private_key.public_key()
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        pubkey_pem = public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
        sig_doc = {
            "signed_file": "integrity.sha256",
            "algorithm": "ed25519",
            "signature_hex": signature_bytes.hex(),
            "public_key_pem": pubkey_pem,
        }
        sig_path = bundle_dir / "signature.json"
        sig_path.write_text(json.dumps(sig_doc, indent=2), encoding="utf-8")
    except Exception as exc:
        errors.append(f"Signing failed: {exc}")
        return {"ok": False, "signature_file": None, "errors": errors}

    try:
        manifest_path = bundle_dir / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["signed"] = True
            manifest["signature_algorithm"] = "ed25519"
            manifest["signature_file"] = "signature.json"
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
            _write_integrity(bundle_dir, [manifest_path, bundle_dir / "tool_calls.jsonl", bundle_dir / "validator.json"])
    except Exception:
        pass

    return {"ok": True, "signature_file": str(sig_path), "errors": []}


def verify_bundle(bundle_dir: Path) -> dict:
    """Verify the integrity of an existing bundle.

    Returns a dict with ``ok`` (bool) and ``errors`` (list[str]).
    """
    integrity_path = bundle_dir / "integrity.sha256"
    if not integrity_path.exists():
        return {"ok": False, "errors": ["integrity.sha256 not found"]}

    errors: list[str] = []
    with integrity_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parts = line.split("  ", 1)
            if len(parts) != 2:
                errors.append(f"malformed integrity line: {line!r}")
                continue
            expected_digest, filename = parts
            file_path = bundle_dir / filename
            if not file_path.exists():
                errors.append(f"missing file: {filename}")
                continue
            actual_digest = _sha256_file(file_path)
            if actual_digest != expected_digest:
                errors.append(f"hash mismatch for {filename}: expected {expected_digest}, got {actual_digest}")

    try:
        manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"failed to read manifest.json: {exc}")
        return {"ok": False, "errors": errors}

    sandbox = manifest.get("sandbox")
    if not isinstance(sandbox, dict):
        errors.append("manifest missing sandbox declaration")
        return {"ok": False, "errors": errors}

    fs_roots = sandbox.get("filesystem_roots")
    net_hosts = sandbox.get("network_hosts")
    if not isinstance(fs_roots, list) or not isinstance(net_hosts, list):
        errors.append("manifest sandbox must include filesystem_roots and network_hosts lists")
        return {"ok": False, "errors": errors}

    from agent_bench.env.environment import NetworkGuard, SandboxViolation
    guard = NetworkGuard(net_hosts)

    try:
        tool_calls = (bundle_dir / "tool_calls.jsonl").read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        errors.append(f"failed to read tool_calls.jsonl: {exc}")
        return {"ok": False, "errors": errors}

    for idx, line in enumerate(tool_calls, start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"tool_calls.jsonl line {idx}: invalid JSON ({exc})")
            continue
        io_audit = entry.get("io_audit")
        if io_audit is None:
            errors.append(f"tool_calls.jsonl line {idx}: missing io_audit")
            continue
        if not isinstance(io_audit, list):
            errors.append(f"tool_calls.jsonl line {idx}: io_audit must be list")
            continue
        for audit in io_audit:
            if not isinstance(audit, dict):
                errors.append(f"tool_calls.jsonl line {idx}: audit entry must be object")
                continue
            audit_type = audit.get("type")
            if audit_type == "fs":
                path = audit.get("path")
                if not isinstance(path, str):
                    errors.append(f"tool_calls.jsonl line {idx}: fs audit missing path")
                    continue
                allowed = any(
                    root == "/" or path == root or path.startswith(root + "/")
                    for root in fs_roots
                )
                if not allowed:
                    errors.append(
                        f"tool_calls.jsonl line {idx}: fs audit path outside allowlist: {path}"
                    )
            elif audit_type == "net":
                host = audit.get("host")
                if not isinstance(host, str):
                    errors.append(f"tool_calls.jsonl line {idx}: net audit missing host")
                    continue
                try:
                    guard.check(host)
                except SandboxViolation as exc:
                    errors.append(f"tool_calls.jsonl line {idx}: {exc}")
            else:
                errors.append(f"tool_calls.jsonl line {idx}: unknown audit type {audit_type!r}")

    return {"ok": len(errors) == 0, "errors": errors}
