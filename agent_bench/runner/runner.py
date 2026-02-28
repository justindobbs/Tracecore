"""Main execution loop."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from uuid import uuid4

from agent_bench.agent.loader import load_agent
from agent_bench.env.environment import Environment, GuardedEnv, SandboxViolation
from agent_bench.runner.budgets import Budgets
from agent_bench.runner.failures import FAILURE_TYPES, classify_failure
from agent_bench.runner.results import make_result
from agent_bench.tasks.loader import load_task

try:  # pragma: no cover - fallback for editable installs
    _HARNESS_VERSION = metadata.version("agent-bench")
except metadata.PackageNotFoundError:  # pragma: no cover - fallback when package metadata missing
    _HARNESS_VERSION = "0.0.0-dev"

SPEC_VERSION = "tracecore-spec-v0.1"


def _compute_task_hash(task: dict) -> str:
    """SHA-256 over the concatenated bytes of the task's Python source files."""
    task_path: Path | None = task.get("path")
    if task_path is None:
        return "unknown"
    files = [task_path / "setup.py", task_path / "actions.py", task_path / "validate.py"]
    h = hashlib.sha256()
    for f in sorted(files):
        if f.exists():
            h.update(f.read_bytes())
    return h.hexdigest()


_VOLATILE_HASH_FIELDS = {"run_id", "trace_id", "started_at", "completed_at"}


def _stable_payload(result: dict) -> dict:
    """Return a copy of *result* with volatile fields removed for hashing."""
    scrubbed = {k: v for k, v in result.items() if k not in _VOLATILE_HASH_FIELDS}
    if "action_trace" in scrubbed:
        scrubbed["action_trace"] = [
            {k: v for k, v in entry.items() if k != "action_ts"}
            for entry in scrubbed["action_trace"]
        ]
    return scrubbed


def _inject_artifact_hash(result: dict) -> dict:
    """Compute SHA-256 of the stable (non-volatile) canonical JSON and insert as artifact_hash."""
    payload = json.dumps(_stable_payload(result), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    result["artifact_hash"] = "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return result


def _parse_task_ref(task_ref: str) -> tuple[str, int | None]:
    if "@" in task_ref:
        task_id, version = task_ref.split("@", 1)
        return task_id, int(version)
    return task_ref, None


def _action_schema(actions_mod) -> dict[str, list[str]]:
    schema: dict[str, list[str]] = {}
    for name, fn in inspect.getmembers(actions_mod, inspect.isfunction):
        if name.startswith("_") or name == "set_env":
            continue
        params = [p.name for p in inspect.signature(fn).parameters.values()]
        schema[name] = params
    return schema


def _validate_action(action: dict, schema: dict[str, list[str]]) -> tuple[bool, str | None]:
    if not isinstance(action, dict):
        return False, "action_must_be_dict"
    action_type = action.get("type")
    args = action.get("args")
    if not action_type or not isinstance(action_type, str):
        return False, "invalid_action_type"
    if action_type not in schema:
        return False, "unknown_action"
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return False, "args_must_be_dict"
    required = schema[action_type]
    for key in required:
        if key not in args:
            return False, "missing_arg"
    return True, None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _finalize_metadata(base_metadata: dict, *, validator: dict | None = None) -> dict:
    metadata = dict(base_metadata)
    metadata["completed_at"] = _now_iso()
    if validator:
        metadata["validator"] = validator
    return metadata


def _coerce_str(value) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return None


def _snapshot_validation(validation: dict | None) -> dict | None:
    if not isinstance(validation, dict):
        return None
    allowed_keys = (
        "ok",
        "terminal",
        "message",
        "error",
        "failure_reason",
        "failure_type",
        "termination_reason",
    )
    snapshot = {key: validation[key] for key in allowed_keys if key in validation}
    return snapshot or None


def _normalize_terminal_validation(validation: dict | None) -> tuple[str, str, str, dict | None]:
    snapshot = _snapshot_validation(validation) or {}

    failure_reason = (
        _coerce_str(validation.get("failure_reason"))
        if isinstance(validation, dict)
        else None
    )
    if not failure_reason and isinstance(validation, dict):
        for field in ("message", "error"):
            failure_reason = _coerce_str(validation.get(field))
            if failure_reason:
                break
    if not failure_reason:
        failure_reason = "logic_failure"

    termination_reason = None
    if isinstance(validation, dict):
        termination_reason = _coerce_str(validation.get("termination_reason"))
    if not termination_reason:
        termination_reason = "logic_failure"

    failure_type = None
    if isinstance(validation, dict):
        failure_type = _coerce_str(validation.get("failure_type"))
    if failure_type not in FAILURE_TYPES:
        failure_type = classify_failure(termination_reason)

    snapshot.setdefault("ok", False)
    snapshot.setdefault("terminal", True)
    snapshot["failure_reason"] = failure_reason
    snapshot["failure_type"] = failure_type
    snapshot["termination_reason"] = termination_reason

    return failure_reason, failure_type, termination_reason, snapshot


def _result_payload(
    *,
    task: dict,
    sandbox: dict,
    seed: int,
    success: bool,
    termination_reason: str,
    failure_reason: str | None,
    failure_type: str | None,
    steps_used: int,
    tool_calls_used: int,
    action_trace: list[dict],
    metadata: dict | None = None,
):
    metrics = {"steps_used": steps_used, "tool_calls_used": tool_calls_used}
    result = make_result(
        task_id=task["id"],
        version=task["version"],
        seed=seed,
        success=success,
        termination_reason=termination_reason,
        failure_reason=failure_reason,
        failure_type=failure_type,
        steps_used=steps_used,
        tool_calls_used=tool_calls_used,
        metrics=metrics,
        action_trace=action_trace,
    )
    result["sandbox"] = sandbox
    if metadata:
        result.update(metadata)
    return result


def run(agent_path: str, task_ref: str, seed: int = 0) -> dict:
    task_id, version = _parse_task_ref(task_ref)
    task = load_task(task_id, version)

    env = Environment()
    sandbox = task.get("sandbox") or {}
    guarded_env = GuardedEnv(
        env,
        filesystem_roots=sandbox.get("filesystem_roots", ()),
        network_hosts=sandbox.get("network_hosts", ()),
    )
    task["setup"].setup(seed, guarded_env)

    actions_mod = task["actions"]
    if hasattr(actions_mod, "set_env"):
        actions_mod.set_env(guarded_env)

    agent = load_agent(agent_path)
    budgets = task["default_budget"]
    max_steps = int(budgets.get("steps", 0))
    max_tool_calls = int(budgets.get("tool_calls", 0))
    budget = Budgets(max_steps, max_tool_calls)

    schema = _action_schema(actions_mod)

    task_spec = {
        "id": task["id"],
        "description": task["description"],
        "budgets": budgets,
        "actions": schema,
        "sandbox": sandbox,
    }
    agent.reset(task_spec)

    task_ref_full = f"{task['id']}@{task['version']}"
    run_id = uuid4().hex
    base_metadata = {
        "run_id": run_id,
        "trace_id": run_id,
        "agent": agent_path,
        "agent_ref": agent_path,
        "task_ref": task_ref_full,
        "task_hash": _compute_task_hash(task),
        "started_at": _now_iso(),
        "harness_version": _HARNESS_VERSION,
        "spec_version": SPEC_VERSION,
        "runtime_identity": {
            "name": "tracecore",
            "version": _HARNESS_VERSION,
            "git_sha": None,
        },
        "budgets": {
            "steps": max_steps,
            "tool_calls": max_tool_calls,
        },
    }

    last_action = None
    last_result = None
    action_trace = []

    while True:
        if budget.timed_out():
            steps_used = max_steps - budget.steps_remaining
            tool_calls_used = max_tool_calls - budget.tool_calls_remaining
            return _inject_artifact_hash(_result_payload(
                task=task,
                sandbox=sandbox,
                seed=seed,
                success=False,
                termination_reason="timeout",
                failure_reason="timeout",
                failure_type="timeout",
                steps_used=steps_used,
                tool_calls_used=tool_calls_used,
                action_trace=action_trace,
                metadata=_finalize_metadata(base_metadata),
            ))

        if budget.steps_remaining <= 0:
            tool_calls_used = max_tool_calls - budget.tool_calls_remaining
            return _inject_artifact_hash(_result_payload(
                task=task,
                sandbox=sandbox,
                seed=seed,
                success=False,
                termination_reason="steps_exhausted",
                failure_reason="steps_exhausted",
                failure_type="budget_exhausted",
                steps_used=max_steps,
                tool_calls_used=tool_calls_used,
                action_trace=action_trace,
                metadata=_finalize_metadata(base_metadata),
            ))

        observation = {
            "step": max_steps - budget.steps_remaining + 1,
            "task": {"id": task["id"], "description": task["description"]},
            "last_action": last_action,
            "last_action_result": last_result,
            "visible_state": env.visible_state(),
            "budget_remaining": {
                "steps": budget.steps_remaining,
                "tool_calls": budget.tool_calls_remaining,
            },
        }

        try:
            agent.observe(observation)
            action = agent.act()
        except SandboxViolation as exc:
            steps_used = max_steps - budget.steps_remaining
            tool_calls_used = max_tool_calls - budget.tool_calls_remaining
            return _inject_artifact_hash(_result_payload(
                task=task,
                sandbox=sandbox,
                seed=seed,
                success=False,
                termination_reason="sandbox_violation",
                failure_reason=str(exc),
                failure_type="sandbox_violation",
                steps_used=steps_used,
                tool_calls_used=tool_calls_used,
                action_trace=action_trace,
                metadata=_finalize_metadata(base_metadata),
            ))

        budget.consume_step()
        ok, reason = _validate_action(action, schema)
        if not ok:
            steps_used = max_steps - budget.steps_remaining
            tool_calls_used = max_tool_calls - budget.tool_calls_remaining
            return _inject_artifact_hash(_result_payload(
                task=task,
                sandbox=sandbox,
                seed=seed,
                success=False,
                termination_reason="invalid_action",
                failure_reason=reason,
                failure_type="invalid_action",
                steps_used=steps_used,
                tool_calls_used=tool_calls_used,
                action_trace=action_trace,
                metadata=_finalize_metadata(base_metadata),
            ))

        if budget.tool_calls_remaining <= 0:
            steps_used = max_steps - budget.steps_remaining
            return _inject_artifact_hash(_result_payload(
                task=task,
                sandbox=sandbox,
                seed=seed,
                success=False,
                termination_reason="tool_calls_exhausted",
                failure_reason="tool_calls_exhausted",
                failure_type="budget_exhausted",
                steps_used=steps_used,
                tool_calls_used=max_tool_calls,
                action_trace=action_trace,
                metadata=_finalize_metadata(base_metadata),
            ))

        action_type = action["type"]
        args = action.get("args", {}) or {}
        try:
            guarded_env.begin_step(observation["step"])
            result = getattr(actions_mod, action_type)(**args)
            io_audit = guarded_env.consume_audit()
        except SandboxViolation as exc:
            steps_used = max_steps - budget.steps_remaining
            tool_calls_used = max_tool_calls - budget.tool_calls_remaining
            return _inject_artifact_hash(_result_payload(
                task=task,
                sandbox=sandbox,
                seed=seed,
                success=False,
                termination_reason="sandbox_violation",
                failure_reason=str(exc),
                failure_type="sandbox_violation",
                steps_used=steps_used,
                tool_calls_used=tool_calls_used,
                action_trace=action_trace,
                metadata=_finalize_metadata(base_metadata),
            ))
        except Exception as exc:  # pragma: no cover - defensive
            steps_used = max_steps - budget.steps_remaining
            tool_calls_used = max_tool_calls - budget.tool_calls_remaining
            return _inject_artifact_hash(_result_payload(
                task=task,
                sandbox=sandbox,
                seed=seed,
                success=False,
                termination_reason="action_exception",
                failure_reason=f"action_exception:{exc}",
                failure_type="invalid_action",
                steps_used=steps_used,
                tool_calls_used=tool_calls_used,
                action_trace=action_trace,
                metadata=_finalize_metadata(base_metadata),
            ))

        budget.consume_tool_call()

        if action_type == "list_dir" and isinstance(result, dict) and result.get("ok"):
            env.mark_seen(result.get("files", []))

        include_llm_trace = os.getenv("AGENT_BENCH_DISABLE_LLM_TRACE", "").lower() not in {"1", "true", "yes"}
        trace_entry = {
            "step": observation["step"],
            "action_ts": _now_iso(),
            "observation": observation,
            "action": action,
            "result": result,
            "io_audit": io_audit,
            "llm_trace": getattr(agent, "llm_trace", None) if include_llm_trace else None,
            "budget_after_step": {
                "steps": budget.steps_remaining,
                "tool_calls": budget.tool_calls_remaining,
            },
            "budget_delta": {
                "steps": 1,
                "tool_calls": 1,
            },
        }
        action_trace.append(trace_entry)
        last_action = action
        last_result = result

        if budget.tool_calls_remaining < 0:
            steps_used = max_steps - budget.steps_remaining
            return _inject_artifact_hash(_result_payload(
                task=task,
                sandbox=sandbox,
                seed=seed,
                success=False,
                termination_reason="tool_calls_exhausted",
                failure_reason="tool_calls_exhausted",
                failure_type="budget_exhausted",
                steps_used=steps_used,
                tool_calls_used=max_tool_calls,
                action_trace=action_trace,
                metadata=_finalize_metadata(base_metadata),
            ))

        validation = task["validate"].validate(guarded_env)
        if validation.get("ok"):
            steps_used = max_steps - budget.steps_remaining
            tool_calls_used = max_tool_calls - budget.tool_calls_remaining
            validator_snapshot = _snapshot_validation(validation)
            return _inject_artifact_hash(_result_payload(
                task=task,
                sandbox=sandbox,
                seed=seed,
                success=True,
                termination_reason="success",
                failure_reason=None,
                failure_type=None,
                steps_used=steps_used,
                tool_calls_used=tool_calls_used,
                action_trace=action_trace,
                metadata=_finalize_metadata(base_metadata, validator=validator_snapshot),
            ))

        if validation.get("terminal"):
            steps_used = max_steps - budget.steps_remaining
            tool_calls_used = max_tool_calls - budget.tool_calls_remaining
            failure_reason, failure_type, termination_reason, validator_snapshot = _normalize_terminal_validation(
                validation
            )
            return _inject_artifact_hash(_result_payload(
                task=task,
                sandbox=sandbox,
                seed=seed,
                success=False,
                termination_reason=termination_reason,
                failure_reason=failure_reason,
                failure_type=failure_type,
                steps_used=steps_used,
                tool_calls_used=tool_calls_used,
                action_trace=action_trace,
                metadata=_finalize_metadata(base_metadata, validator=validator_snapshot),
            ))

        # Continue loop until a failure condition trips.
