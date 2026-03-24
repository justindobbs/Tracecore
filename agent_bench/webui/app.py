"""Minimal FastAPI UI wrapper for TraceCore."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict
from fastapi.templating import Jinja2Templates

from agent_bench.ledger import list_entries
from agent_bench.leaderboard import list_submissions as list_leaderboard_submissions
from agent_bench.leaderboard import load_submission as load_leaderboard_submission
from agent_bench.pairings import list_pairings
from agent_bench.runner.baseline import (
    build_baselines,
    diff_runs,
    load_latest_baseline,
    load_run_artifact,
)
from agent_bench.runner.failures import FAILURE_TYPES
from agent_bench.runner.runlog import list_runs, load_run, persist_run, _validate_run_id
from agent_bench.runner.runner import run
from agent_bench.tasks.registry import list_task_descriptors
import agent_bench.agents as _bundled_agents_pkg

TEMPLATES_DIR = Path(__file__).with_suffix("").with_name("templates")
TASKS_ROOT = Path("tasks")
AGENTS_ROOT = Path("agents")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app = FastAPI(title="TraceCore UI", version="1.1.3")


class PairingSummary(BaseModel):
    name: str
    agent: str
    task: str
    description: str
    last_run_id: str | None = None
    last_success: bool | None = None
    last_seed: int | None = None


class LedgerTask(BaseModel):
    task_ref: str
    success_rate: float
    avg_steps: float | None = None
    avg_tool_calls: float | None = None
    run_count: int | None = None
    seed: int | None = None
    run_artifact: str | None = None
    bundle_sha256: str | None = None
    bundle_signature: str | None = None
    signed_at: str | None = None


class LedgerEntryPayload(BaseModel):
    agent: str
    description: str | None = None
    suite: str | None = None
    harness_version: str | None = None
    published_at: str | None = None
    maintainer: str | None = None
    bundle_sha256: str | None = None
    bundle_signature: str | None = None
    signed_at: str | None = None
    tasks: list[LedgerTask] = []


class LeaderboardSubmissionSummary(BaseModel):
    submission_id: str
    run_id: str
    agent: str
    task_ref: str
    success: bool | None = None
    ingested_at: str | None = None
    submission_file: str | None = None


class TraceRunPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    run_id: str | None = None


class ErrorPayload(BaseModel):
    error: str

GUIDE_ENTRIES = [
    {
        "agent": "agents/toy_agent.py",
        "success": ["filesystem_hidden_config@1"],
        "notes": "Filesystem discovery reference; should succeed on the hidden config task.",
    },
    {
        "agent": "agents/naive_llm_agent.py",
        "success": ["filesystem_hidden_config@1"],
        "notes": "Minimal baseline; may fail if retries are exhausted.",
    },
    {
        "agent": "agents/rate_limit_agent.py",
        "success": ["rate_limited_api@1"],
        "notes": "Rate-limit retry flow reference; tuned for the API task.",
    },
    {
        "agent": "agents/chain_agent.py",
        "success": ["rate_limited_chain@1", "deterministic_rate_service@1"],
        "notes": "Handshake + rate-limit reference; should solve chained API tasks.",
    },
    {
        "agent": "agents/planner_agent.py",
        "success": ["rate_limited_chain@1"],
        "notes": "Planner-style scaffold; may fail depending on budgets or drift.",
    },
    {
        "agent": "agents/ops_triage_agent.py",
        "success": [
            "log_alert_triage@1",
            "config_drift_remediation@1",
            "incident_recovery_chain@1",
        ],
        "notes": "Operations triage reference; should succeed on ops suite tasks.",
    },
    {
        "agent": "agents/log_stream_monitor_agent.py",
        "success": ["log_stream_monitor@1"],
        "notes": "Log stream patrol reference; polls pages, ignores noise, fires on CRITICAL entry.",
    },
    {
        "agent": "agents/runbook_verifier_agent.py",
        "success": ["runbook_verifier@1"],
        "notes": "Runbook verification reference; stitches phase codes, ACK ID, and handoff token into a checksum.",
    },
    {
        "agent": "agents/sandboxed_code_auditor_agent.py",
        "success": ["sandboxed_code_auditor@1"],
        "notes": "Sandbox audit reference; extracts ISSUE_ID from source and AUDIT_CODE from log, emits combined token.",
    },
    {
        "agent": "agents/cheater_agent.py",
        "success": [],
        "notes": "Expected to fail with sandbox violation; use for defense checks.",
    },
]


def _parse_task_yaml(path: Path) -> dict[str, Any]:
    # Reuse loader-like parsing to avoid external YAML dependency.
    text = path.read_text(encoding="utf-8").splitlines()
    data: dict[str, Any] = {}
    i = 0
    while i < len(text):
        line = text[i].rstrip()
        i += 1
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("description:") and line.endswith("|"):
            desc_lines = []
            while i < len(text):
                raw = text[i]
                if not raw.startswith("  "):
                    break
                desc_lines.append(raw[2:])
                i += 1
            data["description"] = "\n".join(desc_lines).strip()
            continue
        if line.startswith("default_budget:"):
            budget = {}
            while i < len(text):
                raw = text[i]
                if not raw.startswith("  "):
                    break
                key, val = raw.strip().split(":", 1)
                budget[key.strip()] = int(val.strip())
                i += 1
            data["default_budget"] = budget
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            if key == "version":
                data[key] = int(val)
            else:
                data[key] = val
    return data


def _parse_task_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib  # type: ignore[attr-defined]
    except ModuleNotFoundError:  # pragma: no cover
        import tomli as tomllib  # type: ignore[assignment]
    return tomllib.loads(path.read_text(encoding="utf-8"))


def get_task_options() -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    if TASKS_ROOT.exists():
        for task_dir in sorted(TASKS_ROOT.iterdir()):
            toml_path = task_dir / "task.toml"
            yaml_path = task_dir / "task.yaml"
            if toml_path.exists():
                meta = _parse_task_toml(toml_path)
            elif yaml_path.exists():
                meta = _parse_task_yaml(yaml_path)
            else:
                continue
            if meta.get("internal"):
                continue
            entry = {
                "id": meta.get("id", task_dir.name),
                "suite": meta.get("suite", ""),
                "version": meta.get("version", 1),
                "description": meta.get("description", ""),
            }
            entry["ref"] = f"{entry['id']}@{entry['version']}"
            options.append(entry)

    if not options:
        for descriptor in list_task_descriptors():
            options.append({
                "id": descriptor.id,
                "suite": descriptor.suite,
                "version": descriptor.version,
                "description": descriptor.description,
                "ref": f"{descriptor.id}@{descriptor.version}",
            })
    return options


def get_agent_options() -> list[str]:
    # First try local agents directory (like tasks logic)
    if AGENTS_ROOT.exists():
        paths = sorted(p for p in AGENTS_ROOT.glob("*.py") if p.name != "__init__.py")
        if paths:
            return [f"agents/{p.name}" for p in paths]
    
    # Fallback to bundled agents (like tasks registry fallback)
    bundled_root = Path(_bundled_agents_pkg.__file__).parent
    return [f"agents/{p.name}" for p in sorted(bundled_root.glob("*.py")) if p.name != "__init__.py"]

def _build_budget_series(trace_run: dict | None) -> list[dict[str, int]]:
    if not trace_run:
        return []
    series: list[dict[str, int]] = []
    for entry in trace_run.get("action_trace") or []:
        observation = entry.get("observation") or {}
        remaining = observation.get("budget_remaining") or {}
        steps = remaining.get("steps")
        tools = remaining.get("tool_calls")
        if steps is None or tools is None:
            continue
        series.append({
            "step": entry.get("step", len(series) + 1),
            "steps": steps,
            "tool_calls": tools,
        })
    return series


def _normalize_io_entry(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    entry: dict[str, str] = {}
    for key in ("type", "op", "path", "host"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            entry[key] = value.strip()
    return entry or None


def _summarize_io_audit(trace_run: dict | None) -> dict | None:
    if not trace_run:
        return None
    action_trace = trace_run.get("action_trace") or []
    if not action_trace:
        return None
    total = filesystem = network = 0
    step_entries: list[dict[str, Any]] = []
    for entry in action_trace:
        if not isinstance(entry, dict):
            continue
        normalized: list[dict] = []
        for raw in entry.get("io_audit") or []:
            info = _normalize_io_entry(raw)
            if not info:
                continue
            normalized.append(info)
            total += 1
            audit_type = info.get("type")
            if audit_type == "fs":
                filesystem += 1
            elif audit_type == "net":
                network += 1
        if normalized:
            step_entries.append(
                {
                    "step": entry.get("step"),
                    "action": (entry.get("action") or {}).get("type"),
                    "io": normalized,
                }
            )
    if not step_entries:
        return None
    return {
        "total": total,
        "filesystem": filesystem,
        "network": network,
        "steps": step_entries,
    }


def _taxonomy_badge(trace_run: dict | None) -> dict[str, str] | None:
    if not trace_run:
        return None
    success = bool(trace_run.get("success"))
    failure_type = trace_run.get("failure_type")
    if success:
        return {"label": "Success", "kind": "success"}
    if failure_type:
        return {"label": failure_type, "kind": failure_type}
    return {"label": "unknown", "kind": "unknown"}


def _perf_alert_badges(metrics_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    badges: list[dict[str, str]] = []
    if any((row.get("artifact_bytes_avg") or 0) > 200_000 for row in metrics_rows):
        badges.append({"label": "Artifact Growth", "kind": "badge-yellow"})
    if any((row.get("llm_trace_entries_total") or 0) > max(row.get("run_count", 0), 0) * 3 for row in metrics_rows):
        badges.append({"label": "Telemetry Heavy", "kind": "badge-yellow"})
    if any((row.get("reproducibility_rate") or 0) < 0.95 for row in metrics_rows if row.get("reproducibility_rate") is not None):
        badges.append({"label": "Repro Alert", "kind": "badge-red"})
    if not badges:
        badges.append({"label": "Stable", "kind": "badge-green"})
    return badges


def _build_plugin_registry(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enrich task descriptors with action names and basic lint status for the plugin discovery UI."""
    from agent_bench.tasks.loader import _load_module, load_task
    result = []
    for task in tasks:
        local_task_dir = TASKS_ROOT / task["id"]
        is_local_task = TASKS_ROOT.exists() and local_task_dir.exists()
        entry: dict[str, Any] = {
            "id": task["id"],
            "ref": task["ref"],
            "suite": task["suite"],
            "version": task["version"],
            "description": task.get("description", ""),
            "actions": [],
            "lint_ok": None,
            "lint_errors": [],
            "source": "local" if is_local_task else "bundled",
        }
        try:
            if is_local_task:
                actions_path = local_task_dir / "actions.py"
                validate_path = local_task_dir / "validate.py"
                if not actions_path.exists():
                    raise FileNotFoundError(f"Task missing file: {actions_path}")
                if not validate_path.exists():
                    raise FileNotFoundError(f"Task missing file: {validate_path}")
                actions_mod = _load_module(actions_path, f"webui_{task['id']}_actions")
                validate_mod = _load_module(validate_path, f"webui_{task['id']}_validate")
                loaded = {"actions": actions_mod, "validate": validate_mod}
            else:
                loaded = load_task(task["id"], task["version"])
            actions_mod = loaded.get("actions")
            if actions_mod is not None:
                import inspect
                entry["actions"] = [
                    name for name, obj in inspect.getmembers(actions_mod, inspect.isfunction)
                    if not name.startswith("_")
                    and inspect.getfile(obj) == inspect.getfile(actions_mod)
                ]
            validate_mod = loaded.get("validate")
            lint_errors: list[str] = []
            if actions_mod is None:
                lint_errors.append("missing actions module")
            if validate_mod is None or not hasattr(validate_mod, "validate"):
                lint_errors.append("missing validate.validate()")
            if not hasattr(actions_mod, "action_schema") if actions_mod else True:
                lint_errors.append("action_schema() not defined (warning)")
            entry["lint_ok"] = len([e for e in lint_errors if "warning" not in e]) == 0
            entry["lint_errors"] = lint_errors
        except Exception as exc:
            entry["lint_ok"] = False
            entry["lint_errors"] = [str(exc)]
        result.append(entry)
    return result


def _group_agent_options(agents: list[str]) -> dict[str, list[str]]:
    local_agents = [agent for agent in agents if AGENTS_ROOT.exists() and agent.startswith("agents/")]
    bundled_agents = [agent for agent in agents if agent not in local_agents]
    return {
        "local": local_agents,
        "bundled": bundled_agents,
    }


def _group_task_options(tasks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    local_tasks: list[dict[str, Any]] = []
    bundled_tasks: list[dict[str, Any]] = []
    for task in tasks:
        local_task_dir = TASKS_ROOT / task["id"]
        if TASKS_ROOT.exists() and local_task_dir.exists():
            local_tasks.append(task)
        else:
            bundled_tasks.append(task)
    return {
        "local": local_tasks,
        "bundled": bundled_tasks,
    }


def _group_plugin_registry(plugin_registry: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "local": [entry for entry in plugin_registry if entry.get("source") == "local"],
        "bundled": [entry for entry in plugin_registry if entry.get("source") != "local"],
    }


def _filter_compare_step_summary(
    compare_step_summary: list[dict[str, Any]],
    compare_filter: str | None,
) -> list[dict[str, Any]]:
    if not compare_filter or compare_filter == "all":
        return compare_step_summary
    if compare_filter == "action":
        return [entry for entry in compare_step_summary if entry.get("action_changed")]
    if compare_filter == "result":
        return [entry for entry in compare_step_summary if entry.get("result_changed")]
    if compare_filter == "io":
        return [entry for entry in compare_step_summary if entry.get("has_io_drift")]
    if compare_filter == "mixed":
        return [
            entry
            for entry in compare_step_summary
            if sum(
                1
                for flag in (
                    entry.get("action_changed"),
                    entry.get("result_changed"),
                    entry.get("has_io_drift"),
                )
                if flag
            ) >= 2
        ]
    return compare_step_summary


def _suggest_compare_inputs(recent_runs: list[dict[str, Any]]) -> dict[str, str]:
    if len(recent_runs) < 2:
        return {"run_a": "", "run_b": ""}

    for idx, newer in enumerate(recent_runs):
        newer_task = newer.get("task_ref")
        newer_agent = newer.get("agent")
        newer_seed = newer.get("seed")
        newer_id = newer.get("run_id")
        if not newer_id:
            continue
        for older in recent_runs[idx + 1 :]:
            older_id = older.get("run_id")
            if not older_id:
                continue
            if (
                older.get("task_ref") == newer_task
                and older.get("agent") == newer_agent
                and older.get("seed") == newer_seed
            ):
                return {"run_a": older_id, "run_b": newer_id}

        for older in recent_runs[idx + 1 :]:
            older_id = older.get("run_id")
            if not older_id:
                continue
            if older.get("task_ref") == newer_task and older.get("agent") == newer_agent:
                return {"run_a": older_id, "run_b": newer_id}

    first = recent_runs[0].get("run_id") or ""
    second = recent_runs[1].get("run_id") or ""
    return {"run_a": second, "run_b": first}


def _load_compare_diff(run_a: str | None, run_b: str | None) -> tuple[dict | None, str | None]:
    if not run_a or not run_b:
        return None, None
    try:
        artifact_a = load_run_artifact(run_a)
        artifact_b = load_run_artifact(run_b)
        return diff_runs(artifact_a, artifact_b), None
    except FileNotFoundError:
        return None, "One of the provided run references could not be found."
    except Exception as exc:
        return None, str(exc)


def _summarize_compare_diff(compare_diff: dict[str, Any] | None) -> dict[str, Any]:
    if not compare_diff:
        return {
            "compare_delta": None,
            "compare_step_summary": [],
            "compare_taxonomy_summary": [],
            "compare_budget_badges": [],
            "compare_io_step_count": 0,
            "compare_changed_step_count": 0,
            "compare_divergence_summary": [],
        }

    summary = compare_diff.get("summary", {})
    steps = summary.get("steps", {})
    tools = summary.get("tool_calls", {})
    compare_delta = {
        "steps_a": steps.get("run_a"),
        "steps_b": steps.get("run_b"),
        "tools_a": tools.get("run_a"),
        "tools_b": tools.get("run_b"),
        "steps_delta": (steps.get("run_b") or 0) - (steps.get("run_a") or 0),
        "tools_delta": (tools.get("run_b") or 0) - (tools.get("run_a") or 0),
    }

    compare_step_summary: list[dict[str, Any]] = []
    compare_io_step_count = 0
    for entry in compare_diff.get("step_diffs") or []:
        run_a = entry.get("run_a") or {}
        run_b = entry.get("run_b") or {}
        action_a = (run_a.get("action") or {}).get("type")
        action_b = (run_b.get("action") or {}).get("type")
        result_a = run_a.get("result")
        result_b = run_b.get("result")
        io_delta = entry.get("io_audit_delta") or {}
        has_io_drift = bool(io_delta.get("added") or io_delta.get("removed"))
        if has_io_drift:
            compare_io_step_count += 1
        compare_step_summary.append(
            {
                "step": entry.get("step"),
                "action_a": action_a,
                "action_b": action_b,
                "action_changed": action_a != action_b,
                "result_changed": result_a != result_b,
                "has_io_drift": has_io_drift,
            }
        )

    taxonomy = compare_diff.get("taxonomy") or {}
    compare_taxonomy_summary = [
        {
            "label": "Failure type",
            "same": taxonomy.get("same_failure_type"),
            "run_a": (taxonomy.get("run_a") or {}).get("failure_type") or "none",
            "run_b": (taxonomy.get("run_b") or {}).get("failure_type") or "none",
        },
        {
            "label": "Termination reason",
            "same": taxonomy.get("same_termination_reason"),
            "run_a": (taxonomy.get("run_a") or {}).get("termination_reason") or "none",
            "run_b": (taxonomy.get("run_b") or {}).get("termination_reason") or "none",
        },
    ]
    taxonomy_change_count = sum(1 for item in compare_taxonomy_summary if not item.get("same"))

    budget_delta = compare_diff.get("budget_delta") or {}
    compare_budget_badges = [
        {
            "label": "Steps",
            "value": budget_delta.get("steps", 0),
            "kind": "pill-warn" if budget_delta.get("steps", 0) > 0 else ("pill-ok" if budget_delta.get("steps", 0) < 0 else "pill-neutral"),
        },
        {
            "label": "Tool calls",
            "value": budget_delta.get("tool_calls", 0),
            "kind": "pill-warn" if budget_delta.get("tool_calls", 0) > 0 else ("pill-ok" if budget_delta.get("tool_calls", 0) < 0 else "pill-neutral"),
        },
        {
            "label": "Wall",
            "value": budget_delta.get("wall_clock_s", 0),
            "suffix": "s",
            "kind": "pill-warn" if budget_delta.get("wall_clock_s", 0) > 0 else ("pill-ok" if budget_delta.get("wall_clock_s", 0) < 0 else "pill-neutral"),
        },
    ]

    compare_divergence_summary = [
        {
            "label": "Outcome",
            "value": "changed" if not summary.get("same_success") else "match",
            "kind": "danger" if not summary.get("same_success") else "ok",
        },
        {
            "label": "Taxonomy",
            "value": f"{taxonomy_change_count} shift{'s' if taxonomy_change_count != 1 else ''}",
            "kind": "danger" if taxonomy_change_count else "ok",
        },
        {
            "label": "IO drift",
            "value": f"{compare_io_step_count} step{'s' if compare_io_step_count != 1 else ''}",
            "kind": "danger" if compare_io_step_count else "ok",
        },
    ]

    return {
        "compare_delta": compare_delta,
        "compare_step_summary": compare_step_summary[:10],
        "compare_taxonomy_summary": compare_taxonomy_summary,
        "compare_budget_badges": compare_budget_badges,
        "compare_io_step_count": compare_io_step_count,
        "compare_changed_step_count": len(compare_step_summary),
        "compare_divergence_summary": compare_divergence_summary,
    }


def _template_context(request: Request, **extra: Any) -> dict[str, Any]:
    tasks = get_task_options()
    agents = get_agent_options()
    recent_filters = extra.pop("recent_filters", None) or {}
    baseline_filters = extra.pop("baseline_filters", None) or {}
    compare_filters = extra.pop("compare_filters", None) or {"drift": "all"}
    recent_runs = list_runs(
        limit=8,
        agent=recent_filters.get("agent"),
        task_ref=recent_filters.get("task_ref"),
        failure_type=recent_filters.get("failure_type"),
    )
    baselines = build_baselines(
        max_runs=400,
        agent=baseline_filters.get("agent"),
        task_ref=baseline_filters.get("task_ref"),
    )
    published_baseline = load_latest_baseline()
    selected_task_ref = extra.get("selected_task")
    if selected_task_ref is None and tasks:
        selected_task_ref = tasks[0]["ref"]
    selected_task_meta = next((t for t in tasks if t["ref"] == selected_task_ref), None)
    extra = dict(extra)
    extra.pop("selected_task", None)
    compare_inputs = extra.pop("compare_inputs", None) or {"run_a": "", "run_b": ""}
    pairing_cards = []
    for p in list_pairings():
        last = list_runs(agent=p.agent, task_ref=p.task, limit=1)
        last_run = last[0] if last else None
        pairing_cards.append({
            "name": p.name,
            "agent": p.agent,
            "task": p.task,
            "description": p.description,
            "last_run_id": last_run["run_id"] if last_run else None,
            "last_success": (last_run.get("failure_type") is None) if last_run else None,
            "last_seed": last_run.get("seed") if last_run else None,
        })
    suggested_compare_inputs = _suggest_compare_inputs(recent_runs)
    compare_inputs = {
        "run_a": compare_inputs.get("run_a") or suggested_compare_inputs.get("run_a") or "",
        "run_b": compare_inputs.get("run_b") or suggested_compare_inputs.get("run_b") or "",
    }
    compare_diff = extra.get("compare_diff")
    compare_summary = _summarize_compare_diff(compare_diff)
    filtered_compare_step_summary = _filter_compare_step_summary(
        compare_summary["compare_step_summary"],
        compare_filters.get("drift"),
    )

    trace_run = extra.get("trace_run")
    trace_budget_series = _build_budget_series(trace_run)
    trace_taxonomy = _taxonomy_badge(trace_run)
    trace_io_summary = _summarize_io_audit(trace_run)

    plugin_registry = _build_plugin_registry(tasks)
    grouped_agents = _group_agent_options(agents)
    grouped_tasks = _group_task_options(tasks)
    grouped_plugins = _group_plugin_registry(plugin_registry)

    base = {
        "request": request,
        "tasks": tasks,
        "agents": agents,
        "plugin_registry": plugin_registry,
        "grouped_agents": grouped_agents,
        "grouped_tasks": grouped_tasks,
        "grouped_plugins": grouped_plugins,
        "pairings": pairing_cards,
        "selected_task": selected_task_ref,
        "selected_task_meta": selected_task_meta,
        "recent_runs": recent_runs,
        "baselines": baselines,
        "published_baseline": published_baseline,
        "compare_diff": compare_diff,
        "compare_delta": compare_summary["compare_delta"],
        "compare_step_summary": filtered_compare_step_summary,
        "compare_step_summary_total": len(compare_summary["compare_step_summary"]),
        "compare_taxonomy_summary": compare_summary["compare_taxonomy_summary"],
        "compare_budget_badges": compare_summary["compare_budget_badges"],
        "compare_io_step_count": compare_summary["compare_io_step_count"],
        "compare_changed_step_count": compare_summary["compare_changed_step_count"],
        "compare_divergence_summary": compare_summary["compare_divergence_summary"],
        "compare_error": extra.get("compare_error"),
        "compare_inputs": compare_inputs,
        "compare_suggestions": suggested_compare_inputs,
        "compare_filters": compare_filters,
        "recent_filters": recent_filters,
        "baseline_filters": baseline_filters,
        "failure_types": FAILURE_TYPES,
        "trace_budget_series": trace_budget_series,
        "trace_taxonomy": trace_taxonomy,
        "trace_io_summary": trace_io_summary,
    }
    base.update(extra)
    return base


def _load_trace(run_id: str | None) -> tuple[dict | None, str | None]:
    if not run_id:
        return None, None
    try:
        _validate_run_id(run_id)
        return load_run(run_id), None
    except FileNotFoundError:
        return None, f"Trace {run_id} not found."
    except Exception as exc:
        return None, f"Failed to load trace: {exc}"


def _strip_io_audit(trace_run: dict | None) -> dict | None:
    if not trace_run:
        return trace_run
    clone = dict(trace_run)
    trace = []
    for entry in clone.get("action_trace") or []:
        if not isinstance(entry, dict):
            continue
        trimmed = {k: v for k, v in entry.items() if k != "io_audit"}
        trace.append(trimmed)
    clone["action_trace"] = trace
    return clone


@app.get("/api/pairings", response_model=list[PairingSummary])
async def api_pairings() -> list[PairingSummary]:
    result: list[PairingSummary] = []
    for p in list_pairings():
        last = list_runs(agent=p.agent, task_ref=p.task, limit=1)
        last_run = last[0] if last else None
        result.append(
            PairingSummary(
                name=p.name,
                agent=p.agent,
                task=p.task,
                description=p.description,
                last_run_id=last_run["run_id"] if last_run else None,
                last_success=(last_run.get("failure_type") is None) if last_run else None,
                last_seed=last_run.get("seed") if last_run else None,
            )
        )
    return result


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    trace_id = request.query_params.get("trace_id")
    compare_run_a = request.query_params.get("compare_a") or ""
    compare_run_b = request.query_params.get("compare_b") or ""
    compare_drift = request.query_params.get("compare_drift") or "all"
    active_tab = request.query_params.get("tab") or None
    recent_filters = {
        "agent": request.query_params.get("recent_agent") or None,
        "task_ref": request.query_params.get("recent_task") or None,
        "failure_type": request.query_params.get("recent_failure") or None,
    }
    baseline_filters = {
        "agent": request.query_params.get("baseline_agent") or None,
        "task_ref": request.query_params.get("baseline_task") or None,
    }
    baseline_submitted = any(param in request.query_params for param in ("baseline_agent", "baseline_task"))
    trace_run, trace_error = _load_trace(trace_id)
    compare_diff, compare_error = _load_compare_diff(compare_run_a, compare_run_b)
    return templates.TemplateResponse(
        request,
        "index.html",
        _template_context(
            request,
            trace_run=trace_run,
            trace_error=trace_error,
            trace_id=trace_id,
            recent_filters=recent_filters,
            baseline_filters=baseline_filters,
            baseline_submitted=baseline_submitted,
            compare_diff=compare_diff,
            compare_error=compare_error,
            compare_inputs={"run_a": compare_run_a, "run_b": compare_run_b},
            compare_filters={"drift": compare_drift},
            active_tab=active_tab,
        ),
    )


@app.get("/run", response_class=HTMLResponse)
async def run_task_redirect() -> RedirectResponse:
    """Browsers sometimes prefetch GET /run; send them back to the dashboard."""
    return RedirectResponse(url="/", status_code=307)


@app.post("/run", response_class=HTMLResponse)
async def run_task(
    request: Request,
    agent: str = Form(""),
    task: str = Form(""),
    seed: int | None = Form(None),
    replay: str | None = Form(None),
) -> HTMLResponse:
    result: dict[str, Any] | None = None
    error: str | None = None
    trace_run: dict[str, Any] | None = None

    try:
        if replay:
            _validate_run_id(replay)
            artifact = load_run(replay)
            recorded_agent = artifact.get("agent")
            recorded_task = artifact.get("task_ref")
            recorded_seed = artifact.get("seed", 0)

            agent = agent or recorded_agent or ""
            task = task or recorded_task or ""
            seed = recorded_seed if seed is None else seed

            if not agent or not task:
                raise ValueError("Replay requires artifact with agent/task or explicit overrides")
        else:
            if not agent or not task:
                raise ValueError("Agent and task are required (or provide a replay run_id)")
            seed = 0 if seed is None else seed

        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: run(agent, task, seed=seed)
        )
        try:
            persist_run(result)
        except Exception as exc:  # pragma: no cover - best-effort logging
            error = f"run succeeded but failed to persist artifact: {exc}"
        trace_run = result
    except Exception as exc:  # pragma: no cover - defensive for UI feedback
        error = str(exc)

    return templates.TemplateResponse(
        request,
        "index.html",
        _template_context(
            request,
            selected_agent=agent,
            selected_task=task,
            selected_seed=seed if seed is not None else 0,
            result=result,
            error=error,
            trace_run=trace_run,
            trace_id=trace_run.get("run_id") if trace_run else None,
            result_download_id=trace_run.get("run_id") if trace_run else None,
        ),
    )


@app.get("/traces/{run_id}", response_class=HTMLResponse)
async def view_trace(request: Request, run_id: str) -> HTMLResponse:
    trace_run, trace_error = _load_trace(run_id)
    return templates.TemplateResponse(
        request,
        "index.html",
        _template_context(
            request,
            trace_run=trace_run,
            trace_error=trace_error,
            trace_id=run_id,
        ),
    )


@app.get(
    "/api/traces/{run_id}",
    response_model=TraceRunPayload | ErrorPayload,
)
async def trace_api(run_id: str, response: Response, include_io: bool = False) -> TraceRunPayload | ErrorPayload:
    trace_run, trace_error = _load_trace(run_id)
    if trace_run:
        payload = trace_run if include_io else _strip_io_audit(trace_run)
        return TraceRunPayload.model_validate(payload)
    status_code = 404 if "not found" in (trace_error or "").lower() else 500
    response.status_code = status_code
    return ErrorPayload(error=trace_error or "unknown_error")


@app.get("/api/runs/diff")
async def api_runs_diff(a: str, b: str, response: Response) -> dict | ErrorPayload:
    """Return a structured IO-audit diff between two run artifacts.

    Query params: ``a`` and ``b`` are run_ids or paths.
    """
    try:
        artifact_a = load_run_artifact(a)
        artifact_b = load_run_artifact(b)
        return diff_runs(artifact_a, artifact_b)
    except FileNotFoundError as exc:
        response.status_code = 404
        return ErrorPayload(error=str(exc))
    except Exception as exc:
        response.status_code = 500
        return ErrorPayload(error=str(exc))


@app.get("/api/runs/{run_id}/io-audit")
async def api_run_io_audit(run_id: str, response: Response) -> dict | ErrorPayload:
    """Return per-step IO audit entries for a single run.

    Response shape::

        {
          "run_id": "...",
          "task_ref": "...",
          "steps": [
            {
              "step": 1,
              "action": "read_file",
              "io_audit": [{"type": "fs", "op": "read", "path": "..."}, ...]
            },
            ...
          ],
          "summary": {"total": N, "filesystem": N, "network": N}
        }
    """
    run = load_run(run_id)
    if not run:
        response.status_code = 404
        return ErrorPayload(error=f"Run {run_id!r} not found")

    steps = []
    total = fs_count = net_count = 0
    for entry in run.get("action_trace") or []:
        io = entry.get("io_audit") or []
        action_type = (entry.get("action") or {}).get("type", "")
        steps.append({
            "step": entry.get("step"),
            "action": action_type,
            "io_audit": io,
        })
        for item in io:
            total += 1
            if item.get("type") == "fs":
                fs_count += 1
            elif item.get("type") == "net":
                net_count += 1

    return {
        "run_id": run.get("run_id"),
        "task_ref": run.get("task_ref"),
        "steps": steps,
        "summary": {"total": total, "filesystem": fs_count, "network": net_count},
    }


@app.get("/baselines/latest")
async def download_latest_baseline() -> FileResponse:
    payload = load_latest_baseline()
    if not payload:
        raise HTTPException(status_code=404, detail="No baseline export found")
    path = Path(payload["_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Baseline file missing")
    return FileResponse(path, media_type="application/json", filename=payload.get("_filename", path.name))


@app.get("/api/ledger", response_model=list[LedgerEntryPayload])
async def api_ledger() -> list[LedgerEntryPayload]:
    return [LedgerEntryPayload.model_validate(entry) for entry in list_entries()]


@app.get("/ledger", response_class=HTMLResponse)
async def ledger(request: Request) -> HTMLResponse:
    entries = list_entries()
    return templates.TemplateResponse(
        request,
        "ledger.html",
        {
            "request": request,
            "entries": entries,
        },
    )


@app.get("/api/leaderboard", response_model=list[LeaderboardSubmissionSummary])
async def api_leaderboard() -> list[LeaderboardSubmissionSummary]:
    return [LeaderboardSubmissionSummary.model_validate(entry) for entry in list_leaderboard_submissions()]


@app.get("/api/leaderboard/{run_id}", response_model=dict | ErrorPayload)
async def api_leaderboard_submission(run_id: str, response: Response) -> dict | ErrorPayload:
    payload = load_leaderboard_submission(run_id)
    if payload is None:
        response.status_code = 404
        return ErrorPayload(error="leaderboard_submission_not_found")
    return payload


@app.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard(request: Request) -> HTMLResponse:
    submissions = list_leaderboard_submissions()
    return templates.TemplateResponse(
        request,
        "leaderboard.html",
        {
            "request": request,
            "submissions": submissions,
        },
    )


@app.get("/guide", response_class=HTMLResponse)
async def guide(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "guide.html",
        {
            "request": request,
            "guide_entries": GUIDE_ENTRIES,
        },
    )


@app.get("/api/metrics")
async def api_metrics(
    task: str | None = None,
    agent: str | None = None,
    limit: int = 500,
) -> dict:
    """Return aggregate metrics for all runs, optionally filtered by task/agent."""
    from agent_bench.runner.metrics import compute_all_metrics, compute_metrics
    if task or agent:
        return compute_metrics(task_ref=task, agent=agent, limit=limit)
    return {"metrics": compute_all_metrics(limit=limit)}


@app.get("/metrics", response_class=HTMLResponse)
async def metrics_page(request: Request) -> HTMLResponse:
    """Render the metrics dashboard page."""
    from agent_bench.runner.metrics import compute_all_metrics
    rows = compute_all_metrics(limit=500)
    recent_runs = list_runs(limit=6)
    return templates.TemplateResponse(
        request,
        "metrics.html",
        {
            "request": request,
            "metrics_rows": rows,
            "total_tasks": len({r["task_ref"] for r in rows}),
            "total_runs": sum(r.get("run_count", 0) for r in rows),
            "recent_runs": recent_runs,
            "perf_alert_badges": _perf_alert_badges(rows),
        },
    )


@app.post("/compare", response_class=HTMLResponse)
async def compare_runs(
    request: Request,
    run_a: str = Form(""),
    run_b: str = Form(""),
    compare_drift: str = Form("all"),
) -> HTMLResponse:
    compare_error: str | None = None
    diff: dict | None = None
    if not run_a or not run_b:
        compare_error = "Both run references are required"
    else:
        diff, compare_error = _load_compare_diff(run_a, run_b)

    return templates.TemplateResponse(
        request,
        "index.html",
        _template_context(
            request,
            compare_diff=diff,
            compare_error=compare_error,
            compare_inputs={"run_a": run_a, "run_b": run_b},
            compare_filters={"drift": compare_drift or "all"},
            active_tab="compare",
            selected_task=request.query_params.get("task"),
        ),
    )
