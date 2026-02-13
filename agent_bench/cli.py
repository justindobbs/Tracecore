"""CLI entrypoint."""

from __future__ import annotations

import argparse
import json
import sys

from agent_bench.runner.baseline import build_baselines, export_baseline
from agent_bench.runner.failures import FAILURE_TYPES
from agent_bench.runner.runlog import list_runs, persist_run
from agent_bench.runner.runner import run


def _cmd_run(args: argparse.Namespace) -> int:
    result = run(args.agent, args.task, seed=args.seed)
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


def main() -> int:
    parser = argparse.ArgumentParser(prog="agent-bench")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run an agent against a task")
    run_parser.add_argument("--agent", required=True, help="Path to the agent module")
    run_parser.add_argument("--task", required=True, help="Task reference (e.g., filesystem_hidden_config@1)")
    run_parser.add_argument("--seed", type=int, default=0, help="Deterministic seed")
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

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
