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

    return {"ok": len(errors) == 0, "errors": errors}
