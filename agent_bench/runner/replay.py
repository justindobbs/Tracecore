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

Usage::

    from agent_bench.runner.replay import load_bundle_trace, check_replay, check_strict

    report = check_replay(bundle_dir, fresh_result)
    if not report["ok"]:
        for err in report["errors"]:
            print(err)
"""

from __future__ import annotations

import json
from pathlib import Path


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
            f"step {step}: action mismatch — baseline={b_action!r} fresh={f_action!r}"
        )
    b_result = baseline_entry.get("result")
    f_result = fresh_entry.get("result")
    if b_result != f_result:
        errors.append(
            f"step {step}: result mismatch — baseline={b_result!r} fresh={f_result!r}"
        )
    return errors


def check_replay(bundle_dir: Path, fresh_result: dict) -> dict:
    """Compare *fresh_result* against the baseline bundle at *bundle_dir*.

    Returns ``{"ok": bool, "errors": list[str], "mode": "replay"}``.
    """
    errors: list[str] = []

    manifest = load_bundle_manifest(bundle_dir)
    baseline_trace = load_bundle_trace(bundle_dir)
    fresh_trace = fresh_result.get("action_trace", [])

    if manifest.get("success") != fresh_result.get("success"):
        errors.append(
            f"success mismatch — baseline={manifest.get('success')} "
            f"fresh={fresh_result.get('success')}"
        )

    if manifest.get("termination_reason") != fresh_result.get("termination_reason"):
        errors.append(
            f"termination_reason mismatch — baseline={manifest.get('termination_reason')!r} "
            f"fresh={fresh_result.get('termination_reason')!r}"
        )

    if manifest.get("failure_type") != fresh_result.get("failure_type"):
        errors.append(
            f"failure_type mismatch — baseline={manifest.get('failure_type')!r} "
            f"fresh={fresh_result.get('failure_type')!r}"
        )

    if len(baseline_trace) != len(fresh_trace):
        errors.append(
            f"step count mismatch — baseline={len(baseline_trace)} fresh={len(fresh_trace)}"
        )

    for idx, (b_entry, f_entry) in enumerate(zip(baseline_trace, fresh_trace), start=1):
        errors.extend(_compare_step(b_entry, f_entry, idx))

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
            f"steps_used exceeded baseline — baseline={b_steps} fresh={f_steps}"
        )

    b_tools = manifest.get("tool_calls_used")
    f_tools = fresh_result.get("tool_calls_used")
    if b_tools is not None and f_tools is not None and f_tools > b_tools:
        errors.append(
            f"tool_calls_used exceeded baseline — baseline={b_tools} fresh={f_tools}"
        )

    return {"ok": len(errors) == 0, "errors": errors, "mode": "strict"}
