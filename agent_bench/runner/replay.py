"""Replay enforcement for baseline bundles.

Given a baseline bundle directory (produced by :func:`agent_bench.runner.bundle.write_bundle`)
and a fresh run result, this module compares the two traces step-by-step and returns a
structured divergence report.

Replay rules (enforced by :func:`check_replay`):
- ``success`` must match.
- ``termination_reason`` must match.
- ``failure_type`` must match.
- Every trace entry's ``action`` (type + args) must match the baseline.
- Every trace entry's ``result`` must match the baseline.
- Step count must match.

Strict mode (enforced by :func:`check_strict`, a superset of replay):
- All replay rules apply.
- ``steps_used`` must not exceed the baseline.
- ``tool_calls_used`` must not exceed the baseline.

Record mode (enforced by :func:`check_record`):
- Compares two raw run result dicts (no bundle required).
- Same rules as replay: success, termination_reason, failure_type, step count, per-step action+result.
- Used by ``--record`` to verify determinism before sealing a bundle.

Usage::

    from agent_bench.runner.replay import load_bundle_trace, check_replay, check_strict, check_record

    report = check_replay(bundle_dir, fresh_result)
    if not report["ok"]:
        for err in report["errors"]:
            print(err)

    det_report = check_record(run_a, run_b)
    if not det_report["ok"]:
        print("NonDeterministic:", det_report["errors"])
"""

from __future__ import annotations

import json
from pathlib import Path

from agent_bench.env.environment import NetworkGuard, SandboxViolation


def load_bundle_trace(bundle_dir: Path) -> list[dict]:
    """Load the ``tool_calls.jsonl`` from a bundle directory."""
    path = bundle_dir / "tool_calls.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"tool_calls.jsonl not found in bundle: {bundle_dir}")
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_bundle_manifest(bundle_dir: Path) -> dict:
    """Load ``manifest.json`` from a bundle directory."""
    path = bundle_dir / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"manifest.json not found in bundle: {bundle_dir}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _compare_step(baseline_entry: dict, fresh_entry: dict, step: int) -> list[str]:
    """Return a list of divergence descriptions for a single step, or empty list if identical."""
    errors: list[str] = []
    b_action = baseline_entry.get("action", {})
    f_action = fresh_entry.get("action", {})
    if b_action != f_action:
        errors.append(
            f"step {step}: action mismatch -- baseline={b_action!r} fresh={f_action!r}"
        )
    b_result = baseline_entry.get("result")
    f_result = fresh_entry.get("result")
    if b_result != f_result:
        errors.append(
            f"step {step}: result mismatch -- baseline={b_result!r} fresh={f_result!r}"
        )
    b_audit = baseline_entry.get("io_audit", [])
    f_audit = fresh_entry.get("io_audit", [])
    if b_audit != f_audit:
        errors.append(
            f"step {step}: io_audit mismatch -- baseline={b_audit!r} fresh={f_audit!r}"
        )
    return errors


def _validate_sandbox(sandbox: dict | None, *, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(sandbox, dict):
        return [f"{label} missing sandbox declaration"]
    fs_roots = sandbox.get("filesystem_roots")
    net_hosts = sandbox.get("network_hosts")
    if not isinstance(fs_roots, list) or not isinstance(net_hosts, list):
        errors.append(f"{label} sandbox must include filesystem_roots and network_hosts lists")
    return errors


def _audit_allowed(io_audit: list[dict], sandbox: dict, *, label: str, step: int) -> list[str]:
    errors: list[str] = []
    fs_roots = sandbox.get("filesystem_roots", [])
    net_hosts = sandbox.get("network_hosts", [])
    guard = NetworkGuard(net_hosts)
    for entry in io_audit:
        if not isinstance(entry, dict):
            errors.append(f"{label} step {step}: audit entry must be object")
            continue
        audit_type = entry.get("type")
        if audit_type == "fs":
            path = entry.get("path")
            if not isinstance(path, str):
                errors.append(f"{label} step {step}: fs audit missing path")
                continue
            allowed = any(
                root == "/" or path == root or path.startswith(root + "/")
                for root in fs_roots
            )
            if not allowed:
                errors.append(f"{label} step {step}: fs audit outside allowlist: {path}")
        elif audit_type == "net":
            host = entry.get("host")
            if not isinstance(host, str):
                errors.append(f"{label} step {step}: net audit missing host")
                continue
            try:
                guard.check(host)
            except SandboxViolation as exc:
                errors.append(f"{label} step {step}: {exc}")
        else:
            errors.append(f"{label} step {step}: unknown audit type {audit_type!r}")
    return errors


def check_replay(bundle_dir: Path, fresh_result: dict) -> dict:
    """Compare *fresh_result* against the baseline bundle at *bundle_dir*.

    Returns ``{"ok": bool, "errors": list[str], "mode": "replay"}``.
    """
    errors: list[str] = []

    manifest = load_bundle_manifest(bundle_dir)
    baseline_trace = load_bundle_trace(bundle_dir)
    fresh_trace = fresh_result.get("action_trace", [])

    errors.extend(_validate_sandbox(manifest.get("sandbox"), label="manifest"))
    errors.extend(_validate_sandbox(fresh_result.get("sandbox"), label="run"))
    if not errors:
        if manifest.get("sandbox") != fresh_result.get("sandbox"):
            errors.append("sandbox mismatch -- manifest vs run")

    if manifest.get("success") != fresh_result.get("success"):
        errors.append(
            f"success mismatch -- baseline={manifest.get('success')} "
            f"fresh={fresh_result.get('success')}"
        )

    if manifest.get("termination_reason") != fresh_result.get("termination_reason"):
        errors.append(
            f"termination_reason mismatch -- baseline={manifest.get('termination_reason')!r} "
            f"fresh={fresh_result.get('termination_reason')!r}"
        )

    if manifest.get("failure_type") != fresh_result.get("failure_type"):
        errors.append(
            f"failure_type mismatch -- baseline={manifest.get('failure_type')!r} "
            f"fresh={fresh_result.get('failure_type')!r}"
        )

    if len(baseline_trace) != len(fresh_trace):
        errors.append(
            f"step count mismatch -- baseline={len(baseline_trace)} fresh={len(fresh_trace)}"
        )

    for idx, (b_entry, f_entry) in enumerate(zip(baseline_trace, fresh_trace), start=1):
        if "io_audit" not in b_entry:
            errors.append(f"baseline step {idx}: missing io_audit")
        if "io_audit" not in f_entry:
            errors.append(f"run step {idx}: missing io_audit")
        errors.extend(_compare_step(b_entry, f_entry, idx))
        if not errors:
            errors.extend(_audit_allowed(b_entry.get("io_audit", []), manifest.get("sandbox", {}), label="baseline", step=idx))
            errors.extend(_audit_allowed(f_entry.get("io_audit", []), manifest.get("sandbox", {}), label="run", step=idx))

    return {"ok": len(errors) == 0, "errors": errors, "mode": "replay"}


def check_strict(bundle_dir: Path, fresh_result: dict) -> dict:
    """Replay check plus budget invariants (steps and tool_calls must not exceed baseline).

    Returns ``{"ok": bool, "errors": list[str], "mode": "strict"}``.
    """
    report = check_replay(bundle_dir, fresh_result)
    errors = list(report["errors"])

    manifest = load_bundle_manifest(bundle_dir)

    b_steps = manifest.get("steps_used")
    f_steps = fresh_result.get("steps_used")
    if b_steps is not None and f_steps is not None and f_steps > b_steps:
        errors.append(
            f"steps_used exceeded baseline -- baseline={b_steps} fresh={f_steps}"
        )

    b_tools = manifest.get("tool_calls_used")
    f_tools = fresh_result.get("tool_calls_used")
    if b_tools is not None and f_tools is not None and f_tools > b_tools:
        errors.append(
            f"tool_calls_used exceeded baseline -- baseline={b_tools} fresh={f_tools}"
        )

    return {"ok": len(errors) == 0, "errors": errors, "mode": "strict"}


def check_record(run_a: dict, run_b: dict) -> dict:
    """Verify determinism between two raw run results (no bundle required).

    Compares ``run_a`` (first capture) against ``run_b`` (second capture) using
    the same per-step rules as :func:`check_replay`.  Used by ``--record`` mode
    to confirm the episode is reproducible before sealing a bundle.

    Returns ``{"ok": bool, "errors": list[str], "mode": "record"}``.
    """
    errors: list[str] = []

    if run_a.get("success") != run_b.get("success"):
        errors.append(
            f"success mismatch -- run1={run_a.get('success')} run2={run_b.get('success')}"
        )

    if run_a.get("termination_reason") != run_b.get("termination_reason"):
        errors.append(
            f"termination_reason mismatch -- run1={run_a.get('termination_reason')!r} "
            f"run2={run_b.get('termination_reason')!r}"
        )

    if run_a.get("failure_type") != run_b.get("failure_type"):
        errors.append(
            f"failure_type mismatch -- run1={run_a.get('failure_type')!r} "
            f"run2={run_b.get('failure_type')!r}"
        )

    errors.extend(_validate_sandbox(run_a.get("sandbox"), label="run1"))
    errors.extend(_validate_sandbox(run_b.get("sandbox"), label="run2"))
    if not errors and run_a.get("sandbox") != run_b.get("sandbox"):
        errors.append("sandbox mismatch -- run1 vs run2")

    trace_a = run_a.get("action_trace", [])
    trace_b = run_b.get("action_trace", [])

    if len(trace_a) != len(trace_b):
        errors.append(
            f"step count mismatch -- run1={len(trace_a)} run2={len(trace_b)}"
        )

    for idx, (entry_a, entry_b) in enumerate(zip(trace_a, trace_b), start=1):
        if "io_audit" not in entry_a:
            errors.append(f"run1 step {idx}: missing io_audit")
        if "io_audit" not in entry_b:
            errors.append(f"run2 step {idx}: missing io_audit")
        errors.extend(_compare_step(entry_a, entry_b, idx))
        if not errors:
            errors.extend(_audit_allowed(entry_a.get("io_audit", []), run_a.get("sandbox", {}), label="run1", step=idx))
            errors.extend(_audit_allowed(entry_b.get("io_audit", []), run_b.get("sandbox", {}), label="run2", step=idx))

    return {"ok": len(errors) == 0, "errors": errors, "mode": "record"}
