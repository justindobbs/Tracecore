"""Policy gate script for TraceCore CI pipelines.

Reads a run artifact and an optional baseline artifact, then enforces
configurable thresholds. Exits non-zero when any gate fails so CI jobs
can block on policy violations.

Usage::

    python scripts/policy_gate.py \\
        --run-json run.json \\
        --baseline .agent_bench/baselines/my_baseline.json \\
        --require-success \\
        --max-steps 180 \\
        --max-step-delta 10 \\
        --max-tool-call-delta 5

Exit codes:
    0  All gates passed.
    1  One or more gates failed (details printed to stdout).
    2  Input files missing or unreadable.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_json(path: str, label: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"error: {label} not found: {path}", file=sys.stderr)
        sys.exit(2)
    try:
        with p.open(encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        print(f"error: failed to parse {label} ({path}): {exc}", file=sys.stderr)
        sys.exit(2)


def _run_gates(args: argparse.Namespace) -> list[str]:
    failures: list[str] = []

    run = _load_json(args.run_json, "run artifact")

    if args.require_success and not run.get("success"):
        ft = run.get("failure_type") or "unknown"
        failures.append(f"require_success: run did not succeed (failure_type={ft})")

    steps_used = run.get("steps_used")
    tool_calls_used = run.get("tool_calls_used")

    if args.max_steps is not None and steps_used is not None:
        if steps_used > args.max_steps:
            failures.append(
                f"max_steps: steps_used {steps_used} exceeds max_steps {args.max_steps}"
            )

    if args.max_tool_calls is not None and tool_calls_used is not None:
        if tool_calls_used > args.max_tool_calls:
            failures.append(
                f"max_tool_calls: tool_calls_used {tool_calls_used} exceeds max_tool_calls {args.max_tool_calls}"
            )

    if args.baseline:
        baseline = _load_json(args.baseline, "baseline artifact")

        baseline_steps = baseline.get("steps_used")
        baseline_tool_calls = baseline.get("tool_calls_used")

        if args.max_step_delta is not None and steps_used is not None and baseline_steps is not None:
            delta = abs(steps_used - baseline_steps)
            if delta > args.max_step_delta:
                failures.append(
                    f"max_step_delta: steps_used delta {delta} "
                    f"(run={steps_used}, baseline={baseline_steps}) "
                    f"exceeds max_step_delta {args.max_step_delta}"
                )

        if (
            args.max_tool_call_delta is not None
            and tool_calls_used is not None
            and baseline_tool_calls is not None
        ):
            delta = abs(tool_calls_used - baseline_tool_calls)
            if delta > args.max_tool_call_delta:
                failures.append(
                    f"max_tool_call_delta: tool_calls_used delta {delta} "
                    f"(run={tool_calls_used}, baseline={baseline_tool_calls}) "
                    f"exceeds max_tool_call_delta {args.max_tool_call_delta}"
                )

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TraceCore CI policy gate — enforces thresholds on run artifacts."
    )
    parser.add_argument("--run-json", required=True, help="Path to the run artifact JSON file")
    parser.add_argument(
        "--baseline",
        help="Path to a baseline run artifact for delta comparisons (optional)",
    )
    parser.add_argument(
        "--require-success",
        action="store_true",
        help="Fail if the run did not succeed",
    )
    parser.add_argument("--max-steps", type=int, help="Maximum allowed steps_used")
    parser.add_argument("--max-tool-calls", type=int, help="Maximum allowed tool_calls_used")
    parser.add_argument(
        "--max-step-delta",
        type=int,
        help="Maximum allowed absolute difference in steps_used vs baseline",
    )
    parser.add_argument(
        "--max-tool-call-delta",
        type=int,
        help="Maximum allowed absolute difference in tool_calls_used vs baseline",
    )

    args = parser.parse_args()
    failures = _run_gates(args)

    if failures:
        print("Policy gate failures:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("Policy gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
