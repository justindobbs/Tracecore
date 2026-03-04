"""Spec compliance validator for TraceCore artifacts.

Validates a run result dict against the TraceCore Specification v1.0 requirements:
  - JSON schema conformance (spec/artifact-schema-v1.0.json)
  - Required top-level metadata fields (including wall_clock_elapsed_s)
  - Canonical failure_type taxonomy
  - Trace entry structure

Usage::

    from agent_bench.runner.spec_check import check_spec_compliance

    report = check_spec_compliance(result)
    if not report["ok"]:
        for err in report["errors"]:
            print(err)
"""

from __future__ import annotations

import json
from pathlib import Path

_SCHEMA_PATH = Path(__file__).parent.parent / "spec" / "artifact-schema-v1.0.json"
_SCHEMA_PATH_FALLBACK = Path(__file__).parent.parent / "spec" / "artifact-schema-v0.1.json"

_CANONICAL_FAILURE_TYPES = {
    "budget_exhausted",
    "invalid_action",
    "sandbox_violation",
    "logic_failure",
    "timeout",
    "non_termination",
}

_REQUIRED_SPEC_FIELDS = {
    "spec_version",
    "runtime_identity",
    "run_id",
    "trace_id",
    "agent_ref",
    "task_ref",
    "task_hash",
    "seed",
    "budgets",
    "success",
    "termination_reason",
    "failure_type",
    "steps_used",
    "tool_calls_used",
    "started_at",
    "completed_at",
    "wall_clock_elapsed_s",
    "harness_version",
    "artifact_hash",
    "action_trace",
    "validator",
}

_TRACE_ENTRY_REQUIRED = {
    "step",
    "action_ts",
    "observation",
    "action",
    "result",
    "io_audit",
    "budget_after_step",
    "budget_delta",
}


def _load_schema() -> dict | None:
    for path in (_SCHEMA_PATH, _SCHEMA_PATH_FALLBACK):
        try:
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            continue
    return None


def _validate_jsonschema(result: dict, schema: dict) -> list[str]:
    try:
        import jsonschema
        errors = []
        validator = jsonschema.Draft202012Validator(schema)
        for err in sorted(validator.iter_errors(result), key=lambda e: list(e.path)):
            path = " -> ".join(str(p) for p in err.path) or "(root)"
            errors.append(f"schema: {path}: {err.message}")
        return errors
    except ImportError:
        return ["schema: jsonschema package not installed; install it to enable full schema validation"]


def check_spec_compliance(result: dict) -> dict:
    """Validate *result* against TraceCore Spec v1.0 compliance rules.

    Returns ``{"ok": bool, "errors": list[str], "mode": "strict-spec"}``.
    """
    errors: list[str] = []

    schema = _load_schema()
    if schema is None:
        errors.append(f"spec: cannot load schema from {_SCHEMA_PATH}")
    else:
        errors.extend(_validate_jsonschema(result, schema))

    missing = _REQUIRED_SPEC_FIELDS - result.keys()
    for field in sorted(missing):
        if not any(f"-> {field}:" in e or f"'{field}'" in e for e in errors):
            errors.append(f"spec: required field missing: {field}")

    spec_version = result.get("spec_version")
    if spec_version and not str(spec_version).startswith("tracecore-spec-v"):
        errors.append(
            f"spec: spec_version must match pattern 'tracecore-spec-v<major>.<minor>'; got {spec_version!r}"
        )

    runtime_identity = result.get("runtime_identity")
    if runtime_identity is not None:
        if not isinstance(runtime_identity, dict):
            errors.append("spec: runtime_identity must be an object")
        else:
            for sub in ("name", "version"):
                if not runtime_identity.get(sub):
                    errors.append(f"spec: runtime_identity.{sub} is missing or empty")

    artifact_hash = result.get("artifact_hash")
    if artifact_hash is not None and not str(artifact_hash).startswith("sha256:"):
        errors.append(f"spec: artifact_hash must begin with 'sha256:'; got {artifact_hash!r}")

    task_hash = result.get("task_hash")
    if task_hash == "":
        errors.append("spec: task_hash must not be empty")

    failure_type = result.get("failure_type")
    if failure_type is not None and failure_type not in _CANONICAL_FAILURE_TYPES:
        errors.append(
            f"spec: failure_type {failure_type!r} is not in canonical taxonomy "
            f"({', '.join(sorted(_CANONICAL_FAILURE_TYPES))})"
        )

    action_trace = result.get("action_trace")
    if isinstance(action_trace, list):
        for idx, entry in enumerate(action_trace, start=1):
            if not isinstance(entry, dict):
                errors.append(f"spec: action_trace[{idx}] is not an object")
                continue
            missing_entry = _TRACE_ENTRY_REQUIRED - entry.keys()
            for f in sorted(missing_entry):
                errors.append(f"spec: action_trace[{idx}] missing field: {f}")

    return {"ok": len(errors) == 0, "errors": errors, "mode": "strict-spec"}
