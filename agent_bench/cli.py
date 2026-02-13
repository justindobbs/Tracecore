"""CLI entrypoint."""

from __future__ import annotations

import argparse
import json
import sys

from agent_bench.runner.baseline import build_baselines, export_baseline
from agent_bench.webui.app import app
from agent_bench.runner.failures import FAILURE_TYPES
from agent_bench.runner.runlog import list_runs, load_run, persist_run
from agent_bench.runner.runner import run


def _cmd_run(args: argparse.Namespace) -> int:
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
        if not args.agent or not args.task:
            raise SystemExit("agent and task are required unless using --replay")
        agent = args.agent
        task = args.task
        seed = args.seed if args.seed is not None else 0

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


def _cmd_baseline(args: argparse.Namespace) -> int:
    rows = build_baselines(agent=args.agent, task_ref=args.task, max_runs=args.limit)
    payload: object = rows
    if args.export is not None:
        target = None if args.export == "" else args.export
        meta = {
            "agent_filter": args.agent,
            "task_filter": args.task,
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


def main() -> int:
    parser = argparse.ArgumentParser(prog="agent-bench")
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
    baseline_parser.set_defaults(func=_cmd_baseline)

    dashboard_parser = subparsers.add_parser("dashboard", help="Launch the web UI dashboard (FastAPI/uvicorn)")
    dashboard_parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    dashboard_parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    dashboard_parser.add_argument("--reload", action="store_true", help="Enable autoreload (dev only)")
    dashboard_parser.set_defaults(func=_cmd_dashboard)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
