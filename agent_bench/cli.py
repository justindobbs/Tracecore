"""CLI entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_bench.config import AgentBenchConfig, ConfigError, load_config
from agent_bench.runner.baseline import (
    build_baselines,
    diff_runs,
    export_baseline,
    load_run_artifact,
)
from agent_bench.runner.failures import FAILURE_TYPES
from agent_bench.runner.runlog import list_runs, load_run, persist_run
from agent_bench.runner.runner import run
from agent_bench.tasks.registry import validate_registry_entries, validate_task_path
from agent_bench.webui.app import app


def _load_config_from_args(config_path: str | None) -> AgentBenchConfig | None:
    try:
        return load_config(config_path)
    except ConfigError as exc:
        raise SystemExit(str(exc))


def _resolve_run_inputs(
    args: argparse.Namespace,
    config: AgentBenchConfig | None,
    *,
    require_seed: bool = True,
) -> tuple[str | None, str | None, int | None]:
    agent = getattr(args, "agent", None)
    task = getattr(args, "task", None)
    seed = getattr(args, "seed", None) if require_seed else None

    if config:
        agent = agent or config.get_default_agent()
        if task is None:
            task = config.get_task(agent=agent)
        if task is None:
            task = config.get_default_task()
        if require_seed and seed is None:
            seed = config.get_seed(agent=agent)
    return agent, task, seed


def _cmd_run(args: argparse.Namespace) -> int:
    config = getattr(args, "_config", None)
    if args.replay:
        artifact = load_run(args.replay)
        recorded_agent = artifact.get("agent")
        recorded_task = artifact.get("task_ref")
        recorded_seed = artifact.get("seed", 0)

        agent = args.agent or recorded_agent
        task = args.task or recorded_task
        seed = args.seed if args.seed is not None else recorded_seed

        if not agent or not task:
            raise SystemExit("replay requires an artifact with agent/task or explicit overrides")

        if agent != recorded_agent or task != recorded_task or seed != recorded_seed:
            print(
                "warning: overriding recorded artifact values for replay "
                f"(run_id={args.replay}, agent={recorded_agent}, task={recorded_task}, seed={recorded_seed})",
                file=sys.stderr,
            )
    else:
        agent, task, seed = _resolve_run_inputs(args, config)
        if not agent or not task:
            raise SystemExit(
                "agent and task are required unless using --replay (set CLI flags or defaults in agent-bench.toml)"
            )
        seed = 0 if seed is None else seed

    result = run(agent, task, seed=seed)
    try:
        persist_run(result)
    except Exception as exc:  # pragma: no cover - logging failure shouldn't abort run
        print(f"warning: failed to persist run artifact ({exc})", file=sys.stderr)
    print(json.dumps(result, indent=2))
    return 0


def _cmd_runs_list(args: argparse.Namespace) -> int:
    runs = list_runs(
        agent=args.agent,
        task_ref=args.task,
        limit=args.limit,
        failure_type=args.failure_type,
    )
    print(json.dumps(runs, indent=2))
    return 0


def _compare_exit_code(diff: dict) -> int:
    summary = diff.get("summary", {})
    same_agent = bool(summary.get("same_agent"))
    same_task = bool(summary.get("same_task"))
    if not same_agent or not same_task:
        return 2
    if diff.get("step_diffs"):
        return 1
    if not summary.get("same_success"):
        return 1
    steps = summary.get("steps", {})
    tools = summary.get("tool_calls", {})
    if steps.get("run_a") != steps.get("run_b"):
        return 1
    if tools.get("run_a") != tools.get("run_b"):
        return 1
    return 0


def _print_diff_text(diff: dict, exit_code: int) -> None:
    summary = diff.get("summary", {})
    run_a = diff.get("run_a", {})
    run_b = diff.get("run_b", {})

    status = "identical"
    if exit_code == 2:
        status = "incompatible"
    elif exit_code == 1:
        status = "different"

    print(f"Compare: {status}")
    print(f"Agent A: {run_a.get('agent')}")
    print(f"Agent B: {run_b.get('agent')}")
    print(f"Task A: {run_a.get('task_ref')}")
    print(f"Task B: {run_b.get('task_ref')}")
    print(f"Success A: {run_a.get('success')}")
    print(f"Success B: {run_b.get('success')}")
    print(f"Steps A: {summary.get('steps', {}).get('run_a')}")
    print(f"Steps B: {summary.get('steps', {}).get('run_b')}")
    print(f"Tool calls A: {summary.get('tool_calls', {}).get('run_a')}")
    print(f"Tool calls B: {summary.get('tool_calls', {}).get('run_b')}")

    step_diffs = diff.get("step_diffs") or []
    if step_diffs:
        first = step_diffs[0]
        print(f"First divergence: step {first.get('step')}")


def _cmd_baseline(args: argparse.Namespace) -> int:
    config = getattr(args, "_config", None)
    compare = getattr(args, "compare", None)
    if compare:
        run_a = load_run_artifact(compare[0])
        run_b = load_run_artifact(compare[1])
        diff = diff_runs(run_a, run_b)
        exit_code = _compare_exit_code(diff)
        if args.format == "text":
            _print_diff_text(diff, exit_code)
        else:
            print(json.dumps(diff, indent=2))
        return exit_code
    agent, task, _ = _resolve_run_inputs(args, config, require_seed=False)
    rows = build_baselines(agent=agent, task_ref=task, max_runs=args.limit)
    payload: object = rows
    if args.export is not None:
        target = None if args.export == "" else args.export
        meta = {
            "agent_filter": agent,
            "task_filter": task,
            "limit": args.limit,
        }
        path = export_baseline(rows, path=target, metadata=meta)
        payload = {"rows": rows, "export_path": str(path)}
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_dashboard(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)
    return 0


def _cmd_tasks_validate(args: argparse.Namespace) -> int:
    errors: list[str] = []
    paths = getattr(args, "path", None) or []
    if not paths and not args.registry:
        args.registry = True

    for raw_path in paths:
        path = Path(raw_path)
        path_errors = validate_task_path(path)
        if path_errors:
            for err in path_errors:
                errors.append(f"{path}: {err}")

    if args.registry:
        errors.extend(validate_registry_entries())

    payload = {"valid": not errors, "errors": errors}
    print(json.dumps(payload, indent=2))
    return 0 if not errors else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="agent-bench")
    parser.add_argument("--config", help="Path to agent-bench.toml (defaults to ./agent-bench.toml)")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run an agent against a task")
    run_parser.add_argument("--agent", help="Path to the agent module")
    run_parser.add_argument("--task", help="Task reference (e.g., filesystem_hidden_config@1)")
    run_parser.add_argument("--seed", type=int, help="Deterministic seed (defaults to 0)")
    run_parser.add_argument(
        "--replay",
        help="Replay a prior run_id; agent/task/seed default to recorded values and can be overridden",
    )
    run_parser.set_defaults(func=_cmd_run)

    runs_parser = subparsers.add_parser("runs", help="Inspect stored run artifacts")
    runs_sub = runs_parser.add_subparsers(dest="runs_command")
    runs_list = runs_sub.add_parser("list", help="List recent runs (newest first)")
    runs_list.add_argument("--agent", help="Filter by agent path")
    runs_list.add_argument("--task", dest="task", help="Filter by task reference")
    runs_list.add_argument("--limit", type=int, default=20, help="Maximum runs to return")
    runs_list.add_argument(
        "--failure-type",
        choices=("success",) + FAILURE_TYPES,
        help="Filter by failure type (or 'success' for completed runs)",
    )
    runs_list.set_defaults(func=_cmd_runs_list)

    baseline_parser = subparsers.add_parser("baseline", help="Compute baseline stats from persisted runs")
    baseline_parser.add_argument("--agent", help="Filter by agent path")
    baseline_parser.add_argument("--task", dest="task", help="Filter by task reference")
    baseline_parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum number of runs to consider per filter (newest first)",
    )
    baseline_parser.add_argument(
        "--export",
        nargs="?",
        const="",
        help="Persist the baseline to .agent_bench/baselines (optionally supply relative path)",
    )
    baseline_parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("RUN_A", "RUN_B"),
        help="Diff two run artifacts (paths or run_ids) instead of computing aggregate stats",
    )
    baseline_parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format for --compare (default: json)",
    )
    baseline_parser.set_defaults(func=_cmd_baseline)

    dashboard_parser = subparsers.add_parser("dashboard", help="Launch the web UI dashboard (FastAPI/uvicorn)")
    dashboard_parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    dashboard_parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    dashboard_parser.add_argument("--reload", action="store_true", help="Enable autoreload (dev only)")
    dashboard_parser.set_defaults(func=_cmd_dashboard)

    tasks_parser = subparsers.add_parser("tasks", help="Inspect and validate task metadata")
    tasks_sub = tasks_parser.add_subparsers(dest="tasks_command")
    tasks_validate = tasks_sub.add_parser("validate", help="Validate task manifests and registry entries")
    tasks_validate.add_argument(
        "--path",
        action="append",
        help="Path to a task directory (repeatable)",
    )
    tasks_validate.add_argument(
        "--registry",
        action="store_true",
        help="Validate all registry entries (including plugins)",
    )
    tasks_validate.set_defaults(func=_cmd_tasks_validate)

    args = parser.parse_args()
    config = _load_config_from_args(getattr(args, "config", None))
    setattr(args, "_config", config)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
