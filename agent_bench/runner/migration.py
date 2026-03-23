"""Run artifact migration helpers for legacy `.agent_bench/runs` entries."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from agent_bench.runner.failures import classify_failure, validate_failure_type
from agent_bench.runner.runner import SPEC_VERSION, _HARNESS_VERSION, _inject_artifact_hash
from agent_bench.runner.runlog import RUN_LOG_ROOT


CURRENT_SPEC_VERSION = SPEC_VERSION


_REQUIRED_TOP_LEVEL_DEFAULTS = {
    "agent_ref": None,
    "task_hash": "unknown",
    "runtime_identity": None,
    "budgets": None,
    "artifact_hash": None,
    "validator": None,
    "evidence_links": None,
}


def _normalize_runtime_identity(payload: dict) -> dict:
    existing = payload.get("runtime_identity")
    if isinstance(existing, dict):
        normalized = dict(existing)
    else:
        normalized = {}
    normalized.setdefault("name", "tracecore")
    normalized.setdefault("version", payload.get("harness_version") or _HARNESS_VERSION)
    normalized.setdefault("git_sha", None)
    return normalized



def _normalize_budgets(payload: dict) -> dict:
    existing = payload.get("budgets")
    if isinstance(existing, dict):
        normalized = dict(existing)
    else:
        normalized = {}
    steps_used = payload.get("steps_used")
    tool_calls_used = payload.get("tool_calls_used")
    normalized.setdefault("steps", int(steps_used) if isinstance(steps_used, int) else 0)
    normalized.setdefault("tool_calls", int(tool_calls_used) if isinstance(tool_calls_used, int) else 0)
    return normalized


def _normalize_evidence_links(payload: dict) -> dict:
    existing = payload.get("evidence_links")
    if isinstance(existing, dict):
        normalized = dict(existing)
    else:
        normalized = {}
    normalized.setdefault("bundle_dir", None)
    normalized.setdefault("bundle_manifest", None)
    return normalized



def _normalize_action_trace(payload: dict) -> list[dict]:
    trace = payload.get("action_trace")
    if not isinstance(trace, list):
        return []
    normalized: list[dict] = []
    for index, raw in enumerate(trace, start=1):
        entry = dict(raw) if isinstance(raw, dict) else {}
        entry.setdefault("step", index)
        entry.setdefault("action_ts", payload.get("started_at"))
        entry.setdefault("observation", {})
        entry.setdefault("action", {})
        entry.setdefault("result", {})
        entry.setdefault("io_audit", [])
        entry.setdefault("budget_after_step", {"steps": 0, "tool_calls": 0})
        entry.setdefault("budget_delta", {"steps": 0, "tool_calls": 0})
        normalized.append(entry)
    return normalized



def migrate_run_artifact(payload: dict) -> tuple[dict, bool]:
    migrated = deepcopy(payload)
    changed = False

    for key, default in _REQUIRED_TOP_LEVEL_DEFAULTS.items():
        if key not in migrated:
            migrated[key] = default
            changed = True

    if migrated.get("spec_version") != CURRENT_SPEC_VERSION:
        migrated["spec_version"] = CURRENT_SPEC_VERSION
        changed = True

    runtime_identity = _normalize_runtime_identity(migrated)
    if migrated.get("runtime_identity") != runtime_identity:
        migrated["runtime_identity"] = runtime_identity
        changed = True

    if migrated.get("agent") and not migrated.get("agent_ref"):
        migrated["agent_ref"] = migrated.get("agent")
        changed = True

    budgets = _normalize_budgets(migrated)
    if migrated.get("budgets") != budgets:
        migrated["budgets"] = budgets
        changed = True

    evidence_links = _normalize_evidence_links(migrated)
    if migrated.get("evidence_links") != evidence_links:
        migrated["evidence_links"] = evidence_links
        changed = True

    if "success" not in migrated:
        migrated["success"] = migrated.get("failure_type") is None
        changed = True

    success = bool(migrated.get("success"))

    if success:
        if migrated.get("failure_type") is not None:
            migrated["failure_type"] = None
            changed = True
        if migrated.get("termination_reason") is None:
            migrated["termination_reason"] = "success"
            changed = True
        if migrated.get("failure_reason") is not None:
            migrated["failure_reason"] = None
            changed = True
    else:
        termination_reason = migrated.get("termination_reason") or "logic_failure"
        if migrated.get("termination_reason") != termination_reason:
            migrated["termination_reason"] = termination_reason
            changed = True
        failure_type = migrated.get("failure_type") or classify_failure(termination_reason)
        validated = validate_failure_type(False, failure_type)
        if migrated.get("failure_type") != validated:
            migrated["failure_type"] = validated
            changed = True
        if migrated.get("failure_reason") is None:
            migrated["failure_reason"] = termination_reason
            changed = True

    trace = _normalize_action_trace(migrated)
    if migrated.get("action_trace") != trace:
        migrated["action_trace"] = trace
        changed = True

    if migrated.get("artifact_hash") is None or changed:
        migrated = _inject_artifact_hash(migrated)
        changed = True

    return migrated, changed



def migrate_run_file(path: Path, *, write: bool = False) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    migrated, changed = migrate_run_artifact(payload)
    if write and changed:
        path.write_text(json.dumps(migrated, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "path": str(path),
        "changed": changed,
        "artifact": migrated,
    }



def migrate_run_directory(root: Path = RUN_LOG_ROOT, *, write: bool = False) -> dict:
    if not root.exists():
        return {"ok": True, "root": str(root), "files": [], "changed": 0}

    files: list[dict] = []
    changed = 0
    errors: list[str] = []
    for path in sorted(root.glob("*.json")):
        try:
            result = migrate_run_file(path, write=write)
            files.append({"path": result["path"], "changed": result["changed"]})
            if result["changed"]:
                changed += 1
        except Exception as exc:
            errors.append(f"{path}: {exc}")

    return {
        "ok": len(errors) == 0,
        "root": str(root),
        "files": files,
        "changed": changed,
        "errors": errors,
    }
